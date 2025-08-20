# apps/inventory/api/v1/views/alerts.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Case, When, Avg
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.alerts import (
    InventoryAlertSerializer, InventoryAlertDetailSerializer,
    AlertRuleSerializer, AlertConfigurationSerializer, BulkAlertActionSerializer
)
from apps.inventory.models.alerts.alerts import InventoryAlert
from apps.inventory.services.alerts.alert_service import AlertService
from apps.inventory.services.alerts.notification_service import NotificationService
from apps.inventory.utils.exceptions import InventoryError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import ALERT_TYPES, ALERT_STATUSES, ALERT_PRIORITIES


class InventoryAlertViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing inventory alerts and notifications.
    
    Supports:
    - Real-time alert monitoring
    - Alert acknowledgment and resolution
    - Bulk alert operations
    - Alert rule management
    - Performance metrics and analytics
    """
    serializer_class = InventoryAlertSerializer
    detail_serializer_class = InventoryAlertDetailSerializer
    queryset = InventoryAlert.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific alerts with optimizations."""
        return InventoryAlert.objects.select_related(
            'product', 'warehouse', 'acknowledged_by', 'resolved_by'
        ).with_context_data().order_by('-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return self.detail_serializer_class
        elif self.action == 'bulk_action':
            return BulkAlertActionSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get alerts dashboard summary with key metrics."""
        try:
            queryset = self.get_queryset()
            
            # Calculate key metrics
            total_alerts = queryset.count()
            active_alerts = queryset.filter(status=ALERT_STATUSES.ACTIVE).count()
            acknowledged_alerts = queryset.filter(status=ALERT_STATUSES.ACKNOWLEDGED).count()
            resolved_alerts = queryset.filter(status=ALERT_STATUSES.RESOLVED).count()
            
            # Priority breakdown
            priority_breakdown = queryset.filter(
                status=ALERT_STATUSES.ACTIVE
            ).values('priority').annotate(
                count=Count('id')
            ).order_by('priority')
            
            # Alert type breakdown
            type_breakdown = queryset.filter(
                status=ALERT_STATUSES.ACTIVE
            ).values('alert_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Recent alerts (last 24 hours)
            recent_alerts = queryset.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Critical alerts requiring immediate attention
            critical_alerts = queryset.filter(
                status=ALERT_STATUSES.ACTIVE,
                priority=ALERT_PRIORITIES.CRITICAL
            ).count()
            
            # Response time metrics
            response_times = queryset.filter(
                acknowledged_at__isnull=False
            ).extra(
                select={
                    'response_time': '(acknowledged_at - created_at)'
                }
            ).values('response_time')
            
            avg_response_time_hours = None
            if response_times.exists():
                total_seconds = sum(
                    rt['response_time'].total_seconds() 
                    for rt in response_times if rt['response_time']
                )
                avg_response_time_hours = total_seconds / len(response_times) / 3600
            
            return Response({
                'success': True,
                'data': {
                    'total_alerts': total_alerts,
                    'active_alerts': active_alerts,
                    'acknowledged_alerts': acknowledged_alerts,
                    'resolved_alerts': resolved_alerts,
                    'critical_alerts': critical_alerts,
                    'recent_alerts_24h': recent_alerts,
                    'avg_response_time_hours': round(avg_response_time_hours, 2) if avg_response_time_hours else None,
                    'priority_breakdown': {
                        item['priority']: item['count'] 
                        for item in priority_breakdown
                    },
                    'type_breakdown': list(type_breakdown)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve alerts dashboard summary')
    
    @action(detail=False, methods=['get'])
    def active_alerts(self, request):
        """Get all active alerts with filtering options."""
        try:
            # Base query for active alerts
            active_alerts = self.get_queryset().filter(status=ALERT_STATUSES.ACTIVE)
            
            # Apply filters
            alert_type = request.query_params.get('alert_type')
            if alert_type:
                active_alerts = active_alerts.filter(alert_type=alert_type)
            
            priority = request.query_params.get('priority')
            if priority:
                active_alerts = active_alerts.filter(priority=priority)
            
            warehouse_id = request.query_params.get('warehouse_id')
            if warehouse_id:
                active_alerts = active_alerts.filter(warehouse_id=warehouse_id)
            
            product_id = request.query_params.get('product_id')
            if product_id:
                active_alerts = active_alerts.filter(product_id=product_id)
            
            # Sort by priority and creation time
            active_alerts = active_alerts.order_by('priority', '-created_at')
            
            page = self.paginate_queryset(active_alerts)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(active_alerts, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'total': active_alerts.count()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve active alerts')
    
    @action(detail=False, methods=['get'])
    def critical_alerts(self, request):
        """Get critical alerts requiring immediate attention."""
        try:
            critical_alerts = self.get_queryset().filter(
                status=ALERT_STATUSES.ACTIVE,
                priority=ALERT_PRIORITIES.CRITICAL
            ).order_by('-created_at')
            
            # Add escalation information
            alerts_data = []
            for alert in critical_alerts:
                alert_data = self.get_serializer(alert).data
                
                # Calculate age in hours
                age_hours = (timezone.now() - alert.created_at).total_seconds() / 3600
                alert_data['age_hours'] = round(age_hours, 1)
                
                # Check if escalation is needed (e.g., >2 hours without acknowledgment)
                alert_data['needs_escalation'] = age_hours > 2 and not alert.acknowledged_at
                
                alerts_data.append(alert_data)
            
            return Response({
                'success': True,
                'data': alerts_data,
                'total': len(alerts_data),
                'escalation_count': sum(1 for alert in alerts_data if alert['needs_escalation'])
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve critical alerts')
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert."""
        try:
            alert = self.get_object()
            
            if alert.status != ALERT_STATUSES.ACTIVE:
                return Response({
                    'success': False,
                    'errors': ['Only active alerts can be acknowledged']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            alert_service = AlertService(request.user.tenant)
            notes = request.data.get('notes', '')
            
            with transaction.atomic():
                alert_service.acknowledge_alert(
                    alert=alert,
                    user=request.user,
                    notes=notes
                )
            
            return Response({
                'success': True,
                'message': 'Alert acknowledged successfully',
                'data': {
                    'alert_id': alert.id,
                    'status': alert.status,
                    'acknowledged_at': alert.acknowledged_at,
                    'acknowledged_by': alert.acknowledged_by.get_full_name()
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to acknowledge alert')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert."""
        try:
            alert = self.get_object()
            
            if alert.status == ALERT_STATUSES.RESOLVED:
                return Response({
                    'success': False,
                    'errors': ['Alert is already resolved']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            alert_service = AlertService(request.user.tenant)
            resolution_notes = request.data.get('resolution_notes', '')
            
            with transaction.atomic():
                alert_service.resolve_alert(
                    alert=alert,
                    user=request.user,
                    resolution_notes=resolution_notes
                )
            
            return Response({
                'success': True,
                'message': 'Alert resolved successfully',
                'data': {
                    'alert_id': alert.id,
                    'status': alert.status,
                    'resolved_at': alert.resolved_at,
                    'resolved_by': alert.resolved_by.get_full_name()
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to resolve alert')
    
    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss an alert (mark as not relevant)."""
        try:
            alert = self.get_object()
            
            if alert.status == ALERT_STATUSES.DISMISSED:
                return Response({
                    'success': False,
                    'errors': ['Alert is already dismissed']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            alert_service = AlertService(request.user.tenant)
            dismissal_reason = request.data.get('dismissal_reason', 'Not relevant')
            
            with transaction.atomic():
                alert_service.dismiss_alert(
                    alert=alert,
                    user=request.user,
                    reason=dismissal_reason
                )
            
            return Response({
                'success': True,
                'message': 'Alert dismissed successfully',
                'data': {
                    'alert_id': alert.id,
                    'status': alert.status,
                    'dismissal_reason': dismissal_reason
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to dismiss alert')
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on multiple alerts."""
        try:
            alert_ids = request.data.get('alert_ids', [])
            action = request.data.get('action')  # 'acknowledge', 'resolve', 'dismiss'
            notes = request.data.get('notes', '')
            
            if not alert_ids or not action:
                return Response({
                    'success': False,
                    'errors': ['alert_ids and action are required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if action not in ['acknowledge', 'resolve', 'dismiss']:
                return Response({
                    'success': False,
                    'errors': ['Invalid action. Must be acknowledge, resolve, or dismiss']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            alert_service = AlertService(request.user.tenant)
            processed_count = 0
            errors = []
            
            with transaction.atomic():
                for alert_id in alert_ids:
                    try:
                        alert = InventoryAlert.objects.get(
                            id=alert_id,
                            tenant=request.user.tenant
                        )
                        
                        if action == 'acknowledge':
                            alert_service.acknowledge_alert(alert, request.user, notes)
                        elif action == 'resolve':
                            alert_service.resolve_alert(alert, request.user, notes)
                        elif action == 'dismiss':
                            alert_service.dismiss_alert(alert, request.user, notes)
                        
                        processed_count += 1
                        
                    except InventoryAlert.DoesNotExist:
                        errors.append(f"Alert {alert_id} not found")
                    except Exception as e:
                        errors.append(f"Error processing alert {alert_id}: {str(e)}")
            
            return Response({
                'success': True,
                'processed_count': processed_count,
                'error_count': len(errors),
                'errors': errors,
                'message': f'{action.title()}d {processed_count} alerts successfully'
            })
        except Exception as e:
            return self.handle_error(e, f'Failed to perform bulk {action}')
    
    @action(detail=False, methods=['post'])
    def generate_alerts(self, request):
        """Manually trigger alert generation process."""
        try:
            alert_service = AlertService(request.user.tenant)
            
            # Get optional filters
            warehouse_id = request.data.get('warehouse_id')
            alert_types = request.data.get('alert_types', [])
            
            with transaction.atomic():
                generated_alerts = alert_service.generate_alerts(
                    warehouse_id=warehouse_id,
                    alert_types=alert_types
                )
            
            return Response({
                'success': True,
                'message': 'Alerts generated successfully',
                'data': {
                    'generated_count': len(generated_alerts),
                    'alert_types_generated': list(set(
                        alert.alert_type for alert in generated_alerts
                    ))
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate alerts')
    
    @action(detail=False, methods=['get'])
    def alert_trends(self, request):
        """Get alert trends and analytics."""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            # Daily alert trends
            daily_trends = self.get_queryset().filter(
                created_at__gte=start_date
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(
                total_alerts=Count('id'),
                critical_alerts=Count('id', filter=Q(priority=ALERT_PRIORITIES.CRITICAL)),
                resolved_alerts=Count('id', filter=Q(status=ALERT_STATUSES.RESOLVED))
            ).order_by('day')
            
            # Alert type trends
            type_trends = self.get_queryset().filter(
                created_at__gte=start_date
            ).values('alert_type').annotate(
                count=Count('id'),
                avg_resolution_time=Avg(
                    F('resolved_at') - F('created_at'),
                    filter=Q(resolved_at__isnull=False)
                )
            ).order_by('-count')
            
            # Warehouse alert distribution
            warehouse_distribution = self.get_queryset().filter(
                created_at__gte=start_date
            ).values(
                'warehouse__name', 'warehouse__id'
            ).annotate(
                alert_count=Count('id'),
                critical_count=Count('id', filter=Q(priority=ALERT_PRIORITIES.CRITICAL))
            ).order_by('-alert_count')
            
            # Response time metrics
            response_metrics = {
                'avg_acknowledgment_time': None,
                'avg_resolution_time': None,
                'alerts_within_sla': 0,
                'total_responded_alerts': 0
            }
            
            acknowledged_alerts = self.get_queryset().filter(
                created_at__gte=start_date,
                acknowledged_at__isnull=False
            )
            
            if acknowledged_alerts.exists():
                total_ack_time = sum(
                    (alert.acknowledged_at - alert.created_at).total_seconds()
                    for alert in acknowledged_alerts
                )
                response_metrics['avg_acknowledgment_time'] = total_ack_time / acknowledged_alerts.count() / 3600
            
            resolved_alerts = self.get_queryset().filter(
                created_at__gte=start_date,
                resolved_at__isnull=False
            )
            
            if resolved_alerts.exists():
                total_res_time = sum(
                    (alert.resolved_at - alert.created_at).total_seconds()
                    for alert in resolved_alerts
                )
                response_metrics['avg_resolution_time'] = total_res_time / resolved_alerts.count() / 3600
                
                # Count alerts resolved within SLA (e.g., 24 hours)
                sla_hours = 24
                response_metrics['alerts_within_sla'] = sum(
                    1 for alert in resolved_alerts
                    if (alert.resolved_at - alert.created_at).total_seconds() <= sla_hours * 3600
                )
                response_metrics['total_responded_alerts'] = resolved_alerts.count()
            
            return Response({
                'success': True,
                'data': {
                    'period_days': days,
                    'daily_trends': list(daily_trends),
                    'type_trends': list(type_trends),
                    'warehouse_distribution': list(warehouse_distribution),
                    'response_metrics': response_metrics
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve alert trends')
    
    @action(detail=False, methods=['get'])
    def alert_rules(self, request):
        """Get current alert rules configuration."""
        try:
            alert_service = AlertService(request.user.tenant)
            
            # Get alert rules from settings
            alert_rules = alert_service.get_alert_rules()
            
            return Response({
                'success': True,
                'data': {
                    'alert_rules': alert_rules,
                    'rule_count': len(alert_rules)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve alert rules')
    
    @action(detail=False, methods=['post'])
    def update_alert_rules(self, request):
        """Update alert rules configuration."""
        try:
            alert_service = AlertService(request.user.tenant)
            new_rules = request.data.get('rules', {})
            
            # Validate and update rules
            updated_rules = alert_service.update_alert_rules(new_rules)
            
            return Response({
                'success': True,
                'message': 'Alert rules updated successfully',
                'data': {
                    'updated_rules': updated_rules
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to update alert rules')
    
    @action(detail=False, methods=['post'])
    def test_notification(self, request):
        """Test notification system with sample alert."""
        try:
            notification_service = NotificationService(request.user.tenant)
            
            test_data = {
                'recipient': request.data.get('recipient', request.user.email),
                'notification_type': request.data.get('notification_type', 'email'),
                'alert_type': request.data.get('alert_type', ALERT_TYPES.LOW_STOCK)
            }
            
            result = notification_service.send_test_notification(test_data)
            
            return Response({
                'success': True,
                'message': 'Test notification sent successfully',
                'data': result
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to send test notification')