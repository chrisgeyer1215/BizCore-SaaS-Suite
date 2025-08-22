# ============================================================================
# backend/apps/crm/services/opportunity_service.py - Advanced Opportunity Management Service
# ============================================================================

from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max, Min
from django.utils import timezone
from typing import Dict, List, Optional, Tuple, Union
import json
import statistics
import numpy as np
from datetime import timedelta, datetime
from collections import defaultdict
from dataclasses import dataclass

from .base import BaseService, ServiceException, ServiceContext
from ..models import Opportunity, Pipeline, PipelineStage, OpportunityProduct, Account


@dataclass
class OpportunityIntelligence:
    """Data class for opportunity intelligence insights"""
    win_probability: float
    expected_close_date: datetime
    risk_factors: List[str]
    success_indicators: List[str]
    recommended_actions: List[str]
    competitive_threats: List[str]
    deal_velocity_score: int
    next_best_action: str


class OpportunityAI:
    """Advanced AI engine for opportunity intelligence"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._model_cache = {}
    
    def predict_win_probability(self, opportunity_ win probability using ML model"""
        try:
            features = self._extract_win_probability_features(opportunity_data)
            model = self._get_win_probability_model()
            
            probability = model.predict_proba([features])[0][1]
            return min(1.0, max(0.0, probability))
            
        except Exception as e:
            return self._fallback_win_probability(opportunity_data)
    
    def _extract_win[float]:
        """Extract features for win probability prediction"""
        features = []
        
        # Stage progression features
        features.append(opp_data.get('current_stage_probability', 0) / 100)
        features.append(opp_data.get('stage_progression_velocity', 0))
        features.append(opp_data.get('time_in_current_stage_days', 0) / 30)
        
        # Engagement features
        features.append(min(1.0, opp_data.get('activities_count', 0) / 10))
        features.append(min(1.0, opp_data.get('stakeholder_meetings', 0) / 5))
        features.append(1 if opp_data.get('champion_identified', False) else 0)
        
        # Account features
        features.append(opp_data.get('account_health_score', 50) / 100)
        features.append(min(1.0, opp_data.get('account_revenue', 0) / 1000000))
        features.append(1 if opp_data.get('existing_customer', False) else 0)
        
        # Deal characteristics
        features.append(min(1.0, opp_data.get('deal_size', 0) / 100000))
        features.append(opp_data.get('competitive_situation', 1) / 3)  # 0-3 scale
        features.append(opp_data.get('budget_confirmed', 0.5))  # 0-1 scale
        
        # Temporal features
        features.append(opp_data.get('days_since_created', 0) / 90)
        features.append(opp_data.get('days_to_close', 30) / 90)
        
        return features
    
    def analyze_deal:
        """Analyze deal velocity and progression patterns"""
        velocity_analysis = {
            'current_velocity': 0,
            'expected_velocity': 0,
            'velocity_trend': 'NORMAL',
            'bottlenecks': [],
            'acceleration_opportunities': []
        }
        
        # Calculate current velocity
        days_in_pipeline = opportunity_data.get('days_since_created', 1)
        current_stage_probability = opportunity_data.get('current_stage_probability', 0)
        
        velocity_analysis['current_velocity'] = current_stage_probability / days_in_pipeline if days_in_pipeline > 0 else 0
        
        # Compare with expected velocity
        expected_cycle_length = opportunity_data.get('expected_sales_cycle_days', 60)
        expected_velocity = 100 / expected_cycle_length
        
        velocity_analysis['expected_velocity'] = expected_velocity
        
        # Determine trend
        velocity_ratio = velocity_analysis['current_velocity'] / expected_velocity if expected_velocity > 0 else 1
        
        if velocity_ratio > 1.2:
            velocity_analysis['velocity_trend'] = 'ACCELERATING'
        elif velocity_ratio < 0.8:
            velocity_analysis['velocity_trend'] = 'DECELERATING'
        else:
            velocity_analysis['velocity_trend'] = 'NORMAL'
        
        # Identify bottlenecks and opportunities
        if opportunity_data.get('time_in_current_stage_days', 0) > 14:
            velocity_analysis['bottlenecks'].append('Extended time in current stage')
        
        if opportunity_data.get('activities_count', 0) < 3:
            velocity_analysis['bottlenecks'].append('Low engagement activity')
        
        if not opportunity_data.get('champion_identified', False):
            velocity_analysis['acceleration_opportunities'].append('Identify executive champion')
        
        return velocity_analysis
    
    def predict_close_date(self, opportunity_data: Dict) -> datetime:
        """Predict realistic close date based on patterns"""
        try:
            # Current close date
            current_close_date = opportunity_data.get('close_date')
            if not current_close_date:
                current_close_date = timezone.now().date() + timedelta(days=30)
            
            # Calculate velocity-based prediction
            current_stage_prob = opportunity_data.get('current_stage_probability', 0)
            remaining_probability = 100 - current_stage_prob
            
            # Historical velocity data (mock - would come from analytics)
            avg_velocity_per_day = 1.5  # probability points per day
            
            predicted_days_remaining = remaining_probability / avg_velocity_per_day
            
            # Adjust for deal complexity factors
            complexity_multiplier = 1.0
            
            if opportunity_data.get('deal_size', 0) > 100000:
                complexity_multiplier += 0.3
            
            if opportunity_data.get('competitive_situation', 1) > 2:
                complexity_multiplier += 0.2
            
            if not opportunity_data.get('budget_confirmed', True):
                complexity_multiplier += 0.4
            
            adjusted_days = predicted_days_remaining * complexity_multiplier
            
            predicted_close = timezone.now().date() + timedelta(days=int(adjusted_days))
            
            return predicted_close
            
        except Exception as e:
            # Fallback to current close date or 30 days
            return current_close_date or timezone.now().date() + timedelta(days=30)


class OpportunityService(BaseService):
    """Advanced opportunity management service with AI-powered insights"""
    
    def __init__(self, tenant=None, user=None, context: ServiceContext = None):
        super().__init__(tenant, user, context)
        self.ai_engine = OpportunityAI(tenant.id if tenant else 0)
        
    def create_intelligent = None,
                                     auto_enrich: bool = True, ai_insights: bool = True) -> Opportunity:
        """Create opportunity with AI-powered enrichment and insights"""
        try:
            with transaction.atomic():
                # Data validation
                is_valid, validation_errors = self.validate_data_integrity(
                    opportunity_data, self._get_opportunity_schema()
                )
                if not is_valid:
                    raise ServiceException(
                        f"Opportunity validation failed: {', '.join(validation_errors)}",
                        code='INVALID_OPPORTUNITY_DATA'
                    )
                
                # Intelligent data enrichment
                if auto_enrich:
                    enriched_data = self.enrich_opportunity_data(opportunity_data)
                    opportunity_data.update(enriched_data)
                
                # Create opportunity
                opportunity = Opportunity.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **opportunity_data
                )
                
                # Ad
                    self._add_products_with_intelligence(opportunity, products_data)
                
                # Generate AI insights
                if ai_insights:
                    intelligence = self.generate_opportunity_intelligence(opportunity)
                    self._apply_initial_intelligence(opportunity, intelligence)
                
                # Set up opportunity tracking
                self._initialize_opportunity_tracking(opportunity)
                
                # Create initial activities and milestones
                self._create_initial_opportunity_plan(opportunity)
                
                self.log_activity('CREATE_INTELLIGENT_OPPORTUNITY', 'Opportunity', opportunity.id, {
                    'opportunity_name': opportunity.name,
                    'amount': opportunity.amount,
                    'win_probability': getattr(opportunity, 'ai_win_probability', None),
                    'account_name': opportunity.account.name,
                    'products_count': len(products_data) if products_data else 0
                })
                
                return opportunity
                
        except Exception as e:
            if isinstance(e, ServiceException):
                raise
            raise ServiceException(f"Failed to create intelligent opportunity: {str(e)}")
    
    def _get_opportunity_schema(self) -> Dict:
        """Get opportunity validation schema"""
        return {
            'name': {'required': True, 'min_length': 3},
            'amount': {'required': True, 'validator': lambda x: x > 0},
            'close_date': {'required': True},
            'account': {'required': True},
            'pipeline': {'required': True}
        }
    
    def en:
        """Enrich opportunity data with intelligence"""
        enriched_data = {}
        
        try:
            # Account-based enrichment
            if opportunity_data.get('account'):
                account_intelligence = self._gather_account_intelligence(opportunity_data['account'])
                enriched_data.update(account_intelligence)
            
            # Industry-based intelligence
            industry_data = self._gather_industry_intelligence(opportunity_data)
            enriched_data.update(industry_data)
            
            # Competitive intelligence
            competitive_data = self._analyze_competitive_landscape(opportunity_data)
            enriched_data.update(competitive_data)
            
            # Temporal intelligence (seasonal factors, timing)
            temporal_data = self._analyze_temporal_factors(opportunity_data)
            enriched_data.update(temporal_data)
            
        except Exception as e:
            logger.warning(f"Opportunity enrichment failed: {e}")
        
        return enriched_data
    
    def generate_opportunity_intelligence(self, opportunity: Opportunity) -> OpportunityIntelligence:
        """Generate comprehensive AI-powered opportunity intelligence"""
        # Gather data for analysis
        opp_data = self._gather_opportunity_intelligence_data(opportunity)
        
        # AI predictions
        win_probability = self.ai_engine.predict_win_probability(opp_data)
        expected_close_date = self.ai_engine.predict_close_date(opp_data)
        
        # Velocity analysis
        velocity_analysis = self.ai_engine.analyze_deal_velocity(opp_data)
        
        # Risk and success factor analysis
        risk_factors = self._identify_risk_factors(opp_data)
        success_indicators = self._identify_success_indicators(opp_data)
        
        # Recommendations
        recommended_actions = self._generate_intelligent_recommendations(opp_data, win_probability)
        
        # Competitive analysis
        competitive_threats = self._analyze_competitive_threats(opp_data)
        
        # Next best action
        next_best_action = self._determine_next_best_action(opp_data, win_probability)
        
        return OpportunityIntelligence(
            win_probability=win_probability,
            expected_close_date=expected_close_date,
            risk_factors=risk_factors,
            success_indicators=success_indicators,
            recommended_actions=recommended_actions,
            competitive_threats=competitive_threats,
            deal_velocity_score=int(velocity_analysis['current_velocity'] * 100),
            next_best_action=next_best_action
        )
    
    def _gather_opportunity_intelligence_data(self, opportunity: Opportunity) -> Dict:
        """Gather comprehensive data for AI analysis"""
        now = timezone.now()
        
        # Basic opportunity data
        data = {
            'opportunity_id': opportunity.id,
            'current_stage_probability': opportunity.stage.probability if opportunity.stage else 0,
            'deal_size': opportunity.amount or 0,
            'days_since_created': (now.date() - opportunity.created_at.date()).days,
            'close_date': opportunity.close_date,
            'days_to_close': (opportunity.close_date - now.date()).days if opportunity.close_date else 30,
        }
        
        # Account intelligence
        if opportunity.account:
            account_health = getattr(opportunity.account, 'health_score', 50)
            data.update({
                'account_health_score': account_health,
                'account_revenue': opportunity.account.annual_revenue or 0,
                'existing_customer': opportunity.account.opportunities.filter(is_won=True).exists()
            })
        
        # Activity and engagement data
        activities = opportunity.activities.all()
        data.update({
            'activities_count': activities.count(),
            'days_since_last_activity': (
                (now - activities.order_by('-created_at').first().created_at).days
                if activities.exists() else 999
            ),
            'stakeholder_meetings': activities.filter(
                activity_type__name__icontains='meeting'
            ).count()
        })
        
        # Stage progression data
        if opportunity.stage:
            data.update({
                'time_in_current_stage_days': (
                    (now.date() - (opportunity.last_stage_change or opportunity.created_at).date()).days
                ),
                'stage_progression_velocity': self._calculate_stage_velocity(opportunity)
            })
        
        # Products and pricing data
        opp_products = opportunity.products.all()
        if opp_products.exists():
            data.update({
                'products_count': opp_products.count(),
                'total_product_value': sum(p.price * p.quantity for p in opp_products),
                'discount_percentage': self._calculate_discount_percentage(opportunity)
            })
        
        # Competitive and qualification data (would come from custom fields or related models)
        data.update({
            'budget_confirmed': 0.7,  # Mock - would come from qualification data
            'decision_maker_engaged': True,  # Mock
            'champion_identified': False,  # Mock
            'competitive_situation': 2,  # 0-3 scale, mock
            'expected_sales_cycle_days': 60  # Mock - based on historical data
        })
        
        return data
    
    def intelligent_stage_progression(self, opportunity: Opportunity, target_stage_id: int,
                                    auto_validate: bool = True) -> Dict:
        """Intelligent stage progression with validation and recommendations"""
        try:
            target_stage = PipelineStage.objects.get(
                id=target_stage_id,
                pipeline=opportunity.pipeline,
                tenant=self.tenant
            )
            
            # Validate stage progression readiness
            if auto_validate:
                validation_result = self._validate_stage_progression(opportunity, target_stage)
                if not validation_result['ready']:
                    return {
                        'success': False,
                        'blocked': True,
                        'blocking_reasons': validation_result['blocking_reasons'],
                        'recommendations': validation_result['recommendations']
                    }
            
            old_stage = opportunity.stage
            
            with transaction.atomic():
                # Update opportunity
                opportunity.stage = target_stage
                opportunity.probability = target_stage.probability
                opportunity.last_stage_change = timezone.now()
                
                # Generate AI insights for new stage
                intelligence = self.generate_opportunity_intelligence(opportunity)
                
                # Update AI predictions
                opportunity.ai_win_probability = intelligence.win_probability
                opportunity.ai_expected_close_date = intelligence.expected_close_date
                
                # Handle stage-specific logic
                if target_stage.stage_type in ['WON', 'LOST']:
                    opportunity.is_closed = True
                    opportunity.is_won = (target_stage.stage_type == 'WON')
                    opportunity.closed_date = timezone.now()
                    
                    if opportunity.is_won:
                        self._handle_opportunity_won(opportunity)
                    else:
                        self._handle_opportunity_lost(opportunity, intelligence.risk_factors)
                
                opportunity.save()
                
                # Create stage progression activity
                self._create_stage_progression_activity(opportunity, old_stage, target_stage)
                
                # Update pipeline metrics
                self._update_pipeline_metrics(opportunity.pipeline)
                
                self.log_activity('INTELLIGENT_STAGE_PROGRESSION', 'Opportunity', opportunity.id, {
                    'old_stage': old_stage.name if old_stage else None,
                    'new_stage': target_stage.name,
                    'new_win_probability': intelligence.win_probability,
                    'recommended_actions': intelligence.recommended_actions[:3]
                })
                
                return {
                    'success': True,
                    'new_stage': target_stage.name,
                    'new_probability': target_stage.probability,
                    'ai_win_probability': intelligence.win_probability,
                    'intelligence': {
                        'risk_factors': intelligence.risk_factors,
                        'success_indicators': intelligence.success_indicators,
                        'recommended_actions': intelligence.recommended_actions,
                        'next_best_action': intelligence.next_best_action
                    }
                }
                
        except PipelineStage.DoesNotExist:
            raise ServiceException("Invalid target stage", code='INVALID_STAGE')
        except Exception as e:
            if isinstance(e, ServiceException):
                raise
            raise ServiceException(f"Stage progression failed: {str(e)}")
    
    def _validate_stage_progression(self, opportunity: Opportunity, target_stage: PipelineStage) -> Dict:
        """Validate if opportunity is ready for stage progression"""
        validation_result = {
            'ready': True,
            'blocking_reasons': [],
            'recommendations': []
        }
        
        # Stage sequence validation
        if opportunity.stage:
            current_order = opportunity.stage.sort_order
            target_order = target_stage.sort_order
            
            # Don't allow jumping multiple stages forward
            if target_order > current_order + 1 and target_stage.stage_type not in ['LOST']:
                validation_result['ready'] = False
                validation_result['blocking_reasons'].append('Cannot skip pipeline stages')
                validation_result['recommendations'].append('Progress through intermediate stages first')
        
        # Stage-specific validations
        stage_requirements = self._get_stage_requirements(target_stage)
        
        for requirement in stage_requirements:
            if not self._check_stage_requirement(opportunity, requirement):
                validation_result['ready'] = False
                validation_result['blocking_reasons'].append(requirement['message'])
                validation_result['recommendations'].append(requirement['recommendation'])
        
        return validation_result
    
    def _get_stage_requirements(self, stage: PipelineStage) -> List[Dict]:
        """Get requirements for progressing to specific stage"""
        requirements_map = {
            'QUALIFICATION': [
                {
                    'check': 'budget_confirmed',
                    'message': 'Budget not confirmed',
                    'recommendation': 'Qualify budget and decision-making process'
                }
            ],
            'PROPOSAL': [
                {
                    'check': 'needs_identified',
                    'message': 'Customer needs not fully identified',
                    'recommendation': 'Complete needs analysis and discovery'
                },
                {
                    'check': 'decision_maker_engaged',
                    'message': 'Decision maker not engaged',
                    'recommendation': 'Identify and engage primary decision maker'
                }
            ],
            'NEGOTIATION': [
                {
                    'check': 'proposal_delivered',
                    'message': 'Proposal not delivered',
                    'recommendation': 'Deliver formal proposal before negotiation'
                }
            ]
        }
        
        return requirements_map.get(stage.stage_type, [])
    
    def generate_sales_forecast_advanced(self, forecast_period_days: int = 90,
                                       confidence_levels: List[float] = [0.9, 0.7, 0.5]) -> Dict:
        """Generate advanced sales forecast with multiple confidence scenarios"""
        end_date = timezone.now().date() + timedelta(days=forecast_period_days)
        
        # Get opportunities in forecast period
        forecast_opportunities = Opportunity.objects.filter(
            tenant=self.tenant,
            is_closed=False,
            close_date__lte=end_date
        ).select_related('stage', 'account', 'owner')
        
        forecast_data = {
            'forecast_period_days': forecast_period_days,
            'total_opportunities': forecast_opportunities.count(),
            'scenarios': {},
            'monthly_breakdown': [],
            'by_owner': [],
            'by_pipeline': [],
            'risk_analysis': {},
            'recommendations': []
        }
        
        # Generate scenarios for different confidence levels
        for confidence in confidence_levels:
            scenario_data = self._calculate_forecast_scenario(forecast_opportunities, confidence)
            forecast_data['scenarios'][f'{int(confidence*100)}%_confidence'] = scenario_data
        
        # Monthly breakdown
        forecast_data['monthly_breakdown'] = self._generate_monthly_forecast_breakdown(
            forecast_opportunities, forecast_period_days
        )
        
        # Forecast by sales rep
        forecast_data['by_owner'] = self._generate_owner_forecast_breakdown(forecast_opportunities)
        
        # Pipeline analysis
        forecast_data['by_pipeline'] = self._generate_pipeline_forecast_breakdown(forecast_opportunities)
        
        # Risk analysis
        forecast_data['risk_analysis'] = self._analyze_forecast_risks(forecast_opportunities)
        
        # Generate recommendations
        forecast_data['recommendations'] = self._generate_forecast_recommendations(forecast_data)
        
        return forecast_data
    
    def _calculate_forecast_scenario(self, opportunities, confidence_threshold: float) -> Dict:
        """Calculate forecast scenario for given confidence threshold"""
        total_weighted_value = 0
        total_ai_weighted_value = 0
        included_opportunities = 0
        
        scenario_opportunities = []
        
        for opp in opportunities:
            # Traditional stage-based probability
            stage_probability = opp.probability or 0
            
            # AI-enhanced probability (if available)
            ai_probability = getattr(opp, 'ai_win_probability', stage_probability)
            
            # Use AI probability if it's significantly different and confidence is high
            final_probability = ai_probability if confidence_threshold >= 0.7 else stage_probability
            
            if final_probability >= confidence_threshold * 100:
                weighted_value = (opp.amount or 0) * (final_probability / 100)
                total_weighted_value += weighted_value
                
                ai_weighted_value = (opp.amount or 0) * (ai_probability / 100)
                total_ai_weighted_value += ai_weighted_value
                
                included_opportunities += 1
                
                scenario_opportunities.append({
                    'opportunity_id': opp.id,
                    'name': opp.name,
                    'amount': opp.amount,
                    'stage_probability': stage_probability,
                    'ai_probability': ai_probability,
                    'final_probability': final_probability,
                    'weighted_value': weighted_value,
                    'close_date': opp.close_date.isoformat() if opp.close_date else None
                })
        
        return {
            'confidence_threshold': confidence_threshold,
            'total_pipeline_value': sum(opp.amount or 0 for opp in opportunities),
            'total_weighted_value': total_weighted_value,
            'total_ai_weighted_value': total_ai_weighted_value,
            'included_opportunities': included_opportunities,
            'opportunities': sorted(scenario_opportunities, key=lambda x: x['weighted_value'], reverse=True)
        }
    
    def analyze_pipeline_health_comprehensive(self, pipeline_id: Optional[int] = None) -> Dict:
        """Comprehensive pipeline health analysis with AI insights"""
        if pipeline_id:
            opportunities = Opportunity.objects.filter(
                pipeline_id=pipeline_id,
                tenant=self.tenant,
                is_closed=False
            )
            pipeline = Pipeline.objects.get(id=pipeline_id, tenant=self.tenant)
        else:
            opportunities = Opportunity.objects.filter(
                tenant=self.tenant,
                is_closed=False
            )
            pipeline = None
        
        analysis = {
            'pipeline_overview': self._analyze_pipeline_overview(opportunities, pipeline),
            'stage_analysis': self._analyze_pipeline_stages(opportunities, pipeline),
            'velocity_analysis': self._analyze_pipeline_velocity(opportunities),
            'conversion_analysis': self._analyze_stage_conversions(opportunities, pipeline),
            'health_indicators': self._calculate_pipeline_health_indicators(opportunities),
            'bottleneck_analysis': self._identify_pipeline_bottlenecks(opportunities, pipeline),
            'ai_insights': self._generate_pipeline_ai_insights(opportunities),
            'recommendations': self._generate_pipeline_recommendations(opportunities, pipeline)
        }
        
        return analysis
    
    def _analyze_pipeline_velocity(self, opportunities) -> Dict:
        """Analyze pipeline velocity metrics"""
        velocity_data = {
            'average_velocity': 0,
            'velocity_by_stage': {},
            'velocity_trends': [],
            'fast_moving_deals': [],
            'stalled_deals': []
        }
        
        total_velocity = 0
        velocity_count = 0
        
        for opp in opportunities:
            opp_data = self._gather_opportunity_intelligence_data(opp)
            velocity_analysis = self.ai_engine.analyze_deal_velocity(opp_data)
            
            current_velocity = velocity_analysis['current_velocity']
            total_velocity += current_velocity
            velocity_count += 1
            
            # Categorize deals by velocity
            if velocity_analysis['velocity_trend'] == 'ACCELERATING':
                velocity_data['fast_moving_deals'].append({
                    'opportunity_id': opp.id,
                    'name': opp.name,
                    'velocity': current_velocity,
                    'acceleration_factors': velocity_analysis.get('acceleration_opportunities', [])
                })
            elif velocity_analysis['velocity_trend'] == 'DECELERATING':
                velocity_data['stalled_deals'].append({
                    'opportunity_id': opp.id,
                    'name': opp.name,
                    'velocity': current_velocity,
                    'bottlenecks': velocity_analysis.get('bottlenecks', [])
                })
            
            # Velocity by stage
            stage_name = opp.stage.name if opp.stage else 'Unknown'
            if stage_name not in velocity_data['velocity_by_stage']:
                velocity_data['velocity_by_stage'][stage_name] = []
            velocity_data['velocity_by_stage'][stage_name].append(current_velocity)
        
        # Calculate averages
        velocity_data['average_velocity'] = total_velocity / velocity_count if velocity_count > 0 else 0
        
        for stage, velocities in velocity_data['velocity_by_stage'].items():
            velocity_data['velocity_by_stage'][stage] = {
                'average': statistics.mean(velocities),
                'median': statistics.median(velocities),
                'count': len(velocities)
            }
        
        return velocity_data
    
    # Helper methods continue...
    def _determine_next_best_action(self, o
        """Determine the next best action for the opportunity"""
        if win_probability > 0.8:
            return "PREPARE_PROPOSAL"
        elif win_probability > 0.6:
            return "SCHEDULE_DECISION_MAKER_MEETING"
        elif win_probability > 0.4:
            return "CONDUCT_NEEDS_ANALYSIS"
        elif opp_data.get('days_since_last_activity', 0) > 14:
            return "RE_ENGAGE_STAKEHOLDERS"
        else:
            return "QUALIFY_OPPORTUNITY"