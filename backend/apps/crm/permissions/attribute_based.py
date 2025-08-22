# ============================================================================
# backend/apps/crm/permissions/attribute_based.py - Attribute-Based Access Control (ABAC)
# ============================================================================

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
import logging

from .base import ObjectLevelPermission

logger = logging.getLogger(__name__)


class AttributeBasedPermission(ObjectLevelPermission):
    """
    Advanced Attribute-Based Access Control (ABAC) with dynamic policy evaluation
    """
    
    # ABAC Policy Engine - Defines access rules based on attributes
    ABAC_POLICIES = {
        'high_value_opportunity_access': {
            'description': 'Access to high-value opportunities requires senior role or ownership',
            'conditions': [
                {
                    'subject_attributes': ['user.role', 'user.experience_level', 'user.performance_score'],
                    'resource_attributes': ['opportunity.amount', 'opportunity.stage'],
                    'environment_attributes': ['current_time', 'access_location'],
                    'action': 'view',
                    'rule': 'self._evaluate_high_value_opportunity_access'
                }
            ]
        },
        'sensitive_lead_information': {
            'description': 'PII and scoring data requires specific permissions',
            'conditions': [
                {
                    'subject_attributes': ['user.role', 'user.clearance_level', 'user.department'],
                    'resource_attributes': ['lead.data_sensitivity', 'lead.source_type'],
                    'environment_attributes': ['request_origin', 'time_of_day'],
                    'action': 'view_sensitive',
                    'rule': 'self._evaluate_sensitive_lead_access'
                }
            ]
        },
        'financial_data_access': {
            'description': 'Financial data requires finance role or management approval',
            'conditions': [
                {
                    'subject_attributes': ['user.role', 'user.department', 'user.clearance_level'],
                    'resource_attributes': ['data.financial_classification', 'data.confidentiality'],
                    'environment_attributes': ['business_hours', 'secure_network'],
                    'action': 'view_financial',
                    'rule': 'self._evaluate_financial_data_access'
                }
            ]
        },
        'territory_management': {
            'description': 'Territory changes require management role and geographic authorization',
            'conditions': [
                {
                    'subject_attributes': ['user.role', 'user.geographic_authority', 'user.management_level'],
                    'resource_attributes': ['territory.region', 'territory.importance', 'territory.revenue'],
                    'environment_attributes': ['change_magnitude', 'approval_workflow'],
                    'action': 'modify_territory',
                    'rule': 'self._evaluate_territory_management_access'
                }
            ]
        },
        'customer_data_retention': {
            'description': 'Customer data access based on retention policies and consent',
            'conditions': [
                {
                    'subject_attributes': ['user.role', 'user.data_handler_certification'],
                    'resource_attributes': ['customer.consent_status', 'customer.data_age', 'customer.jurisdiction'],
                    'environment_attributes': ['retention_period', 'legal_hold_status'],
                    'action': 'access_customer_data',
                    'rule': 'self._evaluate_customer_data_retention'
                }
            ]
        }
    }
    
    def has_object_permission(self, request, view, obj) -> bool:
        """Enhanced object permission with ABAC policy evaluation"""
        try:
            # First, run standard object-level checks
            if not super().has_object_permission(request, view, obj):
                return False
            
            # Extract attributes for ABAC evaluation
            subject_attributes = self._extract_subject_attributes(request.user, request)
            resource_attributes = self._extract_resource_attributes(obj)
            environment_attributes = self._extract_environment_attributes(request, view)
            action = self._determine_action(view, request.method)
            
            # Evaluate applicable ABAC policies
            return self._evaluate_abac_policies(
                subject_attributes, resource_attributes, 
                environment_attributes, action, request, view, obj
            )
            
        except Exception as e:
            logger.error(f"ABAC permission evaluation failed: {e}", exc_info=True)
            return False
    
    def _extract_subject_attributes(self, user, request) -> Dict:
        """Extract subject (user) attributes for ABAC evaluation"""
        try:
            attributes = {
                'user_id': user.id,
                'username': user.username,
                'role': getattr(request, 'user_roles', []),
                'department': getattr(user, 'department', None),
                'experience_level': self._calculate_user_experience_level(user),
                'performance_score': self._get_user_performance_score(user),
                'clearance_level': getattr(user, 'security_clearance', 'STANDARD'),
                'management_level': self._get_management_level(user),
                'geographic_authority': self._get_geographic_authority(user),
                'data_handler_certification': self._has_data_handler_certification(user),
                'last_training_date': getattr(user, 'last_security_training', None),
                'account_creation_date': user.date_joined,
                'recent_violations': self._get_recent_security_violations(user),
                'active_sessions': self._get_active_session_count(user)
            }
            
            return attributes
            
        except Exception as e:
            logger.error(f"Subject attribute extraction failed: {e}")
            return {'user_id': user.id if user else None}
    
    def _extract_resource_attributes(self, obj) -> Dict:
        """Extract resource (object) attributes for ABAC evaluation"""
        try:
            attributes = {
                'object_type': obj.__class__.__name__,
                'object_id': getattr(obj, 'id', None),
                'created_date': getattr(obj, 'created_at', None),
                'last_modified': getattr(obj, 'updated_at', None),
                'owner': getattr(obj, 'created_by', None),
                'assigned_to': getattr(obj, 'assigned_to', None),
                'tenant': getattr(obj, 'tenant', None)
            }
            
            # Object-specific attributes
            if hasattr(obj, 'amount'):  # Financial objects
                attributes.update({
                    'amount': obj.amount,
                    'financial_classification': self._classify_financial_amount(obj.amount),
                    'requires_approval': obj.amount > 50000,
                    'currency': getattr(obj, 'currency', 'USD')
                })
            
            if hasattr(obj, 'status'):  # Status-based objects
                attributes.update({
                    'status': obj.status,
                    'is_active': getattr(obj, 'is_active', True),
                    'lifecycle_stage': self._determine_lifecycle_stage(obj)
                })
            
            if hasattr(obj, 'source'):  # Lead-like objects
                attributes.update({
                    'source_type': getattr(obj.source, 'type', None) if obj.source else None,
                    'data_sensitivity': self._assess_data_sensitivity(obj),
                    'lead_score': getattr(obj, 'score', 0)
                })
            
            # Privacy and compliance attributes
            attributes.update({
                'contains_pii': self._contains_pii(obj),
                'data_classification': self._classify_data_sensitivity(obj),
                'retention_period': self._calculate_retention_period(obj),
                'geographic_restrictions': self._get_geographic_restrictions(obj)
            })
            
            return attributes
            
        except Exception as e:
            logger.error(f"Resource attribute extraction failed: {e}")
            return {'object_type': obj.__class__.__name__ if obj else 'Unknown'}
    
    def _extract_environment_attributes(self, request, view) -> Dict:
        """Extract environment attributes for ABAC evaluation"""
        try:
            current_time = timezone.now()
            
            attributes = {
                'current_time': current_time,
                'time_of_day': current_time.hour,
                'day_of_week': current_time.weekday(),
                'is_business_hours': 9 <= current_time.hour <= 17,
                'is_weekend': current_time.weekday() >= 5,
                'client_ip': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_method': request.method,
                'request_origin': self._determine_request_origin(request),
                'access_location': self._determine_access_location(request),
                'secure_connection': request.is_secure(),
                'session_age': self._calculate_session_age(request),
                'concurrent_sessions': self._count_concurrent_sessions(request.user),
                'recent_failed_attempts': self._count_recent_failed_attempts(request.user),
                'network_type': self._determine_network_type(request),
                'device_type': self._determine_device_type(request),
                'risk_score': self._calculate_request_risk_score(request),
                'tenant_security_level': self._get_tenant_security_level(request)
            }
            
            return attributes
            
        except Exception as e:
            logger.error(f"Environment attribute extraction failed: {e}")
            return {'current_time': timezone.now()}
    
    def _evaluate_abac_policies(self, subject_attrs: Dict, resource_attrs: Dict,
                               environment_attrs: Dict, action: str, 
                               request, view, obj) -> bool:
        """Evaluate all applicable ABAC policies"""
        try:
            # Find applicable policies for this action and resource type
            applicable_policies = []
            
            for policy_name, policy_config in self.ABAC_POLICIES.items():
                for condition in policy_config['conditions']:
                    if condition['action'] == action or condition['action'] == 'any':
                        applicable_policies.append((policy_name, condition))
            
            # If no specific policies apply, use default behavior
            if not applicable_policies:
                return True
            
            # Evaluate each applicable policy
            policy_results = []
            
            for policy_name, condition in applicable_policies:
                try:
                    # Get the evaluation rule
                    rule_name = condition['rule']
                    if rule_name.startswith('self.'):
                        rule_method = getattr(self, rule_name.split('.', 1)[1])
                    else:
                        continue  # Skip unknown rules
                    
                    # Execute the rule
                    result = rule_method(
                        subject_attrs, resource_attrs, environment_attrs,
                        request, view, obj
                    )
                    
                    policy_results.append({
                        'policy': policy_name,
                        'result': result,
                        'rule': rule_name
                    })
                    
                    # Log policy evaluation
                    logger.info(f"ABAC Policy {policy_name}: {'ALLOW' if result else 'DENY'}")
                    
                except Exception as e:
                    logger.error(f"Policy {policy_name} evaluation failed: {e}")
                    policy_results.append({
                        'policy': policy_name,
                        'result': False,  # Fail-safe
                        'error': str(e)
                    })
            
            # Combine policy results (all must pass for access)
            final_result = all(result['result'] for result in policy_results)
            
            # Log final decision
            logger.info(f"ABAC Final Decision: {'ALLOW' if final_result else 'DENY'} - "
                       f"Policies evaluated: {len(policy_results)}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"ABAC policy evaluation failed: {e}", exc_info=True)
            return False  # Fail-safe
    
    # ============================================================================
    # POLICY EVALUATION RULES
    # ============================================================================
    
    def _evaluate_high_value_opportunity_access(self, subject_attrs: Dict, resource_attrs: Dict,
                                              environment_attrs: Dict, request, view, obj) -> bool:
        """Evaluate access to high-value opportunities"""
        try:
            opportunity_amount = resource_attrs.get('amount', 0)
            user_roles = subject_attrs.get('role', [])
            user_performance = subject_attrs.get('performance_score', 0)
            
            # High-value threshold
            if opportunity_amount < 50000:
                return True  # Standard access for lower amounts
            
            # High-value opportunity requirements
            if opportunity_amount >= 100000:
                # Very high value - requires senior roles or exceptional performance
                senior_roles = ['SALES_MANAGER', 'TENANT_ADMIN', 'SYSTEM_ADMIN']
                if any(role in user_roles for role in senior_roles):
                    return True
                
                # Or exceptional performance with management approval
                if user_performance >= 90:
                    approval_required = self._check_management_approval(request.user, obj)
                    return approval_required
                
                return False
            
            else:  # 50K-100K range
                # Moderate high value - requires good performance or ownership
                if resource_attrs.get('owner') == subject_attrs.get('user_id'):
                    return True  # Owner access
                
                if user_performance >= 75:
                    return True  # Good performers get access
                
                # Or specific roles
                allowed_roles = ['SALES_MANAGER', 'SALES_REP', 'TENANT_ADMIN', 'SYSTEM_ADMIN']
                return any(role in user_roles for role in allowed_roles)
            
        except Exception as e:
            logger.error(f"High-value opportunity evaluation failed: {e}")
            return False
    
    def _evaluate_sensitive_lead_access(self, subject_attrs: Dict, resource_attrs: Dict,
                                      environment_attrs: Dict, request, view, obj) -> bool:
        """Evaluate access to sensitive lead information"""
        try:
            data_sensitivity = resource_attrs.get('data_sensitivity', 'LOW')
            user_clearance = subject_attrs.get('clearance_level', 'STANDARD')
            user_roles = subject_attrs.get('role', [])
            is_business_hours = environment_attrs.get('is_business_hours', False)
            
            # Low sensitivity - general access
            if data_sensitivity == 'LOW':
                return True
            
            # Medium sensitivity - requires business hours and proper role
            if data_sensitivity == 'MEDIUM':
                allowed_roles = ['SALES_REP', 'SALES_MANAGER', 'MARKETING_MANAGER', 'TENANT_ADMIN']
                if any(role in user_roles for role in allowed_roles):
                    return is_business_hours or user_clearance in ['HIGH', 'EXECUTIVE']
                return False
            
            # High sensitivity - requires high clearance and secure environment
            if data_sensitivity == 'HIGH':
                if user_clearance in ['HIGH', 'EXECUTIVE']:
                    secure_network = environment_attrs.get('network_type') == 'CORPORATE'
                    return secure_network and is_business_hours
                return False
            
            # Critical sensitivity - executive access only
            if data_sensitivity == 'CRITICAL':
                executive_roles = ['TENANT_ADMIN', 'SYSTEM_ADMIN']
                return (any(role in user_roles for role in executive_roles) and 
                       user_clearance == 'EXECUTIVE')
            
            return False
            
        except Exception as e:
            logger.error(f"Sensitive lead access evaluation failed: {e}")
            return False
    
    def _evaluate_financial_data_access(self, subject_attrs: Dict, resource_attrs: Dict,
                                      environment_attrs: Dict, request, view, obj) -> bool:
        """Evaluate access to financial data"""
        try:
            financial_classification = resource_attrs.get('financial_classification', 'LOW')
            user_department = subject_attrs.get('department', '')
            user_roles = subject_attrs.get('role', [])
            is_business_hours = environment_attrs.get('is_business_hours', False)
            secure_connection = environment_attrs.get('secure_connection', False)
            
            # Basic financial data
            if financial_classification == 'LOW':
                basic_roles = ['SALES_REP', 'SALES_MANAGER', 'ANALYST']
                return any(role in user_roles for role in basic_roles)
            
            # Sensitive financial data
            if financial_classification in ['MEDIUM', 'HIGH']:
                # Finance department always has access
                if user_department == 'FINANCE':
                    return secure_connection
                
                # Management roles during business hours
                management_roles = ['SALES_MANAGER', 'TENANT_ADMIN']
                if any(role in user_roles for role in management_roles):
                    return is_business_hours and secure_connection
                
                return False
            
            # Confidential financial data
            if financial_classification == 'CONFIDENTIAL':
                executive_roles = ['TENANT_ADMIN', 'SYSTEM_ADMIN']
                finance_access = user_department == 'FINANCE' and 'FINANCE_MANAGER' in user_roles
                
                return ((any(role in user_roles for role in executive_roles) or finance_access) 
                       and secure_connection and is_business_hours)
            
            return False
            
        except Exception as e:
            logger.error(f"Financial data access evaluation failed: {e}")
            return False
    
    def _evaluate_territory_management_access(self, subject_attrs: Dict, resource_attrs: Dict,
                                            environment_attrs: Dict, request, view, obj) -> bool:
        """Evaluate territory management access"""
        try:
            territory_importance = resource_attrs.get('importance', 'STANDARD')
            territory_revenue = resource_attrs.get('revenue', 0)
            user_geographic_authority = subject_attrs.get('geographic_authority', [])
            user_management_level = subject_attrs.get('management_level', 0)
            user_roles = subject_attrs.get('role', [])
            
            # Standard territories
            if territory_importance == 'STANDARD' and territory_revenue < 1000000:
                manager_roles = ['SALES_MANAGER', 'TERRITORY_MANAGER']
                return any(role in user_roles for role in manager_roles)
            
            # Important territories
            if territory_importance == 'HIGH' or territory_revenue >= 1000000:
                # Requires senior management
                if user_management_level >= 3:  # Senior management level
                    return True
                
                # Or specific geographic authority
                territory_region = resource_attrs.get('region')
                if territory_region in user_geographic_authority:
                    return 'REGIONAL_MANAGER' in user_roles
                
                return False
            
            # Strategic territories
            if territory_importance == 'STRATEGIC':
                executive_roles = ['TENANT_ADMIN', 'VP_SALES', 'SYSTEM_ADMIN']
                return any(role in user_roles for role in executive_roles)
            
            return False
            
        except Exception as e:
            logger.error(f"Territory management evaluation failed: {e}")
            return False
    
    def _evaluate_customer_data_retention(self, subject_attrs: Dict, resource_attrs: Dict,
                                        environment_attrs: Dict, request, view, obj) -> bool:
        """Evaluate customer data access based on retention policies"""
        try:
            consent_status = resource_attrs.get('consent_status', 'UNKNOWN')
            data_age_days = self._calculate_data_age_days(resource_attrs.get('created_date'))
            customer_jurisdiction = resource_attrs.get('jurisdiction', 'US')
            retention_period = environment_attrs.get('retention_period', 2555)  # 7 years default
            legal_hold = environment_attrs.get('legal_hold_status', False)
            user_certification = subject_attrs.get('data_handler_certification', False)
            
            # Legal hold overrides retention policies
            if legal_hold:
                return user_certification and 'COMPLIANCE_OFFICER' in subject_attrs.get('role', [])
            
            # Check consent status
            if consent_status == 'WITHDRAWN':
                # Only compliance team can access withdrawn consent data
                compliance_roles = ['COMPLIANCE_OFFICER', 'PRIVACY_OFFICER', 'LEGAL']
                return any(role in subject_attrs.get('role', []) for role in compliance_roles)
            
            if consent_status == 'EXPIRED':
                # Expired consent - limited access for 30 days
                if data_age_days <= 30:
                    return user_certification
                return False
            
            # Check retention period
            if data_age_days > retention_period:
                # Data past retention - only legal/compliance access
                legal_roles = ['COMPLIANCE_OFFICER', 'LEGAL', 'SYSTEM_ADMIN']
                return any(role in subject_attrs.get('role', []) for role in legal_roles)
            
            # Jurisdiction-specific rules
            if customer_jurisdiction == 'EU':
                # GDPR requirements - must have certification
                return user_certification and consent_status in ['ACTIVE', 'IMPLIED']
            
            # Standard access for valid data
            return consent_status in ['ACTIVE', 'IMPLIED', 'LEGITIMATE_INTEREST']
            
        except Exception as e:
            logger.error(f"Customer data retention evaluation failed: {e}")
            return False
    
    # ============================================================================
    # HELPER METHODS FOR ATTRIBUTE EXTRACTION AND EVALUATION
    # ============================================================================
    
    def _calculate_user_experience_level(self, user) -> str:
        """Calculate user experience level based on tenure and activity"""
        try:
            from django.utils import timezone
            
            tenure_days = (timezone.now() - user.date_joined).days
            
            if tenure_days > 1095:  # 3+ years
                return 'EXPERT'
            elif tenure_days > 730:  # 2+ years
                return 'SENIOR'
            elif tenure_days > 365:  # 1+ year
                return 'EXPERIENCED'
            elif tenure_days > 90:   # 3+ months
                return 'INTERMEDIATE'
            else:
                return 'NOVICE'
                
        except Exception:
            return 'NOVICE'
    
    def _get_user_performance_score(self, user) -> float:
        """Get user performance score from analytics"""
        try:
            # This would integrate with your ActivityService productivity metrics
            # Placeholder implementation
            return 75.0
            
        except Exception:
            return 50.0
    
    def _get_management_level(self, user) -> int:
        """Determine management level (0=individual contributor, 1=supervisor, 2=manager, 3=director, 4=VP, 5=C-level)"""
        try:
            if hasattr(user, 'memberships'):
                roles = user.memberships.values_list('role', flat=True)
                
                if any('SYSTEM_ADMIN' in role for role in roles):
                    return 5
                elif any('TENANT_ADMIN' in role for role in roles):
                    return 4
                elif any('VP' in role for role in roles):
                    return 4
                elif any('DIRECTOR' in role for role in roles):
                    return 3
                elif any('MANAGER' in role for role in roles):
                    return 2
                elif any('SUPERVISOR' in role for role in roles):
                    return 1
                else:
                    return 0
            
            return 0
            
        except Exception:
            return 0
    
    def _classify_financial_amount(self, amount) -> str:
        """Classify financial amount by sensitivity level"""
        try:
            if not amount:
                return 'LOW'
            
            amount = float(amount)
            
            if amount >= 1000000:  # $1M+
                return 'CONFIDENTIAL'
            elif amount >= 100000:  # $100K+
                return 'HIGH'
            elif amount >= 10000:   # $10K+
                return 'MEDIUM'
            else:
                return 'LOW'
                
        except Exception:
            return 'LOW'
    
    def _assess_data_sensitivity(self, obj) -> str:
        """Assess data sensitivity of an object"""
        try:
            sensitivity_score = 0
            
            # Check for PII fields
            pii_fields = ['email', 'phone', 'address', 'ssn', 'tax_id']
            for field in pii_fields:
                if hasattr(obj, field) and getattr(obj, field):
                    sensitivity_score += 1
            
            # Check for financial data
            financial_fields = ['revenue', 'salary', 'credit_score', 'bank_account']
            for field in financial_fields:
                if hasattr(obj, field) and getattr(obj, field):
                    sensitivity_score += 2
            
            # Check for confidential notes
            if hasattr(obj, 'notes') and getattr(obj, 'notes'):
                notes = str(obj.notes).lower()
                confidential_keywords = ['confidential', 'sensitive', 'private', 'internal']
                if any(keyword in notes for keyword in confidential_keywords):
                    sensitivity_score += 3
            
            # Map score to sensitivity level
            if sensitivity_score >= 5:
                return 'CRITICAL'
            elif sensitivity_score >= 3:
                return 'HIGH'
            elif sensitivity_score >= 1:
                return 'MEDIUM'
            else:
                return 'LOW'
                
        except Exception:
            return 'LOW'
    
    def _contains_pii(self, obj) -> bool:
        """Check if object contains personally identifiable information"""
        try:
            pii_fields = ['email', 'phone', 'mobile_phone', 'address', 'birth_date', 
                         'ssn', 'tax_id', 'passport_number', 'drivers_license']
            
            return any(hasattr(obj, field) and getattr(obj, field) for field in pii_fields)
            
        except Exception:
            return False
    
    def _determine_request_origin(self, request) -> str:
        """Determine the origin of the request"""
        try:
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            
            if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
                return 'MOBILE_APP'
            elif 'api' in user_agent or 'curl' in user_agent or 'postman' in user_agent:
                return 'API_CLIENT'
            elif 'bot' in user_agent or 'crawler' in user_agent:
                return 'BOT'
            else:
                return 'WEB_BROWSER'
                
        except Exception:
            return 'UNKNOWN'
    
    def _calculate_request_risk_score(self, request) -> int:
        """Calculate risk score for the request (0-100)"""
        try:
            risk_score = 0
            
            # IP-based risk
            client_ip = self._get_client_ip(request)
            if self._is_high_risk_ip(client_ip):
                risk_score += 30
            
            # Time-based risk
            current_hour = timezone.now().hour
            if current_hour < 6 or current_hour > 22:  # Outside normal hours
                risk_score += 10
            
            # User agent risk
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            if not user_agent or len(user_agent) < 20:
                risk_score += 20
            
            # Session age risk
            session_age = self._calculate_session_age(request)
            if session_age > 12:  # Session older than 12 hours
                risk_score += 15
            
            # Failed attempts
            failed_attempts = self._count_recent_failed_attempts(request.user)
            risk_score += min(failed_attempts * 5, 25)
            
            return min(risk_score, 100)
            
        except Exception:
            return 50  # Medium risk default
    
    def _is_high_risk_ip(self, ip_address: str) -> bool:
        """Check if IP address is considered high risk"""
        try:
            # This would integrate with threat intelligence services
            # Placeholder implementation
            high_risk_patterns = ['10.0.0', '192.168.', '127.0.0']  # Example patterns
            return any(ip_address.startswith(pattern) for pattern in high_risk_patterns)
            
        except Exception:
            return False