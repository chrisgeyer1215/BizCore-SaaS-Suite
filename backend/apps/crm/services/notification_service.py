# ============================================================================
# backend/apps/crm/services/notification_service.py - Notification Management Service
# ============================================================================

from typing import Dict, List, Any, Optional
from django.db import transaction
from django.core.mail import send_mail, send_mass_mail
from django.template import Context, Template
from django.utils import timezone
from django.contrib.auth import get_user_model
import json
import logging
from datetime import timedelta

from .base import BaseService, CacheableMixin, CRMServiceException
from ..models import EmailTemplate, EmailLog, SMSLog

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService(BaseService, CacheableMixin):
    """Comprehensive notification service for email, SMS, and in-app notifications"""
    
    def __init__(self, tenant, user=None):
        super().__init__(tenant, user)
        self.email_providers = self._initialize_email_providers()
        self.sms_providers = self._initialize_sms_providers()
    
    @transaction.atomic
    def send_email_notification(self, recipients: List[str], subject: str, 
                               message: str, template_id: Optional[int] = None,
                               context_ = None, **kwargs) -> Dict:
        """Send email notification with template support and tracking"""
        
        if not recipients:
            return {'status': 'error', 'message': 'No recipients provided'}
        
        sent_count = 0
        failed_count = 0
        email_logs = []
        
        # Process template if provided
        if template_id:
            try:
                template = EmailTemplate.objects.get(id=template_id, tenant=self.tenant)
                rendered_content = template.render_content(context_data or {})
                subject = rendered_content['subject']
                message = rendered_content['body']
                is_html = rendered_content['is_html']
            except EmailTemplate.DoesNotExist:
                return {'status': 'error', 'message': 'Template not found'}
        else:
            is_html = kwargs.get('is_html', False)
        
        # Email configuration
        from_email = kwargs.get('from_email', self._get_default_from_email())
        from_name = kwargs.get('from_name', self._get_default_from_name())
        reply_to = kwargs.get('reply_to')
        attachments = kwargs.get('attachments', [])
        
        for recipient in recipients:
            try:
                # Personalize content for individual recipient
                personalized_content = self._personalize_content(
                    subject, message, recipient, context_data
                )
                
                # Send email
                success = self._send_single_email(
                    recipient=recipient,
                    subject=personalized_content['subject'],
                    message=personalized_content['message'],
                    from_email=from_email,
                    from_name=from_name,
                    reply_to=reply_to,
                    is_html=is_html,
                    attachments=attachments
                )
                
                if success:
                    sent_count += 1
                    status = 'SENT'
                else:
                    failed_count += 1
                    status = 'FAILED'
                
                # Log email
                email_log = self._create_email_log(
                    recipient=recipient,
                    subject=personalized_content['subject'],
                    message=personalized_content['message'],
                    template=EmailTemplate.objects.get(id=template_id) if template_id else None,
                    status=status,
                    from_email=from_email,
                    from_name=from_name,
                    **kwargs
                )
                email_logs.append(email_log)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send email to {recipient}: {str(e)}")
                
                # Log failed email
                email_log = self._create_email_log(
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    status='FAILED',
                    error_message=str(e),
                    from_email=from_email,
                    **kwargs
                )
                email_logs.append(email_log)
        
        return {
            'status': 'completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_recipients': len(recipients),
            'email_logs': [log.id for log in email_logs]
        }
    
    @transaction.atomic
    def send_sms_notification(self, recipients: List[str], message: str, 
                             contextkwargs) -> Dict:
        """Send SMS notifications with provider failover"""
        
        if not recipients:
            return {'status': 'error', 'message': 'No recipients provided'}
        
        sent_count = 0
        failed_count = 0
        sms_logs = []
        
        provider = kwargs.get('provider', 'default')
        
        for recipient in recipients:
            try:
                # Validate phone number
                formatted_number = self._format_phone_number(recipient)
                if not formatted_number:
                    failed_count += 1
                    continue
                
                # Personalize message
                personalized_message = self._personalize_sms_content(
                    message, recipient, context_data
                )
                
                # Send SMS
                success, provider_response = self._send_single_sms(
                    recipient=formatted_number,
                    message=personalized_message,
                    provider=provider
                )
                
                if success:
                    sent_count += 1
                    status = 'SENT'
                else:
                    failed_count += 1
                    status = 'FAILED'
                
                # Log SMS
                sms_log = self._create_sms_log(
                    recipient=formatted_number,
                    message=personalized_message,
                    status=status,
                    provider=provider,
                    provider_response=provider_response,
                    **kwargs
                )
                sms_logs.append(sms_log)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send SMS to {recipient}: {str(e)}")
                
                # Log failed SMS
                sms_log = self._create_sms_log(
                    recipient=recipient,
                    message=message,
                    status='FAILED',
                    error_message=str(e),
                    provider=provider,
                    **kwargs
                )
                sms_logs.append(sms_log)
        
        return {
            'status': 'completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_recipients': len(recipients),
            'sms_logs': [log.id for log in sms_logs]
        }
    
    def send_in_app_notification(self, recipients: List[User], title: str, 
                                message: str, notification_type: str = 'INFO',
                                action_url: str = None, **kwargs) -> Dict:
        """Send in-app notifications"""
        
        # This would integrate with a real-time notification system
        # For now, we'll create database records that can be polled
        
        notifications_created = 0
        
        for recipient in recipients:
            try:
                # Create notification record (would need a Notification model)
                notification_data = {
                    'tenant': self.tenant,
                    'recipient': recipient,
                    'title': title,
                    'message': message,
                    'notification_type': notification_type,
                    'action_url': action_url,
                    'is_read': False,
                    'created_by': self.user,
                    'sent_at': timezone.now(),
                }
                
                # Store in cache for real-time notifications
                cache_key = f"notifications:{self.tenant.id}:{recipient.id}"
                cached_notifications = self.get_from_cache(cache_key, [])
                cached_notifications.append(notification_data)
                self.set_cache(cache_key, cached_notifications[-50:], 3600)  # Keep last 50
                
                notifications_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create in-app notification for {recipient.username}: {str(e)}")
        
        return {
            'status': 'completed',
            'notifications_created': notifications_created,
            'total_recipients': len(recipients)
        }
    
    def send_notification_batch(self, notification_batch: List[Dict]) -> Dict:
        """Send multiple notifications in a batch"""
        
        results = {
            'email': {'sent': 0, 'failed': 0},
            'sms': {'sent': 0, 'failed': 0},
            'in_app': {'sent': 0, 'failed': 0},
            'total_processed': 0,
            'errors': []
        }
        
        for notification in notification_batch:
            try:
                notification_type = notification.get('type', 'email')
                
                if notification_type == 'email':
                    result = self.send_email_notification(**notification)
                    results['email']['sent'] += result.get('sent_count', 0)
                    results['email']['failed'] += result.get('failed_count', 0)
                    
                elif notification_type == 'sms':
                    result = self.send_sms_notification(**notification)
                    results['sms']['sent'] += result.get('sent_count', 0)
                    results['sms']['failed'] += result.get('failed_count', 0)
                    
                elif notification_type == 'in_app':
                    result = self.send_in_app_notification(**notification)
                    results['in_app']['sent'] += result.get('notifications_created', 0)
                
                results['total_processed'] += 1
                
            except Exception as e:
                results['errors'].append({
                    'notification': notification,
                    'error': str(e)
                })
        
        return results
    
    def track_email_engagement(self, email_log_id: int, event_type: str, 
                              event -> Dict:
        """Track email engagement events (opens, clicks, bounces)"""
        
        try:
            email_log = EmailLog.objects.get(id=email_log_id, tenant=self.tenant)
            
            if event_type == 'OPENED':
                email_log.status = 'OPENED'
                email_log.opened_datetime = timezone.now()
                email_log.open_count += 1
                
            elif event_type == 'CLICKED':
                email_log.status = 'CLICKED'
                email_log.clicked_datetime = timezone.now()
                email_log.click_count += 1
                
            elif event_type == 'BOUNCED':
                email_log.status = 'BOUNCED'
                email_log.bounce_reason = event_data.get('reason', 'Unknown')
                
            elif event_type == 'UNSUBSCRIBED':
                email_log.status = 'UNSUBSCRIBED'
                
            elif event_type == 'REPLIED':
                email_log.status = 'REPLIED'
                email_log.replied_datetime = timezone.now()
            
            email_log.save()
            
            # Update template usage statistics if applicable
            if email_log.template:
                email_log.template.usage_count += 1
                email_log.template.last_used = timezone.now()
                email_log.template.save()
            
            return {'status': 'tracked', 'event_type': event_type}
            
        except EmailLog.DoesNotExist:
            return {'status': 'error', 'message': 'Email log not found'}
    
    def create_email_template(self, template_data: Dict) -> EmailTemplate:
        """Create new email template"""
        
        self.require_permission('can_manage_email_templates')
        
        template_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
        })
        
        template = EmailTemplate.objects.create(**template_data)
        
        self.logger.info(f"Email template created: {template.name}")
        return template
    
    def get_notification_analytics(self, date_range: Dict = None) -> Dict:
        """Get comprehensive notification analytics"""
        
        date_filter = self._build_date_filter(date_range)
        
        # Email analytics
        email_logs = EmailLog.objects.filter(tenant=self.tenant, **date_filter)
        email_stats = {
            'total_sent': email_logs.count(),
            'delivered': email_logs.filter(status='DELIVERED').count(),
            'opened': email_logs.filter(status='OPENED').count(),
            'clicked': email_logs.filter(status='CLICKED').count(),
            'bounced': email_logs.filter(status='BOUNCED').count(),
            'unsubscribed': email_logs.filter(status='UNSUBSCRIBED').count(),
        }
        
        # Calculate rates
        if email_stats['total_sent'] > 0:
            email_stats['delivery_rate'] = (email_stats['delivered'] / email_stats['total_sent']) * 100
            email_stats['open_rate'] = (email_stats['opened'] / email_stats['total_sent']) * 100
            email_stats['click_rate'] = (email_stats['clicked'] / email_stats['total_sent']) * 100
            email_stats['bounce_rate'] = (email_stats['bounced'] / email_stats['total_sent']) * 100
        
        # SMS analytics
        sms_logs = SMSLog.objects.filter(tenant=self.tenant, **date_filter)
        sms_stats = {
            'total_sent': sms_logs.count(),
            'delivered': sms_logs.filter(status='DELIVERED').count(),
            'failed': sms_logs.filter(status='FAILED').count(),
        }
        
        if sms_stats['total_sent'] > 0:
            sms_stats['delivery_rate'] = (sms_stats['delivered'] / sms_stats['total_sent']) * 100
        
        # Template performance
        template_performance = EmailTemplate.objects.filter(
            tenant=self.tenant,
            email_logs__in=email_logs
        ).values('name', 'template_type').annotate(
            usage_count=models.Count('email_logs'),
            open_rate=models.Avg('email_logs__open_count'),
            click_rate=models.Avg('email_logs__click_count')
        ).order_by('-usage_count')[:10]
        
        return {
            'email_statistics': email_stats,
            'sms_statistics': sms_stats,
            'template_performance': list(template_performance),
            'period': date_range or 'all_time'
        }
    
    def _send_single_email(self, recipient: str, subject: str, message: str,
                          from_email: str, from_name: str = None,
                          reply_to: str = None, is_html: bool = False,
                          attachments: List = None) -> bool:
        """Send single email using configured provider"""
        
        try:
            # Use Django's send_mail for basic implementation
            # In production, this would integrate with services like SendGrid, Mailgun, etc.
            
            email_kwargs = {
                'subject': subject,
                'message': message if not is_html else '',
                'from_email': f"{from_name} <{from_email}>" if from_name else from_email,
                'recipient_list': [recipient],
                'fail_silently': False,
            }
            
            if is_html:
                email_kwargs['html_message'] = message
            
            send_mail(**email_kwargs)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            return False
    
    def _send_single_sms(self, recipient: str, message: str, 
                        provider: str = 'default') -> tuple:
        """Send single SMS using configured provider"""
        
        try:
            # This would integrate with SMS providers like Twilio, AWS SNS, etc.
            # For now, we'll simulate the response
            
            success = True  # Simulate success
            provider_response = {
                'message_id': f"sms_{timezone.now().timestamp()}",
                'status': 'sent',
                'cost': 0.05  # Simulated cost
            }
            
            return success, provider_response
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {recipient}: {str(e)}")
            return False, {'error': str(e)}
    
    def _create_email_log(self, recipient: str, subject: str, message: str,
                         status: str, from_email: str, from_name: str = None,
                         template: EmailTemplate = None, **kwargs) -> EmailLog:
        """Create email log entry"""
        
        email_log = EmailLog.objects.create(
            tenant=self.tenant,
            subject=subject,
            sender_email=from_email,
            sender_name=from_name or '',
            recipient_email=recipient,
            body_html=message if kwargs.get('is_html') else '',
            body_text=message if not kwargs.get('is_html') else '',
            template=template,
            status=status,
            sent_datetime=timezone.now(),
            created_by=self.user,
            error_message=kwargs.get('error_message', ''),
            provider=kwargs.get('provider', 'default'),
        )
        
        return email_log
    
    def _create_sms_log(self, recipient: str, message: str, status: str,
                       provider: str, provider_response: Dict = None,
                       **kwargs) -> SMSLog:
        """Create SMS log entry"""
        
        sms_log = SMSLog.objects.create(
            tenant=self.tenant,
            sms_type='OUTBOUND',
            phone_number=recipient,
            message=message,
            sender=self.user,
            status=status,
            sent_datetime=timezone.now(),
            provider=provider,
            provider_message_id=provider_response.get('message_id', '') if provider_response else '',
            cost=provider_response.get('cost', 0) if provider_response else 0,
            error_message=kwargs.get('error_message', ''),
        )
        
        return sms_log
    
    def _personalize_content(self, subject: str, message: str, recipient: str,
                           context_:
        """Personalize email content for recipient"""
        
        context = context_data or {}
        context.update({
            'recipient_email': recipient,
            'tenant_name': self.tenant.name,
            'current_date': timezone.now().strftime('%Y-%m-%d'),
        })
        
        # Process subject template
        try:
            subject_template = Template(subject)
            personalized_subject = subject_template.render(Context(context))
        except Exception as e:
            logger.warning(f"Failed to personalize subject: {str(e)}")
            personalized_subject = subject
        
        # Process message template
        try:
            message_template = Template(message)
            personalized_message = message_template.render(Context(context))
        except Exception as e:
            logger.warning(f"Failed to personalize message: {str(e)}")
            personalized_message = message
        
        return {
            'subject': personalized_subject,
            'message': personalized_message
        }
    
    def _personalize_sms_content(self, message: str, recipient: str,
                                -> str:
        """Personalize SMS content for recipient"""
        
        context = context_data or {}
        context.update({
            'recipient_phone': recipient,
            'tenant_name': self.tenant.name,
        })
        
        try:
            message_template = Template(message)
            return message_template.render(Context(context))
        except Exception as e:
            logger.warning(f"Failed to personalize SMS: {str(e)}")
            return message
    
    def _format_phone_number(self, phone_number: str) -> Optional[str]:
        """Format and validate phone number"""
        
        # Remove non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # Basic validation (would be more sophisticated in production)
        if len(cleaned) >= 10:
            # Format as international number (simplified)
            if cleaned.startswith('1') and len(cleaned) == 11:
                return f"+{cleaned}"
            elif len(cleaned) == 10:
                return f"+1{cleaned}"
            else:
                return f"+{cleaned}"
        
        return None
    
    def _initialize_email_providers(self) -> Dict:
        """Initialize email provider configurations"""
        return {
            'default': 'django',
            'sendgrid': 'sendgrid_config',
            'mailgun': 'mailgun_config',
        }
    
    def _initialize_sms_providers(self) -> Dict:
        """Initialize SMS provider configurations"""
        return {
            'default': 'twilio',
            'twilio': 'twilio_config',
            'aws_sns': 'sns_config',
        }
    
    def _get_default_from_email(self) -> str:
        """Get default from email address"""
        return getattr(self.tenant, 'default_from_email', 'noreply@example.com')
    
    def _get_default_from_name(self) -> str:
        """Get default from name"""
        return getattr(self.tenant, 'company_name', 'CRM System')
    
    def _build_date_filter(self, date_range: Dict = None) -> Dict:
        """Build date filter for analytics queries"""
        if not date_range:
            return {}
        
        date_filter = {}
        if date_range.get('start_date'):
            date_filter['sent_datetime__gte'] = date_range['start_date']
        if date_range.get('end_date'):
            date_filter['sent_datetime__lte'] = date_range['end_date']
        
        return date_filter