# ============================================================================
# backend/apps/crm/permissions/__init__.py - Complete Permissions Module (Final Version)
# ============================================================================

from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# IMPORT BASE PERMISSION CLASSES
# ============================================================================

try:
    from .base import CRMPermission, TenantPermission, ObjectLevelPermission
except ImportError as e:
    logger.error(f"Failed to import base permissions: {e}")
    raise ImproperlyConfigured(f"Base permission classes are required: {e}")

# ============================================================================
# IMPORT CORE CRM PERMISSION CLASSES
# ============================================================================

try:
    # Account management permissions
    from .account import AccountPermission, ContactPermission, IndustryPermission
    
    # Lead management permissions
    from .lead import LeadPermission, LeadSourcePermission
    
    # Opportunity management permissions
    from .opportunity import OpportunityPermission, PipelinePermission
    
    # Activity management permissions
    from .activity import ActivityPermission, ActivityTypePermission
    
    # Campaign management permissions
    from .campaign import CampaignPermission, CampaignMemberPermission
    
    # Ticket management permissions
    from .ticket import TicketPermission, TicketCategoryPermission
    
    # Document management permissions
    from .document import DocumentPermission, DocumentCategoryPermission, DocumentSharePermission
    
    # Territory management permissions
    from .territory import TerritoryPermission, TerritoryAssignmentPermission, TeamPermission
    
    # Product management permissions
    from .product import ProductPermission, ProductCategoryPermission, PricingModelPermission, ProductBundlePermission
    
    # Analytics permissions
    from .analytics import AnalyticsPermission, ReportPermission, DashboardPermission
    
    # Workflow permissions
    from .workflow import WorkflowPermission, WorkflowExecutionPermission, IntegrationPermission
    
    # System administration permissions
    from .system import SystemAdminPermission, AuditPermission
    
    logger.info("✅ All core CRM permission classes imported successfully")
    
except ImportError as e:
    logger.error(f"Failed to import core CRM permissions: {e}")
    # Create placeholder classes for missing permissions
    class MissingPermission(CRMPermission):
        """Placeholder for missing permission classes"""
        pass
    
    # Assign placeholders for missing classes
    globals().update({
        name: MissingPermission for name in [
            'AccountPermission', 'ContactPermission', 'IndustryPermission',
            'LeadPermission', 'LeadSourcePermission', 'OpportunityPermission', 
            'PipelinePermission', 'ActivityPermission', 'ActivityTypePermission',
            'CampaignPermission', 'CampaignMemberPermission', 'TicketPermission', 
            'TicketCategoryPermission', 'DocumentPermission', 'DocumentCategoryPermission',
            'DocumentSharePermission', 'TerritoryPermission', 'TerritoryAssignmentPermission',
            'TeamPermission', 'ProductPermission', 'ProductCategoryPermission',
            'PricingModelPermission', 'ProductBundlePermission', 'AnalyticsPermission',
            'ReportPermission', 'DashboardPermission', 'WorkflowPermission',
            'WorkflowExecutionPermission', 'IntegrationPermission', 'SystemAdminPermission',
            'AuditPermission'
        ]
    })

# ============================================================================
# IMPORT YOUR EXISTING PERMISSION UTILITIES
# ============================================================================

try:
    # Import ALL your existing files with correct names
    from .attribute_based import AttributeBasedPermission  # Your ABAC system
    from .mixins import PermissionMixin, AuditMixin, SecurityMixin  # Your view mixins
    from .audit import AuditPermission, CompliancePermission  # Your comprehensive audit system
    from .role_based import RoleBasedPermission, DynamicRolePermission
    from .field_level import FieldLevelPermission, SensitiveDataPermission
    from .ip_based import IPBasedPermission
    from .time_based import TimeBasedPermission
    
    logger.info("✅ All additional permission utilities imported from existing files")
    
except ImportError as e:
    logger.warning(f"Some additional permission utilities not available: {e}")
    
    # Create missing classes only if they don't exist
    missing_classes = []
    
    # Check each class and create only if missing
    if 'FieldLevelPermission' not in globals():
        missing_classes.append('FieldLevelPermission')
        class FieldLevelPermission(CRMPermission):
            """Field-level permission checking"""
            
            def get_allowed_fields(self, user, model, action):
                """Get list of fields user can access for given action"""
                if user.is_superuser:
                    return '__all__'
                
                # Get user's role-based field permissions
                user_roles = getattr(user, 'crm_roles', [])
                field_permissions = getattr(model, '_field_permissions', {})
                
                allowed_fields = set()
                for role in user_roles:
                    role_fields = field_permissions.get(role, {}).get(action, [])
                    allowed_fields.update(role_fields)
                
                return list(allowed_fields) if allowed_fields else []
    
    if 'SensitiveDataPermission' not in globals():
        missing_classes.append('SensitiveDataPermission')
        class SensitiveDataPermission(FieldLevelPermission):
            """Sensitive data field permission checking"""
            pass
    
    if 'IPBasedPermission' not in globals():
        missing_classes.append('IPBasedPermission')
        class IPBasedPermission(CRMPermission):
            """IP address-based permission checking"""
            
            def get_client_ip(self, request):
                """Get client IP address"""
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR', '')
                return ip
    
    if 'TimeBasedPermission' not in globals():
        missing_classes.append('TimeBasedPermission')
        class TimeBasedPermission(CRMPermission):
            """Time-based permission checking"""
            
            def is_within_business_hours(self, request):
                """Check if request is within business hours"""
                from datetime import datetime, time
                import pytz
                
                # Get tenant timezone
                tenant_tz = getattr(request.tenant, 'timezone', 'UTC') if hasattr(request, 'tenant') else 'UTC'
                tz = pytz.timezone(tenant_tz)
                
                current_time = datetime.now(tz).time()
                business_start = time(9, 0)  # 9:00 AM
                business_end = time(17, 0)   # 5:00 PM
                
                return business_start <= current_time <= business_end
    
    if 'RoleBasedPermission' not in globals():
        missing_classes.append('RoleBasedPermission')
        class RoleBasedPermission(CRMPermission):
            """Role-based permission system"""
            
            def get_user_permissions(self, user):
                """Get all permissions for user based on roles"""
                if user.is_superuser:
                    return ['*']  # All permissions
                
                permissions = set()
                user_roles = getattr(user, 'crm_roles', [])
                
                for role in user_roles:
                    role_permissions = getattr(role, 'permissions', [])
                    permissions.update(role_permissions)
                
                return list(permissions)
    
    if 'DynamicRolePermission' not in globals():
        missing_classes.append('DynamicRolePermission')
        DynamicRolePermission = RoleBasedPermission  # Alias for compatibility
    
    # Create additional mixins if not imported from your existing file
    if 'TenantPermissionMixin' not in globals():
        missing_classes.append('TenantPermissionMixin')
        class TenantPermissionMixin:
            """Mixin for tenant-aware permission handling"""
            
            def get_tenant(self, request):
                """Get tenant from request"""
                return getattr(request, 'tenant', None)
            
            def check_tenant_permissions(self, request, obj=None):
                """Check tenant-specific permissions"""
                tenant = self.get_tenant(request)
                
                if not tenant:
                    return False
                
                # Check if object belongs to user's tenant
                if obj and hasattr(obj, 'tenant'):
                    return obj.tenant == tenant
                
                return True
    
    if 'RolePermissionMixin' not in globals():
        missing_classes.append('RolePermissionMixin')
        class RolePermissionMixin:
            """Mixin for role-based permission handling"""
            
            def get_user_roles(self, user):
                """Get user's roles"""
                if hasattr(user, 'crm_profile'):
                    return user.crm_profile.roles.all()
                return []
            
            def has_role(self, user, role_name):
                """Check if user has specific role"""
                user_roles = self.get_user_roles(user)
                return any(role.name == role_name for role in user_roles)
    
    if missing_classes:
        logger.info(f"📝 Created placeholder classes for: {', '.join(missing_classes)}")

# ============================================================================
# PERMISSION REGISTRY
# ============================================================================

# Permission registry for dynamic permission checking
PERMISSION_REGISTRY = {
    # Core CRM models
    'account': AccountPermission,
    'contact': ContactPermission,
    'industry': IndustryPermission,
    'lead': LeadPermission,
    'leadsource': LeadSourcePermission,
    'opportunity': OpportunityPermission,
    'pipeline': PipelinePermission,
    'activity': ActivityPermission,
    'activitytype': ActivityTypePermission,
    'campaign': CampaignPermission,
    'campaignmember': CampaignMemberPermission,
    'ticket': TicketPermission,
    'ticketcategory': TicketCategoryPermission,
    'document': DocumentPermission,
    'documentcategory': DocumentCategoryPermission,
    'documentshare': DocumentSharePermission,
    'territory': TerritoryPermission,
    'territoryassignment': TerritoryAssignmentPermission,
    'team': TeamPermission,
    'product': ProductPermission,
    'productcategory': ProductCategoryPermission,
    'pricingmodel': PricingModelPermission,
    'productbundle': ProductBundlePermission,
    'analytics': AnalyticsPermission,
    'report': ReportPermission,
    'dashboard': DashboardPermission,
    'workflowrule': WorkflowPermission,
    'workflowexecution': WorkflowExecutionPermission,
    'integration': IntegrationPermission,
    'system': SystemAdminPermission,
    'audit': AuditPermission,
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_permission_class(model_name):
    """Get permission class for a model"""
    return PERMISSION_REGISTRY.get(model_name.lower(), CRMPermission)

def register_permission(model_name, permission_class):
    """Register a custom permission class for a model"""
    PERMISSION_REGISTRY[model_name.lower()] = permission_class
    logger.info(f"Registered permission class {permission_class.__name__} for {model_name}")

def has_model_permission(user, model_name, action, obj=None):
    """Check if user has permission for model action"""
    try:
        permission_class = get_permission_class(model_name)
        permission = permission_class()
        
        # Create a mock request object for permission checking
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.tenant = getattr(user, 'current_tenant', None)
                self.META = {}
                self.user_roles = getattr(user, 'crm_roles', [])
                self.user_permissions = getattr(user, 'crm_permissions', [])
                self.method = 'GET'
                self.path = '/'
                
                # Add session mock
                class MockSession:
                    session_key = 'mock_session'
                
                self.session = MockSession()
                
                def is_secure(self):
                    return True
        
        request = MockRequest(user)
        
        # Check basic permission
        if not permission.has_permission(request, None):
            return False
        
        # Check object-level permission if object provided
        if obj and hasattr(permission, 'has_object_permission'):
            return permission.has_object_permission(request, None, obj)
        
        return True
        
    except Exception as e:
        logger.error(f"Permission check failed for {user} on {model_name}.{action}: {e}")
        return False

def get_user_permissions_for_model(user, model_name):
    """Get all permissions user has for a specific model"""
    permission_class = get_permission_class(model_name)
    
    if hasattr(permission_class, 'get_user_permissions'):
        return permission_class().get_user_permissions(user, model_name)
    
    # Default permission check for standard CRUD operations
    actions = ['view', 'add', 'change', 'delete']
    user_permissions = []
    
    for action in actions:
        if has_model_permission(user, model_name, action):
            user_permissions.append(f'{action}_{model_name.lower()}')
    
    return user_permissions

def check_field_permissions(user, model_name, field_name, action):
    """Check if user has permission to access specific field"""
    permission_class = get_permission_class(model_name)
    
    if hasattr(permission_class, 'check_field_permission'):
        return permission_class().check_field_permission(user, field_name, action)
    
    # Use SensitiveDataPermission if available
    if 'SensitiveDataPermission' in globals():
        sensitive_permission = SensitiveDataPermission()
        if hasattr(sensitive_permission, 'check_field_access'):
            return sensitive_permission.check_field_access(user, model_name, field_name, action)
    
    # Default: allow all fields if user has model permission
    return has_model_permission(user, model_name, action)

def get_filtered_queryset(user, queryset, action='view'):
    """Filter queryset based on user permissions"""
    model_name = queryset.model._meta.model_name
    permission_class = get_permission_class(model_name)
    
    if hasattr(permission_class, 'filter_queryset'):
        return permission_class().filter_queryset(user, queryset, action)
    
    # Default tenant filtering
    if hasattr(queryset.model, 'tenant') and hasattr(user, 'current_tenant'):
        return queryset.filter(tenant=user.current_tenant)
    
    return queryset

def validate_permissions_setup():
    """Validate that all required permissions are properly configured"""
    validation_results = {
        'registered_permissions': len(PERMISSION_REGISTRY),
        'missing_permissions': [],
        'invalid_permissions': [],
        'existing_files': [],
        'existing_classes': [],
        'placeholder_classes': [],
        'is_valid': True
    }
    
    # Check each registered permission class
    for model_name, permission_class in PERMISSION_REGISTRY.items():
        try:
            # Try to instantiate the permission class
            instance = permission_class()
            
            # Check if it has required methods
            required_methods = ['has_permission']
            for method in required_methods:
                if not hasattr(instance, method):
                    validation_results['invalid_permissions'].append(
                        f"{permission_class.__name__} missing method: {method}"
                    )
                    validation_results['is_valid'] = False
            
            # Check if this is a real implementation or placeholder
            if permission_class.__name__ == 'MissingPermission':
                validation_results['placeholder_classes'].append(model_name)
            else:
                validation_results['existing_classes'].append(model_name)
                    
        except Exception as e:
            validation_results['invalid_permissions'].append(
                f"Failed to instantiate {permission_class.__name__}: {e}"
            )
            validation_results['is_valid'] = False
    
    # Check for existing files
    import os
    permissions_dir = os.path.dirname(__file__)
    
    try:
        existing_files = [
            f for f in os.listdir(permissions_dir) 
            if f.endswith('.py') and not f.startswith('__')
        ]
        validation_results['existing_files'] = [f[:-3] for f in existing_files]  # Remove .py extension
    except Exception:
        validation_results['existing_files'] = []
    
    return validation_results

def get_abac_policies():
    """Get ABAC policies from AttributeBasedPermission"""
    try:
        if hasattr(AttributeBasedPermission, 'ABAC_POLICIES'):
            return AttributeBasedPermission.ABAC_POLICIES
        return {}
    except:
        return {}

def get_compliance_frameworks():
    """Get compliance frameworks from AuditPermission"""
    try:
        if hasattr(AuditPermission, 'COMPLIANCE_FRAMEWORKS'):
            return AuditPermission.COMPLIANCE_FRAMEWORKS
        return {}
    except:
        return {}

def get_audit_event_types():
    """Get audit event types from AuditPermission"""
    try:
        if hasattr(AuditPermission, 'AUDIT_EVENT_TYPES'):
            return AuditPermission.AUDIT_EVENT_TYPES
        return {}
    except:
        return {}

def get_data_sensitivity_config():
    """Get data sensitivity configuration from AuditPermission"""
    try:
        if hasattr(AuditPermission, 'DATA_SENSITIVITY_AUDIT'):
            return AuditPermission.DATA_SENSITIVITY_AUDIT
        return {}
    except:
        return {}

def evaluate_abac_policy(user, obj, action, request=None):
    """Evaluate ABAC policy for user, object, and action"""
    try:
        permission = AttributeBasedPermission()
        
        # Create mock request if not provided
        if not request:
            class MockRequest:
                def __init__(self, user):
                    self.user = user
                    self.tenant = getattr(user, 'current_tenant', None)
                    self.META = {}
                    self.method = 'GET'
                    self.path = '/'
                    self.user_roles = getattr(user, 'crm_roles', [])
                    
                    class MockSession:
                        session_key = 'mock_session'
                    
                    self.session = MockSession()
                    
                def is_secure(self):
                    return True
            
            request = MockRequest(user)
        
        # Create mock view
        class MockView:
            def __init__(self, action):
                self.action = action
        
        view = MockView(action)
        
        return permission.has_object_permission(request, view, obj)
        
    except Exception as e:
        logger.error(f"ABAC policy evaluation failed: {e}")
        return False

def check_compliance_requirements(user, framework, obj=None):
    """Check compliance requirements for specific framework"""
    try:
        if 'CompliancePermission' in globals():
            compliance_permission = CompliancePermission()
            
            # Create mock request
            class MockRequest:
                def __init__(self, user):
                    self.user = user
                    self.tenant = getattr(user, 'current_tenant', None)
                    self.META = {}
                    self.method = 'GET'
                    self.path = '/'
                    
                    class MockSession:
                        session_key = 'mock_session'
                    
                    self.session = MockSession()
                    
                def is_secure(self):
                    return True
            
            request = MockRequest(user)
            
            # Check framework compliance
            frameworks = get_compliance_frameworks()
            framework_config = frameworks.get(framework, {})
            
            return compliance_permission._check_framework_compliance(
                request, None, framework, framework_config
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Compliance check failed for {framework}: {e}")
        return True

def get_user_effective_permissions(user, context=None):
    """Get user's effective permissions with context"""
    try:
        from .role_based import DynamicRolePermission
        
        role_permission = DynamicRolePermission()
        base_permissions = role_permission.get_user_permissions(user)
        
        # Add context-specific permissions
        context_permissions = []
        if context:
            # Add time-based permissions
            if hasattr(context, 'is_business_hours') and context.is_business_hours:
                context_permissions.extend(['business_hours_actions'])
            
            # Add location-based permissions
            if hasattr(context, 'is_secure_location') and context.is_secure_location:
                context_permissions.extend(['secure_location_actions'])
        
        return {
            'base_permissions': base_permissions,
            'context_permissions': context_permissions,
            'effective_permissions': base_permissions + context_permissions,
            'user_id': user.id,
            'evaluated_at': timezone.now().isoformat(),
            'compliance_frameworks': list(get_compliance_frameworks().keys()),
            'abac_policies': list(get_abac_policies().keys())
        }
        
    except Exception as e:
        logger.error(f"Effective permissions calculation failed: {e}")
        return {
            'base_permissions': [],
            'context_permissions': [],
            'effective_permissions': [],
            'error': str(e)
        }

def check_sensitive_field_access(user, model_name, field_name, action='view'):
    """Check access to sensitive fields using SensitiveDataPermission"""
    try:
        if 'SensitiveDataPermission' in globals():
            sensitive_permission = SensitiveDataPermission()
            return sensitive_permission.check_field_access(user, model_name, field_name, action)
        else:
            # Fallback to standard field permission check
            return check_field_permissions(user, model_name, field_name, action)
    except Exception as e:
        logger.error(f"Sensitive field access check failed: {e}")
        return False

# ============================================================================
# EXPORT ALL CLASSES AND FUNCTIONS
# ============================================================================

__all__ = [
    # Base permission classes
    'CRMPermission', 'TenantPermission', 'ObjectLevelPermission',
    
    # Core CRM permissions
    'AccountPermission', 'ContactPermission', 'IndustryPermission',
    'LeadPermission', 'LeadSourcePermission',
    'OpportunityPermission', 'PipelinePermission', 
    'ActivityPermission', 'ActivityTypePermission',
    'CampaignPermission', 'CampaignMemberPermission',
    'TicketPermission', 'TicketCategoryPermission',
    'DocumentPermission', 'DocumentCategoryPermission', 'DocumentSharePermission',
    'TerritoryPermission', 'TerritoryAssignmentPermission', 'TeamPermission',
    'ProductPermission', 'ProductCategoryPermission', 'PricingModelPermission', 'ProductBundlePermission',
    'AnalyticsPermission', 'ReportPermission', 'DashboardPermission',
    'WorkflowPermission', 'WorkflowExecutionPermission', 'IntegrationPermission',
    'SystemAdminPermission', 'AuditPermission',
    
    # Additional permission utilities (your existing classes)
    'AttributeBasedPermission', 'FieldLevelPermission', 'SensitiveDataPermission',
    'IPBasedPermission', 'RoleBasedPermission', 'DynamicRolePermission', 'TimeBasedPermission',
    'CompliancePermission',  # Your advanced compliance system
    
    # Mixins (your existing mixins)
    'PermissionMixin', 'AuditMixin', 'SecurityMixin', 'TenantPermissionMixin', 'RolePermissionMixin',
    
    # Utility functions
    'get_permission_class', 'register_permission', 'has_model_permission',
    'get_user_permissions_for_model', 'check_field_permissions', 'check_sensitive_field_access',
    'get_filtered_queryset', 'validate_permissions_setup', 'get_user_effective_permissions',
    'get_abac_policies', 'evaluate_abac_policy', 'check_compliance_requirements',
    'get_compliance_frameworks', 'get_audit_event_types', 'get_data_sensitivity_config',
    
    # Permission registry
    'PERMISSION_REGISTRY',
]

# ============================================================================
# INITIALIZATION AND VALIDATION
# ============================================================================

# Run validation in debug mode
import os
if os.environ.get('DEBUG', 'False').lower() == 'true':
    try:
        validation_results = validate_permissions_setup()
        
        if validation_results['is_valid']:
            logger.info(
                f"✅ CRM Permissions validation passed: "
                f"{validation_results['registered_permissions']} permissions registered"
            )
            
            # Show detailed breakdown
            existing_count = len(validation_results['existing_classes'])
            placeholder_count = len(validation_results['placeholder_classes'])
            files_count = len(validation_results['existing_files'])
            
            logger.info(
                f"📊 Permission Status: {existing_count} implemented, "
                f"{placeholder_count} placeholders, {files_count} files found"
            )
            
            # List existing files
            existing_files = validation_results['existing_files']
            logger.info(f"📁 Existing permission files: {', '.join(existing_files)}")
            
        else:
            logger.error(
                f"❌ CRM Permissions validation failed: "
                f"{len(validation_results['invalid_permissions'])} issues found"
            )
            for issue in validation_results['invalid_permissions']:
                logger.error(f"   ❌ {issue}")
    
    except Exception as e:
        logger.error(f"❌ Permission validation error: {e}")

# Log successful initialization
logger.info("🚀 CRM Permissions module initialized successfully")

# Display advanced features if available
abac_policies = get_abac_policies()
if abac_policies:
    logger.info(f"🛡️ ABAC Permission System loaded with {len(abac_policies)} policies")

compliance_frameworks = get_compliance_frameworks()
if compliance_frameworks:
    enabled_frameworks = [f for f, config in compliance_frameworks.items() if config.get('enabled', False)]
    logger.info(f"📋 Compliance Frameworks enabled: {', '.join(enabled_frameworks)}")

audit_events = get_audit_event_types()
if audit_events:
    logger.info(f"📝 Audit Event Types configured: {len(audit_events)} categories")

# Display existing mixins
existing_mixins = []
for mixin_name in ['PermissionMixin', 'AuditMixin', 'SecurityMixin']:
    if mixin_name in globals():
        existing_mixins.append(mixin_name)

if existing_mixins:
    logger.info(f"🔧 Permission Mixins available: {', '.join(existing_mixins)}")