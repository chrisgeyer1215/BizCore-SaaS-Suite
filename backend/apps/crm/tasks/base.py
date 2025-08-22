# ============================================================================
# backend/apps/crm/tasks/base.py - Base Task Classes with Security Integration
# ============================================================================

from celery import Task, current_task
from celery.exceptions import Retry, Ignore
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
import logging
import traceback
import json

from apps.core.celery import app
from ..permissions.base import CRMPermission
from ..models import TaskExecution, TaskLog, AuditLog

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseTask(Task):
    """
    Enhanced base task class with comprehensive error handling, monitoring, and security
    """
    
    # Task configuration
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    
    # Performance monitoring
    track_started = True
    track_started_delay = True
    acks_late = True
    reject_on_worker_lost = True
    
    def __init__(self):
        self.execution_id = None
        self.start_time = None
        self.tenant = None
        self.user = None
        self.security_context = {}
        
    def before_start(self, task_id, args, kwargs):
        """Enhanced pre-execution setup with security validation"""
        try:
            self.start_time = timezone.now()
            self.execution_id = task_id
            
            # Extract security context
            self.security_context = kwargs.get('_security_context', {})
            self.tenant_id = self.security_context.get('tenant_id')
            self.user_id = self.security_context.get('user_id')
            
            # Load tenant and user objects
            if self.tenant_id:
                from apps.core.models import Tenant
                self.tenant = Tenant.objects.filter(id=self.tenant_id).first()
            
            if self.user_id:
                self.user = User.objects.filter(id=self.user_id).first()
            
            # Create task execution record
            self._create_task_execution_record(task_id, args, kwargs)
            
            # Log task start
            self._log_task_event('STARTED', {
                'task_name': self.name,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys()),
                'tenant_id': self.tenant_id,
                'user_id': self.user_id
            })
            
        except Exception as e:
            logger.error(f"Task pre-start failed: {e}", exc_info=True)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Enhanced success handling with audit logging"""
        try:
            execution_time = (timezone.now() - self.start_time).total_seconds()
            
            # Update task execution record
            self._update_task_execution_record(task_id, 'SUCCESS', retval, execution_time)
            
            # Log success
            self._log_task_event('SUCCESS', {
                'execution_time_seconds': execution_time,
                'return_value_type': type(retval).__name__,
                'return_value_size': len(str(retval)) if retval else 0
            })
            
            # Performance monitoring
            self._record_performance_metrics(execution_time, 'success')
            
        except Exception as e:
            logger.error(f"Task success handling failed: {e}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Enhanced failure handling with detailed error analysis"""
        try:
            execution_time = (timezone.now() - self.start_time).total_seconds() if self.start_time else 0
            
            # Analyze error type and severity
            error_analysis = self._analyze_task_error(exc, einfo)
            
            # Update task execution record
            self._update_task_execution_record(task_id, 'FAILURE', {
                'error': str(exc),
                'error_type': type(exc).__name__,
                'traceback': einfo.traceback,
                'analysis': error_analysis
            }, execution_time)
            
            # Log failure
            self._log_task_event('FAILURE', {
                'error_message': str(exc),
                'error_type': type(exc).__name__,
                'execution_time_seconds': execution_time,
                'retry_count': getattr(self.request, 'retries', 0),
                'severity': error_analysis['severity']
            })
            
            # Send alerts for critical failures
            if error_analysis['severity'] in ['HIGH', 'CRITICAL']:
                self._send_failure_alert(exc, task_id, error_analysis)
            
            # Performance monitoring
            self._record_performance_metrics(execution_time, 'failure')
            
        except Exception as e:
            logger.error(f"Task failure handling failed: {e}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Enhanced retry handling with intelligent backoff"""
        try:
            retry_count = getattr(self.request, 'retries', 0)
            
            # Log retry attempt
            self._log_task_event('RETRY', {
                'retry_count': retry_count,
                'error_message': str(exc),
                'next_retry_eta': self._calculate_next_retry_time(retry_count)
            })
            
            # Adaptive retry strategy based on error type
            if isinstance(exc, ConnectionError):
                # Network issues - longer backoff
                raise self.retry(countdown=min(300, 60 * (2 ** retry_count)))
            elif isinstance(exc, MemoryError):
                # Memory issues - don't retry immediately
                raise self.retry(countdown=min(600, 120 * (2 ** retry_count)))
            else:
                # Standard exponential backoff
                raise self.retry(countdown=min(300, 30 * (2 ** retry_count)))
                
        except Exception as e:
            logger.error(f"Task retry handling failed: {e}")
    
    def _create_task_execution_record(self, task_id: str, args: tuple, kwargs: dict):
        """Create detailed task execution record"""
        try:
            TaskExecution.objects.create(
                task_id=task_id,
                task_name=self.name,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                status='RUNNING',
                started_at=self.start_time,
                arguments=json.dumps({
                    'args': [str(arg)[:100] for arg in args],  # Truncate for storage
                    'kwargs': {k: str(v)[:100] for k, v in kwargs.items() if not k.startswith('_')}
                }),
                worker_name=current_task.request.hostname if current_task else 'unknown',
                queue_name=current_task.request.delivery_info.get('routing_key', 'default') if current_task else 'default'
            )
            
        except Exception as e:
            logger.error(f"Task execution record creation failed: {e}")
    
    def _update_task_execution_record(self, task_id: str, status: str, 
                                    result: Any, execution_time: float):
        """Update task execution record with results"""
        try:
            TaskExecution.objects.filter(task_id=task_id).update(
                status=status,
                completed_at=timezone.now(),
                execution_time_seconds=execution_time,
                result=json.dumps(result, default=str) if result else None,
                memory_usage_mb=self._get_memory_usage(),
                cpu_time_seconds=self._get_cpu_time()
            )
            
        except Exception as e:
            logger.error(f"Task execution record update failed: {e}")
    
    def _analyze_task_error(self, exc: Exception, einfo) -> Dict:
        """Analyze task error for severity and actionability"""
        try:
            error_type = type(exc).__name__
            error_message = str(exc)
            
            # Categorize error severity
            if isinstance(exc, (MemoryError, SystemError)):
                severity = 'CRITICAL'
                actionable = True
                recommendation = 'System resources need attention'
            elif isinstance(exc, (ConnectionError, TimeoutError)):
                severity = 'HIGH'
                actionable = True
                recommendation = 'Check network connectivity and external services'
            elif isinstance(exc, (ValueError, TypeError)):
                severity = 'MEDIUM'
                actionable = True
                recommendation = 'Check input data validation'
            elif isinstance(exc, PermissionError):
                severity = 'HIGH'
                actionable = True
                recommendation = 'Check user permissions and security context'
            else:
                severity = 'MEDIUM'
                actionable = False
                recommendation = 'Manual investigation required'
            
            # Extract stack trace context
            stack_context = self._extract_stack_context(einfo.traceback)
            
            return {
                'severity': severity,
                'actionable': actionable,
                'recommendation': recommendation,
                'error_category': self._categorize_error(error_type),
                'stack_context': stack_context,
                'frequency': self._get_error_frequency(error_type)
            }
            
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return {'severity': 'UNKNOWN', 'actionable': False}
    
    def _log_task_event(self, event_type: str, details: Dict):
        """Log task event with structured data"""
        try:
            TaskLog.objects.create(
                task_id=self.execution_id,
                task_name=self.name,
                event_type=event_type,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                timestamp=timezone.now(),
                details=details,
                worker_name=current_task.request.hostname if current_task else 'unknown'
            )
            
        except Exception as e:
            logger.error(f"Task event logging failed: {e}")
    
    def _record_performance_metrics(self, execution_time: float, outcome: str):
        """Record performance metrics for monitoring"""
        try:
            cache_key = f"task_metrics_{self.name}_{outcome}"
            
            # Get existing metrics
            metrics = cache.get(cache_key, {
                'count': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0
            })
            
            # Update metrics
            metrics['count'] += 1
            metrics['total_time'] += execution_time
            metrics['avg_time'] = metrics['total_time'] / metrics['count']
            metrics['min_time'] = min(metrics['min_time'], execution_time)
            metrics['max_time'] = max(metrics['max_time'], execution_time)
            
            # Store updated metrics (1 hour expiry)
            cache.set(cache_key, metrics, 3600)
            
        except Exception as e:
            logger.error(f"Performance metrics recording failed: {e}")


class PermissionAwareTask(BaseTask):
    """
    Task class with integrated permission checking and security validation
    """
    
    def __call__(self, *args, **kwargs):
        """Enhanced task execution with permission validation"""
        try:
            # Validate security context
            if not self._validate_security_context(kwargs):
                raise PermissionError("Invalid or missing security context")
            
            # Check user permissions
            if not self._check_task_permissions():
                raise PermissionError("Insufficient permissions for task execution")
            
            # Check tenant access
            if not self._validate_tenant_access():
                raise PermissionError("Invalid tenant context")
            
            # Execute task with security monitoring
            with self._security_monitoring_context():
                return super().__call__(*args, **kwargs)
                
        except Exception as e:
            self._log_security_violation(str(e))
            raise
    
    def _validate_security_context(self, kwargs: Dict) -> bool:
        """Validate security context provided to task"""
        try:
            security_context = kwargs.get('_security_context', {})
            
            # Required security fields
            required_fields = ['tenant_id', 'user_id', 'permissions', 'timestamp']
            
            for field in required_fields:
                if field not in security_context:
                    logger.warning(f"Missing security context field: {field}")
                    return False
            
            # Check context age (max 1 hour)
            context_timestamp = datetime.fromisoformat(security_context['timestamp'])
            age = timezone.now() - context_timestamp
            
            if age.total_seconds() > 3600:  # 1 hour
                logger.warning(f"Security context too old: {age}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Security context validation failed: {e}")
            return False
    
    def _check_task_permissions(self) -> bool:
        """Check if user has permissions to execute this task"""
        try:
            if not self.user:
                return False
            
            # Get required permission for this task
            required_permission = self._get_required_permission()
            
            if not required_permission:
                return True  # No specific permission required
            
            # Use the permission system to validate
            permission_checker = CRMPermission()
            
            # Create mock request for permission checking
            class MockRequest:
                def __init__(self, user, tenant):
                    self.user = user
                    self.tenant = tenant
                    self.method = 'POST'  # Tasks are considered write operations
                    self.META = {}
            
            mock_request = MockRequest(self.user, self.tenant)
            
            # Check permission
            return self.user.has_perm(required_permission)
            
        except Exception as e:
            logger.error(f"Task permission check failed: {e}")
            return False
    
    def _get_required_permission(self) -> Optional[str]:
        """Get required permission for this task"""
        # Map task names to required permissions
        task_permission_mapping = {
            'send_email_campaign': 'crm.send_campaign',
            'calculate_lead_scores': 'crm.change_lead',
            'auto_assign_leads': 'crm.assign_lead',
            'generate_sales_forecast': 'crm.view_analytics',
            'bulk_data_export': 'crm.export_data',
            'bulk_data_import': 'crm.import_data',
        }
        
        return task_permission_mapping.get(self.name)
    
    def _validate_tenant_access(self) -> bool:
        """Validate tenant access for task execution"""
        try:
            if not self.tenant or not self.user:
                return False
            
            # Check if user has membership in tenant
            if hasattr(self.user, 'memberships'):
                return self.user.memberships.filter(
                    tenant=self.tenant,
                    is_active=True
                ).exists()
            
            return True
            
        except Exception as e:
            logger.error(f"Tenant access validation failed: {e}")
            return False
    
    def _security_monitoring_context(self):
        """Context manager for security monitoring during task execution"""
        class SecurityMonitoringContext:
            def __init__(self, task):
                self.task = task
                self.start_time = timezone.now()
            
            def __enter__(self):
                # Log task security start
                self.task._log_security_event('TASK_SECURITY_START', {
                    'task_name': self.task.name,
                    'user_id': self.task.user_id,
                    'tenant_id': self.task.tenant_id
                })
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                # Log task security end
                execution_time = (timezone.now() - self.start_time).total_seconds()
                
                self.task._log_security_event('TASK_SECURITY_END', {
                    'execution_time': execution_time,
                    'success': exc_type is None,
                    'error_type': exc_type.__name__ if exc_type else None
                })
        
        return SecurityMonitoringContext(self)
    
    def _log_security_violation(self, violation: str):
        """Log security violation during task execution"""
        try:
            AuditLog.objects.create(
                event_type='SECURITY',
                event_subtype='task_security_violation',
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                timestamp=timezone.now(),
                additional_data=json.dumps({
                    'task_name': self.name,
                    'task_id': self.execution_id,
                    'violation': violation,
                    'worker': current_task.request.hostname if current_task else 'unknown'
                })
            )
            
        except Exception as e:
            logger.error(f"Security violation logging failed: {e}")
    
    def _log_security_event(self, event_type: str, details: Dict):
        """Log security event during task execution"""
        try:
            AuditLog.objects.create(
                event_type='SECURITY',
                event_subtype=event_type,
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                timestamp=timezone.now(),
                additional_data=json.dumps({
                    'task_name': self.name,
                    'task_id': self.execution_id,
                    **details
                })
            )
            
        except Exception as e:
            logger.error(f"Security event logging failed: {e}")


class AuditableTask(PermissionAwareTask):
    """
    Task class with comprehensive audit logging for compliance
    """
    
    def __call__(self, *args, **kwargs):
        """Enhanced task execution with comprehensive audit logging"""
        try:
            # Pre-execution audit
            self._audit_task_start(*args, **kwargs)
            
            # Execute task
            result = super().__call__(*args, **kwargs)
            
            # Post-execution audit
            self._audit_task_completion(result)
            
            return result
            
        except Exception as e:
            # Audit task failure
            self._audit_task_failure(e)
            raise
    
    def _audit_task_start(self, *args, **kwargs):
        """Audit task start with comprehensive context"""
        try:
            audit_data = {
                'event_type': 'TASK_EXECUTION',
                'event_subtype': 'TASK_STARTED',
                'task_name': self.name,
                'task_id': self.execution_id,
                'user_id': self.user_id,
                'tenant_id': self.tenant_id,
                'timestamp': timezone.now(),
                'arguments_hash': self._hash_arguments(*args, **kwargs),
                'security_context': self.security_context,
                'worker_info': {
                    'hostname': current_task.request.hostname if current_task else 'unknown',
                    'queue': current_task.request.delivery_info.get('routing_key', 'default') if current_task else 'default'
                }
            }
            
            # Store audit record
            self._store_audit_record(audit_data)
            
        except Exception as e:
            logger.error(f"Task start audit failed: {e}")
    
    def _audit_task_completion(self, result: Any):
        """Audit successful task completion"""
        try:
            execution_time = (timezone.now() - self.start_time).total_seconds()
            
            audit_data = {
                'event_type': 'TASK_EXECUTION',
                'event_subtype': 'TASK_COMPLETED',
                'task_name': self.name,
                'task_id': self.execution_id,
                'user_id': self.user_id,
                'tenant_id': self.tenant_id,
                'timestamp': timezone.now(),
                'execution_time_seconds': execution_time,
                'result_summary': self._summarize_result(result),
                'performance_metrics': {
                    'memory_usage_mb': self._get_memory_usage(),
                    'cpu_time_seconds': self._get_cpu_time()
                }
            }
            
            # Store audit record
            self._store_audit_record(audit_data)
            
        except Exception as e:
            logger.error(f"Task completion audit failed: {e}")
    
    def _audit_task_failure(self, exception: Exception):
        """Audit task failure with error analysis"""
        try:
            execution_time = (timezone.now() - self.start_time).total_seconds() if self.start_time else 0
            
            audit_data = {
                'event_type': 'TASK_EXECUTION',
                'event_subtype': 'TASK_FAILED',
                'task_name': self.name,
                'task_id': self.execution_id,
                'user_id': self.user_id,
                'tenant_id': self.tenant_id,
                'timestamp': timezone.now(),
                'execution_time_seconds': execution_time,
                'error_details': {
                    'error_type': type(exception).__name__,
                    'error_message': str(exception),
                    'retry_count': getattr(self.request, 'retries', 0)
                },
                'failure_analysis': self._analyze_failure(exception)
            }
            
            # Store audit record
            self._store_audit_record(audit_data)
            
        except Exception as e:
            logger.error(f"Task failure audit failed: {e}")
    
    def _"""Store audit record with appropriate retention"""
        try:
            # Determine retention period based on task sensitivity
            retention_days = self._get_audit_retention_days()
            
            AuditLog.objects.create(
                event_type=audit_data['event_type'],
                event_subtype=audit_data['event_subtype'],
                user_id=audit_data.get('user_id'),
                tenant_id=audit_data.get('tenant_id'),
                timestamp=audit_data['timestamp'],
                additional_data=json.dumps({
                    k: v for k, v in audit_data.items() 
                    if k not in ['event_type', 'event_subtype', 'user_id', 'tenant_id', 'timestamp']
                }),
                retention_until=timezone.now() + timedelta(days=retention_days)
            )
            
        except Exception as e:
            logger.error(f"Audit record storage failed: {e}")
    
    def _get_audit_retention_days(self) -> int:
        """Get audit retention period based on task type and sensitivity"""
        # High-sensitivity tasks (financial, compliance)
        high_sensitivity_tasks = [
            'bulk_data_export', 'generate_financial_report',
            'process_payment_data', 'compliance_audit'
        ]
        
        # Medium-sensitivity tasks (customer data)
        medium_sensitivity_tasks = [
            'send_email_campaign', 'calculate_lead_scores',
            'process_customer_data'
        ]
        
        if self.name in high_sensitivity_tasks:
            return 2555  # 7 years for high-sensitivity
        elif self.name in medium_sensitivity_tasks:
            return 1095  # 3 years for medium-sensitivity
        else:
            return 365   # 1 year for standard tasks
    
    def _hash_arguments(self, *args, **kwargs) -> str:
        """Create hash of task arguments for audit purposes"""
        try:
            import hashlib
            
            # Create string representation of arguments
            args_str = json.dumps([str(arg) for arg in args], sort_keys=True)
            kwargs_str = json.dumps({k: str(v) for k, v in kwargs.items() if not k.startswith('_')}, sort_keys=True)
            
            combined_str = f"{args_str}:{kwargs_str}"
            
            # Return SHA-256 hash
            return hashlib.sha256(combined_str.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Argument hashing failed: {e}")
            return "hash_failed"
    
    def _summarize_result(self, result: Any) -> Dict:
        """Create summary of task result for audit purposes"""
        try:
            if result is None:
                return {'type': 'None', 'summary': 'No result'}
            
            result_type = type(result).__name__
            
            if isinstance(result, dict):
                return {
                    'type': result_type,
                    'keys_count': len(result.keys()),
                    'has_errors': 'errors' in result or 'error' in result,
                    'summary': f"Dictionary with {len(result)} keys"
                }
            elif isinstance(result, (list, tuple)):
                return {
                    'type': result_type,
                    'length': len(result),
                    'summary': f"{result_type} with {len(result)} items"
                }
            elif isinstance(result, (int, float)):
                return {
                    'type': result_type,
                    'value': result,
                    'summary': f"{result_type}: {result}"
                }
            elif isinstance(result, str):
                return {
                    'type': result_type,
                    'length': len(result),
                    'summary': f"String with {len(result)} characters"
                }
            else:
                return {
                    'type': result_type,
                    'summary': f"Object of type {result_type}"
                }
                
        except Exception as e:
            logger.error(f"Result summarization failed: {e}")
            return {'type': 'unknown', 'summary': 'Summary failed'}