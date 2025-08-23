# crm/utils/tenant_utils.py
"""
Multi-Tenant Utilities for CRM Module

Provides comprehensive multi-tenant management capabilities including:
- Tenant context management
- Data isolation and security
- Tenant-specific configurations
- Resource limits and quotas
- Tenant analytics and monitoring
- Cross-tenant operations
- Tenant lifecycle management
"""

import functools
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
from decimal import Decimal

from django.db import connection, transaction
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django_tenants.utils import schema_context, get_tenant_model, get_public_schema_name

User = get_user_model()
TenantModel = get_tenant_model()


@dataclass
class TenantLimits:
    """Represents tenant resource limits."""
    max_users: int = 10
    max_leads: int = 1000
    max_opportunities: int = 500
    max_contacts: int = 2000
    max_storage_mb: int = 1000
    max_api_calls_per_day: int = 10000
    max_email_sends_per_month: int = 5000
    custom_fields_limit: int = 50
    automation_rules_limit: int = 20
    integrations_limit: int = 5


@dataclass
class TenantUsage:
    """Represents current tenant resource usage."""
    users_count: int = 0
    leads_count: int = 0
    opportunities_count: int = 0
    contacts_count: int = 0
    storage_used_mb: float = 0.0
    api_calls_today: int = 0
    emails_sent_this_month: int = 0
    custom_fields_count: int = 0
    automation_rules_count: int = 0
    integrations_count: int = 0
    last_updated: datetime = field(default_factory=timezone.now)


@dataclass
class TenantSettings:
    """Represents tenant-specific settings."""
    timezone: str = 'UTC'
    date_format: str = '%Y-%m-%d'
    time_format: str = '%H:%M:%S'
    currency: str = 'USD'
    language: str = 'en'
    business_hours_start: str = '09:00'
    business_hours_end: str = '17:00'
    working_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    logo_url: Optional[str] = None
    company_name: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class TenantManager:
    """
    Comprehensive tenant management system.
    """
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 3600)  # 1 hour
    
    def get_tenant_from_request(self, request) -> Optional[TenantModel]:
        """
        Get tenant from request object.
        
        Args:
            request: Django request object
        
        Returns:
            Tenant instance or None
        """
        if hasattr(request, 'tenant'):
            return request.tenant
        
        # Try to get from subdomain
        host = request.get_host().lower()
        domain_parts = host.split('.')
        
        if len(domain_parts) >= 2:
            subdomain = domain_parts[0]
            try:
                tenant = TenantModel.objects.get(
                    domain_url__icontains=subdomain,
                    is_active=True
                )
                return tenant
            except TenantModel.DoesNotExist:
                pass
        
        # Try to get from custom header
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            try:
                tenant = TenantModel.objects.get(
                    id=tenant_id,
                    is_active=True
                )
                return tenant
            except (TenantModel.DoesNotExist, ValueError):
                pass
        
        return None
    
    def switch_tenant_context(self, tenant: TenantModel) -> None:
        """
        Switch database connection to tenant schema.
        
        Args:
            tenant: Tenant to switch to
        """
        if tenant and hasattr(tenant, 'schema_name'):
            connection.set_schema_to_tenant(tenant)
        else:
            raise ValueError("Invalid tenant object")
    
    @contextmanager
    def tenant_context(self, tenant: TenantModel):
        """
        Context manager for temporary tenant switching.
        
        Args:
            tenant: Tenant to switch to
        
        Usage:
            with tenant_manager.tenant_context(tenant):
                # Operations in tenant context
                leads = Lead.objects.all()
        """
        if not tenant:
            yield
            return
        
        original_schema = connection.schema_name if hasattr(connection, 'schema_name') else None
        
        try:
            with schema_context(tenant.schema_name):
                yield
        finally:
            if original_schema:
                with schema_context(original_schema):
                    pass
    
    def get_tenant_limits(self, tenant: TenantModel) -> TenantLimits:
        """
        Get tenant resource limits based on subscription plan.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            TenantLimits object
        """
        cache_key = f"tenant_limits_{tenant.id}"
        cached_limits = cache.get(cache_key)
        
        if cached_limits:
            return cached_limits
        
        # Get limits based on tenant plan
        plan_limits = self._get_plan_limits(tenant.subscription_plan if hasattr(tenant, 'subscription_plan') else 'basic')
        
        # Override with tenant-specific limits if they exist
        try:
            from crm.models.system import TenantConfiguration
            config = TenantConfiguration.objects.get(tenant=tenant)
            
            if config.custom_limits:
                for limit_name, limit_value in config.custom_limits.items():
                    if hasattr(plan_limits, limit_name):
                        setattr(plan_limits, limit_name, limit_value)
        except:
            pass
        
        # Cache for 1 hour
        cache.set(cache_key, plan_limits, self.cache_timeout)
        return plan_limits
    
    def get_tenant_usage(self, tenant: TenantModel) -> TenantUsage:
        """
        Get current tenant resource usage.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            TenantUsage object
        """
        cache_key = f"tenant_usage_{tenant.id}"
        cached_usage = cache.get(cache_key)
        
        # Return cached if less than 15 minutes old
        if cached_usage and (timezone.now() - cached_usage.last_updated).seconds < 900:
            return cached_usage
        
        usage = TenantUsage()
        
        try:
            with self.tenant_context(tenant):
                # Count users
                from django.contrib.auth import get_user_model
                User = get_user_model()
                usage.users_count = User.objects.filter(is_active=True).count()
                
                # Count CRM records
                try:
                    from crm.models.lead import Lead
                    usage.leads_count = Lead.objects.count()
                except:
                    pass
                
                try:
                    from crm.models.opportunity import Opportunity
                    usage.opportunities_count = Opportunity.objects.count()
                except:
                    pass
                
                try:
                    from crm.models.account import Contact
                    usage.contacts_count = Contact.objects.count()
                except:
                    pass
                
                # Calculate storage usage
                usage.storage_used_mb = self._calculate_storage_usage(tenant)
                
                # Get API usage for today
                usage.api_calls_today = self._get_api_usage_today(tenant)
                
                # Get email usage for this month
                usage.emails_sent_this_month = self._get_email_usage_month(tenant)
                
                # Count custom fields
                usage.custom_fields_count = self._count_custom_fields(tenant)
                
                # Count automation rules
                usage.automation_rules_count = self._count_automation_rules(tenant)
                
                # Count integrations
                usage.integrations_count = self._count_integrations(tenant)
                
                usage.last_updated = timezone.now()
        
        except Exception as e:
            print(f"Error calculating tenant usage: {e}")
        
        # Cache for 15 minutes
        cache.set(cache_key, usage, 900)
        return usage
    
    def check_tenant_limits(self, tenant: TenantModel, resource_type: str, 
                           additional_usage: int = 1) -> Dict[str, Any]:
        """
        Check if tenant can use additional resources.
        
        Args:
            tenant: Tenant instance
            resource_type: Type of resource to check
            additional_usage: Additional usage to check for
        
        Returns:
            Dict with check results
        """
        limits = self.get_tenant_limits(tenant)
        usage = self.get_tenant_usage(tenant)
        
        limit_mappings = {
            'users': (limits.max_users, usage.users_count),
            'leads': (limits.max_leads, usage.leads_count),
            'opportunities': (limits.max_opportunities, usage.opportunities_count),
            'contacts': (limits.max_contacts, usage.contacts_count),
            'storage_mb': (limits.max_storage_mb, usage.storage_used_mb),
            'api_calls': (limits.max_api_calls_per_day, usage.api_calls_today),
            'email_sends': (limits.max_email_sends_per_month, usage.emails_sent_this_month),
            'custom_fields': (limits.custom_fields_limit, usage.custom_fields_count),
            'automation_rules': (limits.automation_rules_limit, usage.automation_rules_count),
            'integrations': (limits.integrations_limit, usage.integrations_count)
        }
        
        if resource_type not in limit_mappings:
            return {
                'allowed': False,
                'error': f"Unknown resource type: {resource_type}"
            }
        
        max_limit, current_usage = limit_mappings[resource_type]
        new_usage = current_usage + additional_usage
        
        if new_usage > max_limit:
            return {
                'allowed': False,
                'error': f"Resource limit exceeded. Current: {current_usage}, Limit: {max_limit}",
                'current_usage': current_usage,
                'limit': max_limit,
                'requested_additional': additional_usage
            }
        
        return {
            'allowed': True,
            'current_usage': current_usage,
            'limit': max_limit,
            'remaining': max_limit - new_usage
        }
    
    def get_tenant_settings(self, tenant: TenantModel) -> TenantSettings:
        """
        Get tenant-specific settings.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            TenantSettings object
        """
        cache_key = f"tenant_settings_{tenant.id}"
        cached_settings = cache.get(cache_key)
        
        if cached_settings:
            return cached_settings
        
        settings_obj = TenantSettings()
        
        try:
            from crm.models.system import TenantConfiguration
            config = TenantConfiguration.objects.get(tenant=tenant)
            
            # Map configuration to settings object
            if config.timezone:
                settings_obj.timezone = config.timezone
            if config.date_format:
                settings_obj.date_format = config.date_format
            if config.time_format:
                settings_obj.time_format = config.time_format
            if config.currency:
                settings_obj.currency = config.currency
            if config.language:
                settings_obj.language = config.language
            if config.business_hours_start:
                settings_obj.business_hours_start = config.business_hours_start
            if config.business_hours_end:
                settings_obj.business_hours_end = config.business_hours_end
            if config.working_days:
                settings_obj.working_days = config.working_days
            if config.logo_url:
                settings_obj.logo_url = config.logo_url
            if config.company_name:
                settings_obj.company_name = config.company_name
            if config.contact_email:
                settings_obj.contact_email = config.contact_email
            if config.phone:
                settings_obj.phone = config.phone
            if config.address:
                settings_obj.address = config.address
            if config.website:
                settings_obj.website = config.website
            if config.industry:
                settings_obj.industry = config.industry
            if config.custom_settings:
                settings_obj.custom_settings = config.custom_settings
        
        except Exception as e:
            print(f"Error loading tenant settings: {e}")
            # Return default settings
        
        # Cache for 1 hour
        cache.set(cache_key, settings_obj, self.cache_timeout)
        return settings_obj
    
    def update_tenant_setting(self, tenant: TenantModel, setting_name: str, 
                             setting_value: Any) -> bool:
        """
        Update a specific tenant setting.
        
        Args:
            tenant: Tenant instance
            setting_name: Name of the setting
            setting_value: New value for the setting
        
        Returns:
            bool: True if successful
        """
        try:
            from crm.models.system import TenantConfiguration
            
            config, created = TenantConfiguration.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'timezone': 'UTC',
                    'currency': 'USD',
                    'language': 'en'
                }
            )
            
            # Update the setting
            if hasattr(config, setting_name):
                setattr(config, setting_name, setting_value)
            else:
                # Store in custom_settings if not a standard field
                if not config.custom_settings:
                    config.custom_settings = {}
                config.custom_settings[setting_name] = setting_value
            
            config.save()
            
            # Invalidate cache
            cache_key = f"tenant_settings_{tenant.id}"
            cache.delete(cache_key)
            
            return True
        
        except Exception as e:
            print(f"Error updating tenant setting: {e}")
            return False
    
    def createstr, Any]) -> Dict[str, Any]:
        """
        Create new tenant with all necessary setup.
        
        Args: data
        
        Returns:
            Dict with creation results
        """
        try:
            with transaction.atomic():
                # Create tenant record
                tenant = TenantModel.objects.create(
                    schema_name=tenant_data['schema_name'],
                    name=tenant_data['name'],
                    domain_url=tenant_data.get('domain_url', f"{tenant_data['schema_name']}.example.com"),
                    is_active=True,
                    created_at=timezone.now()
                )
                
                # Create tenant schema
                tenant.create_schema(check_if_exists=True)
                
                # Switch to tenant schema and create initial data
                with self.tenant_context(tenant):
                    # Create default admin user
                    admin_user = User.objects.create_user(
                        username=tenant_data.get('admin_username', 'admin'),
                        email=tenant_data.get('admin_email'),
                        password=tenant_data.get('admin_password'),
                        is_staff=True,
                        is_superuser=True,
                        first_name=tenant_data.get('admin_first_name', ''),
                        last_name=tenant_data.get('admin_last_name', '')
                    )
                    
                    # Create tenant configuration
                    self._create_initial_tenant_config(tenant, tenant_data)
                    
                    # Create default CRM data
                    self._create_default_crm_data(tenant)
                
                return {
                    'success': True,
                    'tenant_id': tenant.id,
                    'schema_name': tenant.schema_name,
                    'admin_user_id': admin_user.id,
                    'message': 'Tenant created successfully'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_tenant(self, tenant: TenantModel, force: bool = False) -> Dict[str, Any]:
        """
        Delete tenant and all associated data.
        
        Args:
            tenant: Tenant to delete
            force: Force deletion even if there are active users
        
        Returns:
            Dict with deletion results
        """
        try:
            # Check if tenant can be deleted
            if not force:
                with self.tenant_context(tenant):
                    active_users = User.objects.filter(is_active=True).count()
                    if active_users > 0:
                        return {
                            'success': False,
                            'error': f'Cannot delete tenant with {active_users} active users'
                        }
            
            # Archive tenant first
            tenant.is_active = False
            tenant.deleted_at = timezone.now()
            tenant.save()
            
            # Delete schema (optional, can be done later for safety)
            if force:
                tenant.delete_schema()
                tenant.delete()
            
            # Clear cache
            self._clear_tenant_cache(tenant)
            
            return {
                'success': True,
                'message': 'Tenant deleted successfully' if force else 'Tenant archived successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tenant_analytics(self, tenant: TenantModel, 
                           date_range: tuple = None) -> Dict[str, Any]:
        """
        Get comprehensive tenant analytics.
        
        Args:
            tenant: Tenant instance
            date_range: Optional date range (start, end)
        
        Returns:
            Dict with analytics data
        """
        try:
            with self.tenant_context(tenant):
                analytics = {
                    'tenant_info': {
                        'id': tenant.id,
                        'name': tenant.name,
                        'schema_name': tenant.schema_name,
                        'created_at': tenant.created_at.isoformat() if tenant.created_at else None,
                        'is_active': tenant.is_active
                    },
                    'usage': self.get_tenant_usage(tenant).__dict__,
                    'limits': self.get_tenant_limits(tenant).__dict__,
                    'settings': self.get_tenant_settings(tenant).__dict__
                }
                
                # Add CRM-specific analytics
                try:
                    from crm.models.lead import Lead
                    from crm.models.opportunity import Opportunity
                    from crm.models.account import Account, Contact
                    from crm.models.activity import Activity
                    
                    # Date filtering
                    date_filter = {}
                    if date_range:
                        date_filter = {'created_at__range': date_range}
                    
                    analytics['crm_metrics'] = {
                        'leads': {
                            'total': Lead.objects.filter(**date_filter).count(),
                            'new_this_month': Lead.objects.filter(
                                created_at__gte=timezone.now().replace(day=1)
                            ).count(),
                            'converted': Lead.objects.filter(
                                **date_filter, 
                                status='CONVERTED'
                            ).count()
                        },
                        'opportunities': {
                            'total': Opportunity.objects.filter(**date_filter).count(),
                            'open': Opportunity.objects.filter(
                                **date_filter,
                                stage__in=['prospecting', 'qualification', 'proposal', 'negotiation']
                            ).count(),
                            'won': Opportunity.objects.filter(
                                **date_filter,
                                stage='closed_won'
                            ).count(),
                            'total_value': float(Opportunity.objects.filter(
                                **date_filter
                            ).aggregate(Sum('value'))['value__sum'] or 0)
                        },
                        'accounts': Account.objects.filter(**date_filter).count(),
                        'contacts': Contact.objects.filter(**date_filter).count(),
                        'activities_this_month': Activity.objects.filter(
                            created_at__gte=timezone.now().replace(day=1)
                        ).count()
                    }
                
                except Exception as e:
                    print(f"Error getting CRM metrics: {e}")
                    analytics['crm_metrics'] = {}
                
                return analytics
        
        except Exception as e:
            return {'error': str(e)}
    
    def _get_plan_limits(self, plan_name: str) -> TenantLimits:
        """Get resource limits for subscription plan."""
        plan_configs = {
            'basic': TenantLimits(
                max_users=5,
                max_leads=500,
                max_opportunities=200,
                max_contacts=1000,
                max_storage_mb=500,
                max_api_calls_per_day=1000,
                max_email_sends_per_month=1000,
                custom_fields_limit=10,
                automation_rules_limit=5,
                integrations_limit=2
            ),
            'professional': TenantLimits(
                max_users=25,
                max_leads=5000,
                max_opportunities=2000,
                max_contacts=10000,
                max_storage_mb=5000,
                max_api_calls_per_day=10000,
                max_email_sends_per_month=10000,
                custom_fields_limit=50,
                automation_rules_limit=20,
                integrations_limit=10
            ),
            'enterprise': TenantLimits(
                max_users=-1,  # Unlimited
                max_leads=-1,
                max_opportunities=-1,
                max_contacts=-1,
                max_storage_mb=50000,
                max_api_calls_per_day=100000,
                max_email_sends_per_month=100000,
                custom_fields_limit=-1,
                automation_rules_limit=-1,
                integrations_limit=-1
            )
        }
        
        return plan_configs.get(plan_name, plan_configs['basic'])
    
    def _calculate_storage_usage(self, tenant: TenantModel) -> float:
        """Calculate tenant storage usage in MB."""
        try:
            # This would calculate actual storage usage
            # For now, return a mock value
            return 125.5
        except Exception as e:
            print(f"Error calculating storage usage: {e}")
            return 0.0
    
    def _get_api_usage_today(self, tenant: TenantModel) -> int:
        """Get API usage for today."""
        try:
            from crm.models.system import APIUsageLog
            today = timezone.now().date()
            
            return APIUsageLog.objects.filter(
                tenant=tenant,
                created_at__date=today
            ).count()
        except Exception as e:
            return 0
    
    def _get_email_usage_month(self, tenant: TenantModel) -> int:
        """Get email usage for current month."""
        try:
            from crm.models.activity import EmailLog
            start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
            
            return EmailLog.objects.filter(
                tenant=tenant,
                sent_at__gte=start_of_month
            ).count()
        except Exception as e:
            return 0
    
    def _count_custom_fields(self, tenant: TenantModel) -> int:
        """Count custom fields for tenant."""
        try:
            from crm.models.system import CustomField
            return CustomField.objects.filter(tenant=tenant, is_active=True).count()
        except Exception as e:
            return 0
    
    def _count_automation_rules(self, tenant: TenantModel) -> int:
        """Count automation rules for tenant."""
        try:
            from crm.models.workflow import WorkflowRule
            return WorkflowRule.objects.filter(tenant=tenant, is_active=True).count()
        except Exception as e:
            return 0
    
    def _count_integrations(self, tenant: TenantModel) -> int:
        """Count active integrations for tenant."""
        try:
            from crm.models.workflow import Integration
            return Integration.objects.filter(tenant=tenant, is_active=True).count()
        except Exception as e:
            return 0
    
    def _create_initial_tenant_config(self, tenant: TenantModel,]):
        """Create initial tenant configuration."""
        try:
            from crm.models.system import TenantConfiguration
            
            TenantConfiguration.objects.create(
                tenant=tenant,
                timezone=tenant_data.get('timezone', 'UTC'),
                currency=tenant_data.get('currency', 'USD'),
                language=tenant_data.get('language', 'en'),
                company_name=tenant_data.get('company_name'),
                contact_email=tenant_data.get('admin_email'),
                industry=tenant_data.get('industry')
            )
        except Exception as e:
            print(f"Error creating tenant configuration: {e}")
    
    def _create_default_crm_data(self, tenant: TenantModel):
        """Create default CRM data for new tenant."""
        try:
            # Create default pipeline stages
            from crm.models.opportunity import PipelineStage
            
            default_stages = [
                ('Prospecting', 1, 10, False, False),
                ('Qualification', 2, 25, False, False),
                ('Needs Analysis', 3, 40, False, False),
                ('Proposal', 4, 60, False, False),
                ('Negotiation', 5, 80, False, False),
                ('Closed Won', 6, 100, True, True),
                ('Closed Lost', 7, 0, True, False)
            ]
            
            for name, order, probability, is_closed, is_won in default_stages:
                PipelineStage.objects.create(
                    name=name,
                    order=order,
                    probability=probability,
                    is_closed=is_closed,
                    is_won=is_won,
                    tenant=tenant
                )
            
            # Create default lead sources
            from crm.models.lead import LeadSource
            
            default_sources = [
                'Website', 'Referral', 'Cold Call', 'Email Campaign', 
                'Social Media', 'Trade Show', 'Advertisement', 'Partner'
            ]
            
            for source_name in default_sources:
                LeadSource.objects.create(
                    name=source_name,
                    tenant=tenant
                )
        
        except Exception as e:
            print(f"Error creating default
    
    def _clear_tenant_cache(self, tenant: TenantModel):
        """Clear all cached data for tenant."""
        cache_keys = [
            f"tenant_limits_{tenant.id}",
            f"tenant_usage_{tenant.id}",
            f"tenant_settings_{tenant.id}"
        ]
        
        cache.delete_many(cache_keys)


# Decorator for tenant-aware views
def tenant_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure view has valid tenant context.
    
    Usage:
        @tenant_required
        def my_view(request):
            # request.tenant will be available
            return response
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant_manager = TenantManager()
        tenant = tenant_manager.get_tenant_from_request(request)
        
        if not tenant:
            raise PermissionDenied("Valid tenant context required")
        
        request.tenant = tenant
        return view_func(request, *args, **kwargs)
    
    return wrapper


def enforce_tenant_limits(resource_type: str, additional_usage: int = 1):
    """
    Decorator to enforce tenant resource limits.
    
    Usage:
        @enforce_tenant_limits('leads')
        def create_lead(request):
            # This will check if tenant can create another lead
            return response
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if hasattr(request, 'tenant') and request.tenant:
                tenant_manager = TenantManager()
                limit_check = tenant_manager.check_tenant_limits(
                    request.tenant, resource_type, additional_usage
                )
                
                if not limit_check['allowed']:
                    raise PermissionDenied(limit_check['error'])
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Context manager for tenant operations
@contextmanager
def tenant_context(tenant: TenantModel):
    """
    Context manager for tenant operations.
    
    Usage:
        with tenant_context(tenant):
            leads = Lead.objects.all()  # Will query tenant's schema
    """
    tenant_manager = TenantManager()
    with tenant_manager.tenant_context(tenant):
        yield


# Convenience functions
def get_tenant_from_request(request) -> Optional[TenantModel]:
    """Get tenant from request."""
    tenant_manager = TenantManager()
    return tenant_manager.get_tenant_from_request(request)


def check_tenant_limits(tenant: TenantModel, resource_type: str, 
                       additional_usage: int = 1) -> Dict[str, Any]:
    """Check tenant resource limits."""
    tenant_manager = TenantManager()
    return tenant_manager.check_tenant_limits(tenant, resource_type, additional_usage)


def get_tenant_settings(tenant: TenantModel) -> TenantSettings:
    """Get tenant settings."""
    tenant_manager = TenantManager()
    return tenant_manager.get_tenant_settings(tenant)


def update_tenant_setting(tenant: TenantModel, setting_name: str, 
                         setting_value: Any) -> bool:
    """Update tenant setting."""
    tenant_manager = TenantManager()
    return tenant_manager.update_tenant_setting(tenant, setting_name, setting_value)


def get_tenant_analytics(tenant: TenantModel, date_range: tuple = None) -> Dict[str, Any]:
    """Get tenant analytics."""
    tenant_manager = TenantManager()
    return tenant_manager.get_tenant_analytics(tenant, date_range)


def create_demo_tenant(name: str, admin_email: str) -> Dict[str, Any]:
    """Create demo tenant with sample data."""
    tenant_manager = TenantManager()
    
    import uuid
    schema_name = f"demo_{uuid.uuid4().hex[:8]}"
    
    tenant_data = {
        'schema_name': schema_name,
        'name': f"Demo - {name}",
        'domain_url': f"{schema_name}.demo.example.com",
        'admin_email': admin_email,
        'admin_username': 'admin',
        'admin_password': 'demo123!',
        'admin_first_name': 'Demo',
        'admin_last_name': 'Admin',
        'company_name': name,
        'timezone': 'UTC',
        'currency': 'USD',
        'language': 'en'
    }
    
    result = tenant_manager.create_tenant(tenant_data)
    
    if result['success']:
        # Add sample data
        tenant = TenantModel.objects.get(id=result['tenant_id'])
        _create_sample_crm_data(tenant)
        
        result['demo_credentials'] = {
            'username': 'admin',
            'password': 'demo123!',
            'url': f"https://{schema_name}.demo.example.com"
        }
    
    return result


def _create_sample_crm_data(tenant: TenantModel):
    """Create sample CRM data for demo tenant."""
    try:
        with tenant_context(tenant):
            from crm.models.lead import Lead
            from crm.models.account import Account, Contact
            from crm.models.opportunity import Opportunity
            
            # Create sample accounts
            sample_accounts = [
                {'name': 'Acme Corporation', 'industry': 'Technology', 'phone': '+1-555-0101'},
                {'name': 'Global Solutions Inc', 'industry': 'Consulting', 'phone': '+1-555-0102'},
                {'name': 'Innovative Systems', 'industry': 'Software', 'phone': '+1-555-0103'}
            ]
            
            for account_data in sample_accounts:
                account = Account.objects.create(tenant=tenant, **account_data)
                
                # Create sample contacts for each account
                Contact.objects.create(
                    tenant=tenant,
                    account=account,
                    first_name='John',
                    last_name='Smith',
                    email=f'john@{account.name.lower().replace(" ", "")}.com',
                    title='CEO'
                )
            
            # Create sample leads
            sample_leads = [
                {'first_name': 'Jane', 'last_name': 'Doe', 'email': 'jane@example.com', 'company': 'Tech Startup'},
                {'first_name': 'Bob', 'last_name': 'Johnson', 'email': 'bob@sample.com', 'company': 'Marketing Agency'},
                {'first_name': 'Alice', 'last_name': 'Williams', 'email': 'alice@demo.com', 'company': 'Retail Chain'}
            ]
            
            for lead_data in sample_leads:
                Lead.objects.create(tenant=tenant, source='Website', score=65, **lead_data)
            
            # Create sample opportunities
            accounts = Account.objects.all()[:2]
            for i, account in enumerate(accounts):
                Opportunity.objects.create(
                    tenant=tenant,
                    name=f'Q4 Software Implementation - {account.name}',
                    account=account,
                    value=50000 + (i * 25000),
                    stage='qualification',
                    probability=40,
                    expected_close_date=timezone.now().date() + timedelta(days=60)
                )
    
    except Exception as e:
        print(f"Error creating sample CRM