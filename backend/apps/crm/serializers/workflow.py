# ============================================================================
# backend/apps/crm/serializers/workflow.py - Workflow Management Serializers
# ============================================================================

from rest_framework import serializers
from django.utils import timezone
from ..models import WorkflowRule, WorkflowExecution
from .user import UserBasicSerializer


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    """Workflow execution tracking serializer"""
    
    workflow_rule_name = serializers.CharField(source='workflow_rule.name', read_only=True)
    triggered_by_details = UserBasicSerializer(source='triggered_by', read_only=True)
    
    # Execution metrics
    execution_duration = serializers.SerializerMethodField()
    execution_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowExecution
        fields = [
            'id', 'workflow_rule', 'workflow_rule_name', 'status',
            'triggered_by', 'triggered_by_details', 'started_at',
            'completed_at', 'execution_duration', 'error_message',
            'execution_data', 'execution_summary',
            'created_at'
        ]
        read_only_fields = [
            'id', 'workflow_rule_name', 'triggered_by_details',
            'execution_duration', 'execution_summary', 'created_at'
        ]
    
    def get_execution_duration(self, obj):
        """Get execution duration in milliseconds"""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            return int(duration.total_seconds() * 1000)
        return None
    
    def get_execution_summary(self, obj):
        """Get execution summary"""
        return {
            'status': obj.status,
            'duration_ms': self.get_execution_duration(obj),
            'has_error': bool(obj.error_message),
            'actions_executed': len(obj.execution_data.get('actions_results', [])) if obj.execution_data else 0,
            'success_rate': self._calculate_success_rate(obj)
        }
    
    def _calculate_success_rate(self, obj):
        """Calculate success rate of actions"""
        if not obj.execution_data or 'actions_results' not in obj 0
        
        results = obj.execution_data['actions_results']
        if not results:
            return 0
        
        successful = sum(1 for result in results if result.get('success', False))
        return (successful / len(results)) * 100


class WorkflowRuleSerializer(serializers.ModelSerializer):
    """Comprehensive workflow rule serializer"""
    
    # Performance metrics
    success_rate = serializers.SerializerMethodField()
    avg_execution_time = serializers.SerializerMethodField()
    recent_executions = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    
    # Configuration analysis
    complexity_score = serializers.SerializerMethodField()
    trigger_analysis = serializers.SerializerMethodField()
    actions_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowRule
        fields = [
            'id', 'name', 'description', 'trigger_type', 'trigger_object',
            'trigger_conditions', 'actions', 'is_active', 'execution_order',
            # Scheduling
            'schedule_type', 'delay_minutes', 'schedule_datetime',
            'recurrence_pattern',
            # Performance tracking
            'execution_count', 'success_count', 'failure_count',
            'last_executed', 'success_rate', 'avg_execution_time',
            'recent_executions', 'performance_summary',
            # Error handling
            'on_error_action', 'max_retries',
            # Analysis
            'complexity_score', 'trigger_analysis', 'actions_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'execution_count', 'success_count', 'failure_count',
            'last_executed', 'success_rate', 'avg_execution_time',
            'recent_executions', 'performance_summary', 'complexity_score',
            'trigger_analysis', 'actions_summary', 'created_at', 'updated_at'
        ]
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        if obj.execution_count > 0:
            return (obj.success_count / obj.execution_count) * 100
        return 0
    
    def get_avg_execution_time(self, obj):
        """Get average execution time"""
        executions = obj.executions.filter(
            status='COMPLETED',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        if executions.exists():
            total_time = sum([
                (exec.completed_at - exec.started_at).total_seconds()
                for exec in executions
            ])
            return int((total_time / executions.count()) * 1000)  # Convert to milliseconds
        return 0
    
    def get_recent_executions(self, obj):
        """Get recent execution summary"""
        recent = obj.executions.order_by('-created_at')[:10]
        return [
            {
                'id': exec.id,
                'status': exec.status,
                'created_at': exec.created_at,
                'duration_ms': self._get_execution_duration_ms(exec),
                'has_error': bool(exec.error_message)
            }
            for exec in recent
        ]
    
    def get_performance_summary(self, obj):
        """Get performance summary"""
        success_rate = self.get_success_rate(obj)
        return {
            'total_executions': obj.execution_count,
            'success_rate': success_rate,
            'performance_level': 'Excellent' if success_rate > 95 else 'Good' if success_rate > 80 else 'Poor',
            'avg_execution_time_ms': self.get_avg_execution_time(obj),
            'last_execution': obj.last_executed,
            'reliability': 'High' if obj.failure_count == 0 else 'Medium' if success_rate > 90 else 'Low'
        }
    
    def get_complexity_score(self, obj):
        """Calculate workflow complexity score"""
        score = 0
        
        # Base complexity from trigger conditions
        if obj.trigger_conditions:
            score += len(obj.trigger_conditions) * 2
        
        # Action complexity
        if obj.actions:
            score += len(obj.actions) * 3
            
            # Additional complexity for certain action types
            for action in obj.actions:
                action_type = action.get('type', '')
                if action_type in ['WEBHOOK', 'CREATE_RECORD']:
                    score += 5
                elif action_type in ['UPDATE_FIELD', 'SEND_EMAIL']:
                    score += 3
        
        # Scheduling complexity
        if obj.schedule_type != 'IMMEDIATE':
            score += 5
        
        if obj.recurrence_pattern:
            score += 10
        
        # Determine complexity level
        if score < 10:
            level = 'Simple'
        elif score < 30:
            level = 'Moderate'
        elif score < 60:
            level = 'Complex'
        else:
            level = 'Very Complex'
        
        return {'score': score, 'level': level}
    
    def get_trigger_analysis(self, obj):
        """Analyze trigger configuration"""
        return {
            'trigger_type': obj.trigger_type,
            'target_object': obj.trigger_object,
            'conditions_count': len(obj.trigger_conditions) if obj.trigger_conditions else 0,
            'is_time_based': obj.trigger_type == 'TIME_BASED',
            'is_immediate': obj.schedule_type == 'IMMEDIATE',
            'has_conditions': bool(obj.trigger_conditions)
        }
    
    def get_actions_summary(self, obj):
        """Summarize workflow actions"""
        if not obj.actions:
            return {'total_actions': 0, 'action_types': []}
        
        action_types = {}
        for action in obj.actions:
            action_type = action.get('type', 'UNKNOWN')
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        return {
            'total_actions': len(obj.actions),
            'action_types': action_types,
            'has_email_actions': any(action.get('type') == 'SEND_EMAIL' for action in obj.actions),
            'has_update_actions': any(action.get('type') == 'UPDATE_FIELD' for action in obj.actions),
            'has_webhook_actions': any(action.get('type') == 'WEBHOOK' for action in obj.actions)
        }
    
    def _get_execution_duration_ms(self, execution):
        """Get execution duration in milliseconds"""
        if execution.started_at and execution.completed_at:
            duration = execution.completed_at - execution.started_at
            return int(duration.total_seconds() * 1000)
        return None
    
    def validate_actions(self, value):
        """Validate actions configuration"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Actions must be a list")
        
        valid_action_types = [
            'SEND_EMAIL', 'CREATE_TASK', 'UPDATE_FIELD', 'ASSIGN_RECORD',
            'CREATE_RECORD', 'SEND_SMS', 'WEBHOOK', 'SCORE_UPDATE'
        ]
        
        for action in value:
            if not isinstance(action, dict):
                raise serializers.ValidationError("Each action must be a dictionary")
            
            action_type = action.get('type')
            if action_type not in valid_action_types:
                raise serializers.ValidationError(f"Invalid action type: {action_type}")
        
        return value
    
    def validate_trigger_conditions(self, value):
        """Validate trigger conditions"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Trigger conditions must be a dictionary")
        return value


class WorkflowAnalyticsSerializer(serializers.Serializer):
    """Workflow analytics serializer"""
    
    workflow_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    date_range = serializers.CharField(required=False, default='30d')
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'executions', 'success_rate', 'performance', 'errors',
            'trigger_analysis', 'action_effectiveness'
        ]),
        required=False,
        default=['executions', 'success_rate', 'performance']
    )
    
    def validate_date_range(self, value):
        """Validate date range"""
        valid_ranges = ['7d', '30d', '90d', '180d', '1y']
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Date range must be one of: {', '.join(valid_ranges)}")
        return value


class WorkflowTestSerializer(serializers.Serializer):
    """Serializer for testing workflows"""
    
    test_data = serializers.JSONField()
    dry_run = serializers.BooleanField(default=True)
    
    def validate_test_data(self, value):
        """Validate test data"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test data must be a dictionary")
        return value