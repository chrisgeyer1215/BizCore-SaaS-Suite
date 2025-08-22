# ============================================================================
# backend/apps/crm/serializers/base.py - Base CRM Serializers
# ============================================================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import CRMConfiguration

User = get_user_model()


class CRMConfigurationSerializer(serializers.ModelSerializer):
    """CRM Configuration serializer with nested data"""
    
    company_logo_url = serializers.SerializerMethodField()
    default_pipeline_stages = serializers.JSONField(read_only=True)
    
    class Meta:
        model = CRMConfiguration
        fields = [
            'id', 'company_name', 'company_logo', 'company_logo_url', 
            'website', 'industry', 'lead_auto_assignment', 'lead_assignment_method',
            'lead_scoring_enabled', 'lead_scoring_threshold', 'duplicate_lead_detection',
            'opportunity_auto_number', 'opportunity_probability_tracking', 
            'opportunity_forecast_enabled', 'default_opportunity_stage',
            'default_pipeline_stages', 'stage_probability_mapping',
            'email_integration_enabled', 'email_tracking_enabled',
            'activity_reminders_enabled', 'default_reminder_minutes',
            'campaign_tracking_enabled', 'ticket_auto_assignment',
            'territory_management_enabled', 'timezone', 'currency',
            'date_format', 'time_format', 'language',
            'notification_preferences', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'default_pipeline_stages')
    
    def get_company_logo_url(self, obj):
        """Get full URL for company logo"""
        if obj.company_logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.company_logo.url)
        return None
    
    def validate_lead_scoring_threshold(self, value):
        """Validate lead scoring threshold"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Lead scoring threshold must be between 0 and 100")
        return value