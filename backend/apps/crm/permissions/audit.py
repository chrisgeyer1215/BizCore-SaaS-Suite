# ============================================================================
# backend/apps/crm/permissions/audit.py - Comprehensive Audit and Compliance Permissions
# ============================================================================

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
import json
import logging

from .base import ObjectLevelPermission

logger = logging.getLogger(__name__)


class AuditPermission(ObjectLevelPermission):
    """
    Comprehensive audit trail and compliance permission system
    """
    
    # Audit event classifications
    AUDIT_EVENT_TYPES = {
        'AUTHENTICATION': ['login', 'logout', 'password_change', 'mfa_setup', 'account_lockout'],
        'AUTHORIZATION': ['permission_granted', 'permission_denied', 'role_changed', 'access_escalation'],
        'DATA_ACCESS': ['view', 'search', 'export', 'print', 'download'],
        'DATA_MODIFICATION': ['create', 'update', 'delete', 'bulk_update', 'import'],
        'SYSTEM_ADMIN': ['user_created', 'user_deleted', 'settings_changed', 'integration_modified'],
        'COMPLIANCE': ['gdpr_request', 'data_retention', 'consent_updated', 'breach_reported'],
        'SECURITY': ['suspicious_activity', 'failed_login', 'ip_blocked', 'session_terminated']
    }
    
    # Compliance frameworks configuration
    COMPLIANCE_FRAMEWORKS = {
        'GDPR': {
            'enabled': True,
            'retention_period_days': 2555,  # 7 years
            'consent_required': True,
            'right_to_erasure': True,
            'data_portability': True,
            'breach_notification_hours': 72,
            'auditable_events': ['data_access', 'consent_change', 'data_export', 'data_deletion']
        },
        'SOX': {
            'enabled': True,
            'retention_period_days': 2555,  # 7 years
            'segregation_of_duties': True,
            'financial_controls': True,
            'change_approval': True,
            'auditable_events': ['financial_data_access', 'financial_report', 'controls_change']
        },
        'HIPAA': {
            'enabled': False,  # Enable if handling healthcare data
            'retention_period_days': 2190,  # 6 years
            'encryption_required': True,
            'access_logging': True,
            'breach_notification': True,
            'auditable_events': ['phi_access', 'patient_record', 'medical_data']
        },
        'PCI_DSS': {
            'enabled': False,  # Enable if handling payment data
            'retention_period_days': 365,  # 1 year minimum
            'encryption_required': True,
            'access_restrictions': True,
            'vulnerability_management': True,
            'auditable_events': ['payment_data_access', 'card_data', 'transaction']
        }
    }
    
    # Data sensitivity classification for audit purposes
    DATA_SENSITIVITY_AUDIT = {
        'PUBLIC': {
            'audit_level': 'basic',
            'retention_days': 365,
            'access_logging': False
        },
        'INTERNAL': {
            'audit_level': 'standard',
            'retention_days': 1095,  # 3 years
            'access_logging': True
        },
        'CONFIDENTIAL': {
            'audit_level': 'detailed',
            'retention_days': 2555,  # 7 years
            'access_logging': True,
            'approval_required': False
        },
        'RESTRICTED': {
            'audit_level': 'comprehensive',
            'retention_days': 2555,
            'access_logging': True,
            'approval_required': True,
            'segregation_required': True
        },
        'TOP_SECRET': {
            'audit_level': 'maximum',
            'retention_days': 3650,  # 10 years
            'access_logging': True,
            'approval_required': True,
            'segregation_required': True,
            'dual_person_control': True
        }
    }
    
    def has_permission(self, request, view) -> bool:
        """Enhanced permission with comprehensive audit logging"""
        try:
            # Parent permission check
            parent_result = super().has_permission(request, view)
            
            # Audit the permission check
            self._audit_permission_check(request, view, parent_result)
            
            # Additional compliance checks
            if parent_result:
                compliance_result = self._check_compliance_requirements(request, view)
                if not compliance_result:
                    self._audit_compliance_violation(request, view)
                    return False
            
            return parent_result
            
        except Exception as e:
            self._audit_system_error(request, view, str(e))
            logger.error(f"Audit permission check failed: {e}", exc_info=True)
            return False
    
    def has_object_permission(self, request, view, obj) -> bool:
        """Enhanced object permission with detailed audit logging"""
        try:
            # Parent object permission check
            parent_result = super().has_object_permission(request, view, obj)
            
            # Audit the object access attempt
            self._audit_object_access(request, view, obj, parent_result)
            
            # Check data sensitivity requirements
            if parent_result:
                sensitivity_result = self._check_data_sensitivity_compliance(request, view, obj)
                if not sensitivity_result:
                    self._audit_sensitivity_violation(request, view, obj)
                    return False
            
            return parent_result
            
        except Exception as e:
            self._audit_system_error(request, view, str(e), obj)
            logger.error(f"Audit object permission check failed: {e}", exc_info=True)
            return False
    
    def _audit_permission_check(self, request, view, result: bool):
        """Audit permission check with detailed context"""
        try:
            audit_data = {
                'event_type': 'AUTHORIZATION',
                'event_subtype': 'permission_granted' if result else 'permission_denied',
                'user_id': request.user.id if request.user else None,
                'username': request.user.username if request.user else None,
                'tenant_id': getattr(request, 'tenant', {}).id if hasattr(request, 'tenant') else None,
                'view_name': view.__class__.__name__,
                'method': request.method,
                'path': request.path,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now(),
                'result': result,
                'session_id': request.session.session_key if hasattr(request, 'session') else None,
                'request_id': getattr(request, 'id', None),
                'user_roles': getattr(request, 'user_roles', []),
                'geographic_location': self._get_geographic_context(request)
            }
            
            # Store audit log
            self._store_audit_log(audit_data)
            
            # Check for compliance reporting requirements
            self._check_compliance_reporting(audit_data)
            
        except Exception as e:
            logger.error(f"Permission check audit failed: {e}")
    
    def _audit_object_access(self, request, view, obj, result: bool):
        """Audit object-level access with data classification"""
        try:
            # Determine data sensitivity
            data_sensitivity = self._classify_object_sensitivity(obj)
            
            audit_data = {
                'event_type': 'DATA_ACCESS',
                'event_subtype': self._determine_access_type(view, request.method),
                'user_id': request.user.id if request.user else None,
                'tenant_id': getattr(request, 'tenant', {}).id if hasattr(request, 'tenant') else None,
                'object_type': obj.__class__.__name__,
                'object_id': getattr(obj, 'id', None),
                'data_sensitivity': data_sensitivity,
                'result': result,
                'timestamp': timezone.now(),
                'ip_address': self._get_client_ip(request),
                'method': request.method,
                'path': request.path,
                'fields_accessed': self._get_accessed_fields(request, view),
                'business_context': self._get_business_context(obj),
                'data_classification': self._get_data_classification(obj)
            }
            
            # Enhanced logging for sensitive data
            audit_config = self.DATA_SENSITIVITY_AUDIT.get(data_sensitivity, {})
            
            if audit_config.get('access_logging', False):
                # Store detailed audit log
                self._store_detailed_audit_log(audit_data)
                
                # Real-time monitoring for high-sensitivity data
                if data_sensitivity in ['RESTRICTED', 'TOP_SECRET']:
                    self._trigger_real_time_monitoring(audit_data)
            
        except Exception as e:
            logger.error(f"Object access audit failed: {e}")
    
    def _check_compliance_requirements(self, request, view) -> bool:
        """Check compliance framework requirements"""
        try:
            user_roles = getattr(request, 'user_roles', [])
            
            # Check each enabled compliance framework
            for framework, config in self.COMPLIANCE_FRAMEWORKS.items():
                if not config.get('enabled', False):
                    continue
                
                if not self._check_framework_compliance(request, view, framework, config):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Compliance requirement check failed: {e}")
            return True  # Default to allow on error
    
    def _check_framework_compliance(self, request, view, framework: str, config: Dict) -> bool:
        """Check specific compliance framework requirements"""
        try:
            if framework == 'GDPR':
                return self._check_gdpr_compliance(request, view, config)
            elif framework == 'SOX':
                return self._check_sox_compliance(request, view, config)
            elif framework == 'HIPAA':
                return self._check_hipaa_compliance(request, view, config)
            elif framework == 'PCI_DSS':
                return self._check_pci_compliance(request, view, config)
            
            return True
            
        except Exception as e:
            logger.error(f"Framework compliance check failed for {framework}: {e}")
            return True
    
    def _check_gdpr_compliance(self, request, view, config: Dict) -> bool:
        """Check GDPR compliance requirements"""
        try:
            # Check if this is a data subject request
            if self._is_data_subject_request(request, view):
                # Ensure proper authentication and consent
                if not self._verify_data_subject_identity(request):
                    return False
            
            # Check for consent requirements
            if config.get('consent_required', False):
                if not self._check_data_processing_consent(request):
                    return False
            
            # Check data retention policies
            if not self._check_data_retention_compliance(request, config):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"GDPR compliance check failed: {e}")
            return True
    
    def _check_sox_compliance(self, request, view, config: Dict) -> bool:
        """Check SOX compliance requirements"""
        try:
            # Check if this involves financial data
            if self._involves_financial_data(request, view):
                # Check segregation of duties
                if config.get('segregation_of_duties', False):
                    if not self._check_segregation_of_duties(request):
                        return False
                
                # Check for required approvals
                if config.get('change_approval', False):
                    if not self._check_required_approvals(request, view):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"SOX compliance check failed: {e}")
            return True
    
    def _store_audit_log(self, audit_data):
        """Store audit log with proper retention and security"""
        try:
            from ..models import AuditLog
            
            # Create audit log entry
            audit_log = AuditLog.objects.create(
                event_type=audit_data['event_type'],
                event_subtype=audit_data.get('event_subtype', ''),
                user_id=audit_data.get('user_id'),
                tenant_id=audit_data.get('tenant_id'),
                object_type=audit_data.get('object_type', ''),
                object_id=audit_data.get('object_id'),
                timestamp=audit_data['timestamp'],
                ip_address=audit_data.get('ip_address', ''),
                user_agent=audit_data.get('user_agent', ''),
                request_path=audit_data.get('path', ''),
                request_method=audit_data.get('method', ''),
                result=audit_data.get('result', False),
                session_id=audit_data.get('session_id', ''),
                additional_data=json.dumps({
                    k: v for k, v in audit_data.items() 
                    if k not in ['timestamp', 'user_id', 'tenant_id']
                })
            )
            
            # Set retention period based on data sensitivity
            sensitivity = audit_data.get('data_sensitivity', 'INTERNAL')
            retention_config = self.DATA_SENSITIVITY_AUDIT.get(sensitivity, {})
            retention_days = retention_config.get('retention_days', 1095)
            
            audit_log.retention_until = timezone.now() + timedelta(days=retention_days)
            audit_log.save()
            
        except Exception as e:
            logger.error(f"Audit log storage failed: {e}")
    
    def _classify_object_sensitivity(self, obj) -> str:
        """Classify object data sensitivity for audit purposes"""
        try:
            # Check for PII indicators
            pii_fields = ['email', 'phone', 'address', 'ssn', 'tax_id']
            has_pii = any(hasattr(obj, field) and getattr(obj, field) for field in pii_fields)
            
            # Check for financial data
            financial_fields = ['amount', 'revenue', 'salary', 'credit_score']
            has_financial = any(hasattr(obj, field) and getattr(obj, field) for field in financial_fields)
            
            # Check for explicit classification
            if hasattr(obj, 'data_classification'):
                return obj.data_classification
            
            # Infer from content
            if has_pii and has_financial:
                return 'RESTRICTED'
            elif has_financial:
                return 'CONFIDENTIAL'
            elif has_pii:
                return 'CONFIDENTIAL'
            else:
                return 'INTERNAL'
                
        except Exception as e:
            logger.error(f"Object sensitivity classification failed: {e}")
            return 'INTERNAL'
    
    def _get_business_context(self, obj) -> Dict:
        """Get business context for audit logging"""
        try:
            context = {
                'object_type': obj.__class__.__name__,
                'created_date': getattr(obj, 'created_at', None),
                'last_modified': getattr(obj, 'updated_at', None)
            }
            
            # Add object-specific context
            if hasattr(obj, 'amount'):
                context['financial_value'] = float(obj.amount)
            
            if hasattr(obj, 'status'):
                context['status'] = obj.status
            
            if hasattr(obj, 'stage'):
                context['stage'] = obj.stage.name if obj.stage else None
            
            return context
            
        except Exception as e:
            logger.error(f"Business context extraction failed: {e}")
            return {}
    
    def _trigger_real_time_monitoring(self, audit_data):
        """Trigger real-time monitoring for high-sensitivity access"""
        try:
            # Send to security monitoring system
            monitoring_alert = {
                'alert_type': 'HIGH_SENSITIVITY_ACCESS',
                'severity': 'HIGH',
                'timestamp': audit_data['timestamp'].isoformat(),
                'user_id': audit_data.get('user_id'),
                'object_type': audit_data.get('object_type'),
                'data_sensitivity': audit_data.get('data_sensitivity'),
                'ip_address': audit_data.get('ip_address'),
                'geographic_location': audit_data.get('geographic_location')
            }
            
            # Queue for immediate processing
            from ..tasks import process_security_alert
            process_security_alert.delay(monitoring_alert)
            
        except Exception as e:
            logger.error(f"Real-time monitoring trigger failed: {e}")


class CompliancePermission(AuditPermission):
    """
    Enhanced compliance-specific permission system
    """
    
    def has_permission(self, request, view) -> bool:
        """Compliance-enhanced permission checking"""
        try:
            # Parent audit permission check
            if not super().has_permission(request, view):
                return False
            
            # Additional compliance validations
            if not self._validate_compliance_context(request, view):
                return False
            
            # Check for regulatory restrictions
            if not self._check_regulatory_restrictions(request, view):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Compliance permission check failed: {e}")
            return False
    
    def _validate_compliance_context(self, request, view) -> bool:
        """Validate compliance context for the request"""
        try:
            # Check if user has required compliance training
            if not self._check_compliance_training(request.user):
                self._audit_compliance_violation(request, view, 'training_required')
                return False
            
            # Check for active compliance violations
            if self._has_active_violations(request.user):
                self._audit_compliance_violation(request, view, 'active_violations')
                return False
            
            # Check compliance certification status
            if not self._check_compliance_certification(request.user):
                self._audit_compliance_violation(request, view, 'certification_expired')
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Compliance context validation failed: {e}")
            return True
    
    def _check_regulatory_restrictions(self, request, view) -> bool:
        """Check for regulatory restrictions"""
        try:
            # Get user's jurisdiction and applicable regulations
            user_jurisdiction = self._get_user_jurisdiction(request.user)
            applicable_regulations = self._get_applicable_regulations(user_jurisdiction)
            
            for regulation in applicable_regulations:
                if not self._check_regulation_compliance(request, view, regulation):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Regulatory restriction check failed: {e}")
            return True
    
    def _audit_compliance_violation(self, request, view, violation_type: str = None):
        """Audit compliance violations with detailed context"""
        try:
            violation_data = {
                'event_type': 'COMPLIANCE',
                'event_subtype': 'compliance_violation',
                'violation_type': violation_type,
                'user_id': request.user.id if request.user else None,
                'tenant_id': getattr(request, 'tenant', {}).id if hasattr(request, 'tenant') else None,
                'view_name': view.__class__.__name__,
                'timestamp': timezone.now(),
                'ip_address': self._get_client_ip(request),
                'severity': 'HIGH',
                'requires_investigation': True,
                'regulatory_framework': self._identify_applicable_frameworks(request)
            }
            
            # Store violation log
            self._store_compliance_violation_log(violation_data)
            
            # Trigger compliance alert
            self._trigger_compliance_alert(violation_data)
            
        except Exception as e:
            logger.error(f"Compliance violation audit failed: {e}")