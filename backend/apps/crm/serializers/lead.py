# ============================================================================
# backend/apps/crm/serializers/lead.py - Lead Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from ..models import LeadSource, Lead, LeadScoringRule
from .user import UserBasicSerializer
from .account import IndustrySerializer


class LeadSourceSerializer(serializers.ModelSerializer):
    """Lead source serializer with performance metrics"""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    default_assignee_name = serializers.CharField(source='default_assignee.get_full_name', read_only=True)
    
    # Performance metrics
    conversion_rate = serializers.ReadOnlyField()
    roi = serializers.ReadOnlyField()
    cost_per_lead = serializers.ReadOnlyField()
    
    class Meta:
        model = LeadSource
        fields = [
            'id', 'name', 'source_type', 'description', 'campaign', 'campaign_name',
            'total_leads', 'converted_leads', 'total_revenue', 'cost',
            'conversion_rate', 'roi', 'cost_per_lead',
            'is_active', 'auto_assignment_enabled', 'default_assignee',
            'default_assignee_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'campaign_name', 'default_assignee_name', 'total_leads',
            'converted_leads', 'total_revenue', 'conversion_rate', 'roi',
            'cost_per_lead', 'created_at', 'updated_at'
        ]
    
    def validate_cost(self, value):
        """Validate cost"""
        if value < 0:
            raise serializers.ValidationError("Cost cannot be negative")
        return value


class LeadScoringRuleSerializer(serializers.ModelSerializer):
    """Lead scoring rule serializer"""
    
    impact_description = serializers.SerializerMethodField()
    
    class Meta:
        model = LeadScoringRule
        fields = [
            'id', 'name', 'description', 'rule_type', 'field_name',
            'operator', 'value', 'score_change', 'impact_description',
            'is_active', 'priority', 'times_applied', 'last_applied',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'impact_description', 'times_applied', 'last_applied',
            'created_at', 'updated_at'
        ]
    
    def get_impact_description(self, obj):
        """Get description of rule impact"""
        if obj.score_change > 0:
            return f"Adds {obj.score_change} points"
        elif obj.score_change < 0:
            return f"Subtracts {abs(obj.score_change)} points"
        return "No score change"
    
    def validate_score_change(self, value):
        """Validate score change"""
        if not -100 <= value <= 100:
            raise serializers.ValidationError("Score change must be between -100 and 100")
        return value


class LeadSerializer(serializers.ModelSerializer):
    """Comprehensive lead serializer"""
    
    industry_details = IndustrySerializer(source='industry', read_only=True)
    source_details = LeadSourceSerializer(source='source', read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    # Calculated fields
    full_name = serializers.ReadOnlyField()
    days_since_created = serializers.ReadOnlyField()
    days_since_last_activity = serializers.ReadOnlyField()
    score_status = serializers.SerializerMethodField()
    qualification_status = serializers.SerializerMethodField()
    
    # Conversion tracking
    converted_account_name = serializers.CharField(source='converted_account.name', read_only=True)
    converted_contact_name = serializers.CharField(source='converted_contact.display_name', read_only=True)
    converted_opportunity_name = serializers.CharField(source='converted_opportunity.name', read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'lead_number',
            # Personal info
            'salutation', 'first_name', 'last_name', 'full_name', 'email', 'phone', 'mobile',
            # Company info
            'company', 'job_title', 'industry', 'industry_details', 'company_size',
            'annual_revenue', 'website',
            # Lead management
            'status', 'rating', 'source', 'source_details', 'owner', 'owner_details',
            'assigned_date',
            # Scoring
            'score', 'last_score_update', 'score_breakdown', 'score_status',
            # Qualification
            'budget', 'timeframe', 'decision_maker', 'qualification_status',
            # Preferences
            'preferred_contact_method', 'do_not_call', 'do_not_email',
            # Address
            'address',
            # Social media
            'linkedin_url', 'twitter_handle',
            # Conversion tracking
            'converted_account', 'converted_account_name', 'converted_contact',
            'converted_contact_name', 'converted_opportunity', 'converted_opportunity_name',
            'converted_date',
            # Activity tracking
            'last_activity_date', 'next_follow_up_date', 'total_activities',
            'days_since_created', 'days_since_last_activity',
            # Campaign
            'campaign', 'campaign_name',
            # Additional
            'description', 'tags', 'custom_fields',
            # Duplicate detection
            'duplicate_of', 'is_duplicate',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'lead_number', 'full_name', 'industry_details', 'source_details',
            'owner_details', 'campaign_name', 'last_score_update', 'score_breakdown',
            'score_status', 'qualification_status', 'converted_account_name',
            'converted_contact_name', 'converted_opportunity_name', 'total_activities',
            'days_since_created', 'days_since_last_activity', 'created_at', 'updated_at'
        ]
    
    def get_score_status(self, obj):
        """Get lead score status"""
        if obj.score >= 80:
            return 'Hot'
        elif obj.score >= 50:
            return 'Warm'
        else:
            return 'Cold'
    
    def get_qualification_status(self, obj):
        """Get qualification status based on BANT criteria"""
        criteria_met = 0
        
        if obj.budget:
            criteria_met += 1
        if obj.decision_maker:
            criteria_met += 1
        if obj.timeframe:
            criteria_met += 1
        # Authority is implied by decision_maker
        # Need is implied by lead existence
        
        if criteria_met >= 3:
            return 'Highly Qualified'
        elif criteria_met >= 2:
            return 'Qualified'
        elif criteria_met >= 1:
            return 'Partially Qualified'
        else:
            return 'Not Qualified'
    
    def validate_email(self, value):
        """Validate email uniqueness within tenant"""
        if self.instance:
            if Lead.objects.filter(
                tenant=self.context['request'].user.tenant,
                email=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Email already exists for another lead")
        else:
            if Lead.objects.filter(
                tenant=self.context['request'].user.tenant,
                email=value
            ).exists():
                raise serializers.ValidationError("Email already exists for another lead")
        return value
    
    def validate_score(self, value):
        """Validate lead score"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value
    
    def validate_annual_revenue(self, value):
        """Validate annual revenue"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Annual revenue cannot be negative")
        return value


class LeadDetailSerializer(LeadSerializer):
    """Detailed lead serializer with activity history"""
    
    recent_activities = serializers.SerializerMethodField()
    scoring_history = serializers.SerializerMethodField()
    duplicate_leads = serializers.SerializerMethodField()
    
    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + [
            'recent_activities', 'scoring_history', 'duplicate_leads'
        ]
    
    def get_recent_activities(self, obj):
        """Get recent activities"""
        # This would need to be implemented based on your activity tracking
        return []
    
    def get_scoring_history(self, obj):
        """Get scoring history"""
        if obj.score_breakdown:
            return obj.score_breakdown
        return {}
    
    def get_duplicate_leads(self, obj):
        """Get potential duplicate leads"""
        duplicates = obj.duplicates.filter(is_active=True)
        return [
            {
                'id': dup.id,
                'name': dup.full_name,
                'email': dup.email,
                'company': dup.company,
                'created_at': dup.created_at
            }
            for dup in duplicates
        ]


class LeadConversionSerializer(serializers.Serializer):
    """Serializer for lead conversion process"""
    
    create_account = serializers.BooleanField(default=True)
    create_contact = serializers.BooleanField(default=True)
    create_opportunity = serializers.BooleanField(default=False)
    
    # Account creation data
    account_name = serializers.CharField(max_length=255, required=False)
    account_type = serializers.ChoiceField(
        choices=[
            ('PROSPECT', 'Prospect'),
            ('CUSTOMER', 'Customer'),
            ('PARTNER', 'Partner'),
        ],
        default='PROSPECT'
    )
    
    # Opportunity creation data
    opportunity_name = serializers.CharField(max_length=255, required=False)
    opportunity_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False
    )
    opportunity_close_date = serializers.DateField(required=False)
    
    def validate(self, data):
        """Validate conversion data"""
        if data.get('create_opportunity'):
            if not data.get('opportunity_name'):
                raise serializers.ValidationError({
                    'opportunity_name': 'Required when creating opportunity'
                })
            if not data.get('opportunity_amount'):
                raise serializers.ValidationError({
                    'opportunity_amount': 'Required when creating opportunity'
                })
            if not data.get('opportunity_close_date'):
                raise serializers.ValidationError({
                    'opportunity_close_date': 'Required when creating opportunity'
                })
        
        return data


class LeadBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk lead updates"""
    
    lead_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    # Fields that can be bulk updated
    status = serializers.ChoiceField(
        choices=Lead.LEAD_STATUS,
        required=False
    )
    rating = serializers.ChoiceField(
        choices=Lead.LEAD_RATINGS,
        required=False
    )
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    source = serializers.PrimaryKeyRelatedField(
        queryset=LeadSource.objects.all(),
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_lead_ids(self, value):
        """Validate lead IDs exist and belong to tenant"""
        tenant = self.context['request'].user.tenant
        existing_leads = Lead.objects.filter(
            tenant=tenant,
            id__in=value,
            is_active=True
        ).count()
        
        if existing_leads != len(value):
            raise serializers.ValidationError("Some lead IDs are invalid")
        
        return value