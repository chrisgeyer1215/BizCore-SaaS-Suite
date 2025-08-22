# ============================================================================
# backend/apps/crm/serializers/territory.py - Territory Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from ..models import TerritoryType, Territory, TerritoryAssignment, Team, TeamMembership
from .user import UserBasicSerializer


class TerritoryTypeSerializer(serializers.ModelSerializer):
    """Territory type serializer"""
    
    territories_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TerritoryType
        fields = [
            'id', 'name', 'description', 'color', 'icon', 'is_active',
            'sort_order', 'allow_overlap', 'auto_assignment_enabled',
            'requires_approval', 'territories_count'
        ]
        read_only_fields = ['id', 'territories_count']
    
    def get_territories_count(self, obj):
        """Get count of territories of this type"""
        return obj.territories.filter(is_active=True).count()


class TerritoryAssignmentSerializer(serializers.ModelSerializer):
    """Territory assignment serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    territory_name = serializers.CharField(source='territory.name', read_only=True)
    assigned_by_details = UserBasicSerializer(source='assigned_by', read_only=True)
    
    # Assignment status
    is_current = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    assignment_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = TerritoryAssignment
        fields = [
            'id', 'user', 'user_details', 'territory', 'territory_name',
            'role', 'assignment_type', 'start_date', 'end_date', 'is_active',
            'is_current', 'days_remaining', 'assignment_duration',
            # Permissions
            'can_view_all_accounts', 'can_edit_accounts', 'can_create_opportunities',
            'can_manage_leads', 'can_assign_territories',
            # Performance
            'individual_target', 'commission_percentage',
            # Assignment metadata
            'assigned_by', 'assigned_by_details', 'assignment_reason', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_details', 'territory_name', 'assigned_by_details',
            'is_current', 'days_remaining', 'assignment_duration',
            'created_at', 'updated_at'
        ]
    
    def get_assignment_duration(self, obj):
        """Get assignment duration in days"""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days
        elif obj.start_date:
            from django.utils import timezone
            return (timezone.now().date() - obj.start_date).days
        return None
    
    def validate(self, data):
        """Validate assignment data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        
        return data


class TerritorySerializer(serializers.ModelSerializer):
    """Comprehensive territory serializer"""
    
    territory_type_details = TerritoryTypeSerializer(source='territory_type', read_only=True)
    manager_details = UserBasicSerializer(source='manager', read_only=True)
    parent_territory_name = serializers.CharField(source='parent_territory.name', read_only=True)
    
    # Assignments
    assignments = TerritoryAssignmentSerializer(many=True, read_only=True)
    active_assignments_count = serializers.SerializerMethodField()
    
    # Performance metrics
    target_achievement_percentage = serializers.ReadOnlyField()
    is_over_target = serializers.ReadOnlyField()
    team_size = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    
    # Geographic coverage
    geographic_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Territory
        fields = [
            'id', 'name', 'code', 'description', 'territory_type',
            'territory_type_details', 'status', 'manager', 'manager_details',
            # Geographic boundaries
            'countries', 'states_provinces', 'cities', 'postal_codes',
            'zip_code_ranges', 'geographic_summary',
            # Business rules
            'criteria', 'assignment_rules',
            # Targets and performance
            'annual_revenue_target', 'quarterly_target', 'monthly_target',
            'current_revenue', 'ytd_revenue', 'target_achievement_percentage',
            'is_over_target', 'performance_summary',
            # Settings
            'allow_overlap', 'auto_assign_leads', 'auto_assign_accounts',
            'priority_score',
            # Hierarchy
            'parent_territory', 'parent_territory_name', 'level',
            # Assignments
            'assignments', 'active_assignments_count', 'team_size',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'territory_type_details', 'manager_details', 'parent_territory_name',
            'assignments', 'active_assignments_count', 'current_revenue', 'ytd_revenue',
            'target_achievement_percentage', 'is_over_target', 'team_size',
            'performance_summary', 'geographic_summary', 'level', 'created_at', 'updated_at'
        ]
    
    def get_active_assignments_count(self, obj):
        """Get count of active assignments"""
        return obj.assignments.filter(is_active=True).count()
    
    def get_team_size(self, obj):
        """Get total team size"""
        return obj.get_total_team_size()
    
    def get_performance_summary(self, obj):
        """Get performance summary"""
        achievement = obj.target_achievement_percentage
        return {
            'achievement_percentage': float(achievement),
            'performance_level': 'Excellent' if achievement > 100 else 'Good' if achievement > 80 else 'Average',
            'revenue_gap': float(obj.annual_revenue_target - obj.current_revenue) if obj.annual_revenue_target else 0,
            'team_productivity': float(obj.current_revenue / max(obj.get_total_team_size(), 1))
        }
    
    def get_geographic_summary(self, obj):
        """Get geographic coverage summary"""
        return {
            'countries_count': len(obj.countries) if obj.countries else 0,
            'states_count': len(obj.states_provinces) if obj.states_provinces else 0,
            'cities_count': len(obj.cities) if obj.cities else 0,
            'postal_codes_count': len(obj.postal_codes) if obj.postal_codes else 0,
            'coverage_type': self._determine_coverage_type(obj)
        }
    
    def _determine_coverage_type(self, obj):
        """Determine the type of geographic coverage"""
        if obj.countries:
            return 'International'
        elif obj.states_provinces:
            return 'Multi-State'
        elif obj.cities:
            return 'Multi-City'
        elif obj.postal_codes:
            return 'Postal Code'
        else:
            return 'Custom Criteria'


class TeamMembershipSerializer(serializers.ModelSerializer):
    """Team membership serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    assigned_by_details = UserBasicSerializer(source='assigned_by', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    
    # Membership metrics
    tenure_days = serializers.ReadOnlyField()
    is_leader = serializers.ReadOnlyField()
    can_manage_team = serializers.ReadOnlyField()
    
    class Meta:
        model = TeamMembership
        fields = [
            'id', 'user', 'user_details', 'team', 'team_name', 'role', 'status',
            'join_date', 'leave_date', 'rejoin_date', 'is_active',
            'tenure_days', 'is_leader', 'can_manage_team',
            # Assignment
            'assigned_by', 'assigned_by_details', 'assignment_reason',
            # Permissions
            'can_view_team_data', 'can_edit_team_settings', 'can_add_members',
            'can_remove_members', 'can_assign_leads', 'can_view_team_revenue',
            # Performance
            'individual_target', 'commission_percentage',
            # Additional info
            'notes', 'skills', 'certifications',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_details', 'team_name', 'assigned_by_details',
            'tenure_days', 'is_leader', 'can_manage_team', 'created_at', 'updated_at'
        ]


class TeamSerializer(serializers.ModelSerializer):
    """Comprehensive team serializer"""
    
    team_lead_details = UserBasicSerializer(source='team_lead', read_only=True)
    manager_details = UserBasicSerializer(source='manager', read_only=True)
    parent_team_name = serializers.CharField(source='parent_team.name', read_only=True)
    
    # Members
    memberships = TeamMembershipSerializer(many=True, read_only=True)
    total_members = serializers.ReadOnlyField()
    available_spots = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    
    # Performance metrics
    target_achievement_percentage = serializers.ReadOnlyField()
    team_performance = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = [
            'id', 'name', 'code', 'description', 'team_type', 'status',
            'team_lead', 'team_lead_details', 'manager', 'manager_details',
            # Hierarchy
            'parent_team', 'parent_team_name', 'level',
            # Targets and performance
            'team_revenue_target', 'team_goals', 'current_revenue', 'ytd_revenue',
            'target_achievement_percentage', 'team_performance',
            # Team settings
            'max_team_size', 'auto_assign_leads', 'shared_commission_pool',
            'requires_approval_to_join',
            # Members
            'memberships', 'total_members', 'available_spots', 'is_full',
            # Collaboration
            'slack_channel', 'email_list', 'meeting_schedule',
            # Location
            'primary_location', 'timezone',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'team_lead_details', 'manager_details', 'parent_team_name',
            'memberships', 'total_members', 'available_spots', 'is_full',
            'current_revenue', 'ytd_revenue', 'target_achievement_percentage',
            'team_performance', 'level', 'created_at', 'updated_at'
        ]
    
    def get_team_performance(self, obj):
        """Get comprehensive team performance metrics"""
        achievement = obj.target_achievement_percentage
        return {
            'achievement_percentage': float(achievement),
            'performance_rating': 'Excellent' if achievement > 100 else 'Good' if achievement > 80 else 'Needs Improvement',
            'revenue_per_member': float(obj.current_revenue / max(obj.total_members, 1)),
            'team_utilization': float((obj.total_members / max(obj.max_team_size, obj.total_members)) * 100) if obj.max_team_size else 100,
            'leadership_depth': self._calculate_leadership_depth(obj)
        }
    
    def _calculate_leadership_depth(self, obj):
        """Calculate leadership depth ratio"""
        leaders = obj.memberships.filter(
            is_active=True,
            role__in=['LEADER', 'SENIOR']
        ).count()
        total_members = obj.total_members
        
        if total_members > 0:
            return (leaders / total_members) * 100
        return 0


class TerritoryAnalyticsSerializer(serializers.Serializer):
    """Territory analytics serializer"""
    
    territory_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    date_range = serializers.CharField(required=False, default='30d')
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'revenue', 'leads', 'opportunities', 'team_performance',
            'coverage', 'assignment_distribution'
        ]),
        required=False,
        default=['revenue', 'leads', 'opportunities']
    )
    
    def validate_date_range(self, value):
        """Validate date range"""
        valid_ranges = ['7d', '30d', '90d', '180d', '1y']
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Date range must be one of: {', '.join(valid_ranges)}")
        return value


class TeamAnalyticsSerializer(serializers.Serializer):
    """Team analytics serializer"""
    
    team_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    include_individual_performance = serializers.BooleanField(default=False)
    performance_period = serializers.ChoiceField(
        choices=[('current_month', 'Current Month'), ('last_month', 'Last Month'), 
                ('quarter', 'Current Quarter'), ('year', 'Current Year')],
        default='current_month'
    )