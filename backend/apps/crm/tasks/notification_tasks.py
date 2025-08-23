"""
Notification Tasks
Handle system notifications, alerts, and communication delivery
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import logging
import json
from datetime import timedelta
from typing import List, Dict, Any

from .base import TenantAwareTask, RetryableTask, ThrottledTask
from ..models import (
    Notification, NotificationTemplate, NotificationPreference,
    SystemAlert, WebhookDelivery, User
)
from ..services.notification_service import NotificationService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=RetryableTask, bind=True)
def send_notification_task(self, user_id, notification_type, title, message, 
                          related_object_type=None, related_object_id=None, 
                          tenant_id=None, priority='medium', channels=None):
    """
    Send notification to user through multiple channels
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = NotificationService(tenant=tenant)
        
        # Create notification record
        notification = Notification.objects.create(
            tenant=tenant,
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            priority=priority,
            status='pending'
        )
        
        # Get user notification preferences
        preferences = service.get_user_notification_preferences(user, notification_type)
        
        # Determine delivery channels
        if not channels:
            channels = service.determine_delivery_channels(preferences, priority)
        
        delivery_results = []
        
        # Send through each channel
        for channel in channels:
            try:
                if channel == 'email':
                    result = service.send_email_notification(
                        user=user,
                        notification=notification,
                        template_context=self._build_template_context(notification, user, tenant)
                    )
                elif channel == 'sms':
                    result = service.send_sms_notification(user, notification)
                elif channel == 'push':
                    result = service.send_push_notification(user, notification)
                elif channel == 'in_app':
                    result = service.send_in_app_notification(user, notification)
                elif channel == 'slack':
                    result = service.send_slack_notification(user, notification)
                elif channel == 'webhook':
                    result = service.send_webhook_notification(user, notification)
                else:
                    continue
                
                delivery_results.append({
                    'channel': channel,
                    'success': result.get('success', False),
                    'message_id': result.get('message_id'),
                    'error': result.get('error')
                })
                
            except Exception as e:
                logger.error(f"Failed to send {channel} notification to user {user.id}: {e}")
                delivery_results.append({
                    'channel': channel,
                    'success': False,
                    'error': str(e)
                })
        
        # Update notification status
        successful_deliveries = sum(1 for r in delivery_results if r['success'])
        if successful_deliveries > 0:
            notification.status = 'delivered'
            notification.delivered_at = timezone.now()
        else:
            notification.status = 'failed'
        
        notification.delivery_results = delivery_results
        notification.delivery_channels = channels
        notification.save()
        
        logger.info(f"Notification sent to user {user.id}: {successful_deliveries}/{len(channels)} channels successful")
        
        return {
            'status': 'completed',
            'notification_id': notification.id,
            'successful_deliveries': successful_deliveries,
            'total_channels': len(channels),
            'delivery_results': delivery_results
        }
        
    except Exception as e:
        logger.error(f"Notification task failed: {e}")
        raise
    
    def _build_template_context(self, notification, user, tenant):
        """Build context for notification templates"""
        context = {
            'user_name': user.get_full_name(),
            'user_email': user.email,
            'notification_title': notification.title,
            'notification_message': notification.message,
            'notification_type': notification.notification_type,
            'notification_priority': notification.priority,
            'tenant_name': tenant.name if tenant else 'System',
            'dashboard_url': f"{settings.FRONTEND_URL}/dashboard",
            'unsubscribe_url': f"{settings.FRONTEND_URL}/notifications/unsubscribe?token={user.id}",
            'created_at': notification.created_at
        }
        
        # Add related object context if available
        if notification.related_object_type and notification.related_object_id:
            context.update(self._get_related_object_context(
                notification.related_object_type,
                notification.related_object_id,
                tenant
            ))
        
        return context
    
    def _get_related_object_context(self, object_type, object_id, tenant):
        """Get context for related objects"""
        context = {}
        
        try:
            if object_type == 'lead':
                from ..models import Lead
                obj = Lead.objects.get(id=object_id, tenant=tenant)
                context.update({
                    'lead_name': f"{obj.first_name} {obj.last_name}",
                    'lead_company': obj.company,
                    'lead_url': f"{settings.FRONTEND_URL}/leads/{obj.id}"
                })
            elif object_type == 'opportunity':
                from ..models import Opportunity
                obj = Opportunity.objects.get(id=object_id, tenant=tenant)
                context.update({
                    'opportunity_name': obj.name,
                    'opportunity_value': obj.value,
                    'opportunity_url': f"{settings.FRONTEND_URL}/opportunities/{obj.id}"
                })
            elif object_type == 'ticket':
                from ..models import Ticket
                obj = Ticket.objects.get(id=object_id, tenant=tenant)
                context.update({
                    'ticket_subject': obj.subject,
                    'ticket_priority': obj.priority,
                    'ticket_url': f"{settings.FRONTEND_URL}/tickets/{obj.id}"
                })
        except Exception as e:
            logger.warning(f"Failed to get related object context: {e}")
        
        return context


@shared_task(base=ThrottledTask, bind=True)
def send_bulk_notifications_task(self, notification_data_list, tenant_id=None, batch_size=50):
    """
    Send notifications to multiple users in bulk
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = NotificationService(tenant=tenant)
        
        # Apply rate limiting
        self.check_rate_limit('bulk_notifications')
        
        sent_count = 0
        failed_count = 0
        
        # Process in batches to avoid overwhelming the system
        for i in range(0, len(notification_data_list), batch_size):
            batch = notification_data_list[i:i + batch_size]
            
            for notification_data in batch:
                try:
                    # Queue individual notification
                    send_notification_task.delay(
                        user_id=notification_data['user_id'],
                        notification_type=notification_data['notification_type'],
                        title=notification_data['title'],
                        message=notification_data['message'],
                        related_object_type=notification_data.get('related_object_type'),
                        related_object_id=notification_data.get('related_object_id'),
                        tenant_id=tenant_id,
                        priority=notification_data.get('priority', 'medium'),
                        channels=notification_data.get('channels')
                    )
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to queue notification: {e}")
                    failed_count += 1
            
            # Apply throttling between batches
            if i + batch_size < len(notification_data_list):
                self.apply_throttling(delay_factor=0.5)
        
        logger.info(f"Bulk notifications queued: {sent_count} successful, {failed_count} failed")
        
        return {
            'status': 'completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_notifications': len(notification_data_list)
        }
        
    except Exception as e:
        logger.error(f"Bulk notification task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_webhook_deliveries_task(self, tenant_id=None, max_attempts=3):
    """
    Process pending webhook deliveries with retry logic
    """
    try:
        service = NotificationService()
        
        # Find pending webhook deliveries
        pending_deliveries = WebhookDelivery.objects.filter(
            success=False,
            attempts__lt=max_attempts,
            next_retry_at__lte=timezone.now()
        )
        
        if tenant_id:
            tenant = get_tenant_by_id(tenant_id)
            pending_deliveries = pending_deliveries.filter(tenant=tenant)
        
        processed_count = 0
        successful_count = 0
        
        for delivery in pending_deliveries[:100]:  # Process up to 100 at a time
            try:
                # Attempt delivery
                result = service.retry_webhook_delivery(delivery)
                
                # Update delivery record
                delivery.attempts += 1
                delivery.last_attempt_at = timezone.now()
                
                if result.get('success'):
                    delivery.success = True
                    delivery.delivered_at = timezone.now()
                    delivery.response_status = result.get('status_code')
                    delivery.response_body = result.get('response_body')
                    successful_count += 1
                else:
                    delivery.last_error = result.get('error')
                    # Calculate next retry time with exponential backoff
                    delay_minutes = min(60 * (2 ** delivery.attempts), 1440)  # Max 24 hours
                    delivery.next_retry_at = timezone.now() + timedelta(minutes=delay_minutes)
                
                delivery.save()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process webhook delivery {delivery.id}: {e}")
        
        logger.info(f"Processed {processed_count} webhook deliveries, {successful_count} successful")
        
        return {
            'status': 'completed',
            'processed_count': processed_count,
            'successful_count': successful_count
        }
        
    except Exception as e:
        logger.error(f"Webhook delivery processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_system_alert_task(self, alert_type, message, severity='warning', 
                          source=None, affected_users=None, tenant_id=None):
    """
    Send system-wide alerts to administrators
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = NotificationService(tenant=tenant)
        
        # Create system alert record
        alert = SystemAlert.objects.create(
            tenant=tenant,
            alert_type=alert_type,
            message=message,
            severity=severity,
            source=source or 'system',
            status='active',
            created_at=timezone.now()
        )
        
        # Determine recipients based on alert type and severity
        recipients = service.get_alert_recipients(
            alert_type=alert_type,
            severity=severity,
            tenant=tenant,
            affected_users=affected_users
        )
        
        notifications_sent = 0
        
        for recipient in recipients:
            try:
                # Send notification to recipient
                send_notification_task.delay(
                    user_id=recipient['user_id'],
                    notification_type='system_alert',
                    title=f"System Alert: {alert_type.title()}",
                    message=message,
                    related_object_type='system_alert',
                    related_object_id=alert.id,
                    tenant_id=tenant_id,
                    priority='high' if severity in ['critical', 'error'] else 'medium',
                    channels=recipient.get('preferred_channels', ['email', 'in_app'])
                )
                
                notifications_sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send system alert to user {recipient.get('user_id')}: {e}")
        
        logger.info(f"System alert sent to {notifications_sent} recipients")
        
        return {
            'status': 'completed',
            'alert_id': alert.id,
            'notifications_sent': notifications_sent,
            'severity': severity
        }
        
    except Exception as e:
        logger.error(f"System alert task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_escalations_task(self, tenant_id):
    """
    Process escalation rules for overdue items
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = NotificationService(tenant=tenant)
        
        # Process different types of escalations
        escalations_processed = 0
        
        # Ticket escalations
        ticket_escalations = service.process_ticket_escalations(tenant)
        escalations_processed += ticket_escalations
        
        # Lead escalations
        lead_escalations = service.process_lead_escalations(tenant)
        escalations_processed += lead_escalations
        
        # Opportunity escalations
        opportunity_escalations = service.process_opportunity_escalations(tenant)
        escalations_processed += opportunity_escalations
        
        # Activity escalations
        activity_escalations = service.process_activity_escalations(tenant)
        escalations_processed += activity_escalations
        
        logger.info(f"Processed {escalations_processed} escalations for tenant {tenant.name}")
        
        return {
            'status': 'completed',
            'total_escalations': escalations_processed,
            'ticket_escalations': ticket_escalations,
            'lead_escalations': lead_escalations,
            'opportunity_escalations': opportunity_escalations,
            'activity_escalations': activity_escalations
        }
        
    except Exception as e:
        logger.error(f"Escalation processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_digest_notifications_task(self, tenant_id, digest_type='daily', user_ids=None):
    """
    Send digest notifications (daily/weekly summaries)
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = NotificationService(tenant=tenant)
        
        # Get users who should receive digests
        if user_ids:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            users = User.objects.filter(id__in=user_ids)
        else:
            users = service.get_digest_recipients(tenant, digest_type)
        
        sent_count = 0
        
        for user in users:
            try:
                # Check if user wants this type of digest
                if not service.should_send_digest(user, digest_type):
                    continue
                
                # Generate digest content
                digest_data = service.generate_user_digest(
                    user=user,
                    tenant=tenant,
                    digest_type=digest_type
                )
                
                if not digest_data['has_content']:
                    continue  # Skip if no content to digest
                
                # Send digest notification
                send_notification_task.delay(
                    user_id=user.id,
                    notification_type=f'{digest_type}_digest',
                    title=digest_data['title'],
                    message=digest_data['summary'],
                    tenant_id=tenant.id,
                    priority='low',
                    channels=['email']  # Digests typically go via email
                )
                
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send digest to user {user.id}: {e}")
        
        logger.info(f"Sent {sent_count} {digest_type} digest notifications")
        
        return {
            'status': 'completed',
            'digest_type': digest_type,
            'sent_count': sent_count,
            'total_users': len(users)
        }
        
    except Exception as e:
        logger.error(f"Digest notification task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def cleanup_old_notifications_task(self, tenant_id=None, days_to_keep=90):
    """
    Clean up old notification records
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Clean up delivered notifications older than cutoff
        query = Notification.objects.filter(
            created_at__lt=cutoff_date,
            status='delivered'
        )
        
        if tenant_id:
            tenant = get_tenant_by_id(tenant_id)
            query = query.filter(tenant=tenant)
        
        deleted_count = query.delete()[0]
        
        # Clean up old webhook deliveries
        webhook_query = WebhookDelivery.objects.filter(
            delivered_at__lt=cutoff_date,
            success=True
        )
        
        if tenant_id:
            webhook_query = webhook_query.filter(tenant=tenant)
        
        webhook_deleted = webhook_query.delete()[0]
        
        # Clean up resolved system alerts
        alert_query = SystemAlert.objects.filter(
            created_at__lt=cutoff_date,
            status='resolved'
        )
        
        if tenant_id:
            alert_query = alert_query.filter(tenant=tenant)
        
        alerts_deleted = alert_query.delete()[0]
        
        logger.info(f"Notification cleanup: {deleted_count} notifications, {webhook_deleted} webhooks, {alerts_deleted} alerts")
        
        return {
            'status': 'completed',
            'notifications_deleted': deleted_count,
            'webhooks_deleted': webhook_deleted,
            'alerts_deleted': alerts_deleted
        }
        
    except Exception as e:
        logger.error(f"Notification cleanup failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def update_notification_preferences_task(self, user_id, preferences_data, tenant_id=None):
    """
    Update user notification preferences
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = NotificationService(tenant=tenant)
        
        # Update preferences
        updated_preferences = service.update_user_preferences(
            user=user,
            preferences=preferences_data
        )
        
        logger.info(f"Updated notification preferences for user {user.id}")
        
        return {
            'status': 'completed',
            'user_id': user.id,
            'updated_preferences': updated_preferences
        }
        
    except Exception as e:
        logger.error(f"Notification preferences update failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_welcome_notification_series_task(self, user_id, tenant_id, series_type='new_user'):
    """
    Send a series of welcome/onboarding notifications
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        tenant = get_tenant_by_id(tenant_id)
        service = NotificationService(tenant=tenant)
        
        # Get welcome series configuration
        series_config = service.get_welcome_series_config(series_type)
        
        notifications_scheduled = 0
        
        for step in series_config.get('steps', []):
            # Schedule notification with delay
            send_notification_task.apply_async(
                args=[
                    user.id,
                    step['notification_type'],
                    step['title'],
                    step['message']
                ],
                kwargs={
                    'tenant_id': tenant.id,
                    'priority': step.get('priority', 'medium'),
                    'channels': step.get('channels', ['email', 'in_app'])
                },
                countdown=step.get('delay_hours', 0) * 3600
            )
            
            notifications_scheduled += 1
        
        logger.info(f"Scheduled {notifications_scheduled} welcome notifications for user {user.id}")
        
        return {
            'status': 'completed',
            'user_id': user.id,
            'series_type': series_type,
            'notifications_scheduled': notifications_scheduled
        }
        
    except Exception as e:
        logger.error(f"Welcome notification series failed: {e}")
        raise