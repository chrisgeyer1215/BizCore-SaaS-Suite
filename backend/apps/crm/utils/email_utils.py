# crm/utils/email_utils.py
"""
Email Utilities for CRM Module

Provides comprehensive email handling capabilities including:
- Email template rendering and processing
- Email sending with tracking
- Email validation and parsing
- Template management and personalization
- Email campaign utilities
- Bounce and unsubscribe handling
"""

import re
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import ssl

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils.html import strip_tags
from django.core.cache import cache

import bleach
from bs4 import BeautifulSoup


class EmailTemplateProcessor:
    """
    Process and render email templates with personalization.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.default_variables = self._get_default_variables()
    
    def _get_default_variables(self) -> Dict[str, Any]:
        """Get default template variables."""
        current_site = Site.objects.get_current()
        
        return {
            'site_name': current_site.name,
            'site_url': f"https://{current_site.domain}",
            'current_year': datetime.now().year,
            'current_date': timezone.now().strftime('%B %d, %Y'),
            'support_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@example.com'),
            'company_name': getattr(settings, 'COMPANY_NAME', current_site.name),
        }
    
    def render_template(self, 
                       template_content: str, 
                       context = None,
                       recipient -> str:
        """
        Render email template with context data.
        
        Args:
            template_content: Email template Recipient-specific data
        
        Returns:
            str: Rendered template content
        """
        if not template_content:
            return ""
        
        # Combine all context data
        context = self.default_variables.copy()update(context_data)
        if
        # Add recipient-specific variables
            context['recipient_name'] = self._get_recipient_name(recipient_data)
            context['recipient_email'] = recipient_data.get('email', '')
            context['recipient_first_name'] = recipient_data.get('first_name', '')
            context['recipient_last_name'] = recipient_data.get('last_name', '')
        
        try:
            template = Template(template_content)
            rendered = template.render(Context(context))
            return rendered
        except Exception as e:
            # Log error and return original content
            print(f"Template rendering error: {e}")
            return template_content
    
    def _get_recipient_name(
        """Extract recipient name from data."""
        if recipient_data.get('first_name') or recipient_data.get('last_name'):
            return f"{recipient_data.get('first_name', '')} {recipient_data.get('last_name', '')}".strip()
        elif recipient_data.get('company_name'):
            return recipient_data['company_name']
        elif recipient_data.get('email'):
            return recipient_data['email'].split('@')[0]
        else:
            return "Valued Customer"
    
    def process_merge_tags(self, content str:
        """
        Process merge tags in email content.
        
        Args:
             for merge tag replacement
        
        Returns:
            str: Content with merge tags replaced
        """
        # Common merge tag patterns
        merge_patterns = {
            r'\{\{(\w+)\}\}': lambda m: str(data.get(m.group(1), f'{{{{{m.group(1)}}}}}')),
            r'\[\[(\w+)\]\]': lambda m: str(data.get(m.group(1), f'[[{m.group(1)}]]')),
            r'\{(\w+)\}': lambda m: str(data.get(m.group(1), f'{{{m.group(1)}}}')),
        }
        
        processed_content = content
        for pattern, replacement_func in merge_patterns.items():
            processed_content = re.sub(pattern, replacement_func, processed_content)
        
        return processed_content
    
    def validate_template(self, template_content: str) -> Dict[str, Any]:
        """
        Validate email template for common issues.
        
        Args:
            template_content: Template content to validate
        
        Returns:
            Dict: Validation results
        """
        issues = []
        warnings = []
        
        if not template_content.strip():
            issues.append("Template content is empty")
            return {
                'is_valid': False,
                'issues': issues,
                'warnings': warnings
            }
        
        # Check for unclosed merge tags
        unclosed_tags = re.findall(r'\{\{[^}]*$|\[\[[^\]]*$', template_content)
        if unclosed_tags:
            issues.extend([f"Unclosed merge tag: {tag}" for tag in unclosed_tags])
        
        # Check for basic HTML structure if HTML content
        if '<html' in template_content.lower() or '<body' in template_content.lower():
            soup = BeautifulSoup(template_content, 'html.parser')
            
            # Check for missing alt tags on images
            images_without_alt = soup.find_all('img', alt=False)
            if images_without_alt:
                warnings.append(f"{len(images_without_alt)} images missing alt attributes")
            
            # Check for missing unsubscribe link
            if 'unsubscribe' not in template_content.lower():
                warnings.append("No unsubscribe link found")
        
        # Check for suspicious content
        spam_indicators = [
            'free money', 'act now', 'limited time', 'click here now',
            'urgent', 'congratulations you', 'you have won'
        ]
        
        content_lower = template_content.lower()
        found_spam = [indicator for indicator in spam_indicators if indicator in content_lower]
        if found_spam:
            warnings.extend([f"Potential spam indicator: {indicator}" for indicator in found_spam])
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }


class CRMEmailSender:
    """
    Handle email sending with CRM-specific features.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.template_processor = EmailTemplateProcessor(tenant)
    
    def send_crm_email(self,
                      recipient_email: str,
                      subject: str,
                      html_content: str = None,
                      text_content: str = None,
                      template_name: str =[str, Any] = None,[str, Any] = None,
                      attachments: List[Dict[str, Any]] = None,
                      track_opens: bool = True,
                      track_clicks: bool = True,
                      campaign_id: int = None) -> Dict[str, Any]:
        """
        Send CRM email with tracking and personalization.
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text content
            template_name: Email template Recipient-specific data
            attachments: List of attachment dictionaries
            track_opens: Enable open tracking
            track_clicks: Enable click tracking
            campaign_id: Associated campaign ID
        
        Returns:
            Dict: Send result with tracking information
        """
        try:
            # Generate tracking ID
            tracking_id = str(uuid.uuid4())
            
            # Process template if provided
            if template_name and not (html_content or text_content):
                template_data = self._load_email_template(template_name)    html_content = template_data.get('html_content')
                    text_content = template_data.get('text_content')
                    if not subject:
                        subject = template_data.get('subject', '')
            
            # Render content with context
            if html_content:
                html_content = self.template_processor.render_template(
                    html_content, context_data, recipient_data
                )
                
                # Add tracking pixels and links
                if track_opens:
                    html_content = self._add_open_tracking(html_content, tracking_id)
                
                if track_clicks:
                    html_content = self._add_click_tracking(html_content, tracking_id)
            
            if text_content:
                text_content = self.template_processor.render_template(
                    text_content, context_data, recipient_data
                )
            
            # Render subject
            subject = self.template_processor.render_template(
                subject, context_data, recipient_data
            )
            
            # Create email message
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=text_content or strip_tags(html_content or ''),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            
            if html_content:
                email_message.attach_alternative(html_content, "text/html")
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    email_message.attach(
                        attachment['filename'],
                        attachment['content'],
                        attachment.get('mimetype')
                    )
            
            # Send email
            email_message.send()
            
            # Log email send
            self._log_email_send(
                tracking_id=tracking_id,
                recipient_email=recipient_email,
                subject=subject,
                campaign_id=campaign_id,
                status='sent'
            )
            
            return {
                'success': True,
                'tracking_id': tracking_id,
                'message': 'Email sent successfully'
            }
            
        except Exception as e:
            # Log error
            self._log_email_send(
                tracking_id=tracking_id if 'tracking_id' in locals() else None,
                recipient_email=recipient_email,
                subject=subject,
                campaign_id=campaign_id,
                status='failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _load_email_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Load email template from database or files."""
        # Try to load from database first
        try:
            from crm.models.activity import EmailTemplate
            template = EmailTemplate.objects.filter(
                name=template_name,
                tenant=self.tenant,
                is_active=True
            ).first()
            
            if template:
                return {
                    'subject': template.subject,
                    'html_content': template.html_content,
                    'text_content': template.text_content
                }
        except:
            pass
        
        # Fallback to file-based templates
        try:
            html_content = render_to_string(f'crm/emails/{template_name}.html')
            text_content = render_to_string(f'crm/emails/{template_name}.txt')
            subject = render_to_string(f'crm/emails/{template_name}_subject.txt').strip()
            
            return {
                'subject': subject,
                'html_content': html_content,
                'text_content': text_content
            }
        except:
            return None
    
    def _add_open_tracking(self, html_content: str, tracking_id: str) -> str:
        """Add open tracking pixel to HTML content."""
        current_site = Site.objects.get_current()
        tracking_url = f"https://{current_site.domain}/api/crm/email/track/open/{tracking_id}/"
        
        tracking_pixel = f'<img src="{tracking_url}" width="1" height="1" style="display:none;" alt=""/>'
        
        # Try to insert before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
        else:
            html_content += tracking_pixel
        
        return html_content
    
    def _add_click_tracking(self, html_content: str, tracking_id: str) -> str:
        """Add click tracking to links in HTML content."""
        current_site = Site.objects.get_current()
        
        def replace_link(match):
            original_url = match.group(1)
            if original_url.startswith('mailto:') or original_url.startswith('#'):
                return match.group(0)  # Don't track mailto or anchor links
            
            # Create tracking URL
            tracking_url = f"https://{current_site.domain}/api/crm/email/track/click/{tracking_id}/"
            encoded_url = original_url.replace('&', '%26')
            tracked_url = f"{tracking_url}?url={encoded_url}"
            
            return f'href="{tracked_url}"'
        
        # Replace all href attributes
        html_content = re.sub(r'href="([^"]*)"', replace_link, html_content)
        return html_content
    
    def _log_email_send(self, **kwargs):
        """Log email send event."""
        try:
            from crm.models.activity import EmailLog
            
            EmailLog.objects.create(
                tenant=self.tenant,
                tracking_id=kwargs.get('tracking_id'),
                recipient_email=kwargs.get('recipient_email'),
                subject=kwargs.get('subject'),
                campaign_id=kwargs.get('campaign_id'),
                status=kwargs.get('status'),
                error_message=kwargs.get('error_message'),
                sent_at=timezone.now() if kwargs.get('status') == 'sent' else None
            )
        except Exception as e:
            print(f"Failed to log email send: {e}")


def send_crm_email(recipient_email: str,
                  subject: str,
                  html_content: str = None,
                  text_content: str = None,
                  template_name: str = None,
                   Any] = None,
                  tenant=None,
                  **kwargs) -> Dict[str, Any]:
    """
    Convenience function for sending CRM emails.
    
    Args:
        recipient_email: Recipient email address
        subject: Email subject
        html_content: HTML content
        text_content: Plain text content
        template_name: Template Recipient-specific data
        tenant: Tenant instance
        **kwargs: Additional arguments for CRMEmailSender
    
    Returns:
        Dict: Send result
    """
    sender = CRMEmailSender(tenant)
    return sender.send_crm_email(
        recipient_email=recipient_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        template_name=template_name,
        context_data=context_data,
        recipient_data=recipient_data,
        **kwargs
    )


def render_email_template(template_name = None,
                         recipient_ = None,
                         tenant=None) -> Dict[str, str]:
    """
    Render email template without sending.
    
    Args:
        template_name: Template name Recipient-specific data
        tenant: Tenant instance
    
    Returns:
        Dict: Rendered template components
    """
    processor = EmailTemplateProcessor(tenant)
    sender = CRMEmailSender(tenant)
    
    template_data = sender._load_email_template(template_name)
    if not
    
    return {
        'subject': processor.render_template(
            template_data['subject'], context_data, recipient_data
        ),
        'html_content': processor.render_template(
            template_data['html_content'], context_data, recipient_data
        ),
        'text_content': processor.render_template(
            template_data['text_content'], context_data, recipient_data
        )
    }


def validate_email_template(template_content: str, tenant=None) -> Dict[str, Any]:
    """
    Validate email template content.
    
    Args:
        template_content: Template content to validate
        tenant: Tenant instance
    
    Returns:
        Dict: Validation results
    """
    processor = EmailTemplateProcessor(tenant)
    return processor.validate_template(template_content)


def track_email_open(tracking_id: str, ip_address: str = None, user_agent: str = None):
    """
    Track email open event.
    
    Args:
        tracking_id: Email tracking ID
        ip_address: Client IP address
        user_agent: Client user agent
    """
    try:
        from crm.models.activity import EmailLog
        
        email_log = EmailLog.objects.filter(tracking_id=tracking_id).first()
        if email_log and not email_log.opened_at:
            email_log.opened_at = timezone.now()
            email_log.open_ip_address = ip_address
            email_log.open_user_agent = user_agent
            email_log.save(update_fields=['opened_at', 'open_ip_address', 'open_user_agent'])
            
    except Exception as e:
        print(f"Failed to track email open: {e}")


def track_email_click(tracking_id: str, clicked_url: str, ip_address: str = None):
    """
    Track email click event.
    
    Args:
        tracking_id: Email tracking ID
        clicked_url: URL that was clicked
        ip_address: Client IP address
    """
    try:
        from crm.models.activity import EmailLog
        
        email_log = EmailLog.objects.filter(tracking_id=tracking_id).first()
        if email_log:
            # Update click count and last clicked URL
            email_log.click_count = (email_log.click_count or 0) + 1
            email_log.last_clicked_url = clicked_url
            email_log.last_clicked_at = timezone.now()
            email_log.click_ip_address = ip_address
            email_log.save(update_fields=[
                'click_count', 'last_clicked_url', 'last_clicked_at', 'click_ip_address'
            ])
            
    except Exception as e:
        print(f"Failed to track email click: {e}")


def parse_email_content(raw_email: str) -> Dict[str, Any]:
    """
    Parse raw email content and extract components.
    
    Args:
        raw_email: Raw email content
    
    Returns:
        Dict: Parsed email components
    """
    import email
    from email.header import decode_header
    
    try:
        msg = email.message_from_string(raw_email)
        
        # Decode subject
        subject_parts = decode_header(msg.get('Subject', ''))
        subject = ''.join([
            part[0].decode(part[1] or 'utf-8') if isinstance(part[0], bytes) else part[0]
            for part in subject_parts
        ])
        
        # Extract sender and recipient
        from_addr = msg.get('From', '')
        to_addr = msg.get('To', '')
        
        # Extract body content
        html_content = None
        text_content = None
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))
                
                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    text_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == 'text/html' and 'attachment' not in content_disposition:
                    html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'content_type': content_type,
                            'size': len(part.get_payload(decode=True))
                        })
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            
            if content_type == 'text/plain':
                text_content = payload.decode('utf-8', errors='ignore')
            elif content_type == 'text/html':
                html_content = payload.decode('utf-8', errors='ignore')
        
        return {
            'subject': subject,
            'from_address': from_addr,
            'to_address': to_addr,
            'html_content': html_content,
            'text_content': text_content,
            'attachments': attachments,
            'date': msg.get('Date'),
            'message_id': msg.get('Message-ID'),
        }
        
    except Exception as e:
        return {
            'error': f"Failed to parse email: {e}",
            'raw_content': raw_email
        }


class EmailBounceHandler:
    """
    Handle email bounces and unsubscribe requests.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
    
    def process_bounce(self, bounce]) -> bool:
        """
        Process email bounce notification.
        
        Args: data
        
        Returns:
            bool: True if processed successfully
        """
        try:
            recipient_email = bounce_data.get('email')
            bounce_type = bounce_data.get('type', 'unknown')
            bounce_reason = bounce_data.get('reason', '')
            
            if not recipient_email:
                return False
            
            # Update email log if tracking ID provided
            tracking_id = bounce_data.get('tracking_id')
            if tracking_id:
                self._update_email_log_bounce(tracking_id, bounce_type, bounce_reason)
            
            # Handle different bounce types
            if bounce_type in ['permanent', 'hard']:
                self._handle_hard_bounce(recipient_email, bounce_reason)
            elif bounce_type in ['temporary', 'soft']:
                self._handle_soft_bounce(recipient_email, bounce_reason)
            
            return True
            
        except Exception as e:
            print(f"Failed to process bounce: {e}")
            return False
    
    def _update_email_log_bounce(self, tracking_id: str, bounce_type: str, bounce_reason: str):
        """Update email log with bounce information."""
        try:
            from crm.models.activity import EmailLog
            
            email_log = EmailLog.objects.filter(tracking_id=tracking_id).first()
            if email_log:
                email_log.bounce_type = bounce_type
                email_log.bounce_reason = bounce_reason
                email_log.bounced_at = timezone.now()
                email_log.save(update_fields=['bounce_type', 'bounce_reason', 'bounced_at'])
        except Exception as e:
            print(f"Failed to update email log bounce: {e}")
    
    def _handle_hard_bounce(self, email_address: str, reason: str):
        """Handle hard bounce by marking email as invalid."""
        try:
            # Mark email as bounced in relevant models
            from crm.models.account import Contact
            from crm.models.lead import Lead
            
            # Update contacts
            Contact.objects.filter(
                email=email_address,
                tenant=self.tenant
            ).update(
                email_bounced=True,
                email_bounce_reason=reason,
                email_bounce_date=timezone.now()
            )
            
            # Update leads
            Lead.objects.filter(
                email=email_address,
                tenant=self.tenant
            ).update(
                email_bounced=True,
                email_bounce_reason=reason,
                email_bounce_date=timezone.now()
            )
            
        except Exception as e:
            print(f"Failed to handle hard bounce: {e}")
    
    def _handle_soft_bounce(self, email_address: str, reason: str):
        """Handle soft bounce by incrementing bounce count."""
        try:
            from crm.models.account import Contact
            from crm.models.lead import Lead
            
            # Update bounce count for contacts
            contacts = Contact.objects.filter(email=email_address, tenant=self.tenant)
            for contact in contacts:
                contact.soft_bounce_count = (contact.soft_bounce_count or 0) + 1
                contact.last_soft_bounce_date = timezone.now()
                contact.last_soft_bounce_reason = reason
                
                # Mark as bounced if soft bounce count exceeds threshold
                if contact.soft_bounce_count >= 5:
                    contact.email_bounced = True
                    contact.email_bounce_reason = f"Soft bounces exceeded threshold: {reason}"
                    contact.email_bounce_date = timezone.now()
                
                contact.save()
            
            # Similar logic for leads
            leads = Lead.objects.filter(email=email_address, tenant=self.tenant)
            for lead in leads:
                lead.soft_bounce_count = (lead.soft_bounce_count or 0) + 1
                lead.last_soft_bounce_date = timezone.now()
                lead.last_soft_bounce_reason = reason
                
                if lead.soft_bounce_count >= 5:
                    lead.email_bounced = True
                    lead.email_bounce_reason = f"Soft bounces exceeded threshold: {reason}"
                    lead.email_bounce_date = timezone.now()
                
                lead.save()
                
        except Exception as e:
            print(f"Failed to handle soft bounce: {e}")
    
    def process_unsubscribe(self, email_address: str, campaign_id: int = None) -> bool:
        """
        Process unsubscribe request.
        
        Args:
            email_address: Email address to unsubscribe
            campaign_id: Specific campaign to unsubscribe from
        
        Returns:
            bool: True if processed successfully
        """
        try:
            from crm.models.account import Contact
            from crm.models.lead import Lead
            from crm.models.campaign import CampaignMember
            
            if campaign_id:
                # Unsubscribe from specific campaign
                CampaignMember.objects.filter(
                    email=email_address,
                    campaign_id=campaign_id,
                    tenant=self.tenant
                ).update(
                    is_unsubscribed=True,
                    unsubscribed_at=timezone.now()
                )
            else:
                # Global unsubscribe
                Contact.objects.filter(
                    email=email_address,
                    tenant=self.tenant
                ).update(
                    is_unsubscribed=True,
                    unsubscribed_at=timezone.now()
                )
                
                Lead.objects.filter(
                    email=email_address,
                    tenant=self.tenant
                ).update(
                    is_unsubscribed=True,
                    unsubscribed_at=timezone.now()
                )
            
            return True
            
        except Exception as e:
            print(f"Failed to process unsubscribe: {e}")
            return False


# Convenience functions
def get_email_statistics(tenant=None, campaign_id: int = None, 
                        start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """
    Get email statistics for analysis.
    
    Args:
        tenant: Tenant instance
        campaign_id: Specific campaign ID
        start_date: Start date for statistics
        end_date: End date for statistics
    
    Returns:
        Dict: Email statistics
    """
    try:
        from crm.models.activity import EmailLog
        from django.db.models import Count, Q
        
        # Build query filters
        filters = {'tenant': tenant} if tenant else {}
        if campaign_id:
            filters['campaign_id'] = campaign_id
        if start_date:
            filters['sent_at__gte'] = start_date
        if end_date:
            filters['sent_at__lte'] = end_date
        
        # Get email logs
        email_logs = EmailLog.objects.filter(**filters)
        
        # Calculate statistics
        total_sent = email_logs.filter(status='sent').count()
        total_opened = email_logs.filter(opened_at__isnull=False).count()
        total_clicked = email_logs.filter(click_count__gt=0).count()
        total_bounced = email_logs.filter(bounced_at__isnull=False).count()
        
        # Calculate rates
        open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        click_rate = (total_clicked / total_sent * 100) if total_sent > 0 else 0
        bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0
        
        return {
            'total_sent': total_sent,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'total_bounced': total_bounced,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'bounce_rate': round(bounce_rate, 2)
        }
        
    except Exception as e:
        print(f"Failed to get email statistics: {e}")
        return {}