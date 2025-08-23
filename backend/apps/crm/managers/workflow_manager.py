"""
Workflow Manager - Business Process Automation
Advanced workflow and automation management
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
import json
from .base import AnalyticsManager


class WorkflowManager(AnalyticsManager):
    """
    Advanced Workflow Manager
    Business process automation and analytics
    """
    
    def active_workflows(self):
        """Get active workflows"""
        return self.filter(is_active=True)
    
    def by_trigger_type(self, trigger_type):
        """Filter workflows by trigger type"""
        return self.filter(trigger_type=trigger_type)
    
    def scheduled_workflows(self):
        """Get scheduled workflows"""
        return self.filter(trigger_type='scheduled')
    
    def event_driven_workflows(self):
        """Get event-driven workflows"""
        return self.filter(trigger_type__in=['created', 'updated', 'deleted', 'status_changed'])
    
    def get_workflow_performance_analytics(self, tenant, days=30):
        """Get comprehensive workflow performance analytics"""
        from ..models import WorkflowExecution
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Overall workflow metrics
        workflow_metrics = self.for_tenant(tenant).aggregate(
            total_workflows=Count('id'),
            active_workflows=Count('id', filter=Q(is_active=True)),
            automated_workflows=Count('id', filter=Q(
                trigger_type__in=['created', 'updated', 'scheduled']
            )),
            manual_workflows=Count('id', filter=Q(trigger_type='manual'))
        )
        
        # Execution metrics
        execution_metrics = WorkflowExecution.objects.filter(
            tenant=tenant,
            executed_at__range=[start_date, end_date]
        ).aggregate(
            total_executions=Count('id'),
            successful_executions=Count('id', filter=Q(status='completed')),
            failed_executions=Count('id', filter=Q(status='failed')),
            avg_execution_time=Avg('execution_time'),
            total_execution_time=Sum('execution_time')
        )
        
        # Calculate success rate
        success_rate = 0
        if execution_metrics['total_executions'] > 0:
            success_rate = (execution_metrics['successful_executions'] / execution_metrics['total_executions']) * 100
        
        # Top performing workflows
        top_workflows = self.for_tenant(tenant).annotate(
            execution_count=Count('executions', filter=Q(
                executions__executed_at__range=[start_date, end_date]
            )),
            success_count=Count('executions', filter=Q(
                executions__executed_at__range=[start_date, end_date],
                executions__status='completed'
            )),
            avg_execution_time=Avg('executions__execution_time', filter=Q(
                executions__executed_at__range=[start_date, end_date]
            ))
        ).filter(execution_count__gt=0).order_by('-execution_count')[:10]
        
        return {
            'workflow_metrics': workflow_metrics,
            'execution_metrics': {
                **execution_metrics,
                'success_rate': round(success_rate, 2)
            },
            'top_workflows': [
                {
                    'id': wf.id,
                    'name': wf.name,
                    'execution_count': wf.execution_count,
                    'success_count': wf.success_count,
                    'avg_execution_time': wf.avg_execution_time
                }
                for wf in top_workflows
            ],
            'period': f"Last {days} days"
        }
    
    def get_automation_roi_analysis(self, tenant, days=90):
        """Analyze ROI of workflow automation"""
        from ..models import WorkflowExecution
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        roi_data = []
        workflows = self.for_tenant(tenant).filter(is_active=True)
        
        for workflow in workflows:
            executions = WorkflowExecution.objects.filter(
                workflow=workflow,
                executed_at__range=[start_date, end_date],
                status='completed'
            )
            
            execution_count = executions.count()
            if execution_count == 0:
                continue
            
            # Calculate time savings (estimated)
            estimated_manual_time_per_execution = workflow.estimated_manual_time or 30  # minutes
            total_time_saved_minutes = execution_count * estimated_manual_time_per_execution
            total_time_saved_hours = total_time_saved_minutes / 60
            
            # Calculate cost savings (assuming average hourly rate)
            average_hourly_rate = 50  # This could be configurable
            cost_savings = total_time_saved_hours * average_hourly_rate
            
            # Calculate automation costs (development + maintenance)
            automation_cost = workflow.development_cost or 1000  # One-time cost
            maintenance_cost = (workflow.maintenance_cost_per_month or 100) * (days / 30)
            total_automation_cost = automation_cost + maintenance_cost
            
            # Calculate ROI
            roi = 0
            if total_automation_cost > 0:
                roi = ((cost_savings - total_automation_cost) / total_automation_cost) * 100
            
            roi_data.append({
                'workflow': {
                    'id': workflow.id,
                    'name': workflow.name,
                    'trigger_type': workflow.trigger_type
                },
                'roi_metrics': {
                    'execution_count': execution_count,
                    'time_saved_hours': round(total_time_saved_hours, 2),
                    'cost_savings': round(cost_savings, 2),
                    'automation_cost': round(total_automation_cost, 2),
                    'roi_percentage': round(roi, 2),
                    'payback_achieved': roi > 0
                }
            })
        
        return sorted(roi_data, key=lambda x: x['roi_metrics']['roi_percentage'], reverse=True)
    
    def get_workflow_bottleneck_analysis(self, tenant):
        """Identify workflow bottlenecks and optimization opportunities"""
        from ..models import WorkflowExecution
        
        bottleneck_data = []
        workflows = self.for_tenant(tenant).filter(is_active=True)
        
        for workflow in workflows:
            recent_executions = WorkflowExecution.objects.filter(
                workflow=workflow,
                executed_at__gte=timezone.now() - timedelta(days=30)
            )
            
            if not recent_executions.exists():
                continue
            
            execution_metrics = recent_executions.aggregate(
                total_executions=Count('id'),
                failed_executions=Count('id', filter=Q(status='failed')),
                avg_execution_time=Avg('execution_time'),
                max_execution_time=Max('execution_time'),
                min_execution_time=Min('execution_time')
            )
            
            failure_rate = 0
            if execution_metrics['total_executions'] > 0:
                failure_rate = (execution_metrics['failed_executions'] / execution_metrics['total_executions']) * 100
            
            # Identify bottleneck indicators
            bottlenecks = []
            if failure_rate > 10:
                bottlenecks.append('high_failure_rate')
            
            if execution_metrics['avg_execution_time'] and execution_metrics['avg_execution_time'] > 300:  # 5 minutes
                bottlenecks.append('slow_execution')
            
            if execution_metrics['max_execution_time'] and execution_metrics['min_execution_time']:
                time_variance = execution_metrics['max_execution_time'] - execution_metrics['min_execution_time']
                if time_variance > 600:  # 10 minutes variance
                    bottlenecks.append('inconsistent_performance')
            
            # Get common failure reasons
            failure_reasons = recent_executions.filter(
                status='failed'
            ).values('error_message').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            bottleneck_data.append({
                'workflow': {
                    'id': workflow.id,
                    'name': workflow.name,
                    'complexity_score': len(workflow.actions or [])
                },
                'performance_metrics': execution_metrics,
                'bottleneck_indicators': bottlenecks,
                'failure_rate': round(failure_rate, 2),
                'common_failures': list(failure_reasons),
                'optimization_priority': self._calculate_optimization_priority(
                    failure_rate, execution_metrics['avg_execution_time'], len(bottlenecks)
                )
            })
        
        return sorted(bottleneck_data, key=lambda x: x['optimization_priority'], reverse=True)
    
    def _calculate_optimization_priority(self, failure_rate, avg_execution_time, bottleneck_count):
        """Calculate optimization priority score (0-100)"""
        score = 0
        
        # Failure rate impact (40 points)
        score += min(failure_rate * 4, 40)
        
        # Execution time impact (30 points)
        if avg_execution_time:
            # Normalize to 0-30 scale (5+ minutes = max points)
            time_score = min((avg_execution_time / 300) * 30, 30)
            score += time_score
        
        # Bottleneck count impact (30 points)
        score += min(bottleneck_count * 10, 30)
        
        return round(score, 2)
    
    def auto_optimize_workflows(self, tenant, optimization_rules):
        """
        Auto-optimize workflows based on performance data
        
        optimization_rules format:
        {
            'disable_high_failure_workflows': True,
            'failure_rate_threshold': 25,
            'optimize_slow_workflows': True,
            'execution_time_threshold': 300,
            'consolidate_similar_workflows': True
        }
        """
        optimization_results = []
        
        # Get bottleneck analysis
        bottlenecks = self.get_workflow_bottleneck_analysis(tenant)
        
        for bottleneck in bottlenecks:
            workflow_id = bottleneck['workflow']['id']
            workflow = self.get(id=workflow_id)
            
            actions_taken = []
            
            # Disable high failure workflows
            if (optimization_rules.get('disable_high_failure_workflows', False) and
                bottleneck['failure_rate'] > optimization_rules.get('failure_rate_threshold', 25)):
                
                workflow.is_active = False
                workflow.save(update_fields=['is_active', 'modified_at'])
                actions_taken.append('disabled_due_to_high_failure_rate')
            
            # Flag slow workflows for review
            elif (optimization_rules.get('optimize_slow_workflows', False) and
                  bottleneck['performance_metrics']['avg_execution_time'] and
                  bottleneck['performance_metrics']['avg_execution_time'] > optimization_rules.get('execution_time_threshold', 300)):
                
                # Add optimization flag (this would be a custom field)
                # workflow.needs_optimization = True
                # workflow.save(update_fields=['needs_optimization', 'modified_at'])
                actions_taken.append('flagged_for_optimization')
            
            if actions_taken:
                optimization_results.append({
                    'workflow_id': workflow_id,
                    'workflow_name': workflow.name,
                    'actions_taken': actions_taken,
                    'reason': f"Failure rate: {bottleneck['failure_rate']}%, Avg execution time: {bottleneck['performance_metrics']['avg_execution_time']}s"
                })
        
        return {
            'optimization_results': optimization_results,
            'workflows_optimized': len(optimization_results)
        }
    
    def suggest_workflow_improvements(self, tenant, workflow_id=None):
        """Suggest improvements for workflows"""
        workflows = self.for_tenant(tenant).filter(is_active=True)
        if workflow_id:
            workflows = workflows.filter(id=workflow_id)
        
        suggestions = []
        
        for workflow in workflows:
            workflow_suggestions = {
                'workflow': {
                    'id': workflow.id,
                    'name': workflow.name
                },
                'suggestions': []
            }
            
            # Analyze workflow structure
            actions = workflow.actions or []
            conditions = workflow.conditions or []
            
            # Suggest improvements based on structure
            if len(actions) > 10:
                workflow_suggestions['suggestions'].append({
                    'type': 'complexity_reduction',
                    'priority': 'medium',
                    'suggestion': 'Consider breaking this workflow into smaller, focused workflows'
                })
            
            if not conditions:
                workflow_suggestions['suggestions'].append({
                    'type': 'add_conditions',
                    'priority': 'low',
                    'suggestion': 'Add conditions to make workflow more selective and efficient'
                })
            
            # Analyze performance data
            from ..models import WorkflowExecution
            recent_executions = WorkflowExecution.objects.filter(
                workflow=workflow,
                executed_at__gte=timezone.now() - timedelta(days=30)
            )
            
            if recent_executions.exists():
                failure_rate = recent_executions.filter(status='failed').count() / recent_executions.count() * 100
                
                if failure_rate > 5:
                    workflow_suggestions['suggestions'].append({
                        'type': 'error_handling',
                        'priority': 'high',
                        'suggestion': f'Improve error handling - current failure rate is {failure_rate:.1f}%'
                    })
                
                avg_time = recent_executions.aggregate(
                    avg_time=Avg('execution_time')
                )['avg_time']
                
                if avg_time and avg_time > 180:  # 3 minutes
                    workflow_suggestions['suggestions'].append({
                        'type': 'performance_optimization',
                        'priority': 'medium',
                        'suggestion': f'Optimize performance - average execution time is {avg_time:.1f} seconds'
                    })
            
            if workflow_suggestions['suggestions']:
                suggestions.append(workflow_suggestions)
        
        return suggestions
    
    def bulk_workflow_maintenance(self, tenant, maintenance_actions):
        """
        Perform bulk maintenance actions on workflows
        
        maintenance_actions format:
        {
            'cleanup_old_executions': {'days_to_keep': 90},
            'disable_unused_workflows': {'days_without_execution': 60},
            'update_workflow_metadata': True,
            'optimize_trigger_conditions': True
        }
        """
        maintenance_results = {}
        
        # Cleanup old executions
        if 'cleanup_old_executions' in maintenance_actions:
            from ..models import WorkflowExecution
            
            days_to_keep = maintenance_actions['cleanup_old_executions']['days_to_keep']
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            
            deleted_count = WorkflowExecution.objects.filter(
                tenant=tenant,
                executed_at__lt=cutoff_date
            ).delete()[0]
            
            maintenance_results['executions_cleaned'] = deleted_count
        
        # Disable unused workflows
        if 'disable_unused_workflows' in maintenance_actions:
            from ..models import WorkflowExecution
            
            days_threshold = maintenance_actions['disable_unused_workflows']['days_without_execution']
            cutoff_date = timezone.now() - timedelta(days=days_threshold)
            
            unused_workflows = self.for_tenant(tenant).filter(
                is_active=True
            ).exclude(
                executions__executed_at__gte=cutoff_date
            )
            
            disabled_count = unused_workflows.update(
                is_active=False,
                modified_at=timezone.now()
            )
            
            maintenance_results['workflows_disabled'] = disabled_count
        
        # Update workflow metadata
        if maintenance_actions.get('update_workflow_metadata', False):
            from ..models import WorkflowExecution
            
            updated_count = 0
            workflows = self.for_tenant(tenant).filter(is_active=True)
            
            for workflow in workflows:
                executions = WorkflowExecution.objects.filter(workflow=workflow)
                
                if executions.exists():
                    stats = executions.aggregate(
                        total_executions=Count('id'),
                        success_rate=Avg(Case(
                            When(status='completed', then=1),
                            default=0
                        )) * 100,
                        avg_execution_time=Avg('execution_time')
                    )
                    
                    # Update workflow with calculated stats
                    workflow.total_executions = stats['total_executions']
                    workflow.success_rate = stats['success_rate']
                    workflow.avg_execution_time = stats['avg_execution_time']
                    workflow.save(update_fields=[
                        'total_executions', 'success_rate', 'avg_execution_time', 'modified_at'
                    ])
                    updated_count += 1
            
            maintenance_results['metadata_updated'] = updated_count
        
        return maintenance_results