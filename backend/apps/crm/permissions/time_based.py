# ============================================================================
# backend/apps/crm/permissions/time_based.py - Time-Based Access Control
# ============================================================================

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time, timedelta
from django.utils import timezone
import pytz
import logging

from .base import ObjectLevelPermission

logger = logging.getLogger(__name__)


class TimeBasedPermission(ObjectLevelPermission):
    """
    Comprehensive time-based access control with business rules
    """
    
    # Business hours configuration by role and region
    BUSINESS_HOURS_CONFIG = {
        'default': {
            'timezone': 'UTC',
            'business_days': [0, 1, 2, 3, 4],  # Monday-Friday
            'business_hours': {'start': 9, 'end': 17},  # 9 AM - 5 PM
            'lunch_break': {'start': 12, 'end': 13},   # 12 PM - 1 PM
            'overtime_allowed': True,
            'weekend_access': False
        },
        'SALES_REP': {
            'timezone': 'US/Eastern',
            'business_days': [0, 1, 2, 3, 4],
            'business_hours': {'start': 8, 'end': 18},  # 8 AM - 6 PM
            'overtime_allowed': True,
            'weekend_access': True,
            'flexible_hours': True
        },
        'SALES_MANAGER': {
            'timezone': 'US/Eastern',
            'business_days': [0, 1, 2, 3, 4, 5],  # Monday-Saturday
            'business_hours': {'start': 7, 'end': 20},  # 7 AM - 8 PM
            'overtime_allowed': True,
            'weekend_access': True,
            'emergency_access': True
        },
        'CUSTOMER_SUCCESS': {
            'timezone': 'US/Pacific',
            'business_days': [0, 1, 2, 3, 4, 5, 6],  # 24/7 support
            'business_hours': {'start': 6, 'end': 22},  # 6 AM - 10 PM
            'shift_based': True,
            'weekend_access': True
        },
        'FINANCE': {
            'timezone': 'US/Eastern',
            'business_days': [0, 1, 2, 3, 4],
            'business_hours': {'start': 9, 'end': 17},
            'month_end_extended': True,
            'quarter_end_extended': True,
            'year_end_extended': True
        },
        'COMPLIANCE_OFFICER': {
            'timezone': 'US/Eastern',
            'business_days': [0, 1, 2, 3, 4],
            'business_hours': {'start': 9, 'end': 17},
            'emergency_access': True,
            'audit_period_extended': True
        }
    }
    
    # Session timeout configuration by role
    SESSION_TIMEOUT_CONFIG = {
        'SYSTEM_ADMIN': {'timeout_minutes': 240, 'warning_minutes': 30},
        'TENANT_ADMIN': {'timeout_minutes': 180, 'warning_minutes': 20},
        'SALES_MANAGER': {'timeout_minutes': 120, 'warning_minutes': 15},
        'SALES_REP': {'timeout_minutes': 60, 'warning_minutes': 10},
        'VIEWER': {'timeout_minutes': 30, 'warning_minutes': 5},
        'default': {'timeout_minutes': 60, 'warning_minutes': 10}
    }
    
    # Time-sensitive operation windows
    OPERATION_WINDOWS = {
        'high_value_transactions': {
            'allowed_hours': {'start': 9, 'end': 17},
            'allowed_days': [0, 1, 2, 3, 4],  # Business days only
            'requires_dual_approval': True,
            'cooling_off_period': 24  # hours
        },
        'data_export': {
            'allowed_hours': {'start': 10, 'end': 16},
            'allowed_days': [0, 1, 2, 3, 4],
            'max_frequency': 'daily',
            'notification_required': True
        },
        'bulk_operations': {
            'allowed_hours': {'start': 20, 'end': 6},  # After hours only
            'max_duration': 4,  # hours
            'approval_required': True
        },
        'sensitive_data_access': {
            'allowed_hours': {'start': 9, 'end': 17},
            'allowed_days': [0, 1, 2, 3, 4],
            'max_session_duration': 2,  # hours
            'break_required': 30  # minutes between sessions
        }
    }
    
    def has_permission(self, request, view) -> bool:
        """Enhanced permission check with time-based validation"""
        try:
            # Parent permission check
            if not super().has_permission(request, view):
                return False
            
            # Get user roles for time-based configuration
            user_roles = getattr(request, 'user_roles', [])
            
            # Check business hours
            if not self._check_business_hours_access(request, user_roles):
                self._log_time_based_denial(request, 'business_hours_violation')
                return False
            
            # Check session validity and timeout
            if not self._check_session_validity(request, user_roles):
                self._log_time_based_denial(request, 'session_timeout')
                return False
            
            # Check operation-specific time windows
            operation_type = self._determine_operation_type(request, view)
            if not self._check_operation_time_window(request, operation_type):
                self._log_time_based_denial(request, f'operation_window_violation_{operation_type}')
                return False
            
            # Check for time-sensitive data access patterns
            if not self._check_access_patterns(request, user_roles):
                self._log_time_based_denial(request, 'suspicious_access_pattern')
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Time-based permission check failed: {e}", exc_info=True)
            return False
    
    def _check_business_hours_access(self, request, user_roles: List[str]) -> bool:
        """Check if current time falls within allowed business hours"""
        try:
            # Get user's business hours configuration
            config = self._get_user_time_config(user_roles)
            
            # Get current time in user's timezone
            user_timezone = pytz.timezone(config['timezone'])
            current_time = timezone.now().astimezone(user_timezone)
            current_hour = current_time.hour
            current_day = current_time.weekday()
            
            # Check if today is a business day
            if current_day not in config['business_days']:
                # Check if weekend access is allowed
                if not config.get('weekend_access', False):
                    return False
            
            # Check business hours
            business_start = config['business_hours']['start']
            business_end = config['business_hours']['end']
            
            if not (business_start <= current_hour <= business_end):
                # Check for overtime allowance
                if config.get('overtime_allowed', False):
                    # Allow 2 hours before and after business hours
                    extended_start = max(0, business_start - 2)
                    extended_end = min(23, business_end + 2)
                    
                    if not (extended_start <= current_hour <= extended_end):
                        return False
                else:
                    return False
            
            # Check for lunch break restrictions (if applicable)
            if 'lunch_break' in config and not config.get('flexible_hours', False):
                lunch_start = config['lunch_break']['start']
                lunch_end = config['lunch_break']['end']
                
                if lunch_start <= current_hour <= lunch_end:
                    # Check if user has lunch break exemption
                    exemption_roles = ['SALES_MANAGER', 'CUSTOMER_SUCCESS', 'SYSTEM_ADMIN']
                    if not any(role in user_roles for role in exemption_roles):
                        return False
            
            # Special period extensions (month-end, quarter-end, etc.)
            if self._is_special_period() and config.get('month_end_extended', False):
                return True  # Extended access during special periods
            
            return True
            
        except Exception as e:
            logger.error(f"Business hours check failed: {e}")
            return True  # Default to allow on error
    
    def _check_session_validity(self, request, user_roles: List[str]) -> bool:
        """Check session validity and timeout"""
        try:
            # Get session timeout configuration
            timeout_config = self._get_session_timeout_config(user_roles)
            timeout_minutes = timeout_config['timeout_minutes']
            
            # Check session age
            session_start = request.session.get('session_start')
            if session_start:
                session_start_time = datetime.fromisoformat(session_start)
                session_age = timezone.now() - session_start_time
                
                if session_age.total_seconds() > (timeout_minutes * 60):
                    return False
            else:
                # Set session start time if not exists
                request.session['session_start'] = timezone.now().isoformat()
            
            # Update last activity
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Check for concurrent sessions (if limited)
            if not self._check_concurrent_sessions(request):
                return False
            
            # Check for session hijacking indicators
            if not self._check_session_integrity(request):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Session validity check failed: {e}")
            return True
    
    def _check_operation_time_window(self, request, operation_type: str) -> bool:
        """Check if operation is allowed in current time window"""
        try:
            if operation_type not in self.OPERATION_WINDOWS:
                return True  # No restrictions for unknown operations
            
            config = self.OPERATION_WINDOWS[operation_type]
            current_time = timezone.now()
            current_hour = current_time.hour
            current_day = current_time.weekday()
            
            # Check allowed hours
            if 'allowed_hours' in config:
                allowed_start = config['allowed_hours']['start']
                allowed_end = config['allowed_hours']['end']
                
                # Handle overnight windows (e.g., 20:00-06:00)
                if allowed_start > allowed_end:
                    if not (current_hour >= allowed_start or current_hour <= allowed_end):
                        return False
                else:
                    if not (allowed_start <= current_hour <= allowed_end):
                        return False
            
            # Check allowed days
            if 'allowed_days' in config:
                if current_day not in config['allowed_days']:
                    return False
            
            # Check frequency limitations
            if 'max_frequency' in config:
                if not self._check_operation_frequency(request, operation_type, config['max_frequency']):
                    return False
            
            # Check cooling-off period
            if 'cooling_off_period' in config:
                if not self._check_cooling_off_period(request, operation_type, config['cooling_off_period']):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Operation time window check failed: {e}")
            return True
    
    def _check_access_patterns(self, request, user_roles: List[str]) -> bool:
        """Check for suspicious access patterns"""
        try:
            user_id = request.user.id
            current_time = timezone.now()
            
            # Get recent access history
            recent_accesses = self._get_recent_access_history(user_id, hours=24)
            
            # Check for unusual time patterns
            if self._detect_unusual_time_access(recent_accesses, current_time):
                return False
            
            # Check for rapid consecutive accesses
            if self._detect_rapid_access_pattern(recent_accesses):
                return False
            
            # Check for geographic anomalies (if IP tracking enabled)
            if self._detect_geographic_anomalies(request, recent_accesses):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Access pattern check failed: {e}")
            return True
    
    def _get_user_time_config(self, user_roles: List[str]) -> Dict:
        """Get time configuration for user based on their highest priority role"""
        try:
            # Role priority order (highest to lowest)
            role_priority = [
                'SYSTEM_ADMIN', 'TENANT_ADMIN', 'COMPLIANCE_OFFICER',
                'SALES_MANAGER', 'MARKETING_MANAGER', 'CUSTOMER_SUCCESS',
                'FINANCE', 'SALES_REP', 'MARKETING_USER', 'ANALYST', 'VIEWER'
            ]
            
            # Find highest priority role with time configuration
            for role in role_priority:
                if role in user_roles and role in self.BUSINESS_HOURS_CONFIG:
                    return self.BUSINESS_HOURS_CONFIG[role]
            
            return self.BUSINESS_HOURS_CONFIG['default']
            
        except Exception as e:
            logger.error(f"Getting user time config failed: {e}")
            return self.BUSINESS_HOURS_CONFIG['default']
    
    def _get_session_timeout_config(self, user_roles: List[str]) -> Dict:
        """Get session timeout configuration for user roles"""
        try:
            # Use the most permissive timeout from user's roles
            max_timeout = 0
            config = self.SESSION_TIMEOUT_CONFIG['default'].copy()
            
            for role in user_roles:
                if role in self.SESSION_TIMEOUT_CONFIG:
                    role_config = self.SESSION_TIMEOUT_CONFIG[role]
                    if role_config['timeout_minutes'] > max_timeout:
                        max_timeout = role_config['timeout_minutes']
                        config = role_config.copy()
            
            return config
            
        except Exception as e:
            logger.error(f"Getting session timeout config failed: {e}")
            return self.SESSION_TIMEOUT_CONFIG['default']
    
    def _determine_operation_type(self, request, view) -> str:
        """Determine the type of operation being performed"""
        try:
            # Check view name and method to determine operation type
            view_name = view.__class__.__name__.lower()
            method = request.method.upper()
            
            # High-value transaction indicators
            if 'opportunity' in view_name and method in ['POST', 'PUT', 'PATCH']:
                if request.data.get('amount', 0) > 100000:
                    return 'high_value_transactions'
            
            # Data export indicators
            if 'export' in view_name or request.GET.get('format') in ['csv', 'excel', 'pdf']:
                return 'data_export'
            
            # Bulk operations
            if 'bulk' in view_name or request.data.get('bulk_operation'):
                return 'bulk_operations'
            
            # Sensitive data access
            sensitive_views = ['lead', 'contact', 'account']
            if any(sensitive in view_name for sensitive in sensitive_views):
                return 'sensitive_data_access'
            
            return 'standard_operation'
            
        except Exception as e:
            logger.error(f"Operation type determination failed: {e}")
            return 'standard_operation'
    
    def _is_special_period(self) -> bool:
        """Check if current time is during special business periods"""
        try:
            current_date = timezone.now().date()
            
            # Month-end (last 3 days of month)
            next_month = current_date.replace(day=28) + timedelta(days=4)
            last_day_of_month = next_month - timedelta(days=next_month.day)
            
            if (last_day_of_month - current_date).days <= 2:
                return True
            
            # Quarter-end
            if current_date.month in [3, 6, 9, 12]:
                return True
            
            # Year-end (December)
            if current_date.month == 12:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Special period check failed: {e}")
            return False
    
    def _check_concurrent_sessions(self, request) -> bool:
        """Check if user has exceeded concurrent session limits"""
        try:
            # This would integrate with Django's session framework
            # Placeholder implementation
            return True
            
        except Exception as e:
            logger.error(f"Concurrent session check failed: {e}")
            return True
    
    def _check_session_integrity(self, request) -> bool:
        """Check session for signs of hijacking or tampering"""
        try:
            # Check for consistent user agent
            current_ua = request.META.get('HTTP_USER_AGENT', '')
            session_ua = request.session.get('user_agent')
            
            if session_ua and session_ua != current_ua:
                return False
            elif not session_ua:
                request.session['user_agent'] = current_ua
            
            # Check for consistent IP (with some flexibility for NAT/proxy)
            current_ip = self._get_client_ip(request)
            session_ip = request.session.get('ip_address')
            
            if session_ip and not self._is_ip_in_same_network(current_ip, session_ip):
                return False
            elif not session_ip:
                request.session['ip_address'] = current_ip
            
            return True
            
        except Exception as e:
            logger.error(f"Session integrity check failed: {e}")
            return True
    
    def _log_time_based_denial(self, request, reason: str):
        """Log time-based access denial for security monitoring"""
        try:
            denial_event = {
                'event_type': 'TIME_BASED_ACCESS_DENIAL',
                'reason': reason,
                'user_id': request.user.id if request.user else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now().isoformat(),
                'path': request.path,
                'method': request.method
            }
            
            logger.warning(f"Time-based access denied: {denial_event}")
            
        except Exception as e:
            logger.error(f"Time-based denial logging failed: {e}")


class SessionPermission(TimeBasedPermission):
    """
    Enhanced session management with advanced security features
    """
    
    def has_permission(self, request, view) -> bool:
        """Session-aware permission checking"""
        try:
            # Parent time-based check
            if not super().has_permission(request, view):
                return False
            
            # Enhanced session security checks
            if not self._perform_session_security_checks(request):
                return False
            
            # Update session tracking
            self._update_session_tracking(request, view)
            
            return True
            
        except Exception as e:
            logger.error(f"Session permission check failed: {e}")
            return False
    
    def _perform_session_security_checks(self, request) -> bool:
        """Perform comprehensive session security validation"""
        try:
            # Check session fixation
            if not self._check_session_fixation(request):
                return False
            
            # Check session token validity
            if not self._validate_session_token(request):
                return False
            
            # Check for session replay attacks
            if not self._check_session_replay(request):
                return False
            
            # Check device fingerprinting
            if not self._validate_device_fingerprint(request):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Session security checks failed: {e}")
            return False
    
    def _check_session_fixation(self, request) -> bool:
        """Check for session fixation attacks"""
        try:
            # Check if session was created before authentication
            session_created = request.session.get('created_at')
            auth_time = request.session.get('auth_time')
            
            if session_created and auth_time:
                created_dt = datetime.fromisoformat(session_created)
                auth_dt = datetime.fromisoformat(auth_time)
                
                # Session should be regenerated after authentication
                if created_dt < auth_dt:
                    return True
                else:
                    # Potential session fixation
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Session fixation check failed: {e}")
            return True
    
    def _validate_session_token(self, request) -> bool:
        """Validate session token integrity"""
        try:
            # Check for tampered session data
            session_signature = request.session.get('signature')
            
            if session_signature:
                # Verify signature (implementation would depend on your session backend)
                expected_signature = self._calculate_session_signature(request)
                return session_signature == expected_signature
            
            return True
            
        except Exception as e:
            logger.error(f"Session token validation failed: {e}")
            return True
    
    def _calculate_session_signature(self, request) -> str:
        """Calculate expected session signature"""
        try:
            import hmac
            import hashlib
            
            # Create signature from session data and secret
            session_data = str(request.session.session_key)
            secret = getattr(settings, 'SECRET_KEY', 'default_secret')
            
            signature = hmac.new(
                secret.encode('utf-8'),
                session_data.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"Session signature calculation failed: {e}")
            return ""
    
    def _update_session_tracking(self, request, view):
        """Update session tracking information"""
        try:
            # Update activity timestamp
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Track accessed resources
            accessed_resources = request.session.get('accessed_resources', [])
            resource_info = {
                'view': view.__class__.__name__,
                'method': request.method,
                'timestamp': timezone.now().isoformat()
            }
            
            accessed_resources.append(resource_info)
            
            # Keep only recent 100 accesses
            request.session['accessed_resources'] = accessed_resources[-100:]
            
            # Update request count
            request.session['request_count'] = request.session.get('request_count', 0) + 1
            
        except Exception as e:
            logger.error(f"Session tracking update failed: {e}")