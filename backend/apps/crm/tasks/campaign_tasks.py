"""
Campaign Processing Tasks
Handle campaign execution, optimization, and analytics
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Sum, Q, F
import logging
from datetime import timedelta

from .base import TenantAwareTask, BatchProcessingTask, ScheduledTask
from ..models import (
    Campaign, CampaignMember, Lead, Contact, Activity,
    EmailLog, WorkflowRule, WorkflowExecution
)
from ..services.campaign_service import CampaignService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=TenantAwareTask, bind=True)
def execute_campaign_task(self, campaign_id, tenant_id):
    """
    Execute a marketing campaign
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        service = CampaignService(tenant=tenant)
        
        logger.info(f"Executing campaign: {campaign.name}")
        
        # Update campaign status
        campaign.status = 'running'
        campaign.started_at = timezone.now()
        campaign.save(update_fields=['status', 'started_at'])
        
        # Execute campaign based on type
        if campaign.campaign_type == 'email':
            result = service.execute_email_campaign(campaign)
        elif campaign.campaign_type == 'social':
            result = service.execute_social_campaign(campaign)
        elif campaign.campaign_type == 'content':
            result = service.execute_content_campaign(campaign)
        elif campaign.campaign_type == 'paid_ads':
            result = service.execute_paid_ads_campaign(campaign)
        else:
            result = service.execute_generic_campaign(campaign)
        
        # Update campaign with execution results
        campaign.execution_result = result
        campaign.last_executed_at = timezone.now()
        campaign.save(update_fields=['execution_result', 'last_executed_at'])
        
        logger.info(f"Campaign {campaign.name} executed successfully")
        
        return {
            'status': 'completed',
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Campaign execution failed for campaign {campaign_id}: {e}")
        
        # Update campaign status to failed
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.error_message = str(e)
            campaign.save(update_fields=['status', 'error_message'])
        except:
            pass
        
        raise


@shared_task(base=BatchProcessingTask, bind=True)
def add_leads_to_campaign_task(self, campaign_id, lead_ids, tenant_id, batch_size=100):
    """
    Add leads to campaign in batches
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        leads = Lead.objects.filter(id__in=lead_ids, tenant=tenant)
        
        def process_lead_batch(batch):
            """Process a batch of leads"""
            members_to_create = []
            
            for lead in batch:
                # Check if lead already in campaign
                if not CampaignMember.objects.filter(
                    campaign=campaign,
                    lead=lead
                ).exists():
                    members_to_create.append(
                        CampaignMember(
                            campaign=campaign,
                            lead=lead,
                            contact=lead.contact if hasattr(lead, 'contact') else None,
                            joined_at=timezone.now(),
                            status='active'
                        )
                    )
            
            # Bulk create campaign members
            if members_to_create:
                CampaignMember.objects.bulk_create(members_to_create, batch_size=50)
            
            return len(members_to_create)
        
        # Process leads in batches
        result = self.process_in_batches(
            list(leads),
            batch_size=batch_size,
            process_func=process_lead_batch
        )
        
        # Update campaign member count
        campaign.member_count = campaign.members.count()
        campaign.save(update_fields=['member_count'])
        
        logger.info(f"Added {result['processed_items']} leads to campaign {campaign.name}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to add leads to campaign {campaign_id}: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_campaign_analytics_task(self, campaign_id, tenant_id):
    """
    Process and update campaign analytics
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        service = CampaignService(tenant=tenant)
        
        # Calculate campaign metrics
        analytics = service.calculate_comprehensive_analytics(campaign)
        
        # Update campaign with calculated metrics
        campaign.impressions = analytics.get('impressions', 0)
        campaign.clicks = analytics.get('clicks', 0)
        campaign.click_through_rate = analytics.get('click_through_rate', 0)
        campaign.conversions = analytics.get('conversions', 0)
        campaign.conversion_rate = analytics.get('conversion_rate', 0)
        campaign.cost_per_click = analytics.get('cost_per_click', 0)
        campaign.cost_per_lead = analytics.get('cost_per_lead', 0)
        campaign.roi_percentage = analytics.get('roi_percentage', 0)
        campaign.leads_generated = analytics.get('leads_generated', 0)
        campaign.revenue_generated = analytics.get('revenue_generated', 0)
        
        # Email specific metrics
        if campaign.campaign_type == 'email':
            campaign.emails_sent = analytics.get('emails_sent', 0)
            campaign.emails_delivered = analytics.get('emails_delivered', 0)
            campaign.emails_opened = analytics.get('emails_opened', 0)
            campaign.emails_clicked = analytics.get('emails_clicked', 0)
            campaign.emails_bounced = analytics.get('emails_bounced', 0)
            campaign.open_rate = analytics.get('open_rate', 0)
            campaign.bounce_rate = analytics.get('bounce_rate', 0)
            campaign.unsubscribe_rate = analytics.get('unsubscribe_rate', 0)
        
        campaign.analytics_updated_at = timezone.now()
        campaign.save()
        
        logger.info(f"Updated analytics for campaign {campaign.name}")
        
        return {
            'status': 'completed',
            'campaign_id': campaign_id,
            'analytics': analytics
        }
        
    except Exception as e:
        logger.error(f"Campaign analytics processing failed for campaign {campaign_id}: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def optimize_campaign_performance_task(self, tenant_id, optimization_rules=None):
    """
    Optimize campaign performance based on rules and AI insights
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = CampaignService(tenant=tenant)
        
        # Default optimization rules
        default_rules = {
            'pause_low_performing': True,
            'min_roi_threshold': -50.0,
            'max_cost_per_lead': 100.0,
            'increase_budget_high_performers': True,
            'roi_threshold_for_increase': 200.0,
            'budget_increase_percentage': 20.0
        }
        
        rules = optimization_rules or default_rules
        
        # Get active campaigns
        campaigns = Campaign.objects.filter(
            tenant=tenant,
            status='active',
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        optimization_results = []
        
        for campaign in campaigns:
            try:
                # Analyze campaign performance
                performance = service.analyze_campaign_performance(campaign)
                
                actions_taken = []
                
                # Pause low-performing campaigns
                if (rules.get('pause_low_performing', False) and 
                    performance.get('roi_percentage', 0) < rules.get('min_roi_threshold', -50)):
                    
                    campaign.status = 'paused'
                    campaign.paused_at = timezone.now()
                    campaign.pause_reason = f"Automated pause - ROI below threshold ({performance.get('roi_percentage', 0):.1f}%)"
                    campaign.save(update_fields=['status', 'paused_at', 'pause_reason'])
                    actions_taken.append('paused_low_roi')
                
                # Pause campaigns with high cost per lead
                elif (performance.get('cost_per_lead', 0) > rules.get('max_cost_per_lead', 100) and
                      performance.get('leads_generated', 0) > 5):  # Only if sufficient data
                    
                    campaign.status = 'paused'
                    campaign.paused_at = timezone.now()
                    campaign.pause_reason = f"Automated pause - High cost per lead (${performance.get('cost_per_lead', 0):.2f})"
                    campaign.save(update_fields=['status', 'paused_at', 'pause_reason'])
                    actions_taken.append('paused_high_cost')
                
                # Increase budget for high performers
                elif (rules.get('increase_budget_high_performers', False) and
                      performance.get('roi_percentage', 0) > rules.get('roi_threshold_for_increase', 200) and
                      campaign.budget):
                    
                    increase_percentage = rules.get('budget_increase_percentage', 20) / 100
                    budget_increase = campaign.budget * increase_percentage
                    
                    campaign.budget += budget_increase
                    campaign.budget_increased_at = timezone.now()
                    campaign.save(update_fields=['budget', 'budget_increased_at'])
                    actions_taken.append(f'increased_budget_{increase_percentage*100:.0f}%')
                
                if actions_taken:
                    optimization_results.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'performance': performance,
                        'actions_taken': actions_taken
                    })
                    
            except Exception as e:
                logger.error(f"Failed to optimize campaign {campaign.id}: {e}")
        
        logger.info(f"Optimized {len(optimization_results)} campaigns")
        
        return {
            'status': 'completed',
            'optimized_campaigns': len(optimization_results),
            'results': optimization_results
        }
        
    except Exception as e:
        logger.error(f"Campaign optimization failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def schedule_campaign_emails_task(self, campaign_id, tenant_id, send_at=None, batch_size=100):
    """
    Schedule campaign email delivery
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        
        if campaign.campaign_type != 'email':
            raise ValueError(f"Campaign {campaign.name} is not an email campaign")
        
        # Get campaign members who haven't received emails
        members = CampaignMember.objects.filter(
            campaign=campaign,
            email_sent=False,
            is_active=True
        )
        
        total_members = members.count()
        
        if total_members == 0:
            logger.info(f"No members to send emails for campaign {campaign.name}")
            return {'status': 'no_recipients', 'campaign_id': campaign_id}
        
        # Calculate send schedule
        send_time = send_at or timezone.now()
        batch_count = (total_members + batch_size - 1) // batch_size
        
        # Schedule email batches
        from .email_tasks import send_campaign_emails_task
        
        for i in range(batch_count):
            # Stagger batch sends to avoid overwhelming email server
            delay_minutes = i * 2  # 2 minutes between batches
            scheduled_time = send_time + timedelta(minutes=delay_minutes)
            
            send_campaign_emails_task.apply_async(
                args=[campaign_id, tenant_id, batch_size],
                eta=scheduled_time
            )
        
        # Update campaign status
        campaign.email_scheduled = True
        campaign.scheduled_send_time = send_time
        campaign.save(update_fields=['email_scheduled', 'scheduled_send_time'])
        
        logger.info(f"Scheduled {batch_count} email batches for campaign {campaign.name}")
        
        return {
            'status': 'scheduled',
            'campaign_id': campaign_id,
            'total_recipients': total_members,
            'batch_count': batch_count,
            'scheduled_time': send_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Campaign email scheduling failed for campaign {campaign_id}: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def create_campaign_activities_task(self, campaign_id, tenant_id, activity_type='campaign_engagement'):
    """
    Create follow-up activities for campaign members
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        service = CampaignService(tenant=tenant)
        
        # Get campaign members who engaged (opened, clicked, etc.)
        engaged_members = CampaignMember.objects.filter(
            campaign=campaign,
            email_opened=True,
            follow_up_created=False
        )
        
        activities_created = 0
        
        for member in engaged_members[:100]:  # Process up to 100 at a time
            try:
                # Create follow-up activity
                activity = service.create_follow_up_activity(
                    campaign=campaign,
                    member=member,
                    activity_type=activity_type
                )
                
                # Mark follow-up as created
                member.follow_up_created = True
                member.follow_up_activity = activity
                member.save(update_fields=['follow_up_created', 'follow_up_activity'])
                
                activities_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create follow-up activity for member {member.id}: {e}")
        
        logger.info(f"Created {activities_created} follow-up activities for campaign {campaign.name}")
        
        return {
            'status': 'completed',
            'campaign_id': campaign_id,
            'activities_created': activities_created
        }
        
    except Exception as e:
        logger.error(f"Campaign activity creation failed for campaign {campaign_id}: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def process_campaign_webhooks_task(self, tenant_id, webhook_data_list):
    """
    Process webhook data from email service providers
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = CampaignService(tenant=tenant)
        
        processed_count = 0
        
        for webhook_data in webhook_data_list:
            try:
                # Process webhook event (open, click, bounce, unsubscribe, etc.)
                result = service.process_webhook_event(webhook_data)
                
                if result:
                    processed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to
        logger.info(f"Processed {processed_count} webhook events")
        
        return {
            'status': 'completed',
            'processed_count': processed_count
        }
        
    except Exception as e:
        logger.error(f"Campaign webhook processing failed: {e}")
        raise


@shared_task(base=ScheduledTask, bind=True)
def generate_campaign_reports_task(self, tenant_id, report_type='weekly'):
    """
    Generate scheduled campaign performance reports
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = CampaignService(tenant=tenant)
        
        # Determine date range based on report type
        if report_type == 'daily':
            start_date = timezone.now() - timedelta(days=1)
        elif report_type == 'weekly':
            start_date = timezone.now() - timedelta(weeks=1)
        elif report_type == 'monthly':
            start_date = timezone.now() - timedelta(days=30)
        else:
            start_date = timezone.now() - timedelta(weeks=1)
        
        # Generate comprehensive report
        report = service.generate_performance_report(
            start_date=start_date,
            end_date=timezone.now(),
            include_comparisons=True
        )
        
        # Send report to stakeholders
        recipients = service.get_report_recipients(tenant)
        
        if recipients:
            from .email_tasks import send_email_task
            
            for recipient in recipients:
                send_email_task.delay(
                    recipient_email=recipient['email'],
                    subject=f"Campaign Performance Report - {report_type.title()}",
                    message="",
                    template_id='campaign_report',
                    context={
                        'recipient_name': recipient['name'],
                        'report': report,
                        'report_type': report_type,
                        'tenant_name': tenant.name
                    },
                    tenant_id=tenant.id
                )
        
        logger.info(f"Generated {report_type} campaign report for tenant {tenant.name}")
        
        return {
            'status': 'completed',
            'report_type': report_type,
            'report': report,
            'recipients_count': len(recipients)
        }
        
    except Exception as e:
        logger.error(f"Campaign report generation failed: {e}")
        raise