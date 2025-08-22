# ============================================================================
# backend/apps/crm/services/opportunity_service.py - Opportunity Management Service
# ============================================================================

from typing import Dict, List, Optional, Any
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal

from .base import BaseService, CacheableMixin, NotificationMixin, CRMServiceException
from ..models import Opportunity, Pipeline, PipelineStage, OpportunityProduct


class OpportunityService(BaseService, CacheableMixin, NotificationMixin):
    """Comprehensive opportunity management service"""
    
    @transaction.atomic
    def create_ Dict) -> Opportunity:
        """Create new opportunity with validation"""
        self.require_permission('can_create_opportunities')
        
        # Validate required fields
        required_fields = ['name', 'account', 'amount', 'close_date', 'pipeline', 'stage']
        self.validate_data(opportunity_data, required_fields)
        
        # Set defaults
        opportunity_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
            'updated_by': self.user,
        })
        
        # Set default owner if not provided
        if not opportunity_data.get('owner'):
            opportunity_data['owner'] = self.user
        
        # Get stage and set probability
        stage = opportunity_data['stage']
        if isinstance(stage, int):
            stage = PipelineStage.objects.get(id=stage)
        
        opportunity_data['probability'] = stage.probability
        
        opportunity = Opportunity.objects.create(**opportunity_data)
        
        # Initialize stage history
        opportunity.update_stage_history(None, stage)
        
        # Update account metrics
        self._update_account_metrics(opportunity.account)
        
        # Create audit trail
        self.create_audit_trail('CREATE', opportunity)
        
        # Send notifications
        if opportunity.owner and opportunity.owner != self.user:
            self.send_notification(
                [opportunity.owner],
                f"New Opportunity Assigned: {opportunity.name}",
                f"A new opportunity has been assigned to you: {opportunity.name} - ${opportunity.amount}"
            )
        
        self.logger.info(f"Opportunity created: {opportunity.opportunity_number}")
        return opportunity
    
    @transaction.atomic
    def update_opportunity_stage(self, opportunity_id: int, new_stage_id: int, 
                                None) -> Opportunity:
        """Update opportunity stage with progression tracking"""
        opportunity = self.get_queryset(Opportunity).get(id=opportunity_id)
        
        if not self.check_permission('can_edit_all_opportunities') and opportunity.owner != self.user:
            raise PermissionDenied("Cannot edit opportunities not owned by you")
        
        old_stage = opportunity.stage
        new_stage = PipelineStage.objects.get(id=new_stage_id)
        
        # Validate stage progression
        if new_stage.pipeline != opportunity.pipeline:
            raise CRMServiceException("Stage must belong to the same pipeline")
        
        # Update opportunity
        opportunity.stage = new_stage
        opportunity.probability = new_stage.probability
        opportunity.stage_changed_date = timezone.now()
        opportunity.updated_by = self.user
        
        # Apply
            for field, value in update_data.items():
                if hasattr(opportunity, field):
                    setattr(opportunity, field, value)
        
        # Check if closing
        if new_stage.is_closed:
            opportunity.is_closed = True
            opportunity.closed_date = timezone.now()
            opportunity.is_won = new_stage.is_won
            
            if not opportunity.is_won and not opportunity.lost_reason:
                opportunity.lost_reason = update_data.get('lost_reason', 'Not specified')
        
        opportunity.save()
        
        # Update stage history
        opportunity.update_stage_history(old_stage, new_stage)
        
        # Update pipeline metrics
        self._update_pipeline_metrics(opportunity.pipeline)
        
        # Update account metrics
        self._update_account_metrics(opportunity.account)
        
        # Create audit trail
        changes = {
            'stage': {'old': old_stage.name, 'new': new_stage.name},
            'probability': {'old': old_stage.probability, 'new': new_stage.probability}
        }
        self.create_audit_trail('UPDATE', opportunity, changes)
        
        # Send stage change notifications
        self._send_stage_change_notifications(opportunity, old_stage, new_stage)
        
        return opportunity
    
    def add_opportunity_products(self, opportunity_id: int[OpportunityProduct]:
        """Add products to opportunity"""
        opportunity = self.get_queryset(Opportunity).get(id=opportunity_id)
        
        if not self.check_permission('can_edit_all_opportunities') and opportunity.owner != self.user:
            raise PermissionDenied("Cannot edit opportunities not owned by you")
        
        products = []
        total_amount = Decimal('0.00')
        
        with transaction.atomic():
            for product
                product_data.update({
                    'tenant': self.tenant,
                    'opportunity': opportunity,
                    'created_by': self.user,
                })
                
                product = OpportunityProduct.objects.create(**product_data)
                products.append(product)
                total_amount += product.total_price
            
            # Update opportunity amount
            opportunity.amount = total_amount
            opportunity.expected_revenue = (total_amount * opportunity.probability) / 100
            opportunity.save()
        
        self.logger.info(f"Added {len(products)} products to opportunity {opportunity.opportunity_number}")
        return products
    
    def forecast_opportunities(self, filters: Dict = None) -> Dict:
        """Generate opportunity forecast"""
        queryset = self.get_queryset(Opportunity).filter(is_closed=False)
        
        # Apply filters
        if filters:
            if filters.get('owner'):
                queryset = queryset.filter(owner=filters['owner'])
            if filters.get('territory'):
                queryset = queryset.filter(territory=filters['territory'])
            if filters.get('close_date_from'):
                queryset = queryset.filter(close_date__gte=filters['close_date_from'])
            if filters.get('close_date_to'):
                queryset = queryset.filter(close_date__lte=filters['close_date_to'])
        
        # Calculate forecast metrics
        total_opportunities = queryset.count()
        total_pipeline_value = queryset.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        weighted_pipeline = queryset.aggregate(
            weighted=models.Sum(
                models.F('amount') * models.F('probability') / 100.0,
                output_field=models.DecimalField(max_digits=15, decimal_places=2)
            )
        )['weighted'] or Decimal('0.00')
        
        # Stage breakdown
        stage_forecast = queryset.values(
            'stage__name', 'stage__probability'
        ).annotate(
            count=models.Count('id'),
            total_amount=models.Sum('amount'),
            weighted_amount=models.Sum(
                models.F('amount') * models.F('probability') / 100.0,
                output_field=models.DecimalField(max_digits=15, decimal_places=2)
            )
        )
        
        # Monthly forecast
        monthly_forecast = queryset.extra(
            select={'month': 'EXTRACT(month FROM close_date)'}
        ).values('month').annotate(
            count=models.Count('id'),
            total_amount=models.Sum('amount'),
            weighted_amount=models.Sum(
                models.F('amount') * models.F('probability') / 100.0,
                output_field=models.DecimalField(max_digits=15, decimal_places=2)
            )
        )
        
        # Owner forecast
        owner_forecast = queryset.values(
            'owner__first_name', 'owner__last_name'
        ).annotate(
            count=models.Count('id'),
            total_amount=models.Sum('amount'),
            weighted_amount=models.Sum(
                models.F('amount') * models.F('probability') / 100.0,
                output_field=models.DecimalField(max_digits=15, decimal_places=2)
            )
        )
        
        return {
            'summary': {
                'total_opportunities': total_opportunities,
                'total_pipeline_value': total_pipeline_value,
                'weighted_pipeline': weighted_pipeline,
                'average_deal_size': total_pipeline_value / total_opportunities if total_opportunities > 0 else 0,
            },
            'by_stage': list(stage_forecast),
            'by_month': list(monthly_forecast),
            'by_owner': list(owner_forecast),
        }
    
    def get_pipeline_analytics(self, pipeline_id: int, filters: Dict = None) -> Dict:
        """Get comprehensive pipeline analytics"""
        pipeline = Pipeline.objects.get(id=pipeline_id, tenant=self.tenant)
        queryset = self.get_queryset(Opportunity).filter(pipeline=pipeline)
        
        # Apply filters
        if filters:
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        # Stage analysis
        stage_analysis = []
        for stage in pipeline.stages.all():
            stage_opps = queryset.filter(stage=stage)
            won_opps = queryset.filter(stage=stage, is_won=True)
            
            stage_analysis.append({
                'stage_name': stage.name,
                'total_opportunities': stage_opps.count(),
                'total_value': stage_opps.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00'),
                'won_opportunities': won_opps.count(),
                'won_value': won_opps.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00'),
                'conversion_rate': self._calculate_stage_conversion_rate(stage, queryset),
                'average_time_in_stage': self._calculate_average_time_in_stage(stage, queryset),
            })
        
        # Velocity metrics
        velocity_metrics = self._calculate_pipeline_velocity(pipeline, queryset)
        
        # Win/Loss analysis
        closed_opps = queryset.filter(is_closed=True)
        win_loss_analysis = {
            'total_closed': closed_opps.count(),
            'won': closed_opps.filter(is_won=True).count(),
            'lost': closed_opps.filter(is_won=False).count(),
            'win_rate': closed_opps.filter(is_won=True).count() / closed_opps.count() * 100 if closed_opps.count() > 0 else 0,
            'average_deal_size': closed_opps.aggregate(avg=models.Avg('amount'))['avg'] or Decimal('0.00'),
        }
        
        return {
            'pipeline': {
                'name': pipeline.name,
                'total_opportunities': queryset.count(),
                'total_value': queryset.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00'),
            },
            'stages': stage_analysis,
            'velocity': velocity_metrics,
            'win_loss': win_loss_analysis,
        }
    
    def _update_pipeline_metrics(self, pipeline: Pipeline):
        """Update pipeline performance metrics"""
        opportunities = Opportunity.objects.filter(pipeline=pipeline, tenant=self.tenant)
        
        pipeline.total_opportunities = opportunities.count()
        pipeline.total_value = opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        won_opportunities = opportunities.filter(is_won=True)
        if won_opportunities.exists():
            pipeline.average_deal_size = won_opportunities.aggregate(
                avg=models.Avg('amount')
            )['avg'] or Decimal('0.00')
            
            pipeline.win_rate = (won_opportunities.count() / opportunities.count()) * 100
        
        pipeline.save()
    
    def _update_account_metrics(self, account):
        """Update account opportunity metrics"""
        opportunities = account.opportunities.all()
        
        account.total_opportunities = opportunities.count()
        account.total_won_opportunities = opportunities.filter(is_won=True).count()
        account.total_revenue = opportunities.filter(is_won=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        if account.total_won_opportunities > 0:
            account.average_deal_size = account.total_revenue / account.total_won_opportunities
        
        account.save()
    
    def _send_stage_change_notifications(self, opportunity, old_stage, new_stage):
        """Send notifications for stage changes"""
        # Notify owner
        if opportunity.owner:
            self.send_notification(
                [opportunity.owner],
                f"Opportunity Stage Changed: {opportunity.name}",
                f"Opportunity {opportunity.name} moved from {old_stage.name} to {new_stage.name}"
            )
        
        # Notify team members
        team_members = opportunity.team_members.all()
        if team_members:
            self.send_notification(
                list(team_members),
                f"Team Opportunity Updated: {opportunity.name}",
                f"Opportunity {opportunity.name} moved to {new_stage.name}"
            )
        
        # Special notifications for won/lost
        if new_stage.is_closed:
            status = "WON" if new_stage.is_won else "LOST"
            self.send_notification(
                [opportunity.owner] if opportunity.owner else [],
                f"Opportunity {status}: {opportunity.name}",
                f"Opportunity {opportunity.name} has been {status} with value ${opportunity.amount}"
            )
    
    def _calculate_stage_conversion_rate(self, stage, queryset):
        """Calculate conversion rate for a specific stage"""
        # Implementation for stage conversion calculation
        return 0.0
    
    def _calculate_average_time_in_stage(self, stage, queryset):
        """Calculate average time spent in a specific stage"""
        # Implementation for time in stage calculation
        return 0
    
    def _calculate_pipeline_velocity(self, pipeline, queryset):
        """Calculate pipeline velocity metrics"""
        # Implementation for velocity calculation
        return {
            'average_sales_cycle': 0,
            'velocity_score': 0,
            'bottleneck_stages': [],
        }