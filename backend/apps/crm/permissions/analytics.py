# backend/apps/crm/permissions/analytics.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Report, Dashboard

class AnalyticsPermission(CRMPermission):
    """Permission class for Analytics access."""
    
    MODEL_PERMS = {
        'view_analytics': 'Can view analytics',
        'view_sales_analytics': 'Can view sales analytics',
        'view_marketing_analytics': 'Can view marketing analytics',
        'view_support_analytics': 'Can view support analytics',
        'view_financial_analytics': 'Can view financial analytics',
        'view_executive_analytics': 'Can view executive analytics',
        'export_analytics': 'Can export analytics data',
        'create_custom_analytics': 'Can create custom analytics',
    }
    
    def has_permission(self, request, view):
        """Check analytics permissions."""
        if not super().has_permission(request, view):
            return False
        
        # Basic analytics access
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_analytics')
        
        # Specific analytics permissions
        if view.action == 'sales_analytics':
            return self.has_perm(request.user, 'view_sales_analytics')
        elif view.action == 'marketing_analytics':
            return self.has_perm(request.user, 'view_marketing_analytics')
        elif view.action == 'support_analytics':
            return self.has_perm(request.user, 'view_support_analytics')
        elif view.action == 'financial_analytics':
            return self.has_perm(request.user, 'view_financial_analytics')
        elif view.action == 'executive_analytics':
            return self.has_perm(request.user, 'view_executive_analytics')
        elif view.action == 'export':
            return self.has_perm(request.user, 'export_analytics')
        elif view.action == 'create_custom':
            return self.has_perm(request.user, 'create_custom_analytics')
        
        return True
    
    def has_analytics_access(self, user, analytics_type):
        """Check specific analytics access."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_role = user.crm_profile.role
        
        # Role-based analytics access
        analytics_access = {
            'sales': ['sales_rep', 'sales_manager', 'sales_director', 'vp_sales'],
            'marketing': ['marketing_coordinator', 'marketing_manager'],
            'support': ['support_agent', 'support_manager'],
            'financial': ['finance_manager', 'controller', 'cfo'],
            'executive': ['vp_sales', 'cmo', 'cfo', 'ceo'],
        }
        
        allowed_roles = analytics_access.get(analytics_type, [])
        return user_role in allowed_roles or user.is_staff

class ReportPermission(CRMPermission):
    """Permission class for Report model."""
    
    MODEL_PERMS = {
        'view_report': 'Can view reports',
        'add_report': 'Can add reports',
        'change_report': 'Can change reports',
        'delete_report': 'Can delete reports',
        'share_report': 'Can share reports',
        'schedule_report': 'Can schedule reports',
        'export_report': 'Can export reports',
    }
    
    def has_permission(self, request, view):
        """Check report permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_report')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_report')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_report')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_report')
        elif view.action == 'share':
            return self.has_perm(request.user, 'share_report')
        elif view.action == 'schedule':
            return self.has_perm(request.user, 'schedule_report')
        elif view.action == 'export':
            return self.has_perm(request.user, 'export_report')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check report object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Owner can access their reports
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Check if report is shared with user
        if self.is_report_shared(request.user, obj):
            return True
        
        # Public reports
        if hasattr(obj, 'is_public') and obj.is_public:
            return True
        
        # Department/team access
        return self.has_report_team_access(request.user, obj)
    
    def is_report_shared(self, user, report):
        """Check if report is shared with user."""
        if hasattr(report, 'shared_with'):
            return user in report.shared_with.all()
        return False
    
    def has_report_team_access(self, user, report):
        """Check team access to report."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        # Check if report belongs to user's team
        if hasattr(report, 'team'):
            user_team = user.crm_profile.team
            return report.team == user_team
        
        # Check if report belongs to user's department
        if hasattr(report, 'department'):
            user_department = user.crm_profile.department
            return report.department == user_department
        
        return False

class DashboardPermission(CRMPermission):
    """Permission class for Dashboard model."""
    
    MODEL_PERMS = {
        'view_dashboard': 'Can view dashboards',
        'add_dashboard': 'Can add dashboards',
        'change_dashboard': 'Can change dashboards',
        'delete_dashboard': 'Can delete dashboards',
        'customize_dashboard': 'Can customize dashboards',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check dashboard object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Personal dashboards
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True
        
        # Role-based dashboards
        if hasattr(obj, 'role') and hasattr(request.user, 'crm_profile'):
            user_role = request.user.crm_profile.role
            return obj.role == user_role
        
        # Team dashboards
        if hasattr(obj, 'team') and hasattr(request.user, 'crm_profile'):
            user_team = request.user.crm_profile.team
            return obj.team == user_team
        
        # Public dashboards
        if hasattr(obj, 'is_public') and obj.is_public:
            return True
        
        return False