# crm/utils/pipeline_utils.py
"""
Pipeline Management Utilities for CRM Module

Provides comprehensive pipeline management capabilities including:
- Stage progression logic
- Pipeline automation rules
- Stage duration analysis
- Pipeline forecasting
- Conversion rate tracking
- Bottleneck identification
- Pipeline health metrics
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from collections import defaultdict
import statistics

from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, Extract
from django.core.cache import cache


@dataclass
class PipelineStage:
    """Represents a pipeline stage configuration."""
    stage_id: str
    name: str
    order: int
    probability: int  # 0-100
    is_closed: bool = False
    is_won: bool = False
    requirements: List[str] = field(default_factory=list)
    auto_advance_rules: List[Dict[str, Any]] = field(default_factory=list)
    duration_target: Optional[int] = None  # Target days in stage


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics."""
    total_opportunities: int
    total_value: Decimal
    weighted_value: Decimal
    average_deal_size: Decimal
    conversion_rate: float
    average_sales_cycle: float
    stage_distribution: Dict[str, int]
    velocity_metrics: Dict[str, Any]
    forecasted_close: Dict[str, Any]


class PipelineManager:
    """
    Advanced pipeline management with automation and analytics.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.pipeline_stages = self._load_pipeline_stages()
        self.stage_order = {stage.stage_id: stage.order for stage in self.pipeline_stages}
    
    def advance_opportunity(self, opportunity, target_stage: str, 
                          user=None, notes: str = "") -> Dict[str, Any]:
        """
        Advance opportunity to next stage with validation.
        
        Args:
            opportunity: Opportunity instance
            target_stage: Target stage to advance to
            user: User performing the action
            notes: Optional notes for the advancement
        
        Returns:
            Dict: Result of advancement attempt
        """
        try:
            current_stage = opportunity.stage
            target_stage_config = self._get_stage_config(target_stage)
            
            if not target_stage_config:
                return {
                    'success': False,
                    'error': f"Invalid target stage: {target_stage}"
                }
            
            # Validate stage progression
            validation_result = self._validate_stage_progression(
                opportunity, current_stage, target_stage
            )
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['message'],
                    'missing_requirements': validation_result.get('missing_requirements', [])
                }
            
            # Check stage requirements
            requirements_check = self._check_stage_requirements(
                opportunity, target_stage_config
            )
            
            if not requirements_check['met']:
                return {
                    'success': False,
                    'error': "Stage requirements not met",
                    'missing_requirements': requirements_check['missing']
                }
            
            # Update opportunity
            old_stage = opportunity.stage
            old_probability = opportunity.probability
            
            opportunity.stage = target_stage
            opportunity.probability = target_stage_config.probability
            opportunity.stage_changed_at = timezone.now()
            opportunity.save()
            
            # Log stage change
            self._log_stage_change(
                opportunity, old_stage, target_stage, user, notes
            )
            
            # Update stage duration metrics
            self._update_stage_duration(opportunity, old_stage)
            
            # Trigger automation rules
            self._trigger_stage_automation(opportunity, target_stage_config, user)
            
            return {
                'success': True,
                'old_stage': old_stage,
                'new_stage': target_stage,
                'old_probability': old_probability,
                'new_probability': target_stage_config.probability,
                'message': f"Opportunity advanced from {old_stage} to {target_stage}"
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to advance opportunity: {str(e)}"
            }
    
    def get_next_stage(self, current_stage: str) -> Optional[PipelineStage]:
        """Get the next stage in the pipeline."""
        current_order = self.stage_order.get(current_stage)
        if current_order is None:
            return None
        
        # Find next stage by order
        next_stages = [
            stage for stage in self.pipeline_stages 
            if stage.order > current_order
        ]
        
        if next_stages:
            return min(next_stages, key=lambda s: s.order)
        
        return None
    
    def get_previous_stage(self, current_stage: str) -> Optional[PipelineStage]:
        """Get the previous stage in the pipeline."""
        current_order = self.stage_order.get(current_stage)
        if current_order is None:
            return None
        
        # Find previous stage by order
        previous_stages = [
            stage for stage in self.pipeline_stages 
            if stage.order < current_order
        ]
        
        if previous_stages:
            return max(previous_stages, key=lambda s: s.order)
        
        return None
    
    def calculate_stage_duration(self, opportunity, stage: str) -> Optional[int]:
        """Calculate how long opportunity has been in current stage."""
        if opportunity.stage != stage:
            # Calculate historical duration
            return self._get_historical_stage_duration(opportunity, stage)
        else:
            # Calculate current duration
            if opportunity.stage_changed_at:
                return (timezone.now() - opportunity.stage_changed_at).days
            else:
                return (timezone.now() - opportunity.created_at).days
    
    def check_stage_requirements(self, opportunity, stage: str = None) -> Dict[str, Any]:
        """Check if opportunity meets requirements for stage advancement."""
        target_stage = stage or opportunity.stage
        stage_config = self._get_stage_config(target_stage)
        
        if not stage_config:
            return {'met': False, 'missing': ['Invalid stage']}
        
        return self._check_stage_requirements(opportunity, stage_config)
    
    def auto_advance_opportunities(self, batch_size: int = 50) -> Dict[str, Any]:
        """Auto-advance opportunities based on automation rules."""
        try:
            from crm.models.opportunity import Opportunity
            
            # Get opportunities eligible for auto-advancement
            opportunities = Opportunity.objects.filter(
                tenant=self.tenant,
                stage__in=[s.stage_id for s in self.pipeline_stages if s.auto_advance_rules]
            )[:batch_size] if self.tenant else Opportunity.objects.filter(
                stage__in=[s.stage_id for s in self.pipeline_stages if s.auto_advance_rules]
            )[:batch_size]
            
            advanced_count = 0
            skipped_count = 0
            error_count = 0
            
            for opportunity in opportunities:
                try:
                    stage_config = self._get_stage_config(opportunity.stage)
                    if not stage_config or not stage_config.auto_advance_rules:
                        skipped_count += 1
                        continue
                    
                    # Check if auto-advance conditions are met
                    should_advance = self._evaluate_auto_advance_rules(
                        opportunity, stage_config.auto_advance_rules
                    )
                    
                    if should_advance:
                        next_stage = self.get_next_stage(opportunity.stage)
                        if next_stage:
                            result = self.advance_opportunity(
                                opportunity, 
                                next_stage.stage_id,
                                notes="Auto-advanced by system"
                            )
                            if result['success']:
                                advanced_count += 1
                            else:
                                error_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    error_count += 1
                    print(f"Error auto-advancing opportunity {opportunity.id}: {e}")
            
            return {
                'processed': len(opportunities),
                'advanced': advanced_count,
                'skipped': skipped_count,
                'errors': error_count
            }
        
        except Exception as e:
            return {'error': str(e)}
    
    def get_pipeline_metrics(self, date_range: Tuple[datetime, datetime] = None) -> PipelineMetrics:
        """Get comprehensive pipeline metrics."""
        try:
            from crm.models.opportunity import Opportunity
            
            # Build base query
            opportunities = Opportunity.objects.filter(
                tenant=self.tenant
            ) if self.tenant else Opportunity.objects.all()
            
            if date_range:
                opportunities = opportunities.filter(
                    created_at__range=date_range
                )
            
            # Calculate basic metrics
            total_opportunities = opportunities.count()
            total_value = opportunities.aggregate(
                total=Sum('value')
            )['total'] or Decimal('0')
            
            # Calculate weighted value (value * probability)
            weighted_value = Decimal('0')
            for opp in opportunities:
                if opp.value and opp.probability:
                    weighted_value += opp.value * (Decimal(opp.probability) / 100)
            
            average_deal_size = total_value / total_opportunities if total_opportunities > 0 else Decimal('0')
            
            # Calculate conversion rate
            won_opportunities = opportunities.filter(
                stage__in=[s.stage_id for s in self.pipeline_stages if s.is_won]
            ).count()
            conversion_rate = (won_opportunities / total_opportunities * 100) if total_opportunities > 0 else 0
            
            # Calculate average sales cycle
            closed_opportunities = opportunities.filter(
                stage__in=[s.stage_id for s in self.pipeline_stages if s.is_closed]
            )
            
            sales_cycles = []
            for opp in closed_opportunities:
                if opp.closed_date and opp.created_at:
                    cycle_days = (opp.closed_date - opp.created_at.date()).days
                    sales_cycles.append(cycle_days)
            
            average_sales_cycle = statistics.mean(sales_cycles) if sales_cycles else 0
            
            # Stage distribution
            stage_distribution = {}
            for stage in self.pipeline_stages:
                count = opportunities.filter(stage=stage.stage_id).count()
                stage_distribution[stage.name] = count
            
            # Velocity metrics
            velocity_metrics = self._calculate_velocity_metrics(opportunities)
            
            # Forecasted close
            forecasted_close = self._calculate_forecasted_close(opportunities)
            
            return PipelineMetrics(
                total_opportunities=total_opportunities,
                total_value=total_value,
                weighted_value=weighted_value,
                average_deal_size=average_deal_size,
                conversion_rate=conversion_rate,
                average_sales_cycle=average_sales_cycle,
                stage_distribution=stage_distribution,
                velocity_metrics=velocity_metrics,
                forecasted_close=forecasted_close
            )
        
        except Exception as e:
            print(f"Error calculating pipeline metrics: {e}")
            return PipelineMetrics(
                total_opportunities=0,
                total_value=Decimal('0'),
                weighted_value=Decimal('0'),
                average_deal_size=Decimal('0'),
                conversion_rate=0,
                average_sales_cycle=0,
                stage_distribution={},
                velocity_metrics={},
                forecasted_close={}
            )
    
    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify pipeline bottlenecks and problem areas."""
        try:
            from crm.models.opportunity import Opportunity
            
            bottlenecks = []
            
            # Analyze each stage
            for stage in self.pipeline_stages:
                if stage.is_closed:
                    continue
                
                stage_opportunities = Opportunity.objects.filter(
                    tenant=self.tenant,
                    stage=stage.stage_id
                ) if self.tenant else Opportunity.objects.filter(stage=stage.stage_id)
                
                stage_count = stage_opportunities.count()
                if stage_count == 0:
                    continue
                
                # Calculate average duration in stage
                durations = []
                stuck_count = 0
                
                for opp in stage_opportunities:
                    duration = self.calculate_stage_duration(opp, stage.stage_id)
                    if duration is not None:
                        durations.append(duration)
                        
                        # Check if stuck (exceeds target duration)
                        if stage.duration_target and duration > stage.duration_target:
                            stuck_count += 1
                
                if durations:
                    avg_duration = statistics.mean(durations)
                    max_duration = max(durations)
                    
                    # Identify bottleneck criteria
                    is_bottleneck = False
                    reasons = []
                    
                    if stage.duration_target and avg_duration > stage.duration_target * 1.5:
                        is_bottleneck = True
                        reasons.append(f"Average duration ({avg_duration:.1f} days) exceeds target by 50%")
                    
                    if stuck_count > stage_count * 0.3:  # More than 30% stuck
                        is_bottleneck = True
                        reasons.append(f"{stuck_count} opportunities stuck in stage")
                    
                    if max_duration > 90:  # Any opportunity older than 90 days
                        is_bottleneck = True
                        reasons.append(f"Opportunities stale for {max_duration} days")
                    
                    if is_bottleneck:
                        bottlenecks.append({
                            'stage_id': stage.stage_id,
                            'stage_name': stage.name,
                            'opportunities_count': stage_count,
                            'stuck_count': stuck_count,
                            'average_duration': avg_duration,
                            'max_duration': max_duration,
                            'target_duration': stage.duration_target,
                            'severity': 'high' if stuck_count > stage_count * 0.5 else 'medium',
                            'reasons': reasons
                        })
            
            return sorted(bottlenecks, key=lambda x: x['stuck_count'], reverse=True)
        
        except Exception as e:
            print(f"Error identifying bottlenecks: {e}")
            return []
    
    def _load_pipeline_stages(self) -> List[PipelineStage]:
        """Load pipeline stages from database or configuration."""
        stages = []
        
        try:
            from crm.models.opportunity import PipelineStage as DBPipelineStage
            
            db_stages = DBPipelineStage.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).order_by('order') if self.tenant else DBPipelineStage.objects.filter(
                is_active=True
            ).order_by('order')
            
            for db_stage in db_stages:
                stage = PipelineStage(
                    stage_id=db_stage.name.lower().replace(' ', '_'),
                    name=db_stage.name,
                    order=db_stage.order,
                    probability=db_stage.probability,
                    is_closed=db_stage.is_closed,
                    is_won=db_stage.is_won,
                    requirements=db_stage.requirements.split(',') if db_stage.requirements else [],
                    auto_advance_rules=db_stage.auto_advance_rules or [],
                    duration_target=db_stage.duration_target
                )
                stages.append(stage)
        
        except Exception as e:
            print(f"Error loading pipeline stages: {e}")
            # Return default stages
            stages = self._get_default_pipeline_stages()
        
        return stages
    
    def _get_default_pipeline_stages(self) -> List[PipelineStage]:
        """Get default pipeline stages."""
        return [
            PipelineStage('prospecting', 'Prospecting', 1, 10, duration_target=7),
            PipelineStage('qualification', 'Qualification', 2, 25, duration_target=14),
            PipelineStage('needs_analysis', 'Needs Analysis', 3, 40, duration_target=21),
            PipelineStage('proposal', 'Proposal', 4, 60, duration_target=14),
            PipelineStage('negotiation', 'Negotiation', 5, 80, duration_target=10),
            PipelineStage('closed_won', 'Closed Won', 6, 100, is_closed=True, is_won=True),
            PipelineStage('closed_lost', 'Closed Lost', 7, 0, is_closed=True, is_won=False),
        ]
    
    def _get_stage_config(self, stage_id: str) -> Optional[PipelineStage]:
        """Get stage configuration by ID."""
        for stage in self.pipeline_stages:
            if stage.stage_id == stage_id:
                return stage
        return None
    
    def _validate_stage_progression(self, opportunity, current_stage: str, 
                                  target_stage: str) -> Dict[str, Any]:
        """Validate if stage progression is allowed."""
        current_order = self.stage_order.get(current_stage, 0)
        target_order = self.stage_order.get(target_stage)
        
        if target_order is None:
            return {
                'valid': False,
                'message': f"Invalid target stage: {target_stage}"
            }
        
        # Allow progression to any stage (including backwards)
        # But warn about backwards movement
        if target_order < current_order:
            return {
                'valid': True,
                'message': f"Moving backwards from {current_stage} to {target_stage}",
                'warning': True
            }
        
        # Check for skipping stages
        if target_order > current_order + 1:
            skipped_stages = [
                stage.name for stage in self.pipeline_stages
                if current_order < stage.order < target_order
            ]
            return {
                'valid': True,
                'message': f"Skipping stages: {', '.join(skipped_stages)}",
                'warning': True,
                'skipped_stages': skipped_stages
            }
        
        return {'valid': True, 'message': 'Valid progression'}
    
    def _check_stage_requirements(self, opportunity, stage_config: PipelineStage) -> Dict[str, Any]:
        """Check if opportunity meets stage requirements."""
        missing_requirements = []
        
        for requirement in stage_config.requirements:
            if requirement == 'contact_info_complete':
                if not opportunity.account or not opportunity.account.email:
                    missing_requirements.append('Complete contact information required')
            
            elif requirement == 'budget_qualified':
                if not opportunity.budget or opportunity.budget <= 0:
                    missing_requirements.append('Budget qualification required')
            
            elif requirement == 'decision_maker_identified':
                if not hasattr(opportunity, 'decision_maker') or not opportunity.decision_maker:
                    missing_requirements.append('Decision maker must be identified')
            
            elif requirement == 'needs_documented':
                # Check if there are notes or needs analysis
                if not opportunity.description:
                    missing_requirements.append('Customer needs must be documented')
            
            elif requirement == 'proposal_sent':
                # Check if proposal activity exists
                try:
                    from crm.models.activity import Activity
                    has_proposal = Activity.objects.filter(
                        related_to_id=opportunity.id,
                        type='PROPOSAL',
                        tenant=self.tenant
                    ).exists()
                    if not has_proposal:
                        missing_requirements.append('Proposal must be sent')
                except:
                    pass
        
        return {
            'met': len(missing_requirements) == 0,
            'missing': missing_requirements
        }
    
    def _log_stage_change(self, opportunity, old_stage: str, new_stage: str, 
                         user=None, notes: str = ""):
        """Log stage change for audit purposes."""
        try:
            from crm.models.opportunity import OpportunityStageHistory
            
            OpportunityStageHistory.objects.create(
                opportunity=opportunity,
                old_stage=old_stage,
                new_stage=new_stage,
                changed_by=user,
                change_reason=notes,
                changed_at=timezone.now(),
                tenant=self.tenant
            )
        except Exception as e:
            print(f"Error logging stage change: {e}")
    
    def _update_stage_duration(self, opportunity, old_stage: str):
        """Update stage duration metrics."""
        try:
            duration = self.calculate_stage_duration(opportunity, old_stage)
            if duration is not None:
                cache_key = f"stage_duration_{self.tenant.id if self.tenant else 'default'}_{old_stage}"
                durations = cache.get(cache_key, [])
                durations.append(duration)
                # Keep only last 100 durations for memory efficiency
                durations = durations[-100:]
                cache.set(cache_key, durations, 86400)  # Cache for 24 hours
        except Exception as e:
            print(f"Error updating stage duration: {e}")
    
    def _trigger_stage_automation(self, opportunity, stage_config: PipelineStage, user=None):
        """Trigger automation rules for stage advancement."""
        try:
            from crm.models.activity import Activity
            
            for rule in stage_config.auto_advance_rules:
                if rule.get('type') == 'create_activity':
                    Activity.objects.create(
                        type=rule.get('activity_type', 'TASK'),
                        subject=rule.get('subject', f"Follow up on {opportunity.name}"),
                        description=rule.get('description', ''),
                        due_date=timezone.now() + timedelta(days=rule.get('due_days', 1)),
                        assigned_to=user or opportunity.assigned_to,
                        related_to_id=opportunity.id,
                        tenant=self.tenant
                    )
                
                elif rule.get('type') == 'send_notification':
                    # Trigger notification (would integrate with notification system)
                    pass
                
                elif rule.get('type') == 'update_field':
                    field_name = rule.get('field_name')
                    field_value = rule.get('field_value')
                    if hasattr(opportunity, field_name):
                        setattr(opportunity, field_name, field_value)
                        opportunity.save()
        
        except Exception as e:
            print(f"Error triggering stage automation: {e}")
    
    def _evaluate_auto_advance_rules(self, opportunity, rules: List[Dict[str, Any]]) -> bool:
        """Evaluate if opportunity should be auto-advanced based on rules."""
        for rule in rules:
            rule_type = rule.get('type')
            
            if rule_type == 'time_based':
                # Auto-advance after certain time in stage
                duration = self.calculate_stage_duration(opportunity, opportunity.stage)
                target_days = rule.get('days', 30)
                if duration and duration >= target_days:
                    return True
            
            elif rule_type == 'activity_based':
                # Auto-advance based on completed activities
                try:
                    from crm.models.activity import Activity
                    required_activities = rule.get('required_activities', [])
                    
                    for activity_type in required_activities:
                        has_activity = Activity.objects.filter(
                            related_to_id=opportunity.id,
                            type=activity_type,
                            status='COMPLETED',
                            tenant=self.tenant
                        ).exists()
                        if not has_activity:
                            return False
                    return True
                except:
                    pass
            
            elif rule_type == 'field_based':
                # Auto-advance based on field values
                field_name = rule.get('field_name')
                expected_value = rule.get('expected_value')
                if hasattr(opportunity, field_name):
                    field_value = getattr(opportunity, field_name)
                    if field_value == expected_value:
                        return True
        
        return False
    
    def _calculate_velocity_metrics(self, opportunities) -> Dict[str, Any]:
        """Calculate pipeline velocity metrics."""
        try:
            # Calculate average time between stages
            stage_velocities = {}
            
            for stage in self.pipeline_stages:
                if stage.is_closed:
                    continue
                
                # Get opportunities that moved through this stage
                stage_durations = []
                cache_key = f"stage_duration_{self.tenant.id if self.tenant else 'default'}_{stage.stage_id}"
                cached_durations = cache.get(cache_key, [])
                
                if cached_durations:
                    avg_duration = statistics.mean(cached_durations)
                    stage_velocities[stage.name] = {
                        'average_days': round(avg_duration, 1),
                        'sample_size': len(cached_durations)
                    }
            
            return {
                'stage_velocities': stage_velocities,
                'calculation_date': timezone.now().isoformat()
            }
        
        except Exception as e:
            print(f"Error calculating velocity metrics: {e}")
            return {}
    
    def _calculate_forecasted_close(self, opportunities) -> Dict[str, Any]:
        """Calculate forecasted close dates and values."""
        try:
            forecasts = {}
            
            # Group by expected close month
            monthly_forecasts = defaultdict(lambda: {'count': 0, 'value': Decimal('0'), 'weighted_value': Decimal('0')})
            
            for opp in opportunities.filter(expected_close_date__isnull=False):
                if opp.expected_close_date and not any(s.is_closed for s in self.pipeline_stages if s.stage_id == opp.stage):
                    month_key = opp.expected_close_date.strftime('%Y-%m')
                    monthly_forecasts[month_key]['count'] += 1
                    monthly_forecasts[month_key]['value'] += opp.value or Decimal('0')
                    
                    if opp.probability:
                        weighted_value = (opp.value or Decimal('0')) * (Decimal(opp.probability) / 100)
                        monthly_forecasts[month_key]['weighted_value'] += weighted_value
            
            # Convert to regular dict and format
            for month, data in monthly_forecasts.items():
                forecasts[month] = {
                    'opportunities_count': data['count'],
                    'total_value': float(data['value']),
                    'weighted_value': float(data['weighted_value']),
                    'confidence_level': 'medium' if data['count'] > 5 else 'low'
                }
            
            return forecasts
        
        except Exception as e:
            print(f"Error calculating forecasted close: {e}")
            return {}
    
    def _get_historical_stage_duration(self, opportunity, stage: str) -> Optional[int]:
        """Get historical duration for a specific stage."""
        try:
            from crm.models.opportunity import OpportunityStageHistory
            
            # Find when opportunity entered and left this stage
            stage_history = OpportunityStageHistory.objects.filter(
                opportunity=opportunity,
                tenant=self.tenant
            ).order_by('changed_at')
            
            entered_stage = None
            left_stage = None
            
            for history in stage_history:
                if history.new_stage == stage and entered_stage is None:
                    entered_stage = history.changed_at
                elif history.old_stage == stage and entered_stage is not None:
                    left_stage = history.changed_at
                    break
            
            if entered_stage and left_stage:
                return (left_stage - entered_stage).days
            
            return None
        
        except Exception as e:
            print(f"Error getting historical stage duration: {e}")
            return None


# Convenience functions
def get_next_stage(current_stage: str, tenant=None) -> Optional[PipelineStage]:
    """Get next stage in pipeline."""
    manager = PipelineManager(tenant)
    return manager.get_next_stage(current_stage)


def calculate_stage_duration(opportunity, stage: str = None, tenant=None) -> Optional[int]:
    """Calculate stage duration for opportunity."""
    manager = PipelineManager(tenant)
    return manager.calculate_stage_duration(opportunity, stage or opportunity.stage)


def check_stage_requirements(opportunity, stage: str = None, tenant=None) -> Dict[str, Any]:
    """Check stage requirements for opportunity."""
    manager = PipelineManager(tenant)
    return manager.check_stage_requirements(opportunity, stage)


def auto_advance_opportunities(tenant=None, batch_size: int = 50) -> Dict[str, Any]:
    """Auto-advance eligible opportunities."""
    manager = PipelineManager(tenant)
    return manager.auto_advance_opportunities(batch_size)


def identify_pipeline_bottlenecks(tenant=None) -> List[Dict[str, Any]]:
    """Identify pipeline bottlenecks."""
    manager = PipelineManager(tenant)
    return manager.identify_bottlenecks()


def get_pipeline_health_score(tenant=None) -> Dict[str, Any]:
    """Calculate overall pipeline health score."""
    manager = PipelineManager(tenant)
    metrics = manager.get_pipeline_metrics()
    bottlenecks = manager.identify_bottlenecks()
    
    # Calculate health score based on multiple factors
    health_score = 100
    
    # Reduce score for bottlenecks
    for bottleneck in bottlenecks:
        if bottleneck['severity'] == 'high':
            health_score -= 15
        elif bottleneck['severity'] == 'medium':
            health_score -= 8
    
    # Reduce score for low conversion rate
    if metrics.conversion_rate < 20:
        health_score -= 20
    elif metrics.conversion_rate < 40:
        health_score -= 10
    
    # Reduce score for long sales cycle
    if metrics.average_sales_cycle > 90:
        health_score -= 15
    elif metrics.average_sales_cycle > 60:
        health_score -= 8
    
    health_score = max(0, min(100, health_score))
    
    # Determine health level
    if health_score >= 80:
        health_level = 'Excellent'
    elif health_score >= 60:
        health_level = 'Good'
    elif health_score >= 40:
        health_level = 'Fair'
    else:
        health_level = 'Poor'
    
    return {
        'health_score': health_score,
        'health_level': health_level,
        'total_opportunities': metrics.total_opportunities,
        'total_value': float(metrics.total_value),
        'conversion_rate': metrics.conversion_rate,
        'average_sales_cycle': metrics.average_sales_cycle,
        'bottleneck_count': len(bottlenecks),
        'recommendations': generate_pipeline_recommendations(metrics, bottlenecks, health_score)
    }


def generate_pipeline_recommendations(metrics: PipelineMetrics, 
                                    bottlenecks: List[Dict[str, Any]], 
                                    health_score: int) -> List[str]:
    """Generate recommendations for pipeline improvement."""
    recommendations = []
    
    if health_score < 60:
        recommendations.append("Pipeline needs immediate attention - consider pipeline review meeting")
    
    if bottlenecks:
        recommendations.append(f"Address {len(bottlenecks)} identified bottleneck(s) in pipeline stages")
        for bottleneck in bottlenecks[:3]:  # Top 3 bottlenecks
            recommendations.append(f"Focus on {bottleneck['stage_name']} stage - {bottleneck['stuck_count']} opportunities stuck")
    
    if metrics.conversion_rate < 25:
        recommendations.append("Improve lead qualification to increase conversion rate")
    
    if metrics.average_sales_cycle > 75:
        recommendations.append("Streamline sales process to reduce average sales cycle")
    
    if metrics.total_opportunities < 10:
        recommendations.append("Increase lead generation activities to build pipeline")
    
    return recommendations[:5]  # Return top 5 recommendations