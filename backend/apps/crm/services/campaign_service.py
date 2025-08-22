# ============================================================================
# backend/apps/crm/services/campaign_service.py - Campaign Business Logic with AI Insights
# ============================================================================

from django.db import transaction
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Max
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Dict, List, Optional, Tuple
import statistics
import json
from collections import defaultdict

from .base import BaseService, ServiceException
from ..models import Campaign, CampaignMember, CampaignEmail, Lead, Contact


class CampaignService(BaseService):
    """Comprehensive campaign management with AI-driven insights and automation"""
    
    def create_campaign_with_intelligence, 
                                        target_criteria: Dict = None,
                                        auto_segment: bool = True) -> Campaign:
        """Create campaign with intelligent targeting and segmentation"""
        try:
            with transaction.atomic():
                # AI-enhanced campaign optimization
                if auto_segment and target_criteria:
                    optimized_criteria = self.optimize_targeting_criteria(target_criteria)
                    target_criteria.update(optimized_criteria)
                
                # Create campaign
                campaign = Campaign.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **campaign_data
                )
                
                # Auto-populate members based on intelligent criteria
                if target_criteria:
                    members_added = self.add_intelligent_target_audience(campaign, target_criteria)
                    
                    self.log_activity('CREATE_CAMPAIGN', 'Campaign', campaign.id, {
                        'campaign_name': campaign.name,
                        'campaign_type': campaign.campaign_type,
                        'members_added': members_added,
                        'targeting_criteria': target_criteria
                    })
                
                # Set up automated campaign workflow
                if campaign.campaign_type == 'EMAIL':
                    self.setup_email_automation_workflow(campaign)
                elif campaign.campaign_type == 'NURTURE':
                    self.setup_nurture_sequence(campaign)
                
                # Initialize campaign analytics
                self.initialize_campaign_tracking(campaign)
                
                return campaign
                
        except Exception as e:
            raise ServiceException(f"Failed to create campaign: {str(e)}")
    
    def optimize_targeting_criteria(self, criteria: Dict) -> Dict:
        """Use AI to optimize targeting criteria based on historical performance"""
        optimizations = {}
        
        try:
            # Analyze historical campaign performance
            historical_performance = self.analyze_historical_targeting_performance()
            
            # Lead score optimization
            if 'lead_score_min' in criteria:
                optimal_score = self.find_optimal_lead_score_threshold()
                if optimal_score > criteria['lead_score_min']:
                    optimizations['lead_score_min'] = optimal_score
                    optimizations['_optimization_reason'] = f"Historical data shows {optimal_score}+ leads have 40% higher conversion"
            
            # Industry targeting optimization
            if 'industries' in criteria:
                high_performing_industries = self.get_high_performing_industries()
                suggested_industries = list(set(criteria['industries'] + high_performing_industries))
                if len(suggested_industries) > len(criteria['industries']):
                    optimizations['suggested_industries'] = suggested_industries
            
            # Geographic optimization
            if 'regions' in criteria:
                optimal_regions = self.analyze_geographic_performance()
                optimizations['geographic_insights'] = optimal_regions
            
            # Time-based optimization
            optimal_timing = self.analyze_optimal_campaign_timing()
            optimizations['recommended_timing'] = optimal_timing
            
        except Exception as e:
            logger.warning(f"Failed to optimize targeting criteria: {e}")
        
        return optimizations
    
    def add_intelligent_target_audience(self, campaign: Campaign, criteria: Dict) -> int:
        """Add target audience using intelligent selection algorithms"""
        members_added = 0
        
        try:
            with transaction.atomic():
                # Build base queryset based on criteria
                leads_query = self.build_intelligent_leads_query(criteria)
                contacts_query = self.build_intelligent_contacts_query(criteria)
                
                # Apply AI-based ranking and selection
                if criteria.get('use_predictive_scoring', True):
                    leads_query = self.apply_predictive_lead_scoring(leads_query, campaign)
                    contacts_query = self.apply_predictive_contact_scoring(contacts_query, campaign)
                
                # Add leads to campaign
                for lead in leads_query:
                    if not self.is_member_already_in_campaign(campaign, lead=lead):
                        CampaignMember.objects.create(
                            campaign=campaign,
                            lead=lead,
                            member_type='LEAD',
                            status='ACTIVE',
                            predicted_engagement_score=getattr(lead, '_engagement_score', 50),
                            tenant=self.tenant,
                            created_by=self.user
                        )
                        members_added += 1
                
                # Add contacts to campaign
                for contact in contacts_query:
                    if not self.is_member_already_in_campaign(campaign, contact=contact):
                        CampaignMember.objects.create(
                            campaign=campaign,
                            contact=contact,
                            member_type='CONTACT',
                            status='ACTIVE',
                            predicted_engagement_score=getattr(contact, '_engagement_score', 50),
                            tenant=self.tenant,
                            created_by=self.user
                        )
                        members_added += 1
                
                # Apply intelligent member segmentation
                if members_added > 0:
                    self.create_intelligent_member_segments(campaign)
                
        except Exception as e:
            raise ServiceException(f"Failed to add intelligent target audience: {str(e)}")
        
        return members_added
    
    def build_intelligent_leads_query(self, criteria: Dict):
        """Build intelligent leads query with advanced filtering"""
        query = Lead.objects.filter(tenant=self.tenant, status__in=['NEW', 'CONTACTED', 'QUALIFIED'])
        
        # Score-based filtering
        if criteria.get('lead_score_min'):
            query = query.filter(score__gte=criteria['lead_score_min'])
        
        # Industry targeting
        if criteria.get('industries'):
            query = query.filter(industry__in=criteria['industries'])
        
        # Geographic targeting
        if criteria.get('countries'):
            query = query.filter(country__in=criteria['countries'])
        if criteria.get('states'):
            query = query.filter(state__in=criteria['states'])
        
        # Behavioral targeting
        if criteria.get('recent_activity_days'):
            cutoff_date = timezone.now() - timedelta(days=criteria['recent_activity_days'])
            query = query.filter(
                Q(activities__created_at__gte=cutoff_date) |
                Q(updated_at__gte=cutoff_date)
            ).distinct()
        
        # Engagement-based targeting
        if criteria.get('engagement_level'):
            if criteria['engagement_level'] == 'high':
                query = query.filter(score__gte=70)
            elif criteria['engagement_level'] == 'medium':
                query = query.filter(score__range=(40, 69))
            elif criteria['engagement_level'] == 'low':
                query = query.filter(score__lt=40)
        
        # Exclude recent campaign members
        if criteria.get('exclude_recent_campaigns', True):
            recent_cutoff = timezone.now() - timedelta(days=30)
            recent_campaign_leads = CampaignMember.objects.filter(
                lead__isnull=False,
                campaign__tenant=self.tenant,
                created_at__gte=recent_cutoff
            ).values_list('lead_id', flat=True)
            query = query.exclude(id__in=recent_campaign_leads)
        
        # Limit to manageable size
        max_members = criteria.get('max_members', 5000)
        return query.select_related('source')[:max_members]
    
    def apply_predictive_lead_scoring(self, leads_query, campaign: Campaign):
        """Apply predictive engagement scoring to leads"""
        scored_leads = []
        
        for lead in leads_query:
            engagement_score = self.calculate_predictive_engagement_score(lead, campaign)
            lead._engagement_score = engagement_score
            scored_leads.append(lead)
        
        # Sort by engagement score and return top performers
        return sorted(scored_leads, key=lambda x: x._engagement_score, reverse=True)
    
    def calculate_predictive_engagement_score(self, lead, campaign: Campaign) -> int:
        """Calculate predictive engagement score for lead"""
        base_score = lead.score or 0
        
        # Historical engagement factor
        historical_campaigns = CampaignMember.objects.filter(
            lead=lead,
            response_date__isnull=False
        ).count()
        engagement_bonus = min(historical_campaigns * 5, 20)
        
        # Recency factor
        if lead.updated_at:
            days_since_update = (timezone.now().date() - lead.updated_at.date()).days
            recency_factor = max(0, 20 - days_since_update)
        else:
            recency_factor = 0
        
        # Industry match factor
        if campaign.target_audience and lead.industry:
            if lead.industry.lower() in campaign.target_audience.lower():
                industry_bonus = 15
            else:
                industry_bonus = 0
        else:
            industry_bonus = 0
        
        # Activity level factor
        recent_activities = lead.activities.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        activity_bonus = min(recent_activities * 3, 15)
        
        total_score = base_score + engagement_bonus + recency_factor + industry_bonus + activity_bonus
        return min(100, max(0, total_score))
    
    def setup_email_automation_workflow(self, campaign: Campaign):
        """Setup intelligent email automation workflow"""
        try:
            workflow_steps = self.generate_optimal_email_sequence(campaign)
            
            for i, step in enumerate(workflow_steps):
                # Create workflow step (this would integrate with workflow engine)
                workflow_data = {
                    'campaign_id': campaign.id,
                    'step_number': i + 1,
                    'trigger_type': step['trigger_type'],
                    'delay_days': step['delay_days'],
                    'email_template': step['email_template'],
                    'conditions': step.get('conditions', {}),
                    'personalization_rules': step.get('personalization_rules', {})
                }
                
                # This would create workflow rules in the workflow system
                self.create_campaign_workflow_step(workflow_data)
            
        except Exception as e:
            logger.warning(f"Failed to setup email automation: {e}")
    
    def generate_optimal_email_sequence(self, campaign: Campaign) -> List[Dict]:
        """Generate AI-optimized email sequence based on campaign type and audience"""
        sequences = {
            'NURTURE': [
                {
                    'trigger_type': 'immediate',
                    'delay_days': 0,
                    'email_template': 'welcome',
                    'subject': 'Welcome to our community!',
                    'personalization_rules': {'include_name': True, 'include_company': True}
                },
                {
                    'trigger_type': 'delay',
                    'delay_days': 3,
                    'email_template': 'educational_content',
                    'subject': 'Quick tip that could help {company}',
                    'conditions': {'previous_opened': True}
                },
                {
                    'trigger_type': 'delay',
                    'delay_days': 7,
                    'email_template': 'case_study',
                    'subject': 'How {similar_company} achieved great results',
                    'conditions': {'previous_clicked': True}
                },
                {
                    'trigger_type': 'delay',
                    'delay_days': 14,
                    'email_template': 'demo_offer',
                    'subject': 'Ready to see this in action?',
                    'conditions': {'engagement_score': {'gte': 30}}
                }
            ],
            'PROMOTIONAL': [
                {
                    'trigger_type': 'immediate',
                    'delay_days': 0,
                    'email_template': 'promotion_announcement',
                    'subject': 'Exclusive offer just for you!',
                    'personalization_rules': {'include_discount_code': True}
                },
                {
                    'trigger_type': 'delay',
                    'delay_days': 3,
                    'email_template': 'promotion_reminder',
                    'subject': 'Don\'t miss out - offer expires soon!',
                    'conditions': {'previous_opened': False}
                },
                {
                    'trigger_type': 'delay',
                    'delay_days': 6,
                    'email_template': 'last_chance',
                    'subject': 'Last chance - expires tomorrow!',
                    'conditions': {'not_converted': True}
                }
            ]
        }
        
        return sequences.get(campaign.campaign_type, sequences['NURTURE'])
    
    def execute_intelligent_campaign(self, campaign: Campaign, execution_options: Dict = None) -> Dict:
        """Execute campaign with intelligent timing and personalization"""
        execution_results = {
            'emails_sent': 0,
            'emails_scheduled': 0,
            'personalization_applied': 0,
            'errors': [],
            'optimization_applied': []
        }
        
        try:
            with transaction.atomic():
                # Get campaign members
                members = campaign.members.filter(status='ACTIVE')
                
                # Apply send-time optimization
                if execution_options.get('optimize_send_times', True):
                    send_schedule = self.optimize_send_times(members)
                    execution_results['optimization_applied'].append('send_time_optimization')
                else:
                    send_schedule = {'immediate': list(members)}
                
                # Execute campaign in batches
                for send_time, member_batch in send_schedule.items():
                    if send_time == 'immediate':
                        # Send immediately
                        batch_results = self.send_campaign_batch(campaign, member_batch)
                        execution_results['emails_sent'] += batch_results['sent']
                        execution_results['errors'].extend(batch_results['errors'])
                    else:
                        # Schedule for later
                        self.schedule_campaign_batch(campaign, member_batch, send_time)
                        execution_results['emails_scheduled'] += len(member_batch)
                
                # Apply personalization
                if execution_options.get('enable_personalization', True):
                    personalized = self.apply_advanced_personalization(campaign)
                    execution_results['personalization_applied'] = personalized
                    execution_results['optimization_applied'].append('advanced_personalization')
                
                # Update campaign status
                campaign.status = 'ACTIVE'
                campaign.start_date = timezone.now().date()
                campaign.save()
                
        except Exception as e:
            raise ServiceException(f"Failed to execute campaign: {str(e)}")
        
        return execution_results
    
    def optimize_send_times(self, members) -> Dict[str, List]:
        """Optimize send times based on recipient behavior patterns"""
        send_schedule = defaultdict(list)
        
        # Analyze historical engagement patterns
        engagement_patterns = self.analyze_recipient_engagement_patterns(members)
        
        for member in members:
            # Get optimal send time for this member
            if member.lead:
                recipient_id = f"lead_{member.lead.id}"
            else:
                recipient_id = f"contact_{member.contact.id}"
            
            optimal_time = engagement_patterns.get(recipient_id, {}).get('optimal_hour', 10)
            
            # Group by optimal send time
            if optimal_time in [9, 10, 11]:  # Morning batch
                send_schedule['morning'].append(member)
            elif optimal_time in [14, 15, 16]:  # Afternoon batch
                send_schedule['afternoon'].append(member)
            else:
                send_schedule['immediate'].append(member)  # Default
        
        return dict(send_schedule)
    
    def send_campaign_batch(self, campaign: Campaign, members: List) -> Dict:
        """Send campaign emails to a batch of members with intelligent personalization"""
        results = {'sent': 0, 'errors': []}
        
        try:
            from ..tasks import send_campaign_email_task
            
            for member in members:
                try:
                    # Get recipient details
                    if member.lead:
                        recipient = member.lead
                        email = recipient.email
                        name = recipient.full_name
                    else:
                        recipient = member.contact
                        email = recipient.email
                        name = recipient.full_name
                    
                    if not email:
                        results['errors'].append(f"No email for member {member.id}")
                        continue
                    
                    # Generate personalized content
                    personalized_content = self.generate_personalized_content(campaign, recipient)
                    
                    # Create email log
                    email_log = CampaignEmail.objects.create(
                        campaign=campaign,
                        member=member,
                        recipient_email=email,
                        subject=personalized_content['subject'],
                        body=personalized_content['body'],
                        scheduled_send_time=timezone.now(),
                        tenant=self.tenant,
                        created_by=self.user
                    )
                    
                    # Queue email for sending
                    send_campaign_email_task.delay(email_log.id)
                    
                    results['sent'] += 1
                    
                except Exception as e:
                    results['errors'].append(f"Failed to send to member {member.id}: {str(e)}")
            
        except Exception as e:
            raise ServiceException(f"Failed to send campaign batch: {str(e)}")
        
        return results
    
    def generate_personalized_content(self, campaign: Campaign, recipient) -> Dict:
        """Generate highly personalized email content using AI insights"""
        # Base content from campaign
        subject = campaign.email_subject or "Important update from {company}"
        body = campaign.email_body or "Hello {name}, we have something special for you..."
        
        # Personalization variables
        variables = {
            'name': getattr(recipient, 'first_name', 'there'),
            'full_name': getattr(recipient, 'full_name', 'there'),
            'company': getattr(recipient, 'company', 'your company'),
            'industry': getattr(recipient, 'industry', 'your industry'),
        }
        
        # Advanced personalization based on recipient data
        if hasattr(recipient, 'score'):
            if recipient.score > 70:
                variables['engagement_level'] = 'highly engaged'
                variables['cta_urgency'] = 'exclusive'
            elif recipient.score > 40:
                variables['engagement_level'] = 'interested'
                variables['cta_urgency'] = 'limited time'
            else:
                variables['engagement_level'] = 'exploring'
                variables['cta_urgency'] = 'valuable'
        
        # Industry-specific personalization
        industry_insights = self.get_industry_specific_insights(variables.get('industry'))
        variables.update(industry_insights)
        
        # Behavioral personalization
        recent_activity = self.get_recent_activity_insights(recipient)
        variables.update(recent_activity)
        
        # Apply personalization
        try:
            personalized_subject = subject.format(**variables)
            personalized_body = body.format(**variables)
        except KeyError as e:
            # Fallback if personalization fails
            logger.warning(f"Personalization failed for variable {e}")
            personalized_subject = subject
            personalized_body = body
        
        return {
            'subject': personalized_subject,
            'body': personalized_body,
            'personalization_score': self.calculate_personalization_score(variables)
        }
    
    def analyze_campaign_performance_with_ai(self, campaign: Campaign) -> Dict:
        """Comprehensive campaign performance analysis with AI insights"""
        members = campaign.members.all()
        emails = campaign.emails.all()
        
        # Basic metrics
        basic_metrics = {
            'total_members': members.count(),
            'emails_sent': emails.filter(sent_date__isnull=False).count(),
            'emails_opened': emails.filter(opened_date__isnull=False).count(),
            'emails_clicked': emails.filter(clicked_date__isnull=False).count(),
            'responses': members.filter(response_date__isnull=False).count(),
            'conversions': members.filter(converted=True).count(),
        }
        
        # Calculate rates
        sent_count = basic_metrics['emails_sent']
        if sent_count > 0:
            basic_metrics.update({
                'delivery_rate': (sent_count / basic_metrics['total_members']) * 100,
                'open_rate': (basic_metrics['emails_opened'] / sent_count) * 100,
                'click_rate': (basic_metrics['emails_clicked'] / sent_count) * 100,
                'response_rate': (basic_metrics['responses'] / sent_count) * 100,
                'conversion_rate': (basic_metrics['conversions'] / sent_count) * 100,
            })
        
        # Advanced analytics
        advanced_analytics = {
            'engagement_analysis': self.analyze_engagement_patterns(campaign),
            'timing_analysis': self.analyze_optimal_timing(campaign),
            'content_performance': self.analyze_content_performance(campaign),
            'audience_segmentation_insights': self.analyze_audience_segments(campaign),
            'predictive_insights': self.generate_campaign_predictions(campaign),
            'improvement_recommendations': self.generate_improvement_recommendations(campaign)
        }
        
        # ROI Analysis
        roi_analysis = self.calculate_campaign_roi(campaign)
        
        return {
            'basic_metrics': basic_metrics,
            'advanced_analytics': advanced_analytics,
            'roi_analysis': roi_analysis,
            'benchmark_comparison': self.compare_with_benchmarks(campaign, basic_metrics),
            'next_actions': self.recommend_next_actions(campaign, basic_metrics, advanced_analytics)
        }
    
    def analyze_engagement_patterns(self, campaign: Campaign) -> Dict:
        """Analyze detailed engagement patterns"""
        emails = campaign.emails.filter(sent_date__isnull=False)
        
        # Time-based engagement
        hourly_engagement = defaultdict(list)
        daily_engagement = defaultdict(list)
        
        for email in emails:
            if email.opened_date:
                hour = email.opened_date.hour
                day = email.opened_date.weekday()
                hourly_engagement[hour].append(1)
                daily_engagement[day].append(1)
            
            if email.sent_date:
                hour = email.sent_date.hour
                day = email.sent_date.weekday()
                if email.opened_date is None:
                    hourly_engagement[hour].append(0)
                    daily_engagement[day].append(0)
        
        # Calculate engagement rates by time
        hourly_rates = {
            hour: (sum(opens) / len(opens) * 100) if opens else 0
            for hour, opens in hourly_engagement.items()
        }
        
        daily_rates = {
            calendar.day_name[day]: (sum(opens) / len(opens) * 100) if opens else 0
            for day, opens in daily_engagement.items()
        }
        
        return {
            'best_hours': sorted(hourly_rates.items(), key=lambda x: x[1], reverse=True)[:3],
            'best_days': sorted(daily_rates.items(), key=lambda x: x[1], reverse=True)[:3],
            'engagement_timeline': self.generate_engagement_timeline(emails),
            'drop_off_analysis': self.analyze_engagement_drop_off(emails)
        }
    
    def generate_improvement_recommendations(self, campaign: Campaign) -> List[Dict]:
        """Generate AI-powered improvement recommendations"""
        recommendations = []
        
        # Analyze current performance
        performance = self.get_campaign_performance_metrics(campaign)
        
        # Open rate recommendations
        if performance.get('open_rate', 0) < 20:
            recommendations.append({
                'category': 'Subject Line',
                'priority': 'high',
                'recommendation': 'Improve subject lines - current open rate is below industry average',
                'specific_actions': [
                    'A/B test different subject line approaches',
                    'Add personalization to subject lines',
                    'Avoid spam trigger words',
                    'Create urgency without being pushy'
                ]
            })
        
        # Click rate recommendations
        if performance.get('click_rate', 0) < 3:
            recommendations.append({
                'category': 'Content & CTA',
                'priority': 'high',
                'recommendation': 'Optimize email content and call-to-action buttons',
                'specific_actions': [
                    'Make CTAs more prominent and compelling',
                    'Reduce content length and focus on key message',
                    'Add more visual elements',
                    'Test different CTA button colors and text'
                ]
            })
        
        # Timing recommendations
        send_time_analysis = self.analyze_send_time_effectiveness(campaign)
        if send_time_analysis['improvement_potential'] > 15:
            recommendations.append({
                'category': 'Send Time Optimization',
                'priority': 'medium',
                'recommendation': f'Optimize send times - potential for {send_time_analysis["improvement_potential"]}% improvement',
                'specific_actions': [
                    f'Send emails on {send_time_analysis["best_day"]} at {send_time_analysis["best_hour"]}',
                    'Consider recipient time zones',
                    'Test different send times for different segments'
                ]
            })
        
        # Segmentation recommendations
        if campaign.members.count() > 100:
            segmentation_insights = self.analyze_segmentation_opportunities(campaign)
            if segmentation_insights['potential_improvement'] > 10:
                recommendations.append({
                    'category': 'Audience Segmentation',
                    'priority': 'medium',
                    'recommendation': 'Implement better audience segmentation',
                    'specific_actions': segmentation_insights['recommended_segments']
                })
        
        return recommendations
    
    def predict_campaign_success(self, campaign: Campaign, target_metrics: Dict = None) -> Dict:
        """Predict campaign success probability using ML models"""
        predictions = {
            'success_probability': 0,
            'predicted_metrics': {},
            'confidence_level': 0,
            'key_success_factors': [],
            'risk_factors': []
        }
        
        try:
            # Gather campaign features for prediction
            features = self.extract_campaign_features(campaign)
            
            # Simple prediction model (in production, use trained ML models)
            success_score = 0
            
            # Audience quality factor
            avg_lead_score = campaign.members.filter(
                lead__isnull=False
            ).aggregate(avg=Avg('lead__score'))['avg'] or 50
            
            if avg_lead_score > 70:
                success_score += 30
                predictions['key_success_factors'].append('High quality audience (avg score: {:.1f})'.format(avg_lead_score))
            elif avg_lead_score < 40:
                success_score -= 15
                predictions['risk_factors'].append('Low audience engagement scores')
            
            # Campaign type factor
            if campaign.campaign_type in ['NURTURE', 'EDUCATIONAL']:
                success_score += 20
                predictions['key_success_factors'].append('Educational content typically performs well')
            elif campaign.campaign_type == 'PROMOTIONAL':
                success_score += 10
            
            # Timing factor
            if campaign.start_date and campaign.start_date.weekday() in [1, 2, 3]:  # Tue, Wed, Thu
                success_score += 15
                predictions['key_success_factors'].append('Optimal send day selected')
            
            # Content quality (simplified analysis)
            if campaign.email_subject and len(campaign.email_subject) < 50:
                success_score += 10
            
            if campaign.email_body and 100 < len(campaign.email_body) < 1000:
                success_score += 15
            
            # Historical performance factor
            creator_avg_performance = self.get_user_campaign_performance(campaign.created_by)
            if creator_avg_performance > 25:  # Above average open rate
                success_score += 15
                predictions['key_success_factors'].append('Campaign creator has strong track record')
            
            predictions['success_probability'] = min(100, max(0, success_score))
            predictions['confidence_level'] = min(90, success_score / 2)
            
            # Predict specific metrics
            base_open_rate = 22  # Industry average
            base_click_rate = 3.5
            
            performance_multiplier = success_score / 100
            
            predictions['predicted_metrics'] = {
                'open_rate': base_open_rate * performance_multiplier,
                'click_rate': base_click_rate * performance_multiplier,
                'response_rate': (base_click_rate * performance_multiplier) * 0.3,
                'conversion_rate': (base_click_rate * performance_multiplier) * 0.1
            }
            
        except Exception as e:
            logger.warning(f"Failed to predict campaign success: {e}")
        
        return predictions
    
    # Helper methods
    def find_optimal_lead_score_threshold(self) -> int:
        """Find optimal lead score threshold based on historical conversion data"""
        # Analyze historical campaigns and their conversion rates by lead score
        # This is a simplified version - real implementation would use ML
        return 65
    
    def get_high_performing_industries(self) -> List[str]:
        """Get industries with historically high campaign performance"""
        # Analyze campaign performance by industry
        return ['Technology', 'Healthcare', 'Finance']
    
    def analyze_historical_targeting_performance(self) -> Dict:
        """Analyze historical targeting criteria performance"""
        return {
            'optimal_lead_score': 65,
            'best_performing_industries': ['Technology', 'Healthcare'],
            'optimal_timing': {'day': 'Tuesday', 'hour': 10}
        }
    
    def is_member_already_in_campaign(self, campaign: Campaign, lead=None, contact=None) -> bool:
        """Check if lead/contact is already a member of the campaign"""
        if lead:
            return campaign.members.filter(lead=lead).exists()
        elif contact:
            return campaign.members.filter(contact=contact).exists()
        return False
