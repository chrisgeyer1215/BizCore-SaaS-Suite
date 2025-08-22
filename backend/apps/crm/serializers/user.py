# ============================================================================
# backend/apps/crm/serializers/user.py - User Management Serializers
# ============================================================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import CRMRole, CRMUserProfile

User = get_user_model()


class CRMRoleSerializer(serializers.ModelSerializer):
    """CRM Role serializer with permission details"""
    
    permissions_summary = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CRMRole
        fields = [
            'id', 'name', 'display_name', 'description', 'is_system_role',
            # Lead permissions
            'can_view_all_leads', 'can_edit_all_leads', 'can_delete_leads',
            'can_assign_leads', 'can_convert_leads', 'can_import_leads', 'can_export_leads',
            # Account permissions
            'can_view_all_accounts', 'can_edit_all_accounts', 'can_delete_accounts',
            'can_manage_contacts',
            # Opportunity permissions
            'can_view_all_opportunities', 'can_edit_all_opportunities', 
            'can_delete_opportunities', 'can_manage_pipeline', 'can_view_forecasts',
            # Campaign permissions
            'can_manage_campaigns', 'can_send_emails', 'can_view_campaign_analytics',
            # Service permissions
            'can_manage_tickets', 'can_view_all_tickets', 'can_escalate_tickets',
            # Reporting permissions
            'can_view_reports', 'can_create_reports', 'can_view_dashboards',
            'can_manage_dashboards',
            # Admin permissions
            'can_manage_settings', 'can_manage_users', 'can_manage_roles',
            'can_manage_territories', 'can_manage_workflows',
            # Data permissions
            'can_import_data', 'can_export_data', 'can_delete_data',
            'can_view_audit_trail',
            # Integration permissions
            'can_manage_integrations', 'can_access_api',
            'custom_permissions', 'permissions_summary', 'users_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'permissions_summary', 'users_count', 'created_at', 'updated_at')
    
    def get_permissions_summary(self, obj):
        """Get summary of key permissions"""
        permissions = []
        if obj.can_manage_settings:
            permissions.append('Admin')
        if obj.can_view_all_leads:
            permissions.append('All Leads')
        if obj.can_view_all_accounts:
            permissions.append('All Accounts')
        if obj.can_view_all_opportunities:
            permissions.append('All Opportunities')
        return permissions
    
    def get_users_count(self, obj):
        """Get count of users with this role"""
        return obj.users.filter(is_active=True).count()
    
    def validate_name(self, value):
        """Validate role name uniqueness within tenant"""
        if self.instance:
            if CRMRole.objects.filter(
                tenant=self.context['request'].user.tenant,
                name=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Role name must be unique within tenant")
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for nested relationships"""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'avatar_url']
        read_only_fields = ['id', 'full_name', 'avatar_url']
    
    def get_avatar_url(self, obj):
        """Get avatar URL if available"""
        # Implement based on your user avatar system
        return None


class CRMUserProfileSerializer(serializers.ModelSerializer):
    """CRM User Profile serializer with performance metrics"""
    
    user = UserBasicSerializer(read_only=True)
    crm_role_details = CRMRoleSerializer(source='crm_role', read_only=True)
    manager_details = UserBasicSerializer(source='manager', read_only=True)
    territory_name = serializers.CharField(source='territory.name', read_only=True)
    
    # Performance metrics
    lead_conversion_percentage = serializers.ReadOnlyField()
    quota_achievement_percentage = serializers.ReadOnlyField()
    performance_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = CRMUserProfile
        fields = [
            'id', 'user', 'crm_role', 'crm_role_details', 'profile_type',
            'employee_id', 'department', 'job_title', 'manager', 'manager_details',
            'phone_number', 'mobile_number', 'extension', 'emergency_contact',
            'emergency_phone', 'office_location', 'territory', 'territory_name',
            'time_zone', 'sales_quota', 'commission_rate',
            # Performance metrics
            'total_leads_assigned', 'total_leads_converted', 'total_opportunities_won',
            'total_revenue_generated', 'average_deal_size', 'conversion_rate',
            'lead_conversion_percentage', 'quota_achievement_percentage',
            'performance_rating',
            # Activity metrics
            'total_activities_logged', 'total_emails_sent', 'total_calls_made',
            'total_meetings_held',
            # Preferences
            'default_dashboard', 'notification_preferences', 'ui_preferences',
            # Social
            'linkedin_profile', 'twitter_handle', 'bio',
            # Targets
            'monthly_target', 'quarterly_target', 'annual_target',
            'is_active', 'last_login_crm', 'login_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'crm_role_details', 'manager_details', 'territory_name',
            'total_leads_assigned', 'total_leads_converted', 'total_opportunities_won',
            'total_revenue_generated', 'average_deal_size', 'conversion_rate',
            'lead_conversion_percentage', 'quota_achievement_percentage',
            'performance_rating', 'total_activities_logged', 'total_emails_sent',
            'total_calls_made', 'total_meetings_held', 'last_login_crm',
            'login_count', 'created_at', 'updated_at'
        ]
    
    def get_performance_rating(self, obj):
        """Calculate performance rating"""
        quota_achievement = obj.quota_achievement_percentage
        conversion_rate = obj.lead_conversion_percentage
        
        if quota_achievement >= 100 and conversion_rate >= 20:
            return 'Excellent'
        elif quota_achievement >= 80 and conversion_rate >= 15:
            return 'Good'
        elif quota_achievement >= 60 and conversion_rate >= 10:
            return 'Average'
        else:
            return 'Needs Improvement'
    
    def validate_sales_quota(self, value):
        """Validate sales quota"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Sales quota cannot be negative")
        return value
    
    def validate_commission_rate(self, value):
        """Validate commission rate"""
        if value is not None and not 0 <= value <= 100:
            raise serializers.ValidationError("Commission rate must be between 0 and 100")
        return value