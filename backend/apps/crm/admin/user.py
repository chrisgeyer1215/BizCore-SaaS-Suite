# backend/apps/crm/admin/user.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.safestring import mark_safe
from .base import BaseModelAdmin, TenantAwareAdmin
from ..models import CRMUserProfile, Team, TeamMembership

@admin.register(CRMUserProfile)
class CRMUserProfileAdmin(TenantAwareAdmin):
    """Admin for CRM User Profiles."""
    
    list_display = [
        'user', 'role', 'team', 'territory', 
        'phone', 'is_active', 'last_login_display'
    ]
    list_filter = [
        'role', 'is_active', 'team', 'territory',
        'created_at', 'last_login'
    ]
    search_fields = [
        'user__first_name', 'user__last_name', 'user__email',
        'phone', 'employee_id'
    ]
    readonly_fields = [
        'last_login', 'login_count', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('user', 'role', 'employee_id', 'phone', 'department')
        }),
        (_('CRM Settings'), {
            'fields': ('team', 'territory', 'quota', 'commission_rate')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'permissions', 'data_access_level')
        }),
        (_('Statistics'), {
            'fields': ('last_login', 'login_count'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def last_login_display(self, obj):
        """Display last login with formatting."""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M')
        return _('Never')
    last_login_display.short_description = _('Last Login')
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'user', 'team', 'territory'
        )

@admin.register(Team)
class TeamAdmin(TenantAwareAdmin):
    """Admin for Teams."""
    
    list_display = [
        'name', 'team_type', 'manager', 'member_count',
        'is_active', 'created_at'
    ]
    list_filter = [
        'team_type', 'is_active', 'created_at'
    ]
    search_fields = [
        'name', 'description', 'manager__user__first_name',
        'manager__user__last_name'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'team_type', 'description', 'manager')
        }),
        (_('Settings'), {
            'fields': ('is_active', 'permissions', 'goals')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def member_count(self, obj):
        """Display team member count."""
        return obj.memberships.filter(is_active=True).count()
    member_count.short_description = _('Members')
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('manager__user')

@admin.register(TeamMembership)
class TeamMembershipAdmin(TenantAwareAdmin):
    """Admin for Team Memberships."""
    
    list_display = [
        'user_profile', 'team', 'role', 'joined_date',
        'is_active'
    ]
    list_filter = [
        'role', 'is_active', 'team', 'joined_date'
    ]
    search_fields = [
        'user_profile__user__first_name',
        'user_profile__user__last_name',
        'team__name'
    ]
    
    fieldsets = (
        (_('Membership Details'), {
            'fields': ('user_profile', 'team', 'role', 'joined_date')
        }),
        (_('Settings'), {
            'fields': ('is_active', 'permissions')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'user_profile__user', 'team'
        )