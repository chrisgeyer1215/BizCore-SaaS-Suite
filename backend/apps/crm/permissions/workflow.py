# backend/apps/crm/permissions/workflow.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import WorkflowRule, WorkflowExecution, Integration

class WorkflowPermission(CRMPermission):
    """Permission class for Workflow management."""
    
    MODEL_PERMS = {
        'view_workflow': 'Can view workflows',
        'add_workflow': 'Can add workflows',
        'change_workflow': 'Can change workflows',
        'delete_workflow': 'Can delete workflows',
        'execute_workflow': 'Can execute workflows',
        'approve_workflow': 'Can approve workflows',
        'debug_workflow': 'Can debug workflows',
        'manage_workflow_templates': 'Can manage workflow templates',
    }
    
    def has_permission(self, request, view):
        """Check workflow permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_workflow')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_workflow')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_workflow')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_workflow')
        elif view.action == 'execute':
            return self.has_perm(request.user, 'execute_workflow')
        elif view.action == 'approve':
            return self.has_perm(request.user, 'approve_workflow')
        elif view.action == 'debug':
            return self.has_perm(request.user, 'debug_workflow')
        elif view.action in ['templates', 'create_template']:
            return self.has_perm(request.user, 'manage_workflow_templates')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check workflow object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Workflow execution requires special checks
        if view.action == 'execute':
            return self.can_execute_workflow(request.user, obj)
        
        # Workflow approval for complex workflows
        if view.action == 'approve':
            return self.can_approve_workflow(request.user, obj)
        
        # Debug access for troubleshooting
        if view.action == 'debug':
            return self.can_debug_workflow(request.user, obj)
        
        # Owner can manage their workflows
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Admin and workflow manager access
        return self.has_workflow_admin_access(request.user)
    
    def can_execute_workflow(self, user, workflow):
        """Check if user can execute workflow."""
        if not self.has_perm(user, 'execute_workflow'):
            return False
        
        # Check if workflow requires approval
        if hasattr(workflow, 'requires_approval') and workflow.requires_approval:
            if not hasattr(workflow, 'approved') or not workflow.approved:
                return False
        
        # Check workflow scope restrictions
        if hasattr(workflow, 'allowed_roles'):
            if hasattr(user, 'crm_profile'):
                user_role = user.crm_profile.role
                return user_role in workflow.allowed_roles
        
        return True
    
    def can_approve_workflow(self, user, workflow):
        """Check if user can approve workflow."""
        if not self.has_perm(user, 'approve_workflow'):
            return False
        
        # Workflow approval hierarchy
        if hasattr(user, 'crm_profile'):
            user_role = user.crm_profile.role
            approval_roles = [
                'workflow_manager', 'system_admin', 'operations_manager'
            ]
            return user_role in approval_roles
        
        return user.is_staff
    
    def can_debug_workflow(self, user, workflow):
        """Check if user can debug workflow."""
        if not self.has_perm(user, 'debug_workflow'):
            return False
        
        # Debug access for developers and admins
        if hasattr(user, 'crm_profile'):
            user_role = user.crm_profile.role
            debug_roles = ['developer', 'system_admin', 'workflow_manager']
            return user_role in debug_roles
        
        return user.is_staff
    
    def has_workflow_admin_access(self, user):
        """Check workflow admin access."""
        if user.is_staff:
            return True
        
        if hasattr(user, 'crm_profile'):
            admin_roles = ['system_admin', 'workflow_manager', 'operations_manager']
            return user.crm_profile.role in admin_roles
        
        return False

class WorkflowExecutionPermission(CRMPermission):
    """Permission class for WorkflowExecution model."""
    
    MODEL_PERMS = {
        'view_workflowexecution': 'Can view workflow executions',
        'retry_workflowexecution': 'Can retry workflow executions',
        'cancel_workflowexecution': 'Can cancel workflow executions',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check workflow execution permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check access to parent workflow
        if hasattr(obj, 'workflow'):
            workflow_permission = WorkflowPermission()
            return workflow_permission.has_object_permission(
                request, view, obj.workflow
            )
        
        return True

class IntegrationPermission(CRMPermission):
    """Permission class for Integration model."""
    
    MODEL_PERMS = {
        'view_integration': 'Can view integrations',
        'add_integration': 'Can add integrations',
        'change_integration': 'Can change integrations',
        'delete_integration': 'Can delete integrations',
        'test_integration': 'Can test integrations',
        'manage_api_keys': 'Can manage API keys',
    }
    
    def has_permission(self, request, view):
        """Integration permissions require high-level access."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for admins and integration managers
        if view.action in ['list', 'retrieve']:
            return (self.has_integration_access(request.user) or
                   self.has_perm(request.user, 'view_integration'))
        
        # Modification requires admin access
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (request.user.is_staff or
                   self.has_integration_admin_role(request.user) or
                   self.has_perm(request.user, f'{view.action}_integration'))
        
        # Testing and API key management
        if view.action == 'test':
            return self.has_perm(request.user, 'test_integration')
        elif view.action in ['manage_keys', 'rotate_keys']:
            return self.has_perm(request.user, 'manage_api_keys')
        
        return True
    
    def has_integration_access(self, user):
        """Check integration access."""
        if hasattr(user, 'crm_profile'):
            integration_roles = [
                'system_admin', 'integration_manager', 'developer',
                'operations_manager'
            ]
            return user.crm_profile.role in integration_roles
        return user.is_staff
    
    def has_integration_admin_role(self, user):
        """Check if user has integration admin role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['system_admin', 'integration_manager']
        return False