# ============================================================================
# backend/apps/crm/tasks/email_tasks.py - Email Campaign and Communication Tasks
# ============================================================================

from celery import group, chain, chord
from typing import Dict, List, Any, Optional
from django.core.mail import send_mail, send_mass_mail
from django.template import Template, Context
from django.utils import timezone
from datetime import timedelta
import logging

from apps.core.celery import app
from .base import AuditableTask
from ..models import Campaign, Lead, Account, Contact, EmailTemplate, EmailLog
from ..services.campaign_service import CampaignService
from ..services.activity_service import ActivityService

logger = logging.getLogger(__name__)


@app.task(base=AuditableTask, bind=True)
def send_email_campaign(self, campaign_id: int, recipient_batch: List[int], 
                       security_context: Dict):
    """
    Send email campaign to a batch of recipients with personalization and tracking
    
    Args:
        campaign_id: Campaign ID
        recipient_batch: List of recipient IDs
        security_context: Security context for permission validation
    """
    try:
        # Initialize services with security context
        campaign_service = CampaignService(
            tenant_id=security_context['tenant_id'],
            user_id=security_context['user_id']
        )
        
        # Get campaign details
        campaign = Campaign.objects.get(id=campaign_id, tenant_id=security_context['tenant_id'])
        
        if not campaign.is_active:
            return {'error': 'Campaign is not active', 'sent_count': 0}
        
        # Get email template
        email_template = campaign.email_template
        if not email_template:
            return {'error': 'No email template configured', 'sent_count': 0}
        
        # Process recipients in batch
        sent_count = 0
        failed_count = 0
        results = []
        
        for recipient_id in recipient_batch:
            try:
                # Get recipient (could be Lead, Account, or Contact)
                recipient = self._get_recipient(recipient_id, campaign.target_audience)
                
                if not recipient or not getattr(recipient, 'email', None):
                    failed_count += 1
                    continue
                
                # Personalize email content
                personalized_content = self._personalize_email_content(
                    email_template, recipient, campaign
                )
                
                # Send email
                success = self._send_single_campaign_email(
                    recipient.email,
                    personalized_content['subject'],
                    personalized_content['content'],
                    campaign,
                    recipient
                )
                
                if success:
                    sent_count += 1
                    
                    # Log email activity
                    self._log_email_activity(campaign, recipient, 'sent')
                    
                    # Update campaign statistics
                    self._update_campaign_stats(campaign_id, 'sent')
                else:
                    failed_count += 1
                    
                results.append({
                    'recipient_id': recipient_id,
                    'email': recipient.email,
                    'status': 'sent' if success else 'failed'
                })
                
            except Exception as e:
                logger.error(f"Failed to send email to recipient {recipient_id}: {e}")
                failed_count += 1
                results.append({
                    'recipient_id': recipient_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Update campaign status
        if sent_count > 0:
            campaign_service.update_campaign_execution_status(
                campaign_id, f"Batch processed: {sent_count} sent, {failed_count} failed"
            )
        
        return {
            'campaign_id': campaign_id,
            'batch_size': len(recipient_batch),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'results': results,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email campaign batch failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'campaign_id': campaign_id,
            'sent_count': 0,
            'failed_count': len(recipient_batch)
        }
    
    def _get_recipient(self, recipient_id: int, target_audience: str):
        """Get recipient object based on target audience type"""
        try:
            if target_audience == 'LEADS':
                return Lead.objects.filter(id=recipient_id, tenant_id=self.tenant_id).first()
            elif target_audience == 'ACCOUNTS':
                return Account.objects.filter(id=recipient_id, tenant_id=self.tenant_id).first()
            elif target_audience == 'CONTACTS':
                return Contact.objects.filter(id=recipient_id, tenant_id=self.tenant_id).first()
            return None
            
        except Exception as e:
            logger.error(f"Failed to get recipient {recipient_id}: {e}")
            return None
    
    def _personalize_email_content(self, template: EmailTemplate, recipient, campaign: Campaign) -> Dict:
        """Personalize email content with recipient data"""
        try:
            # Create context for template rendering
            context = {
                'recipient': recipient,
                'campaign': campaign,
                'company_name': self.tenant.name if self.tenant else 'Our Company',
                'current_date': timezone.now().strftime('%B %d, %Y'),
                'unsubscribe_url': self._generate_unsubscribe_url(recipient, campaign)
            }
            
            # Add recipient-specific context
            if hasattr(recipient, 'first_name'):
                context['first_name'] = recipient.first_name or 'Valued Customer'
            if hasattr(recipient, 'company'):
                context['company'] = recipient.company
            
            # Render subject and content
            subject_template = Template(template.subject)
            content_template = Template(template.content)
            
            personalized_subject = subject_template.render(Context(context))
            personalized_content = content_template.render(Context(context))
            
            return {
                'subject': personalized_subject,
                'content': personalized_content,
                'context': context
            }
            
        except Exception as e:
            logger.error(f"Email personalization failed: {e}")
            return {
                'subject': template.subject,
                'content': template.content
            }


@app.task(base=AuditableTask, bind=True)
def send_email_sequence(self, sequence_config: Dict, target_list: List[int], 
                       security_context: Dict):
    """
    Send automated email sequence (drip campaign) to target list
    
    Args:
        sequence_config: Email sequence configuration
        target_list: List of target recipient IDs
        security_context: Security context
    """
    try:
        sequence_name = sequence_config['name']
        emails = sequence_config['emails']  # List of email configs with delays
        
        # Create workflow for email sequence
        email_tasks = []
        
        for i, email_config in enumerate(emails):
            delay_hours = email_config.get('delay_hours', 0)
            
            # Schedule email task with delay
            if delay_hours > 0:
                eta = timezone.now() + timedelta(hours=delay_hours)
                email_task = send_single_email.apply_async(
                    args=[email_config, target_list, security_context],
                    eta=eta
                )
            else:
                email_task = send_single_email.delay(
                    email_config, target_list, security_context
                )
            
            email_tasks.append(email_task.id)
        
        return {
            'sequence_name': sequence_name,
            'target_count': len(target_list),
            'emails_scheduled': len(emails),
            'task_ids': email_tasks,
            'started_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email sequence setup failed: {e}", exc_info=True)
        return {'error': str(e), 'sequence_name': sequence_config.get('name', 'unknown')}


@app.task(base=AuditableTask, bind=True)
def process_email_bounce
    """
    Process email bounce notification and update recipient status
    
    Args:: Security context
    """
    try:
        email_address = bounce_data.get('email')
        bounce_type = bounce_data.get('type', 'hard')  # hard, soft, complaint
        bounce_reason = bounce_data.get('reason', '')
        
        if not email_address:
            return {'error': 'No email address in bounce data'}
        
        # Find all records with this email address
        bounced_records = []
        
        # Check Leads
        leads = Lead.objects.filter(
            email=email_address, 
            tenant_id=security_context['tenant_id']
        )
        for lead in leads:
            self._handle_email_bounce(lead, bounce_type, bounce_reason)
            bounced_records.append({'type': 'Lead', 'id': lead.id})
        
        # Check Contacts
        contacts = Contact.objects.filter(
            email=email_address,
            tenant_id=security_context['tenant_id']
        )
        for contact in contacts:
            self._handle_email_bounce(contact, bounce_type, bounce_reason)
            bounced_records.append({'type': 'Contact', 'id': contact.id})
        
        # Update EmailLog records
        EmailLog.objects.filter(
            recipient_email=email_address,
            tenant_id=security_context['tenant_id']
        ).update(
            status='bounced',
            bounce_type=bounce_type,
            bounce_reason=bounce_reason,
            bounced_at=timezone.now()
        )
        
        return {
            'email': email_address,
            'bounce_type': bounce_type,
            'records_updated': len(bounced_records),
            'bounced_records': bounced_records,
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email bounce processing failed: {e}", exc_info=True)
        return {'error': str(e), 'email': bounce_data.get('email')}
    
    def _handle_email_bounce(self, record, bounce_type: str, reason: str):
        """Handle email bounce for individual record"""
        try:
            if bounce_type == 'hard':
                # Hard bounce - mark email as invalid
                record.email_status = 'invalid'
                record.email_bounce_count = getattr(record, 'email_bounce_count', 0) + 1
            elif bounce_type == 'soft':
                # Soft bounce - increment bounce count
                bounce_count = getattr(record, 'email_bounce_count', 0) + 1
                record.email_bounce_count = bounce_count
                
                # If too many soft bounces, treat as hard bounce
                if bounce_count >= 3:
                    record.email_status = 'invalid'
            elif bounce_type == 'complaint':
                # Spam complaint - mark for suppression
                record.email_status = 'suppressed'
                record.unsubscribed_at = timezone.now()
            
            record.last_bounce_date = timezone.now()
            record.last_bounce_reason = reason
            record.save()
            
        except Exception as e:
            logger.error(f"Individual bounce handling failed: {e}")


@app.task(base=AuditableTask, bind=True)
def send_single_email(self, email_config: Dict, recipients: List[int], 
                     security_context: Dict):
    """
    Send single email to list of recipients
    
    Args:
        email_config: Email configuration (subject, content, template_id)
        recipients: List of recipient IDs
        security_context: Security context
    """
    try:
        sent_count = 0
        failed_count = 0
        
        # Get email template if specified
        template = None
        if email_config.get('template_id'):
            template = EmailTemplate.objects.filter(
                id=email_config['template_id'],
                tenant_id=security_context['tenant_id']
            ).first()
        
        for recipient_id in recipients:
            try:
                # Get recipient
                recipient = self._get_recipient(recipient_id, email_config.get('audience_type', 'LEADS'))
                
                if not recipient or not getattr(recipient, 'email', None):
                    failed_count += 1
                    continue
                
                # Prepare email content
                if template:
                    personalized = self._personalize_email_content(template, recipient, None)
                    subject = personalized['subject']
                    content = personalized['content']
                else:
                    subject = email_config['subject']
                    content = email_config['content']
                
                # Send email
                success = send_mail(
                    subject=subject,
                    message=content,
                    from_email=None,  # Use default
                    recipient_list=[recipient.email],
                    fail_silently=False,
                    html_message=content if '<html>' in content.lower() else None
                )
                
                if success:
                    sent_count += 1
                    
                    # Log email
                    EmailLog.objects.create(
                        recipient_email=recipient.email,
                        subject=subject,
                        status='sent',
                        sent_at=timezone.now(),
                        tenant_id=security_context['tenant_id'],
                        user_id=security_context['user_id']
                    )
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send email to {recipient_id}: {e}")
                failed_count += 1
        
        return {
            'recipients_count': len(recipients),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Single email send failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'sent_count': 0,
            'failed_count': len(recipients)
        }


@app.task(base=AuditableTask, bind=True)
def send_email_notification(self, notification_config: Dict, security_context: Dict):
    """
    Send system email notifications (alerts, reminders, etc.)
    
    Args:
        notification_config: Notification configuration
        security_context: Security context
    """
    try:
        notification_type = notification_config['type']
        recipients = notification_config['recipients']  # List of email addresses
        subject = notification_config['subject']
        content = notification_config['content']
        priority = notification_config.get('priority', 'normal')
        
        # Add system context to content
        enhanced_content = self._add_system_context(content, security_context)
        
        # Send notification
        success_count = 0
        for recipient_email in recipients:
            try:
                send_mail(
                    subject=f"[CRM] {subject}",
                    message=enhanced_content,
                    from_email=None,
                    recipient_list=[recipient_email],
                    fail_silently=False
                )
                success_count += 1
                
                # Log notification
                EmailLog.objects.create(
                    recipient_email=recipient_email,
                    subject=subject,
                    status='sent',
                    email_type='notification',
                    priority=priority,
                    sent_at=timezone.now(),
                    tenant_id=security_context['tenant_id'],
                    user_id=security_context['user_id']
                )
                
            except Exception as e:
                logger.error(f"Failed to send notification to {recipient_email}: {e}")
        
        return {
            'notification_type': notification_type,
            'recipients_count': len(recipients),
            'success_count': success_count,
            'failed_count': len(recipients) - success_count,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email notification failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'notification_type': notification_config.get('type', 'unknown')
        }
    
    def _add_system_context(self, content: str, security_context: Dict) -> str:
        """Add system context to notification content"""
        try:
            system_footer = f"""

---
System Information:
- Tenant: {self.tenant.name if self.tenant else 'Unknown'}
- Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- User: {self.user.get_full_name() if self.user else 'System'}

This is an automated notification from the CRM system.
"""
            
            return content + system_footer
            
        except Exception as e:
            logger.error(f"System context addition failed: {e}")
            return content


# Workflow tasks for complex email campaigns
@app.task(base=AuditableTask, bind=True)
def execute_email_campaign_workflow(self, campaign_id: int, security_context: Dict):
    """
    Execute complete email campaign workflow with batching and monitoring
    
    Args:
        campaign_id: Campaign ID
        security_context: Security context
    """
    try:
        # Get campaign and validate
        campaign = Campaign.objects.get(id=campaign_id, tenant_id=security_context['tenant_id'])
        
        if not campaign.is_active:
            return {'error': 'Campaign is not active'}
        
        # Get target audience
        campaign_service = CampaignService(
            tenant_id=security_context['tenant_id'],
            user_id=security_context['user_id']
        )
        
        target_recipients = campaign_service.get_campaign_recipients(campaign_id)
        
        if not target_recipients:
            return {'error': 'No recipients found for campaign'}
        
        # Batch recipients for processing
        batch_size = 50  # Process in batches of 50
        recipient_batches = [
            target_recipients[i:i + batch_size] 
            for i in range(0, len(target_recipients), batch_size)
        ]
        
        # Create group of batch tasks
        batch_tasks = group(
            send_email_campaign.s(campaign_id, batch, security_context)
            for batch in recipient_batches
        )
        
        # Execute batches
        batch_results = batch_tasks.apply_async()
        
        # Update campaign status
        campaign_service.update_campaign_execution_status(
            campaign_id, 
            f"Workflow started: {len(recipient_batches)} batches, {len(target_recipients)} recipients"
        )
        
        return {
            'campaign_id': campaign_id,
            'total_recipients': len(target_recipients),
            'batch_count': len(recipient_batches),
            'batch_task_ids': [task.id for task in batch_results.children],
            'workflow_started_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email campaign workflow failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'campaign_id': campaign_id
        }