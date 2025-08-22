# ============================================================================
# backend/apps/crm/serializers/campaign.py - Campaign Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from ..models import Campaign, CampaignTeamMember, CampaignMember, CampaignEmail
from .user import UserBasicSerializer
from .activity import EmailTemplateSerializer
from .lead import LeadSerializer
from .account import ContactBasicSerializer, AccountSerializer


class CampaignTeamMemberSerializer(serializers.ModelSerializer):
    """Campaign team member serializer"""
    
    user_details = UserBasicSerializer(source='user', read_only=True)
    
    class Meta:
        model = CampaignTeamMember
        fields = [
            'id', 'user', 'user_details', 'role', 'can_edit', 'can_view_analytics',
            'can_manage_content', 'assigned_date'
        ]
        read_only_fields = ['id', 'user_details', 'assigned_date']


class CampaignMemberSerializer(serializers.ModelSerializer):
    """Campaign member serializer with engagement tracking"""
    
    lead_details = LeadSerializer(source='lead', read_only=True)
    contact_details = ContactBasicSerializer(source='contact', read_only=True)
    account_details = serializers.SerializerMethodField()
    
    # Engagement metrics
    full_name = serializers.ReadOnlyField()
    engagement_score = serializers.ReadOnlyField()
    engagement_level = serializers.SerializerMethodField()
    last_engagement = serializers.SerializerMethodField()
    
    class Meta:
        model = CampaignMember
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone', 'company',
            # Classification
            'member_type', 'status',
            # CRM relations
            'lead', 'lead_details', 'contact', 'contact_details', 'account', 'account_details',
            # Engagement tracking
            'emails_sent', 'emails_opened', 'emails_clicked', 'last_opened_date',
            'last_clicked_date', 'engagement_score', 'engagement_level', 'last_engagement',
            # Response tracking
            'responded', 'response_date', 'conversion_date',
            # Opt-out
            'unsubscribed_date', 'unsubscribe_reason',
            # Additional data
            'custom_fields', 'tags',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'full_name', 'lead_details', 'contact_details', 'account_details',
            'engagement_score', 'engagement_level', 'last_engagement',
            'created_at', 'updated_at'
        ]
    
    def get_account_details(self, obj):
        """Get basic account details"""
        if obj.account:
            return {
                'id': obj.account.id,
                'name': obj.account.name,
                'account_type': obj.account.account_type
            }
        return None
    
    def get_engagement_level(self, obj):
        """Get engagement level based on score"""
        score = obj.engagement_score
        if score >= 80:
            return 'Highly Engaged'
        elif score >= 50:
            return 'Moderately Engaged'
        elif score >= 20:
            return 'Low Engagement'
        else:
            return 'No Engagement'
    
    def get_last_engagement(self, obj):
        """Get last engagement date"""
        dates = [obj.last_opened_date, obj.last_clicked_date, obj.response_date]
        valid_dates = [d for d in dates if d is not None]
        return max(valid_dates) if valid_dates else None


class CampaignEmailSerializer(serializers.ModelSerializer):
    """Campaign email serializer with performance metrics"""
    
    template_details = EmailTemplateSerializer(source='template', read_only=True)
    performance_summary = serializers.SerializerMethodField()
    
    # Calculated rates
    delivery_rate = serializers.ReadOnlyField()
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    bounce_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = CampaignEmail
        fields = [
            'id', 'subject', 'from_name', 'from_email', 'reply_to_email',
            'html_content', 'text_content', 'template', 'template_details',
            # Scheduling
            'status', 'scheduled_datetime', 'sent_datetime',
            # Recipients and metrics
            'total_recipients', 'sent_count', 'delivered_count', 'opened_count',
            'clicked_count', 'bounced_count', 'unsubscribed_count',
            # Rates
            'delivery_rate', 'open_rate', 'click_rate', 'bounce_rate',
            # A/B Testing
            'is_ab_test', 'ab_test_percentage', 'ab_test_winner',
            # Provider
            'provider', 'provider_campaign_id', 'analytics_data',
            'performance_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'template_details', 'sent_count', 'delivered_count', 'opened_count',
            'clicked_count', 'bounced_count', 'unsubscribed_count', 'delivery_rate',
            'open_rate', 'click_rate', 'bounce_rate', 'performance_summary',
            'created_at', 'updated_at'
        ]
    
    def get_performance_summary(self, obj):
        """Get performance summary"""
        return {
            'overall_performance': 'Excellent' if obj.open_rate > 25 else 'Good' if obj.open_rate > 15 else 'Average',
            'engagement_quality': 'High' if obj.click_rate > 3 else 'Medium' if obj.click_rate > 1 else 'Low',
            'deliverability': 'Good' if obj.bounce_rate < 5 else 'Poor',
            'recommendations': self._get_recommendations(obj)
        }
    
    def _get_recommendations(self, obj):
        """Get performance recommendations"""
        recommendations = []
        
        if obj.open_rate < 15:
            recommendations.append("Consider improving subject line")
        
        if obj.click_rate < 1:
            recommendations.append("Improve call-to-action placement")
        
        if obj.bounce_rate > 5:
            recommendations.append("Clean email list to improve deliverability")
        
        return recommendations


class CampaignSerializer(serializers.ModelSerializer):
    """Comprehensive campaign serializer with ROI analysis"""
    
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    team_members = CampaignTeamMemberSerializer(source='team_memberships', many=True, read_only=True)
    
    # Performance metrics
    conversion_rate = serializers.ReadOnlyField()
    roi = serializers.ReadOnlyField()
    cost_per_lead = serializers.ReadOnlyField()
    email_open_rate = serializers.ReadOnlyField()
    email_click_rate = serializers.ReadOnlyField()
    
    # Calculated fields
    campaign_duration = serializers.SerializerMethodField()
    budget_utilization = serializers.SerializerMethodField()
    performance_grade = serializers.SerializerMethodField()
    channel_performance = serializers.SerializerMethodField()
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'campaign_code', 'description', 'campaign_type', 'status',
            # Dates
            'start_date', 'end_date', 'planned_duration_days', 'campaign_duration',
            # Target and budget
            'target_audience', 'budget_allocated', 'budget_spent', 'budget_utilization',
            # Goals
            'target_leads', 'target_revenue', 'target_conversion_rate',
            # Ownership
            'owner', 'owner_details', 'team_members',
            # Lead performance
            'total_leads', 'qualified_leads', 'converted_leads', 'conversion_rate',
            'total_opportunities', 'won_opportunities', 'total_revenue',
            # ROI metrics
            'roi', 'cost_per_lead', 'performance_grade',
            # Email metrics
            'emails_sent', 'emails_delivered', 'emails_opened', 'emails_clicked',
            'emails_bounced', 'emails_unsubscribed', 'email_open_rate', 'email_click_rate',
            # Web metrics
            'website_visits', 'page_views', 'form_submissions', 'downloads', 'registrations',
            # Social metrics
            'social_impressions', 'social_clicks', 'social_shares', 'social_comments',
            'channel_performance',
            # Content
            'landing_page_url', 'creative_assets', 'tracking_parameters',
            'external_campaign_id', 'tags',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'campaign_code', 'owner_details', 'team_members', 'planned_duration_days',
            'campaign_duration', 'budget_utilization', 'total_leads', 'qualified_leads',
            'converted_leads', 'conversion_rate', 'total_opportunities', 'won_opportunities',
            'total_revenue', 'roi', 'cost_per_lead', 'email_open_rate', 'email_click_rate',
            'performance_grade', 'channel_performance', 'created_at', 'updated_at'
        ]
    
    def get_campaign_duration(self, obj):
        """Get actual campaign duration"""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days
        return None
    
    def get_budget_utilization(self, obj):
        """Calculate budget utilization percentage"""
        if obj.budget_allocated and obj.budget_allocated > 0:
            return float((obj.budget_spent / obj.budget_allocated) * 100)
        return 0
    
    def get_performance_grade(self, obj):
        """Calculate overall performance grade"""
        score = 0
        factors = 0
        
        # ROI factor
        if obj.roi > 100:
            score += 25
        elif obj.roi > 50:
            score += 15
        elif obj.roi > 0:
            score += 10
        factors += 25
        
        # Conversion rate factor
        if obj.conversion_rate > 10:
            score += 25
        elif obj.conversion_rate > 5:
            score += 15
        elif obj.conversion_rate > 2:
            score += 10
        factors += 25
        
        # Email performance factor
        if obj.email_open_rate > 25:
            score += 25
        elif obj.email_open_rate > 15:
            score += 15
        elif obj.email_open_rate > 10:
            score += 10
        factors += 25
        
        # Budget efficiency factor
        budget_util = self.get_budget_utilization(obj)
        if 80 <= budget_util <= 100:
            score += 25
        elif 60 <= budget_util < 120:
            score += 15
        elif budget_util < 150:
            score += 10
        factors += 25
        
        final_score = (score / factors) * 100 if factors > 0 else 0
        
        if final_score >= 80:
            return 'A'
        elif final_score >= 70:
            return 'B'
        elif final_score >= 60:
            return 'C'
        elif final_score >= 50:
            return 'D'
        else:
            return 'F'
    
    def get_channel_performance(self, obj):
        """Analyze performance by channel"""
        channels = {
            'email': {
                'sent': obj.emails_sent,
                'engagement_rate': obj.email_open_rate,
                'conversion_rate': (obj.converted_leads / max(obj.emails_sent, 1)) * 100
            },
            'web': {
                'visits': obj.website_visits,
                'conversion_rate': (obj.form_submissions / max(obj.website_visits, 1)) * 100
            },
            'social': {
                'impressions': obj.social_impressions,
                'engagement_rate': (obj.social_clicks / max(obj.social_impressions, 1)) * 100
            }
        }
        return channels
    
    def validate(self, data):
        """Validate campaign data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        
        budget_allocated = data.get('budget_allocated')
        budget_spent = data.get('budget_spent', 0)
        
        if budget_allocated and budget_spent > budget_allocated:
            raise serializers.ValidationError({
                'budget_spent': 'Budget spent cannot exceed allocated budget'
            })
        
        return data


class CampaignDetailSerializer(CampaignSerializer):
    """Detailed campaign serializer with complete analytics"""
    
    members_summary = serializers.SerializerMethodField()
    emails = CampaignEmailSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    conversion_funnel = serializers.SerializerMethodField()
    
    class Meta(CampaignSerializer.Meta):
        fields = CampaignSerializer.Meta.fields + [
            'members_summary', 'emails', 'recent_activities', 'conversion_funnel'
        ]
    
    def get_members_summary(self, obj):
        """Get campaign members summary"""
        members = obj.members.all()
        return {
            'total_members': members.count(),
            'active_members': members.filter(status='ACTIVE').count(),
            'engaged_members': members.filter(engagement_score__gte=50).count(),
            'converted_members': members.filter(conversion_date__isnull=False).count(),
            'unsubscribed_members': members.filter(status='UNSUBSCRIBED').count()
        }
    
    def get_recent_activities(self, obj):
        """Get recent campaign activities"""
        # This would fetch recent activities related to the campaign
        return []
    
    def get_conversion_funnel(self, obj):
        """Get conversion funnel data"""
        return {
            'impressions': obj.social_impressions + obj.emails_sent,
            'clicks': obj.social_clicks + obj.emails_clicked,
            'website_visits': obj.website_visits,
            'leads': obj.total_leads,
            'qualified_leads': obj.qualified_leads,
            'opportunities': obj.total_opportunities,
            'conversions': obj.converted_leads,
            'revenue': float(obj.total_revenue)
        }


class CampaignCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating campaigns with initial setup"""
    
    create_email_template = serializers.BooleanField(default=False, write_only=True)
    template_subject = serializers.CharField(max_length=255, required=False, write_only=True)
    template_body = serializers.CharField(required=False, write_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'description', 'campaign_type', 'start_date', 'end_date',
            'target_audience', 'budget_allocated', 'target_leads', 'target_revenue',
            'landing_page_url', 'tags', 'create_email_template', 'template_subject',
            'template_body'
        ]
    
    @transaction.atomic
    def create(self, validated_data):
        """Create campaign with optional email template"""
        create_template = validated_data.pop('create_email_template', False)
        template_subject = validated_data.pop('template_subject', '')
        template_body = validated_data.pop('template_body', '')
        
        campaign = super().create(validated_data)
        
        if create_template and template_subject:
            from ..models import EmailTemplate
            EmailTemplate.objects.create(
                tenant=campaign.tenant,
                name=f"{campaign.name} Template",
                subject=template_subject,
                body_html=template_body,
                template_type='MARKETING',
                created_by=self.context['request'].user
            )
        
        return campaign


class CampaignAnalyticsSerializer(serializers.Serializer):
    """Serializer for campaign analytics data"""
    
    date_range = serializers.CharField(required=False, default='30d')
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'leads', 'revenue', 'roi', 'conversion_rate', 'email_performance',
            'web_performance', 'social_performance'
        ]),
        required=False,
        default=['leads', 'revenue', 'roi']
    )
    
    def validate_date_range(self, value):
        """Validate date range format"""
        valid_ranges = ['7d', '30d', '90d', '180d', '1y']
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Date range must be one of: {', '.join(valid_ranges)}")