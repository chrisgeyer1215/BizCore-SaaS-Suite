# ============================================================================
# backend/apps/crm/services/campaign_service.py - Campaign Management Service
# ============================================================================

from typing import Dict, List, Any, Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.mail import send_mass_mail
from decimal import Decimal
from datetime import datetime, timedelta
import csv
import io

from .base import BaseService, CacheableMixin, NotificationMixin, CRMServiceException
from ..models import Campaign, CampaignMember, CampaignEmail, Lead, Contact, Account


class CampaignService(BaseService, CacheableMixin, NotificationMixin):
    """Comprehensive campaign management and analytics service"""
    
    @transaction.atomic
    def create_campaign:
        """Create new marketing campaign"""
        self.require_permission('can_manage_campaigns')
        
        # Validate required fields
        required_fields = ['name', 'campaign_type', 'start_date', 'end_date']
        self.validate_data(campaign_data, required_fields)
        
        # Set defaults
        campaign_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
            'updated_by': self.user,
        })
        
        # Set default owner if not provided
        if not campaign_data.get('owner'):
            campaign_data['owner'] = self.user
        
        campaign = Campaign.objects.create(**campaign_data)
        
        # Create audit trail
        self.create_audit_trail('CREATE', campaign)
        
        self.logger.info(f"Campaign created: {campaign.campaign_code}")
        return campaign
    
    @transaction.atomic
    def add_campaign_members(self, campaign_id: int:
        """Add members to campaign with deduplication"""
        campaign = self.get_queryset(Campaign).get(id=campaign_id)
        
        if not self.check_permission('can_manage_campaigns') and campaign.owner != self.user:
            raise PermissionDenied("Cannot manage campaigns not owned by you")
        
        results = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'details': []
        }
        
        for member_data in members_:
                email = member_data.get('email', '').lower().strip()
                if not email:
                    results['errors'] += 1
                    results['details'].append({
                        'email': 'N/A',
                        'status': 'error',
                        'reason': 'Missing email'
                    })
                    continue
                
                # Check for existing member
                existing_member = CampaignMember.objects.filter(
                    campaign=campaign,
                    email=email
                ).first()
                
                if existing_member:
                    if existing_member.status == 'UNSUBSCRIBED':
                        results['skipped'] += 1
                        results['details'].append({
                            'email': email,
                            'status': 'skipped',
                            'reason': 'Previously unsubscribed'
                        })
                        continue
                    else:
                        # Update existing member
                        for field, value in member_data.items():
                            if hasattr(existing_member, field) and field != 'email':
                                setattr(existing_member, field, value)
                        existing_member.save()
                        results['updated'] += 1
                        results['details'].append({
                            'email': email,
                            'status': 'updated'
                        })
                else:
                    # Create new member
                    member_data.update({
                        'tenant': self.tenant,
                        'campaign': campaign,
                        'email': email,
                        'created_by': self.user,
                    })
                    
                    # Link to existing CRM entities
                    self._link_member_to_crm_entities(member_data)
                    
                    CampaignMember.objects.create(**member_data)
                    results['added'] += 1
                    results['details'].append({
                        'email': email,
                        'status': 'added'
                    })
                    
            except Exception as e:
                results['errors'] += 1
                results['details'].append({
                    'email': member_data.get('email', 'N/A'),
                    'status': 'error',
                    'reason': str(e)
                })
                self.logger.error(f"Error adding campaign member: {e}")
        
        # Update campaign member count
        campaign.refresh_member_count()
        
        self.logger.info(f"Campaign members processed: {results}")
        return results
    
    def import_members_from_csv(self, campaign_id: int, csv_content: str, 
                               mapping: Dict = None) -> Dict:
        """Import campaign members from CSV data"""
        campaign = self.get_queryset(Campaign).get(id=campaign_id)
        
        # Parse CSV
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        # Default field mapping
        default_mapping = {
            'email': 'email',
            'first_name': 'first_name',
            'last_name': 'last_name',
            'company': 'company',
            'phone': 'phone'
        }
        
        field_mapping = mapping or default_mapping
        members_data = []
        
        for row in reader:
            member_data = {}
            for csv_field, crm_field in field_mapping.items():
                if csv_field in row:
                    member_data[crm_field] = row[csv_field]
            members_data.append(member_data)
        
        return self.add_campaign_members(campaign_id, members_data)
    
    @transaction.atomic
    def create_campaign_email(self, campaign_i) -> CampaignEmail:
        """Create campaign email with template processing"""
        campaign = self.get_queryset(Campaign).get(id=campaign_id)
        
        if not self.check_permission('can_send_emails') and campaign.owner != self.user:
            raise PermissionDenied("Cannot create emails for campaigns not owned by you")
        
        # Set defaults
        email_data.update({
            'tenant': self.tenant,
            'campaign': campaign,
            'created_by': self.user,
        })
        
        # Process email template
        if email_data.get('template'):
            template = email_data['template']
            email_data['html_content'] = template.body_html
            email_data['text_content'] = template.body_text
            email_data['subject'] = email_data.get('subject') or template.subject
        
        # Count recipients
        active_members = campaign.members.filter(status='ACTIVE')
        email_data['total_recipients'] = active_members.count()
        
        campaign_email = CampaignEmail.objects.create(**email_data)
        
        self.logger.info(f"Campaign email created: {campaign_email.id} for campaign {campaign.name}")
        return campaign_email
    
    @transaction.atomic
    def send_campaign_email(self, email_id: int, send_immediately: bool = False) -> Dict:
        """Send campaign email to all active members"""
        campaign_email = CampaignEmail.objects.get(
            id=email_id,
            tenant=self.tenant
        )
        
        if campaign_email.status not in ['DRAFT', 'SCHEDULED']:
            raise CRMServiceException("Email has already been sent or is in progress")
        
        if not send_immediately and not campaign_email.scheduled_datetime:
            raise CRMServiceException("Email must be scheduled or sent immediately")
        
        # Update status
        campaign_email.status = 'SENDING'
        campaign_email.save()
        
        try:
            # Get active campaign members
            members = campaign_email.campaign.members.filter(status='ACTIVE')
            
            # Prepare email messages
            messages = []
            sent_count = 0
            
            for member in members:
                try:
                    # Personalize content
                    personalized_content = self._personalize_email_content(
                        campaign_email,
                        member
                    )
                    
                    # Prepare message tuple for send_mass_mail
                    message = (
                        personalized_content['subject'],
                        personalized_content['text_content'],
                        campaign_email.from_email,
                        [member.email]
                    )
                    messages.append(message)
                    sent_count += 1
                    
                    # Track member email
                    self._track_member_email(campaign_email, member, 'SENT')
                    
                except Exception as e:
                    self.logger.error(f"Error preparing email for {member.email}: {e}")
            
            # Send emails in batches
            batch_size = 100
            total_sent = 0
            
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                try:
                    send_mass_mail(batch, fail_silently=False)
                    total_sent += len(batch)
                except Exception as e:
                    self.logger.error(f"Error sending email batch: {e}")
            
            # Update campaign email status
            campaign_email.status = 'SENT'
            campaign_email.sent_datetime = timezone.now()
            campaign_email.sent_count = total_sent
            campaign_email.save()
            
            # Update campaign metrics
            campaign = campaign_email.campaign
            campaign.emails_sent += total_sent
            campaign.save()
            
            return {
                'status': 'sent',
                'total_recipients': len(members),
                'sent_count': total_sent,
                'failed_count': len(members) - total_sent
            }
            
        except Exception as e:
            campaign_email.status = 'FAILED'
            campaign_email.save()
            raise CRMServiceException(f"Failed to send campaign email: {str(e)}")
    
    def track_email_engagement(self, email_id: int, member_email: str, 
                             event None) -> Dict:
        """Track email engagement events (opens, clicks, etc.)"""
        try:
            campaign_email = CampaignEmail.objects.get(id=email_id, tenant=self.tenant)
            member = campaign_email.campaign.members.get(email=member_email)
            
            # Update member engagement
            if event_type == 'OPENED':
                member.emails_opened += 1
                member.last_opened_date = timezone.now()
                campaign_email.opened_count += 1
            elif event_type == 'CLICKED':
                member.emails_clicked += 1
                member.last_clicked_date = timezone.now()
                campaign_email.clicked_count += 1
            elif event_type == 'BOUNCED':
                member.status = 'BOUNCED'
                campaign_email.bounced_count += 1
            elif event_type == 'UNSUBSCRIBED':
                member.status = 'UNSUBSCRIBED'
                member.unsubscribed_date = timezone.now()
                member.unsubscribe_reason = event_data.get('reason', 'User request')
                campaign_email.unsubscribed_count += 1
            
            member.save()
            campaign_email.save()
            
            # Update campaign totals
            self._update_campaign_engagement_metrics(campaign_email.campaign)
            
            return {'status': 'tracked', 'event': event_type}
            
        except Exception as e:
            self.logger.error(f"Error tracking email engagement: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_campaign_analytics(self, campaign_id: int) -> Dict:
        """Get comprehensive campaign analytics"""
        campaign = self.get_queryset(Campaign).get(id=campaign_id)
        
        # Basic metrics
        total_members = campaign.members.count()
        active_members = campaign.members.filter(status='ACTIVE').count()
        
        # Email performance
        total_emails_sent = campaign.emails_sent
        total_opened = campaign.emails_opened
        total_clicked = campaign.emails_clicked
        total_bounced = campaign.emails_bounced
        
        # Calculate rates
        open_rate = (total_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0
        click_rate = (total_clicked / total_emails_sent * 100) if total_emails_sent > 0 else 0
        bounce_rate = (total_bounced / total_emails_sent * 100) if total_emails_sent > 0 else 0
        
        # Lead generation metrics
        generated_leads = Lead.objects.filter(
            tenant=self.tenant,
            campaign=campaign
        ).count()
        
        qualified_leads = Lead.objects.filter(
            tenant=self.tenant,
            campaign=campaign,
            status__in=['QUALIFIED', 'CONVERTED']
        ).count()
        
        # Revenue tracking
        won_opportunities = campaign.opportunities.filter(is_won=True)
        total_revenue = won_opportunities.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # ROI calculation
        roi = 0
        if campaign.budget_spent > 0:
            roi = ((total_revenue - campaign.budget_spent) / campaign.budget_spent) * 100
        
        # Member status breakdown
        member_status_breakdown = campaign.members.values('status').annotate(
            count=models.Count('id')
        )
        
        # Daily engagement trends
        daily_engagement = campaign.members.filter(
            last_opened_date__isnull=False
        ).extra(
            select={'date': 'DATE(last_opened_date)'}
        ).values('date').annotate(
            opens=models.Count('id'),
            unique_opens=models.Count('email', distinct=True)
        ).order_by('date')
        
        # Top performing emails
        top_emails = campaign.emails.annotate(
            open_rate=models.Case(
                models.When(sent_count=0, then=0),
                default=models.F('opened_count') * 100.0 / models.F('sent_count'),
                output_field=models.FloatField()
            )
        ).order_by('-open_rate')[:5]
        
        return {
            'campaign_info': {
                'name': campaign.name,
                'type': campaign.campaign_type,
                'status': campaign.status,
                'start_date': campaign.start_date,
                'end_date': campaign.end_date,
                'budget_allocated': campaign.budget_allocated,
                'budget_spent': campaign.budget_spent,
            },
            'member_metrics': {
                'total_members': total_members,
                'active_members': active_members,
                'member_status_breakdown': list(member_status_breakdown),
            },
            'email_metrics': {
                'total_sent': total_emails_sent,
                'total_delivered': total_emails_sent - total_bounced,
                'total_opened': total_opened,
                'total_clicked': total_clicked,
                'total_bounced': total_bounced,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2),
                'bounce_rate': round(bounce_rate, 2),
            },
            'conversion_metrics': {
                'generated_leads': generated_leads,
                'qualified_leads': qualified_leads,
                'total_opportunities': campaign.total_opportunities,
                'won_opportunities': won_opportunities.count(),
                'total_revenue': total_revenue,
                'roi': round(roi, 2),
            },
            'engagement_trends': list(daily_engagement),
            'top_performing_emails': [
                {
                    'subject': email.subject,
                    'sent_count': email.sent_count,
                    'open_rate': round(email.open_rate, 2) if hasattr(email, 'open_rate') else 0,
                    'click_rate': round(email.click_rate, 2),
                }
                for email in top_emails
            ]
        }
    
    def run_ab_test(self, campaign_id: int, test_config: Dict) -> Dict:
        """Run A/B test for campaign emails"""
        campaign = self.get_queryset(Campaign).get(id=campaign_id)
        
        # Create test variants
        variant_a_data = test_config['variant_a']
        variant_b_data = test_config['variant_b']
        test_percentage = test_config.get('test_percentage', 50)
        
        # Get test audience
        all_members = campaign.members.filter(status='ACTIVE')
        test_size = int(all_members.count() * (test_percentage / 100))
        test_members = all_members[:test_size]
        
        # Split test audience
        split_point = len(test_members) // 2
        group_a = test_members[:split_point]
        group_b = test_members[split_point:]
        
        # Create variant emails
        variant_a = self.create_campaign_email(campaign_id, {
            **variant_a_data,
            'is_ab_test': True,
            'ab_test_percentage': test_percentage,
        })
        
        variant_b = self.create_campaign_email(campaign_id, {
            **variant_b_data,
            'is_ab_test': True,
            'ab_test_percentage': test_percentage,
        })
        
        # Send to test groups (would need to modify send logic to handle specific groups)
        # This is a simplified version - full implementation would need group targeting
        
        return {
            'test_id': f"{variant_a.id}_{variant_b.id}",
            'variant_a_id': variant_a.id,
            'variant_b_id': variant_b.id,
            'group_a_size': len(group_a),
            'group_b_size': len(group_b),
            'test_percentage': test_percentage,
        }
    
    def _link_member_to_crm_ Dict):
        """Link campaign member to existing CRM entities"""
        email = member_data.get('email')
        if not email:
            return
        
        # Try to link to existing lead
        lead = Lead.objects.filter(
            tenant=self.tenant,
            email=email
        ).first()
        
        if lead:
            member_data['lead'] = lead
            member_data['member_type'] = 'LEAD'
            return
        
        # Try to link to existing contact
        contact = Contact.objects.filter(
            tenant=self.tenant,
            email=email
        ).first()
        
        if contact:
            member_data['contact'] = contact
            member_data['account'] = contact.account
            member_data['member_type'] = 'CONTACT'
            return
        
        # Default to prospect
        member_data['member_type'] = 'PROSPECT'
    
    def _personalize_email_content(self, campaign_email: CampaignEmail, 
                                  member: CampaignMember) -> Dict:
        """Personalize email content for specific member"""
        from django.template import Context, Template
        
        context = {
            'member': {
                'first_name': member.first_name,
                'last_name': member.last_name,
                'full_name': member.full_name,
                'email': member.email,
                'company': member.company,
            },
            'campaign': {
                'name': campaign_email.campaign.name,
            },
            'unsubscribe_url': self._generate_unsubscribe_url(member),
        }
        
        # Process subject
        subject_template = Template(campaign_email.subject)
        personalized_subject = subject_template.render(Context(context))
        
        # Process content
        if campaign_email.html_content:
            html_template = Template(campaign_email.html_content)
            personalized_html = html_template.render(Context(context))
        else:
            personalized_html = None
        
        if campaign_email.text_content:
            text_template = Template(campaign_email.text_content)
            personalized_text = text_template.render(Context(context))
        else:
            personalized_text = personalized_html
        
        return {
            'subject': personalized_subject,
            'html_content': personalized_html,
            'text_content': personalized_text,
        }
    
    def _track_member_email(self, campaign_email: CampaignEmail, 
                           member: CampaignMember, status: str):
        """Track individual member email"""
        member.emails_sent += 1
        if status == 'SENT':
            member.save()
    
    def _update_campaign_engagement_metrics(self, campaign: Campaign):
        """Update campaign-level engagement metrics"""
        members = campaign.members.all()
        
        campaign.emails_opened = members.aggregate(
            total=models.Sum('emails_opened')
        )['total'] or 0
        
        campaign.emails_clicked = members.aggregate(
            total=models.Sum('emails_clicked')
        )['total'] or 0
        
        campaign.save()
    
    def _generate_unsubscribe_url(self, member: CampaignMember) -> str:
        """Generate unsubscribe URL for member"""
        import hashlib
        
        # Create secure token
        token_data = f"{member.campaign.id}:{member.email}:{member.created_at.isoformat()}"
        token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
        
        return f"/unsubscribe/{member.campaign.id}/{member.id}/{token}/"