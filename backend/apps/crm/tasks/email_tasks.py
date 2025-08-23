"""
Email Processing Tasks
Handle email sending, campaign delivery, and email analytics
"""

from celery import shared_task
from django.core.mail import send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import logging
from typing import List, Dict, Any
import time

from .base import TenantAwareTask, BatchProcessingTask, MonitoredTask
from ..models import (
    EmailTemplate, EmailLog, Campaign, CampaignMember, 
    Lead, Contact, Activity, EmailBounce
)
from ..services.email_service import EmailService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=MonitoredTask, bind=True)
def send_email_task(self, recipient_email, subject, message, template_id=None, 
                   context=None, tenant_id=None, sender_id=None):
    """
    Send individual email
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = EmailService(tenant=tenant)
        
        result = service.send_email(
            to_email=recipient_email,
            subject=subject,
            message=message,
            template_id=template_id,
            context=context or {},
            sender_id=sender_id
        )
        
        logger.info(f"Email sent successfully to {recipient_email}")
        return {
            'status': 'sent',
            'recipient': recipient_email,
            'email_id': result.get('email_id'),
            'message_id': result.get('message_id')
        }
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        raise


@shared_task(base=BatchProcessingTask, bind=True)
def send_bulk_emails_task(self, email_data_list, tenant_id, sender_id=None, 
                         batch_size=50, delay_between_batches=1):
    """
    Send bulk emails with throttling and error handling
    
    email_data_list format:
    [
        {
            'recipient': 'email@example.com',
            'subject': 'Subject',
            'message': 'Message',
            'template_id': 1,
            'context': {...}
        },
        ...
    ]
    """
    tenant = get_tenant_by_id(tenant_id)
    service = EmailService(tenant=tenant)
    
    def process_email_batch(batch):
        """Process a batch of emails"""
        results = []
        
        for email_data in batch:
            try:
                result = service.send_email(
                    to_email=email_data['recipient'],
                    subject=email_data['subject'],
                    message=email_data.get('message', ''),
                    template_id=email_data.get('template_id'),
                    context=email_data.get('context', {}),
                    sender_id=sender_id
                )
                
                results.append({
                    'recipient': email_data['recipient'],
                    'status': 'sent',
                    'email_id': result.get('email_id')
                })
                
            except Exception as e:
                logger.error(f"Failed to send email to {email_data['recipient']}: {e}")
                results.append({
                    'recipient': email_data['recipient'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Throttling delay between batches
        if delay_between_batches > 0:
            time.sleep(delay_between_batches)
        
        return results
    
    # Process in batches
    return self.process_in_batches(
        email_data_list,
        batch_size=batch_size,
        process_func=process_email_batch
    )


@shared_task(base=TenantAwareTask, bind=True)
def send_campaign_emails_task(self, campaign_id, tenant_id, batch_size=100):
    """
    Send emails for marketing campaign
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        
        # Get campaign members who haven't received emails yet
        members = CampaignMember.objects.filter(
            campaign=campaign,
            email_sent=False,
            is_active=True
        )[:batch_size]
        
        if not members.exists():
            logger.info(f"No pending emails for campaign {campaign.name}")
            return {'status': 'completed', 'sent_count': 0}
        
        service = EmailService(tenant=tenant)
        sent_count = 0
        failed_count = 0
        
        for member in members:
            try:
                # Prepare email context
                context = {
                    'first_name': member.contact.first_name if hasattr(member, 'contact') else '',
                    'last_name': member.contact.last_name if hasattr(member, 'contact') else '',
                    'company': member.contact.company if hasattr(member, 'contact') else '',
                    'campaign_name': campaign.name,
                    'unsubscribe_url': service.generate_unsubscribe_url(member),
                    **campaign.email_context
                }
                
                # Send email
                result = service.send_campaign_email(
                    campaign=campaign,
                    member=member,
                    context=context
                )
                
                # Mark as sent
                member.email_sent = True
                member.email_sent_at = timezone.now()
                member.save(update_fields=['email_sent', 'email_sent_at'])
                
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send campaign email to member {member.id}: {e}")
                failed_count += 1
        
        # Update campaign statistics
        campaign.emails_sent = (campaign.emails_sent or 0) + sent_count
        campaign.save(update_fields=['emails_sent'])
        
        logger.info(f"Campaign {campaign.name}: sent {sent_count}, failed {failed_count}")
        
        # Schedule next batch if there are more members
        remaining_members = CampaignMember.objects.filter(
            campaign=campaign,
            email_sent=False,
            is_active=True
        ).count()
        
        if remaining_members > 0:
            # Schedule next batch with delay
            send_campaign_emails_task.apply_async(
                args=[campaign_id, tenant_id, batch_size],
                countdown=60  # 1 minute delay between batches
            )
        
        return {
            'status': 'batch_completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'remaining_members': remaining_members
        }
        
    except Exception as e:
        logger.error(f"Campaign email task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_email_bounces_task(self, tenant_id=None):
    """
    Process email bounces and update contact status
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = EmailService(tenant=tenant)
        
        # Get unprocessed bounces
        bounces = EmailBounce.objects.filter(
            tenant=tenant,
            processed=False
        )[:1000]  # Process up to 1000 at a time
        
        processed_count = 0
        
        for bounce in bounces:
            try:
                service.process_email_bounce(bounce)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process bounce {bounce.id}: {e}")
        
        logger.info(f"Processed {processed_count} email bounces")
        
        return {
            'status': 'completed',
            'processed_count': processed_count
        }
        
    except Exception as e:
        logger.error(f"Email bounce processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_email_replies_task(self, tenant_id=None):
    """
    Process inbound email replies and create activities
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        service = EmailService(tenant=tenant)
        
        # This would integrate with email service provider APIs
        # to fetch and process inbound emails
        
        replies = service.fetch_email_replies()
        processed_count = 0
        
        for reply in replies:
            try:
                # Create activity for email reply
                activity = service.create_activity_from_email_reply(reply)
                processed_count += 1
                
                logger.info(f"Created activity {activity.id} from email reply")
                
            except Exception as e:
                logger.error(f"Failed to process email reply: {e}")
        
        return {
            'status': 'completed',
            'processed_count': processed_count
        }
        
    except Exception as e:
        logger.error(f"Email reply processing failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_activity_reminder_emails_task(self, tenant_id, reminder_type='due_today'):
    """
    Send reminder emails for activities
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = EmailService(tenant=tenant)
        
        # Get activities needing reminders
        if reminder_type == 'due_today':
            activities = Activity.objects.filter(
                tenant=tenant,
                due_date__date=timezone.now().date(),
                status__in=['pending', 'open'],
                reminder_sent=False
            )
        elif reminder_type == 'overdue':
            activities = Activity.objects.filter(
                tenant=tenant,
                due_date__lt=timezone.now(),
                status__in=['pending', 'open'],
                reminder_sent=False
            )
        else:
            activities = Activity.objects.none()
        
        sent_count = 0
        
        for activity in activities:
            try:
                if activity.assigned_to and activity.assigned_to.email:
                    context = {
                        'activity': activity,
                        'user_name': activity.assigned_to.get_full_name(),
                        'due_date': activity.due_date,
                        'activity_url': f"{settings.FRONTEND_URL}/activities/{activity.id}"
                    }
                    
                    service.send_template_email(
                        template_name='activity_reminder',
                        to_email=activity.assigned_to.email,
                        context=context
                    )
                    
                    # Mark reminder as sent
                    activity.reminder_sent = True
                    activity.save(update_fields=['reminder_sent'])
                    
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send reminder for activity {activity.id}: {e}")
        
        logger.info(f"Sent {sent_count} activity reminder emails")
        
        return {
            'status': 'completed',
            'sent_count': sent_count
        }
        
    except Exception as e:
        logger.error(f"Activity reminder task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_welcome_email_task(self, user_id, tenant_id):
    """
    Send welcome email to new user
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenant = get_tenant_by_id(tenant_id)
        user = User.objects.get(id=user_id)
        service = EmailService(tenant=tenant)
        
        context = {
            'user_name': user.get_full_name(),
            'tenant_name': tenant.name,
            'login_url': f"{settings.FRONTEND_URL}/auth/login",
            'support_email': tenant.support_email or settings.DEFAULT_FROM_EMAIL
        }
        
        service.send_template_email(
            template_name='welcome_email',
            to_email=user.email,
            context=context
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        
        return {
            'status': 'sent',
            'recipient': user.email
        }
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def send_password_reset_email_task(self, user_id, reset_token, tenant_id=None):
    """
    Send password reset email
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        user = User.objects.get(id=user_id)
        service = EmailService(tenant=tenant)
        
        context = {
            'user_name': user.get_full_name(),
            'reset_url': f"{settings.FRONTEND_URL}/auth/reset-password?token={reset_token}",
            'tenant_name': tenant.name if tenant else settings.SITE_NAME
        }
        
        service.send_template_email(
            template_name='password_reset',
            to_email=user.email,
            context=context
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        
        return {
            'status': 'sent',
            'recipient': user.email
        }
        
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def cleanup_email_logs_task(self, tenant_id=None, days_to_keep=90):
    """
    Clean up old email logs
    """
    try:
        tenant = get_tenant_by_id(tenant_id) if tenant_id else None
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        query = EmailLog.objects.filter(sent_at__lt=cutoff_date)
        if tenant:
            query = query.filter(tenant=tenant)
        
        deleted_count = query.delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old email logs")
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Email log cleanup failed: {e}")
        raise


@shared_task(base=MonitoredTask, bind=True)
def generate_email_analytics_task(self, tenant_id, days=30):
    """
    Generate email analytics and update campaign metrics
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = EmailService(tenant=tenant)
        
        # Generate comprehensive email analytics
        analytics = service.generate_email_analytics(days=days)
        
        # Update campaign metrics
        campaigns = Campaign.objects.filter(
            tenant=tenant,
            created_at__gte=timezone.now() - timezone.timedelta(days=days)
        )
        
        updated_campaigns = 0
        for campaign in campaigns:
            metrics = service.calculate_campaign_metrics(campaign)
            
            # Update campaign with calculated metrics
            campaign.open_rate = metrics.get('open_rate', 0)
            campaign.click_through_rate = metrics.get('click_rate', 0)
            campaign.bounce_rate = metrics.get('bounce_rate', 0)
            campaign.unsubscribe_rate = metrics.get('unsubscribe_rate', 0)
            campaign.save(update_fields=[
                'open_rate', 'click_through_rate', 'bounce_rate', 'unsubscribe_rate'
            ])
            
            updated_campaigns += 1
        
        logger.info(f"Generated email analytics and updated {updated_campaigns} campaigns")
        
        return {
            'status': 'completed',
            'analytics': analytics,
            'updated_campaigns': updated_campaigns
        }
        
    except Exception as e:
        logger.error(f"Email analytics generation failed: {e}")
        raise