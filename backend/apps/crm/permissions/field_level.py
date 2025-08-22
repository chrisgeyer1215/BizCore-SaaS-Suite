# ============================================================================
# backend/apps/crm/permissions/field_level.py - Field-Level Security
# ============================================================================

from typing import Dict, List, Any, Optional, Set
from django.db import models
from rest_framework import serializers
import logging

from .base import ObjectLevelPermission

logger = logging.getLogger(__name__)


class FieldLevelPermission(ObjectLevelPermission):
    """
    Field-level access control with granular data protection
    """
    
    # Field security classifications
    FIELD_SECURITY_LEVELS = {
        'PUBLIC': 0,
        'INTERNAL': 1,
        'CONFIDENTIAL': 2,
        'RESTRICTED': 3,
        'TOP_SECRET': 4
    }
    
    # Model field security configurations
    FIELD_SECURITY_CONFIG = {
        'Lead': {
            'email': 'INTERNAL',
            'phone': 'INTERNAL',
            'notes': 'CONFIDENTIAL',
            'source_details': 'RESTRICTED',
            'score': 'CONFIDENTIAL'
        },
        'Account': {
            'revenue': 'CONFIDENTIAL',
            'employee_count': 'INTERNAL',
            'internal_notes': 'RESTRICTED',
            'credit_rating': 'CONFIDENTIAL'
        },
        'Opportunity': {
            'amount': 'CONFIDENTIAL',
            'probability': 'INTERNAL',
            'competitive_notes': 'RESTRICTED',
            'internal_stage_notes': 'CONFIDENTIAL'
        },
        'Contact': {
            'personal_email': 'CONFIDENTIAL',
            'mobile_phone': 'CONFIDENTIAL',
            'salary': 'RESTRICTED',
            'personal_notes': 'CONFIDENTIAL'
        }
    }
    
    # Role-based field access matrix
    ROLE_FIELD_ACCESS = {
        'SYSTEM_ADMIN': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'],
        'TENANT_ADMIN': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'],
        'SALES_MANAGER': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL'],
        'SALES_REP': ['PUBLIC', 'INTERNAL'],
        'MARKETING_MANAGER': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL'],
        'MARKETING_USER': ['PUBLIC', 'INTERNAL'],
        'CUSTOMER_SUCCESS': ['PUBLIC', 'INTERNAL'],
        'ANALYST': ['PUBLIC', 'INTERNAL'],
        'VIEWER': ['PUBLIC']
    }
    
    def filter_serializer_fields(self, serializer: serializers.Serializer, 
                                request, obj=None) -> serializers.Serializer:
        """
        Filter serializer fields based on user permissions
        """
        try:
            if not hasattr(request, 'user_roles'):
                return serializer
            
            user_roles = request.user_roles
            model_name = obj.__class__.__name__ if obj else serializer.Meta.model.__name__
            
            # Get accessible field security levels for user roles
            accessible_levels = set()
            for role in user_roles:
                role_access = self.ROLE_FIELD_ACCESS.get(role, ['PUBLIC'])
                accessible_levels.update(role_access)
            
            # Filter fields based on security levels
            fields_to_remove = []
            model_field_config = self.FIELD_SECURITY_CONFIG.get(model_name, {})
            
            for field_name, field in serializer.fields.items():
                field_security_level = model_field_config.get(field_name, 'PUBLIC')
                
                if field_security_level not in accessible_levels:
                    fields_to_remove.append(field_name)
                    
                # Additional context-based filtering
                elif not self._check_field_context_access(
                    request, obj, field_name, field_security_level
                ):
                    fields_to_remove.append(field_name)
            
            # Remove inaccessible fields
            for field_name in fields_to_remove:
                serializer.fields.pop(field_name, None)
            
            return serializer
            
        except Exception as e:
            logger.error(f"Field filtering failed: {e}")
            return serializer
    
    def _check_field_context_access(self, request, obj, field_name: str, 
                                   security_level: str) -> bool:
        """Check field access based on context"""
        try:
            # Owner always has access to their own data
            if obj and hasattr(obj, 'created_by') and obj.created_by == request.user:
                return True
            
            # Time-based restrictions for sensitive fields
            if security_level in ['RESTRICTED', 'TOP_SECRET']:
                if not self._check_business_hours_access(request):
                    return False
            
            # IP-based restrictions for confidential fields
            if security_level in ['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET']:
                if not self._check_trusted_ip_access(request):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Field context access check failed: {e}")
            return False
    
    def _check_business_hours_access(self, request) -> bool:
        """Check if access is during business hours"""
        try:
            from django.utils import timezone
            current_hour = timezone.now().hour
            return 9 <= current_hour <= 17
            
        except Exception as e:
            logger.error(f"Business hours check failed: {e}")
            return True
    
    def _check_trusted_ip_access(self, request) -> bool:
        """Check if request is from trusted IP"""
        try:
            client_ip = self._get_client_ip(request)
            
            # Get tenant's trusted IP ranges
            if hasattr(request, 'tenant'):
                tenant_config = getattr(request.tenant, 'security_config', {})
                trusted_ips = tenant_config.get('trusted_ips', [])
                
                if trusted_ips and client_ip not in trusted_ips:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Trusted IP check failed: {e}")
            return True


class SensitiveDataPermission(FieldLevelPermission):
    """
    Enhanced sensitive data protection with compliance features
    """
    
    # PII (Personally Identifiable Information) fields
    PII_FIELDS = {
        'Lead': ['email', 'phone', 'first_name', 'last_name', 'address'],
        'Account': ['billing_address', 'phone', 'fax'],
        'Contact': ['email', 'phone', 'mobile_phone', 'home_phone', 'address', 'birth_date'],
        'Activity': ['notes', 'description']  # May contain PII
    }
    
    # Financial data fields
    FINANCIAL_FIELDS = {
        'Account': ['revenue', 'credit_limit', 'credit_rating'],
        'Opportunity': ['amount', 'cost', 'margin'],
        'Product': ['cost', 'price']
    }
    
    # Compliance requirements
    COMPLIANCE_RULES = {
        'GDPR': {
            'applicable_fields': 'PII_FIELDS',
            'require_consent': True,
            'allow_deletion': True,
            'audit_access': True
        },
        'SOX': {
            'applicable_fields': 'FINANCIAL_FIELDS',
            'require_approval': True,
            'audit_changes': True,
            'segregation_of_duties': True
        },
        'HIPAA': {
            'applicable_fields': ['medical_notes', 'health_status'],
            'encryption_required': True,
            'access_logging': True,
            'breach_notification': True
        }
    }
    
    def filter_sensitive request, obj=None) -> Dict:
        """Filter sensitive data based on compliance and permissions"""
        try:
            filtered_data = data.copy()
            model_name = obj.__class__.__name__ if obj else 'Unknown'
            
            # Apply PII filtering
            filtered_data = self._filter_pii_data(filtered_data, request, model_name)
            
            # Apply financial data filtering
            filtered_data = self._filter_financial_data(filtered_data, request, model_name)
            
            # Apply compliance-specific filtering
            filtered_data = self._apply_compliance_filtering(filtered_data, request, model_name)
            
            # Audit sensitive data access
            self._audit_sensitive_data_access(request, obj, filtered_data)
            
            return filtered_data
            
        except Exception as e:
            logger.error(f"Sensitive data filtering failed: {e}")
            return data
    
    def _filter_pii_data( model_name: str) -> Dict:
        """Filter PII data based on permissions"""
        try:
            pii_fields = self.PII_FIELDS.get(model_name, [])
            
            # Check if user has PII access permission
            if not self._has_pii_access_permission(request):
                for field in pii_fields:._mask_pii_field(data[field], field)
            
            return data
            
        except Exception as e:
            logger.error(f"PII filtering failed: {e}")
            return data
    
    def _filter_financial_data(self, data: Dict, request, model_name: str) -> Dict:
        """Filter financial data based on permissions"""
        try:
            financial_fields = self.FINANCIAL_FIELDS.get(model_name, [])
            
            # Check if user has financial data access
            if not self._has_financial_access_permission(request):
                for field in financial_fields:
                        data[field] = self._mask_financial_field(data[field])
            
            return data
            
        except Exception as e:
            logger.error(f"Financial data filtering failed: {e}")
            return data
    
    def _apply_compliance_filtering(self_name: str) -> Dict:
        """Apply compliance-specific filtering"""
        try:
            # Get tenant's compliance requirements
            if hasattr(request, 'tenant'):
                compliance_config = getattr(request.tenant, 'compliance_config', {})
                
                for compliance_type, rules in self.COMPLIANCE_RULES.items():
                    if compliance_config.get(compliance_type, {}).get('enabled', False):
                        data = self._apply_compliance_rule(data, request, compliance_type, rules)
            
            return data
            
        except Exception as e:
            logger.error(f"Compliance filtering failed: {e}")
            return data
    
    def _has_pii_access_permission(self, request) -> bool:
        """Check if user has PII access permission"""
        try:
            if not hasattr(request, 'user_roles'):
                return False
            
            pii_access_roles = ['SYSTEM_ADMIN', 'TENANT_ADMIN', 'HR_MANAGER', 'PRIVACY_OFFICER']
            return any(role in request.user_roles for role in pii_access_roles)
            
        except Exception as e:
            logger.error(f"PII access check failed: {e}")
            return False
    
    def _has_financial_access_permission(self, request) -> bool:
        """Check if user has financial data access permission"""
        try:
            if not hasattr(request, 'user_roles'):
                return False
            
            financial_access_roles = ['SYSTEM_ADMIN', 'TENANT_ADMIN', 'FINANCE_MANAGER', 'SALES_MANAGER']
            return any(role in request.user_roles for role in financial_access_roles)
            
        except Exception as e:
            logger.error(f"Financial access check failed: {e}")
            return False
    
    def _mask_pii_field(self, value: Any, field_name: str) -> str:
        """Mask PII field value"""
        try:
            if not value:
                return value
            
            if field_name in ['email']:
                # Mask email: john.doe@example.com -> j***@example.com
                if '@' in str(value):
                    local, domain = str(value).split('@', 1)
                    masked_local = local[0] + '*' * (len(local) - 1)
                    return f"{masked_local}@{domain}"
            
            elif field_name in ['phone', 'mobile_phone']:
                # Mask phone: +1234567890 -> +***-***-7890
                phone_str = str(value)
                if len(phone_str) >= 4:
                    return '*' * (len(phone_str) - 4) + phone_str[-4:]
            
            elif field_name in ['first_name', 'last_name']:
                # Mask names: John -> J***
                name_str = str(value)
                return name_str[0] + '*' * (len(name_str) - 1) if name_str else ''
            
            # Generic masking for other fields
            return '*' * len(str(value))
            
        except Exception as e:
            logger.error(f"PII masking failed: {e}")
            return '***'
    
    def _mask_financial_field(self, value: Any) -> str:
        """Mask financial field value"""
        try:
            if not value:
                return value
            
            # Convert to string and mask most digits
            value_str = str(value)
            if len(value_str) >= 2:
                return '*' * (len(value_str) - 2) + value_str[-2:]
            else:
                return '**'
                
        except Exception as e:
            logger.error(f"Financial masking failed: {e}")
            return '***'
    
    def _audit_sensitive_data_access(self Dict):
        """Audit sensitive data access for compliance"""
        try:
            from ..models import DataAccessLog
            
            sensitive_fields = []
            model_name = obj.__class__.__name__ if obj else 'Unknown'
            
            # Identify which sensitive fields were accessed
            pii_fields = self.PII_FIELDS.get(model_name, [])
            financial_fields = self.FINANCIAL_FIELDS.get(model_name, [])
            
            for field in accessed_data.keys():
                if field in pii_fields:
                    sensitive_fields.append(f"PII:{field}")
                elif field in financial_fields:
                    sensitive_fields.append(f"FINANCIAL:{field}")
            
            if sensitive_fields:
                DataAccessLog.objects.create(
                    user=request.user,
                    tenant=getattr(request, 'tenant', None),
                    object_type=model_name,
                    object_id=obj.id if obj and hasattr(obj, 'id') else None,
                    sensitive_fields_accessed=sensitive_fields,
                    access_timestamp=timezone.now(),
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    access_reason='API_ACCESS'
                )
            
        except Exception as e:
            logger.error(f"Sensitive data audit logging failed: {e}")