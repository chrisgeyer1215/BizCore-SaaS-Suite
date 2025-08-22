# ============================================================================
# backend/apps/crm/serializers/opportunity.py - Opportunity Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from ..models import Pipeline, PipelineStage, Opportunity, OpportunityTeamMember, OpportunityProduct
from .user import UserBasicSerializer
from .account import AccountSerializer, ContactBasicSerializer


class PipelineStageSerializer(serializers.ModelSerializer):
    """Pipeline stage serializer with conversion metrics"""
    
    conversion_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = PipelineStage
        fields = [
            'id', 'name', 'description', 'stage_type', 'sort_order', 'probability',
            'is_closed', 'is_won', 'required_fields', 'required_activities',
            'auto_actions', 'total_opportunities', 'average_time_in_stage',
            'conversion_rate', 'conversion_metrics',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_opportunities', 'average_time_in_stage', 'conversion_rate',
            'conversion_metrics', 'created_at', 'updated_at'
        ]
    
    def get_conversion_metrics(self, obj):
        """Get detailed conversion metrics"""
        return {
            'total_opportunities': obj.total_opportunities,
            'average_time_days': obj.average_time_in_stage,
            'conversion_rate': float(obj.conversion_rate),
            'won_from_stage': obj.opportunities.filter(is_won=True).count(),
            'lost_from_stage': obj.opportunities.filter(is_closed=True, is_won=False).count()
        }


class PipelineSerializer(serializers.ModelSerializer):
    """Pipeline serializer with stages and metrics"""
    
    stages = PipelineStageSerializer(many=True, read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    performance_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = Pipeline
        fields = [
            'id', 'name', 'description', 'pipeline_type', 'is_default', 'is_active',
            'stages', 'owner', 'owner_details',
            # Performance metrics
            'total_opportunities', 'total_value', 'average_deal_size',
            'average_sales_cycle', 'win_rate', 'performance_metrics',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'stages', 'owner_details', 'total_opportunities', 'total_value',
            'average_deal_size', 'average_sales_cycle', 'win_rate',
            'performance_metrics', 'created_at', 'updated_at'
        ]
    
    def get_performance_metrics(self, obj):
        """Get comprehensive performance metrics"""
        return {
            'pipeline_velocity': float(obj.total_value / max(obj.average_sales_cycle, 1)),
            'conversion_funnel': self._get_conversion_funnel(obj),
            'monthly_trends': self._get_monthly_trends(obj)
        }
    
    def _get_conversion_funnel(self, obj):
        """Get conversion funnel data"""
        stages_data = []
        for stage in obj.stages.all().order_by('sort_order'):
            stages_data.append({
                'stage_name': stage.name,
                'opportunity_count': stage.total_opportunities,
                'total_value': float(stage.opportunities.aggregate(
                    total=models.Sum('amount')
                )['total'] or 0),
                'conversion_rate': float(stage.conversion_rate)
            })
        return stages_data
    
    def _get_monthly_trends(self, obj):
        """Get monthly trend data"""
        # This would calculate monthly metrics for the pipeline
        return []


class OpportunityTeamMemberSerializer(serializers.ModelSerializer):
    """Opportunity team member serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    
    class Meta:
        model = OpportunityTeamMember
        fields = [
            'id', 'user', 'user_details', 'role', 'can_edit', 'can_view_financials',
            'assigned_date'
        ]
        read_only_fields = ['id', 'user_details', 'assigned_date']


class OpportunityProductSerializer(serializers.ModelSerializer):
    """Opportunity product line item serializer"""
    
    net_unit_price = serializers.ReadOnlyField()
    line_total = serializers.SerializerMethodField()
    
    class Meta:
        model = OpportunityProduct
        fields = [
            'id', 'product_name', 'product_code', 'product_id', 'quantity',
            'unit_price', 'discount_percent', 'discount_amount', 'total_price',
            'net_unit_price', 'line_total', 'description', 'product_category',
            'revenue_type', 'recurring_frequency', 'delivery_date',
            'service_start_date', 'service_end_date', 'line_number'
        ]
        read_only_fields = ['id', 'net_unit_price', 'line_total']
    
    def get_line_total(self, obj):
        """Get line total (alias for total_price)"""
        return obj.total_price
    
    def validate_quantity(self, value):
        """Validate quantity"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value
    
    def validate_unit_price(self, value):
        """Validate unit price"""
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value


class OpportunitySerializer(serializers.ModelSerializer):
    """Comprehensive opportunity serializer"""
    
    account_details = serializers.SerializerMethodField()
    primary_contact_details = ContactBasicSerializer(source='primary_contact', read_only=True)
    pipeline_details = PipelineSerializer(source='pipeline', read_only=True)
    stage_details = PipelineStageSerializer(source='stage', read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    territory_name = serializers.CharField(source='territory.name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    original_lead_name = serializers.CharField(source='original_lead.full_name', read_only=True)
    
    # Team and products
    team_members = OpportunityTeamMemberSerializer(source='team_memberships', many=True, read_only=True)
    products = OpportunityProductSerializer(many=True, read_only=True)
    
    # Calculated fields
    days_in_current_stage = serializers.SerializerMethodField()
    probability_adjusted_value = serializers.SerializerMethodField()
    stage_progression = serializers.SerializerMethodField()
    competitive_situation = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'opportunity_number', 'name', 'description', 'opportunity_type',
            # Account and contact
            'account', 'account_details', 'primary_contact', 'primary_contact_details',
            # Pipeline and stage
            'pipeline', 'pipeline_details', 'stage', 'stage_details',
            # Financial
            'amount', 'probability', 'expected_revenue', 'probability_adjusted_value',
            # Dates
            'close_date', 'created_date', 'stage_changed_date', 'days_in_current_stage',
            # Ownership
            'owner', 'owner_details', 'team_members',
            # Source and campaign
            'lead_source', 'campaign', 'campaign_name', 'original_lead', 'original_lead_name',
            # Competition
            'competitors', 'competitive_analysis', 'competitive_situation',
            # Status
            'is_closed', 'is_won', 'closed_date', 'lost_reason',
            # Sales cycle
            'days_in_pipeline', 'stage_history', 'stage_progression',
            # Territory
            'territory', 'territory_name',
            # Planning
            'next_step', 'next_step_date',
            # Integration
            'finance_quote_id', 'finance_invoice_id',
            # Products
            'products',
            # Additional
            'tags', 'custom_fields',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'opportunity_number', 'account_details', 'primary_contact_details',
            'pipeline_details', 'stage_details', 'owner_details', 'territory_name',
            'campaign_name', 'original_lead_name', 'team_members', 'products',
            'expected_revenue', 'probability_adjusted_value', 'created_date',
            'stage_changed_date', 'days_in_current_stage', 'days_in_pipeline',
            'stage_history', 'stage_progression', 'competitive_situation',
            'created_at', 'updated_at'
        ]
    
    def get_account_details(self, obj):
        """Get basic account details"""
        return {
            'id': obj.account.id,
            'name': obj.account.name,
            'account_type': obj.account.account_type,
            'industry': obj.account.industry.name if obj.account.industry else None
        }
    
    def get_days_in_current_stage(self, obj):
        """Calculate days in current stage"""
        if obj.stage_changed_date:
            from django.utils import timezone
            return (timezone.now() - obj.stage_changed_date).days
        return (timezone.now().date() - obj.created_date).days
    
    def get_probability_adjusted_value(self, obj):
        """Get probability-adjusted value"""
        return obj.amount * (obj.probability / 100)
    
    def get_stage_progression(self, obj):
        """Get stage progression analysis"""
        if obj.stage_history:
            return {
                'total_stages': len(obj.stage_history),
                'current_stage_duration': self.get_days_in_current_stage(obj),
                'average_stage_duration': sum([
                    stage.get('days_in_stage', 0) for stage in obj.stage_history
                ]) / len(obj.stage_history) if obj.stage_history else 0,
                'progression_velocity': 'Fast' if self.get_days_in_current_stage(obj) < 30 else 'Slow'
            }
        return None
    
    def get_competitive_situation(self, obj):
        """Analyze competitive situation"""
        competitor_count = len(obj.competitors) if obj.competitors else 0
        return {
            'competitor_count': competitor_count,
            'competitive_intensity': 'High' if competitor_count > 2 else 'Medium' if competitor_count > 0 else 'Low',
            'has_analysis': bool(obj.competitive_analysis)
        }
    
    def validate_amount(self, value):
        """Validate opportunity amount"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value
    
    def validate_probability(self, value):
        """Validate probability"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Probability must be between 0 and 100")
        return value
    
    def validate(self, data):
        """Validate opportunity data"""
        # Ensure stage belongs to pipeline
        pipeline = data.get('pipeline')
        stage = data.get('stage')
        
        if pipeline and stage:
            if stage.pipeline != pipeline:
                raise serializers.ValidationError({
                    'stage': 'Stage must belong to the selected pipeline'
                })
        
        # Validate close date
        close_date = data.get('close_date')
        if close_date:
            from django.utils import timezone
            if close_date < timezone.now().date():
                raise serializers.ValidationError({
                    'close_date': 'Close date cannot be in the past'
                })
        
        return data


class OpportunityDetailSerializer(OpportunitySerializer):
    """Detailed opportunity serializer with full related data"""
    
    recent_activities = serializers.SerializerMethodField()
    revenue_forecast = serializers.SerializerMethodField()
    win_probability_factors = serializers.SerializerMethodField()
    
    class Meta(OpportunitySerializer.Meta):
        fields = OpportunitySerializer.Meta.fields + [
            'recent_activities', 'revenue_forecast', 'win_probability_factors'
        ]
    
    def get_recent_activities(self, obj):
        """Get recent activities"""
        # This would fetch recent activities related to this opportunity
        return []
    
    def get_revenue_forecast(self, obj):
        """Get revenue forecast data"""
        return {
            'expected_revenue': float(obj.expected_revenue),
            'best_case': float(obj.amount),
            'worst_case': float(obj.amount * Decimal('0.5')),  # 50% worst case
            'forecast_confidence': 'High' if obj.probability > 75 else 'Medium' if obj.probability > 50 else 'Low'
        }
    
    def get_win_probability_factors(self, obj):
        """Analyze factors affecting win probability"""
        factors = {
            'positive': [],
            'negative': [],
            'neutral': []
        }
        
        # Analyze various factors
        if obj.primary_contact and obj.primary_contact.is_decision_maker:
            factors['positive'].append('Has decision maker contact')
        
        if obj.competitors:
            factors['negative'].append(f'Facing {len(obj.competitors)} competitors')
        
        if obj.days_in_pipeline > 90:
            factors['negative'].append('Long sales cycle')
        elif obj.days_in_pipeline < 30:
            factors['positive'].append('Fast-moving opportunity')
        
        return factors


class OpportunityCloseSerializer(serializers.Serializer):
    """Serializer for closing opportunities"""
    
    is_won = serializers.BooleanField()
    close_date = serializers.DateField(required=False)
    lost_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    close_notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate close data"""
        if not data.get('is_won') and not data.get('lost_reason'):
            raise serializers.ValidationError({
                'lost_reason': 'Lost reason is required when marking opportunity as lost'
            })
        
        close_date = data.get('close_date')
        if close_date:
            from django.utils import timezone
            if close_date > timezone.now().date():
                raise serializers.ValidationError({
                    'close_date': 'Close date cannot be in the future'
                })
        
        return data


class OpportunityBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk opportunity updates"""
    
    opportunity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    # Fields that can be bulk updated
    stage = serializers.PrimaryKeyRelatedField(
        queryset=PipelineStage.objects.all(),
        required=False
    )
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    probability = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_opportunity_ids(self, value):
        """Validate opportunity IDs"""
        tenant = self.context['request'].user.tenant
        existing_opps = Opportunity.objects.filter(
            tenant=tenant,
            id__in=value,
            is_active=True,
            is_closed=False
        ).count()
        
        if existing_opps != len(value):
            raise serializers.ValidationError("Some opportunity IDs are invalid or already closed")
        
        return value