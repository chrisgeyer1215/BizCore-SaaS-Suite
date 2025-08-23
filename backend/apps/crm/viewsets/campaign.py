# crm/viewsets/campaign.py
"""
Campaign Management ViewSets

Provides REST API endpoints for:
- Marketing campaign creation and management
- Campaign member management and segmentation
- Email campaign automation and scheduling
- Campaign performance analytics and reporting
- A/B testing and optimization
- Lead generation and nurturing campaigns
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from django.db.models import Count, Sum, Avg, Q, F, Case, When, FloatField
from django.db.models.functions import TruncDate, TruncHour, Coalesce
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from crm.models.campaign import Campaign, CampaignMember, CampaignEmail, CampaignType
from crm.models.activity import EmailLog
from crm.serializers.campaign import (
    CampaignSerializer, CampaignDetailSerializer, CampaignCreateSerializer,
    CampaignMemberSerializer, CampaignEmailSerializer, CampaignTypeSerializer
)
from crm.permissions.campaign import CampaignPermission, CampaignEmailPermission
from crm.utils.tenant_utils import get_tenant_from_request, check_tenant_limits
from crm.utils.email_utils import send_crm_email, render_email_template, get_email_statistics
from crm.utils.formatters import format_percentage, format_currency, format_date_display
from .base import CRMBaseViewSet, CRMReadOnlyViewSet, cache_response, require_tenant_limits


class CampaignFilter(filters.FilterSet):
    """Advanced filtering for Campaign ViewSet."""
    
    name = filters.CharFilter(lookup_expr='icontains')
    type = filters.ModelChoiceFilter(queryset=CampaignType.objects.all())
    status = filters.ChoiceFilter(choices=Campaign.STATUS_CHOICES)
    owner = filters.NumberFilter(field_name='owner__id')
    start_date_from = filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_to = filters.DateFilter(field_name='start_date', lookup_expr='lte')
    end_date_from = filters.DateFilter(field_name='end_date', lookup_expr='gte')
    end_date_to = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    budget_min = filters.NumberFilter(field_name='budget', lookup_expr='gte')
    budget_max = filters.NumberFilter(field_name='budget', lookup_expr='lte')
    expected_revenue_min = filters.NumberFilter(field_name='expected_revenue', lookup_expr='gte')
    expected_revenue_max = filters.NumberFilter(field_name='expected_revenue', lookup_expr='lte')
    is_active = filters.BooleanFilter(method='filter_is_active')
    has_members = filters.BooleanFilter(method='filter_has_members')
    performance_rating = filters.ChoiceFilter(
        method='filter_performance_rating',
        choices=[('excellent', 'Excellent'), ('good', 'Good'), ('average', 'Average'), ('poor', 'Poor')]
    )
    
    class Meta:
        model = Campaign
        fields = ['type', 'status', 'owner', 'is_active']
    
    def filter_is_active(self, queryset, name, value):
        """Filter active campaigns."""
        today = timezone.now().date()
        if value:
            return queryset.filter(
                status='ACTIVE',
                start_date__lte=today,
                Q(end_date__gte=today) | Q(end_date__isnull=True)
            )
        else:
            return queryset.exclude(
                status='ACTIVE',
                start_date__lte=today,
                Q(end_date__gte=today) | Q(end_date__isnull=True)
            )
    
    def filter_has_members(self, queryset, name, value):
        """Filter campaigns with/without members."""
        if value:
            return queryset.filter(members__isnull=False).distinct()
        else:
            return queryset.filter(members__isnull=True)
    
    def filter_performance_rating(self, queryset, name, value):
        """Filter by performance rating (calculated dynamically)."""
        # This would require complex annotations for performance calculation
        # For now, return the queryset unchanged
        return queryset


class CampaignViewSet(CRMBaseViewSet):
    """
    ViewSet for Campaign management with comprehensive functionality.
    
    Provides CRUD operations, member management, and campaign analytics.
    """
    
    queryset = Campaign.objects.select_related('type', 'owner').prefetch_related('members', 'emails')
    serializer_class = CampaignSerializer
    filterset_class = CampaignFilter
    search_fields = ['name', 'description', 'objectives']
    ordering_fields = [
        'name', 'start_date', 'end_date', 'budget', 'expected_revenue', 
        'created_at', 'status'
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return CampaignCreateSerializer
        elif self.action == 'retrieve':
            return CampaignDetailSerializer
        return CampaignSerializer
    
    def get_model_permission(self):
        """Get campaign-specific permission class."""
        return CampaignPermission
    
    @require_tenant_limits('campaigns', 1)
    def create(self, request, *args, **kwargs):
        """Create new campaign with automatic setup."""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            # Initialize campaign tracking
            campaign_id = response.data['id']
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                
                # Create initial campaign activity log
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=campaign.tenant,
                    type='CAMPAIGN_CREATED',
                    subject=f'Campaign Created: {campaign.name}',
                    description=f'Campaign "{campaign.name}" was created with budget {format_currency(campaign.budget) if campaign.budget else "N/A"}',
                    assigned_to=request.user,
                    due_date=campaign.start_date,
                    related_object_type='campaign',
                    related_to_id=campaign.id
                )
                
            except Exception as e:
                print(f"Error initializing campaign: {e}")
        
        return response
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate campaign and start execution.
        
        Expected payload:
        {
            "activation_notes": "string",
            "send_welcome_email": boolean,
            "schedule_follow_ups": boolean
        }
        """
        try:
            campaign = self.get_object()
            
            if campaign.status == 'ACTIVE':
                return Response(
                    {'error': 'Campaign is already active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            activation_notes = request.data.get('activation_notes', '')
            send_welcome_email = request.data.get('send_welcome_email', False)
            schedule_follow_ups = request.data.get('schedule_follow_ups', False)
            
            # Validate campaign is ready for activation
            validation_result = self._validate_campaign_activation(campaign)
            if not validation_result['valid']:
                return Response(
                    {
                        'error': 'Campaign cannot be activated',
                        'validation_errors': validation_result['errors']
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update campaign status
                campaign.status = 'ACTIVE'
                campaign.actual_start_date = timezone.now().date()
                campaign.save()
                
                # Log activation
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=campaign.tenant,
                    type='CAMPAIGN_ACTIVATED',
                    subject=f'Campaign Activated: {campaign.name}',
                    description=f'Campaign activated. Notes: {activation_notes}',
                    assigned_to=request.user,
                    due_date=timezone.now().date(),
                    related_object_type='campaign',
                    related_to_id=campaign.id
                )
                
                # Send welcome email if requested
                if send_welcome_email:
                    self._send_campaign_welcome_emails(campaign)
                
                # Schedule follow-ups if requested
                if schedule_follow_ups:
                    self._schedule_campaign_follow_ups(campaign)
                
                return Response({
                    'message': 'Campaign activated successfully',
                    'campaign': CampaignSerializer(campaign).data,
                    'activated_at': campaign.actual_start_date.isoformat(),
                    'members_count': campaign.members.count()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """
        Pause active campaign.
        
        Expected payload:
        {
            "pause_reason": "string",
            "pause_notes": "string"
        }
        """
        try:
            campaign = self.get_object()
            
            if campaign.status != 'ACTIVE':
                return Response(
                    {'error': 'Only active campaigns can be paused'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            pause_reason = request.data.get('pause_reason', '')
            pause_notes = request.data.get('pause_notes', '')
            
            # Update campaign status
            campaign.status = 'PAUSED'
            campaign.save()
            
            # Log pause
            from crm.models.activity import Activity
            Activity.objects.create(
                tenant=campaign.tenant,
                type='CAMPAIGN_PAUSED',
                subject=f'Campaign Paused: {campaign.name}',
                description=f'Campaign paused. Reason: {pause_reason}. Notes: {pause_notes}',
                assigned_to=request.user,
                due_date=timezone.now().date(),
                related_object_type='campaign',
                related_to_id=campaign.id
            )
            
            return Response({
                'message': 'Campaign paused successfully',
                'campaign': CampaignSerializer(campaign).data,
                'pause_reason': pause_reason
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark campaign as completed.
        
        Expected payload:
        {
            "completion_notes": "string",
            "actual_cost": decimal,
            "actual_revenue": decimal,
            "lessons_learned": "string"
        }
        """
        try:
            campaign = self.get_object()
            
            if campaign.status == 'COMPLETED':
                return Response(
                    {'error': 'Campaign is already completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            completion_notes = request.data.get('completion_notes', '')
            actual_cost = request.data.get('actual_cost')
            actual_revenue = request.data.get('actual_revenue')
            lessons_learned = request.data.get('lessons_learned', '')
            
            with transaction.atomic():
                # Update campaign
                campaign.status = 'COMPLETED'
                campaign.actual_end_date = timezone.now().date()
                if actual_cost:
                    campaign.actual_cost = actual_cost
                if actual_revenue:
                    campaign.actual_revenue = actual_revenue
                campaign.save()
                
                # Calculate final metrics
                final_metrics = self._calculate_campaign_metrics(campaign)
                
                # Log completion
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=campaign.tenant,
                    type='CAMPAIGN_COMPLETED',
                    subject=f'Campaign Completed: {campaign.name}',
                    description=f'Campaign completed. ROI: {final_metrics.get("roi", "N/A")}. Notes: {completion_notes}',
                    assigned_to=request.user,
                    due_date=timezone.now().date(),
                    related_object_type='campaign',
                    related_to_id=campaign.id
                )
                
                return Response({
                    'message': 'Campaign completed successfully',
                    'campaign': CampaignSerializer(campaign).data,
                    'final_metrics': final_metrics,
                    'lessons_learned': lessons_learned
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get campaign members with filtering and analytics."""
        try:
            campaign = self.get_object()
            
            # Get members with filters
            members = CampaignMember.objects.filter(campaign=campaign)
            
            # Apply status filter
            status_filter = request.query_params.get('status')
            if status_filter:
                members = members.filter(status=status_filter)
            
            # Apply engagement filter
            engagement_filter = request.query_params.get('engagement')
            if engagement_filter == 'engaged':
                members = members.filter(
                    Q(email_opens__gt=0) | Q(email_clicks__gt=0) | Q(activities_count__gt=0)
                )
            elif engagement_filter == 'unengaged':
                members = members.filter(
                    email_opens=0,
                    email_clicks=0,
                    activities_count=0
                )
            
            # Pagination
            page = self.paginate_queryset(members)
            if page is not None:
                serializer = CampaignMemberSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = CampaignMemberSerializer(members, many=True)
            
            # Add member analytics
            member_stats = {
                'total_members': members.count(),
                'active_members': members.filter(status='ACTIVE').count(),
                'responded_members': members.filter(has_responded=True).count(),
                'unsubscribed_members': members.filter(is_unsubscribed=True).count(),
                'avg_engagement_score': members.aggregate(
                    Avg('engagement_score')
                )['engagement_score__avg'] or 0
            }
            
            return Response({
                'campaign_id': campaign.id,
                'members': serializer.data,
                'member_stats': member_stats
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """
        Add members to campaign with smart segmentation.
        
        Expected payload:
        {
            "member_type": "manual|leads|contacts|custom_query",
            "members": [...] // for manual
            "filters": {...} // for leads/contacts
            "custom_query": {...} // for custom query
            "segment_name": "string"
        }
        """
        try:
            campaign = self.get_object()
            member_type = request.data.get('member_type', 'manual')
            segment_name = request.data.get('segment_name', f'Segment {timezone.now().strftime("%Y%m%d_%H%M")}')
            
            # Check tenant limits
            tenant = get_tenant_from_request(request)
            if tenant:
                current_members = campaign.members.count()
                limit_check = check_tenant_limits(tenant, 'campaign_members', 100)  # Adding up to 100
                if not limit_check['allowed']:
                    return Response(
                        {'error': limit_check['error']},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            added_members = []
            
            with transaction.atomic():
                if member_type == 'manual':
                    # Manual member addition
                    members_data = request.data.get('members', [])
                    added_members = self._add_manual_members(campaign, members_data, segment_name)
                
                elif member_type == 'leads':
                    # Add leads based on filters
                    filters = request.data.get('filters', {})
                    added_members = self._add_leads_as_members(campaign, filters, segment_name)
                
                elif member_type == 'contacts':
                    # Add contacts based on filters
                    filters = request.data.get('filters', {})
                    added_members = self._add_contacts_as_members(campaign, filters, segment_name)
                
                elif member_type == 'custom_query':
                    # Add based on custom query
                    custom_query = request.data.get('custom_query', {})
                    added_members = self._add_custom_query_members(campaign, custom_query, segment_name)
                
                # Log member addition
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=campaign.tenant,
                    type='CAMPAIGN_MEMBERS_ADDED',
                    subject=f'Members Added to Campaign: {campaign.name}',
                    description=f'{len(added_members)} members added to segment "{segment_name}"',
                    assigned_to=request.user,
                    due_date=timezone.now().date(),
                    related_object_type='campaign',
                    related_to_id=campaign.id
                )
                
                return Response({
                    'message': f'{len(added_members)} members added to campaign',
                    'added_count': len(added_members),
                    'segment_name': segment_name,
                    'total_members': campaign.members.count()
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """
        Send email to campaign members.
        
        Expected payload:
        {
            "email_template": "template_name",
            "subject_override": "string",
            "member_filters": {...},
            "schedule_at": "datetime",
            "test_send": boolean,
            "test_email": "string"
        }
        """
        try:
            campaign = self.get_object()
            email_template = request.data.get('email_template')
            subject_override = request.data.get('subject_override')
            member_filters = request.data.get('member_filters', {})
            schedule_at = request.data.get('schedule_at')
            test_send = request.data.get('test_send', False)
            test_email = request.data.get('test_email')
            
            if not email_template:
                return Response(
                    {'error': 'email_template is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Test send
            if test_send:
                if not test_email:
                    return Response(
                        {'error': 'test_email is required for test send'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Send test email
                result = send_crm_email(
                    recipient_email=test_email,
                    subject=f"[TEST] {subject_override or 'Campaign Email'}",
                    template_name=email_template,
                    context_data={'campaign': campaign},
                    recipient_data={'email': test_email, 'first_name': 'Test User'},
                    tenant=campaign.tenant
                )
                
                return Response({
                    'message': 'Test email sent successfully',
                    'test_result': result
                })
            
            # Get target members
            members = campaign.members.filter(
                status='ACTIVE',
                is_unsubscribed=False
            )
            
            # Apply member filters
            if member_filters:
                if member_filters.get('segment'):
                    members = members.filter(segment_name=member_filters['segment'])
                if member_filters.get('engagement_level'):
                    level = member_filters['engagement_level']
                    if level == 'high':
                        members = members.filter(engagement_score__gte=7)
                    elif level == 'medium':
                        members = members.filter(engagement_score__gte=4, engagement_score__lt=7)
                    elif level == 'low':
                        members = members.filter(engagement_score__lt=4)
            
            if schedule_at:
                # Schedule email for later
                campaign_email = CampaignEmail.objects.create(
                    campaign=campaign,
                    template_name=email_template,
                    subject=subject_override or f'{campaign.name} - Campaign Email',
                    scheduled_at=schedule_at,
                    status='SCHEDULED',
                    target_count=members.count(),
                    tenant=campaign.tenant
                )
                
                return Response({
                    'message': f'Email scheduled for {members.count()} members',
                    'scheduled_for': schedule_at,
                    'campaign_email_id': campaign_email.id,
                    'target_count': members.count()
                })
            else:
                # Send immediately
                sent_count = 0
                failed_count = 0
                
                # Create campaign email record
                campaign_email = CampaignEmail.objects.create(
                    campaign=campaign,
                    template_name=email_template,
                    subject=subject_override or f'{campaign.name} - Campaign Email',
                    status='SENDING',
                    target_count=members.count(),
                    tenant=campaign.tenant
                )
                
                # Send to each member
                for member in members.iterator():
                    try:
                        result = send_crm_email(
                            recipient_email=member.email,
                            template_name=email_template,
                            subject=subject_override,
                            context_data={
                                'campaign': campaign,
                                'member': member
                            },
                            recipient_data={
                                'email': member.email,
                                'first_name': member.first_name or 'Valued Customer',
                                'last_name': member.last_name or ''
                            },
                            campaign_id=campaign.id,
                            tenant=campaign.tenant
                        )
                        
                        if result['success']:
                            sent_count += 1
                            # Update member engagement
                            member.last_email_sent = timezone.now()
                            member.emails_sent_count = (member.emails_sent_count or 0) + 1
                            member.save()
                        else:
                            failed_count += 1
                    
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to send email to {member.email}: {e}")
                
                # Update campaign email record
                campaign_email.sent_count = sent_count
                campaign_email.failed_count = failed_count
                campaign_email.status = 'COMPLETED'
                campaign_email.sent_at = timezone.now()
                campaign_email.save()
                
                return Response({
                    'message': f'Email sent to {sent_count} members',
                    'sent_count': sent_count,
                    'failed_count': failed_count,
                    'campaign_email_id': campaign_email.id
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get comprehensive campaign analytics."""
        try:
            campaign = self.get_object()
            
            # Basic metrics
            metrics = self._calculate_campaign_metrics(campaign)
            
            # Email performance
            email_stats = self._get_campaign_email_stats(campaign)
            
            # Member engagement
            engagement_stats = self._get_member_engagement_stats(campaign)
            
            # Conversion tracking
            conversion_stats = self._get_campaign_conversion_stats(campaign)
            
            # Timeline data
            timeline_data = self._get_campaign_timeline(campaign)
            
            return Response({
                'campaign': CampaignSerializer(campaign).data,
                'metrics': metrics,
                'email_performance': email_stats,
                'member_engagement': engagement_stats,
                'conversions': conversion_stats,
                'timeline': timeline_data,
                'recommendations': self._generate_campaign_recommendations(campaign, metrics)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def roi_analysis(self, request, pk=None):
        """Get detailed ROI analysis for campaign."""
        try:
            campaign = self.get_object()
            
            # Calculate costs
            total_cost = float(campaign.actual_cost or campaign.budget or 0)
            
            # Calculate revenue
            total_revenue = float(campaign.actual_revenue or 0)
            
            # If no actual revenue, estimate from opportunities
            if not campaign.actual_revenue:
                estimated_revenue = self._estimate_campaign_revenue(campaign)
                total_revenue = estimated_revenue
            
            # Calculate ROI
            roi_percentage = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
            
            # Cost per acquisition
            conversions = self._get_campaign_conversions_count(campaign)
            cost_per_acquisition = total_cost / conversions if conversions > 0 else 0
            
            # Member metrics
            total_members = campaign.members.count()
            cost_per_member = total_cost / total_members if total_members > 0 else 0
            
            # Email metrics
            email_stats = get_email_statistics(
                tenant=campaign.tenant,
                campaign_id=campaign.id
            )
            
            cost_per_email = total_cost / email_stats.get('total_sent', 1) if email_stats.get('total_sent') else 0
            
            # Benchmarks (industry averages)
            benchmarks = self._get_industry_benchmarks(campaign.type)
            
            return Response({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'roi_analysis': {
                    'total_cost': total_cost,
                    'total_revenue': total_revenue,
                    'net_profit': total_revenue - total_cost,
                    'roi_percentage': round(roi_percentage, 2),
                    'cost_per_acquisition': round(cost_per_acquisition, 2),
                    'cost_per_member': round(cost_per_member, 2),
                    'cost_per_email': round(cost_per_email, 4)
                },
                'performance_vs_benchmarks': {
                    'roi_vs_benchmark': round(roi_percentage - benchmarks.get('avg_roi', 0), 2),
                    'cost_per_acquisition_vs_benchmark': round(
                        cost_per_acquisition - benchmarks.get('avg_cost_per_acquisition', 0), 2
                    )
                },
                'recommendations': self._generate_roi_recommendations(
                    roi_percentage, cost_per_acquisition, benchmarks
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def performance_dashboard(self, request):
        """Get campaign performance dashboard."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Active campaigns
            active_campaigns = queryset.filter(status='ACTIVE')
            
            # Performance metrics
            dashboard_data = {
                'active_campaigns_count': active_campaigns.count(),
                'total_campaign_spend': float(
                    queryset.aggregate(Sum('actual_cost'))['actual_cost__sum'] or 0
                ),
                'total_campaign_revenue': float(
                    queryset.aggregate(Sum('actual_revenue'))['actual_revenue__sum'] or 0
                ),
                'avg_campaign_roi': self._calculate_avg_roi(queryset),
                'top_performing_campaigns': self._get_top_performing_campaigns(queryset),
                'campaign_types_performance': self._get_campaign_types_performance(queryset),
                'monthly_trends': self._get_monthly_campaign_trends(queryset)
            }
            
            # Recent activities
            recent_activities = self._get_recent_campaign_activities(queryset)
            
            return Response({
                'dashboard_metrics': dashboard_data,
                'recent_activities': recent_activities,
                'insights': self._generate_dashboard_insights(dashboard_data)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _validate_campaign_activation(self, campaign):
        """Validate if campaign is ready for activation."""
        errors = []
        
        if not campaign.start_date:
            errors.append('Start date is required')
        
        if campaign.members.count() == 0:
            errors.append('Campaign must have at least one member')
        
        if not campaign.type:
            errors.append('Campaign type is required')
        
        # Check for email template if it's an email campaign
        if campaign.type and 'email' in campaign.type.name.lower():
            email_templates = CampaignEmail.objects.filter(campaign=campaign)
            if not email_templates.exists():
                errors.append('Email campaign requires at least one email template')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _send_campaign_welcome_emails(self, campaign):
        """Send welcome emails to campaign members."""
        try:
            # This would send welcome emails using a predefined template
            active_members = campaign.members.filter(
                status='ACTIVE',
                is_unsubscribed=False
            )
            
            for member in active_members[:50]:  # Limit to prevent overwhelming
                send_crm_email(
                    recipient_email=member.email,
                    subject=f'Welcome to {campaign.name}',
                    template_name='campaign_welcome',
                    context_data={'campaign': campaign, 'member': member},
                    recipient_data={
                        'email': member.email,
                        'first_name': member.first_name or 'Valued Customer'
                    },
                    campaign_id=campaign.id,
                    tenant=campaign.tenant
                )
        except Exception as e:
            print(f"Error sending welcome emails: {e}")
    
    def _schedule_campaign_follow_ups(self, campaign):
        """Schedule follow-up activities for campaign."""
        try:
            from crm.models.activity import Activity
            
            # Schedule follow-up activities based on campaign type
            follow_up_date = campaign.start_date + timedelta(days=7)
            
            Activity.objects.create(
                tenant=campaign.tenant,
                type='FOLLOW_UP',
                subject=f'Follow up on {campaign.name} campaign',
                description=f'Review campaign performance and member engagement',
                assigned_to=campaign.owner,
                due_date=follow_up_date,
                related_object_type='campaign',
                related_to_id=campaign.id
            )
        except Exception as e:
            print(f"Error scheduling follow-ups: {e}")
    
    def _add_manual_members(self, campaign, members_data, segment_name):
        """Add manual members to campaign."""
        added_members = []
        
        for member_data:
                member, created = CampaignMember.objects.get_or_create(
                    campaign=campaign,
                    email=member_data.get('email'),
                    defaults={
                        'first_name': member_data.get('first_name', ''),
                        'last_name': member_data.get('last_name', ''),
                        'phone': member_data.get('phone', ''),
                        'company': member_data.get('company', ''),
                        'segment_name': segment_name,
                        'status': 'ACTIVE',
                        'joined_at': timezone.now(),
                        'tenant': campaign.tenant
                    }
                )
                
                if created:
                    added_members.append(member)
                    
            except Exception as e:
                print(f"Error adding member {member_data.get('email')}: {e}")
        
        return added_members
    
    def _add_leads_as_members(self, campaign, filters, segment_name):
        """Add leads as campaign members based on filters."""
        try:
            from crm.models.lead import Lead
            
            # Build lead query
            leads_query = Lead.objects.filter(tenant=campaign.tenant)
            
            # Apply filters
            if filters.get('status'):
                leads_query = leads_query.filter(status=filters['status'])
            if filters.get('source'):
                leads_query = leads_query.filter(source=filters['source'])
            if filters.get('score_min'):
                leads_query = leads_query.filter(score__gte=filters['score_min'])
            if filters.get('created_after'):
                leads_query = leads_query.filter(created_at__gte=filters['created_after'])
            
            added_members = []
            
            for lead in leads_query:
                try:
                    member, created = CampaignMember.objects.get_or_create(
                        campaign=campaign,
                        email=lead.email,
                        defaults={
                            'first_name': lead.first_name,
                            'last_name': lead.last_name,
                            'phone': lead.phone,
                            'company': lead.company,
                            'segment_name': segment_name,
                            'status': 'ACTIVE',
                            'joined_at': timezone.now(),
                            'source_type': 'lead',
                            'source_id': lead.id,
                            'tenant': campaign.tenant
                        }
                    )
                    
                    if created:
                        added_members.append(member)
                        
                except Exception as e:
                    print(f"Error adding lead {lead.email}: {e}")
            
            return added_members
            
        except Exception as e:
            print(f"Error adding leads: {e}")
            return []
    
    def _add_contacts_as_members(self, campaign, filters, segment_name):
        """Add contacts as campaign members based on filters."""
        try:
            from crm.models.account import Contact
            
            # Build contact query
            contacts_query = Contact.objects.filter(tenant=campaign.tenant)
            
            # Apply filters
            if filters.get('account_type'):
                contacts_query = contacts_query.filter(account__type=filters['account_type'])
            if filters.get('department'):
                contacts_query = contacts_query.filter(department=filters['department'])
            if filters.get('is_primary'):
                contacts_query = contacts_query.filter(is_primary=filters['is_primary'])
            
            added_members = []
            
            for contact in contacts_query:
                try:
                    member, created = CampaignMember.objects.get_or_create(
                        campaign=campaign,
                        email=contact.email,
                        defaults={
                            'first_name': contact.first_name,
                            'last_name': contact.last_name,
                            'phone': contact.phone,
                            'company': contact.account.name if contact.account else '',
                            'segment_name': segment_name,
                            'status': 'ACTIVE',
                            'joined_at': timezone.now(),
                            'source_type': 'contact',
                            'source_id': contact.id,
                            'tenant': campaign.tenant
                        }
                    )
                    
                    if created:
                        added_members.append(member)
                        
                except Exception as e:
                    print(f"Error adding contact {contact.email}: {e}")
            
            return added_members
            
        except Exception as e:
            print(f"Error adding contacts: {e}")
            return []
    
    def _add_custom_query_members(self, campaign, custom_query, segment_name):
        """Add members based on custom query parameters."""
        # This would implement custom query logic
        # For now, return empty list
        return []
    
    def _calculate_campaign_metrics(self, campaign):
        """Calculate comprehensive campaign metrics."""
        try:
            # Basic metrics
            total_members = campaign.members.count()
            active_members = campaign.members.filter(status='ACTIVE').count()
            
            # Cost metrics
            total_cost = float(campaign.actual_cost or campaign.budget or 0)
            total_revenue = float(campaign.actual_revenue or 0)
            
            # ROI calculation
            roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
            
            # Duration metrics
            if campaign.actual_start_date:
                if campaign.actual_end_date:
                    duration_days = (campaign.actual_end_date - campaign.actual_start_date).days
                else:
                    duration_days = (timezone.now().date() - campaign.actual_start_date).days
            else:
                duration_days = 0
            
            return {
                'total_members': total_members,
                'active_members': active_members,
                'total_cost': total_cost,
                'total_revenue': total_revenue,
                'roi_percentage': round(roi, 2),
                'duration_days': duration_days,
                'cost_per_member': round(total_cost / total_members, 2) if total_members > 0 else 0
            }
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            return {}
    
    def _get_campaign_email_stats(self, campaign):
        """Get email performance statistics for campaign."""
        try:
            return get_email_statistics(
                tenant=campaign.tenant,
                campaign_id=campaign.id
            )
        except:
            return {}
    
    def _get_member_engagement_stats(self, campaign):
        """Get member engagement statistics."""
        try:
            members = campaign.members.all()
            
            return {
                'total_members': members.count(),
                'engaged_members': members.filter(
                    Q(email_opens__gt=0) | Q(email_clicks__gt=0)
                ).count(),
                'avg_engagement_score': members.aggregate(
                    Avg('engagement_score')
                )['engagement_score__avg'] or 0,
                'unsubscribed_count': members.filter(is_unsubscribed=True).count(),
                'bounced_count': members.filter(email_bounced=True).count()
            }
        except:
            return {}
    
    def _get_campaign_conversion_stats(self, campaign):
        """Get campaign conversion statistics."""
        try:
            # Count leads/opportunities generated from this campaign
            from crm.models.lead import Lead
            from crm.models.opportunity import Opportunity
            
            campaign_leads = Lead.objects.filter(
                source=f'Campaign: {campaign.name}',
                tenant=campaign.tenant
            )
            
            campaign_opportunities = Opportunity.objects.filter(
                source=f'Campaign: {campaign.name}',
                tenant=campaign.tenant
            )
            
            return {
                'leads_generated': campaign_leads.count(),
                'opportunities_created': campaign_opportunities.count(),
                'opportunities_won': campaign_opportunities.filter(stage__is_won=True).count(),
                'conversion_value': float(
                    campaign_opportunities.filter(stage__is_won=True).aggregate(
                        Sum('actual_value')
                    )['actual_value__sum'] or 0
                )
            }
        except:
            return {}
    
    def _get_campaign_timeline(self, campaign):
        """Get campaign timeline events."""
        try:
            from crm.models.activity import Activity
            
            timeline_events = Activity.objects.filter(
                related_object_type='campaign',
                related_to_id=campaign.id,
                tenant=campaign.tenant
            ).order_by('-created_at')[:20]
            
            timeline_data = []
            for activity in timeline_events:
                timeline_data.append({
                    'date': activity.created_at.isoformat(),
                    'event_type': activity.type,
                    'description': activity.subject,
                    'details': activity.description,
                    'user': activity.assigned_to.get_full_name() if activity.assigned_to else 'System'
                })
            
            return timeline_data
        except:
            return []
    
    def _generate_campaign_recommendations(self, campaign, metrics):
        """Generate recommendations for campaign improvement."""
        recommendations = []
        
        roi = metrics.get('roi_percentage', 0)
        if roi < 100:
            recommendations.append({
                'type': 'improvement',
                'message': f'Campaign ROI is {roi}%, below break-even',
                'action': 'Review targeting, messaging, and budget allocation'
            })
        
        engagement_stats = self._get_member_engagement_stats(campaign)
        engaged_rate = (engagement_stats.get('engaged_members', 0) / 
                       max(engagement_stats.get('total_members', 1), 1) * 100)
        
        if engaged_rate < 20:
            recommendations.append({
                'type': 'attention',
                'message': f'Low engagement rate: {engaged_rate:.1f}%',
                'action': 'Improve email content and timing'
            })
        
        unsubscribe_rate = (engagement_stats.get('unsubscribed_count', 0) / 
                          max(engagement_stats.get('total_members', 1), 1) * 100)
        
        if unsubscribe_rate > 2:
            recommendations.append({
                'type': 'warning',
                'message': f'High unsubscribe rate: {unsubscribe_rate:.1f}%',
                'action': 'Review email frequency and relevance'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'success',
                'message': 'Campaign is performing well',
                'action': 'Continue current strategy and consider scaling'
            })
        
        return recommendations
    
    def _estimate_campaign_revenue(self, campaign):
        """Estimate revenue from campaign based on opportunities."""
        try:
            from crm.models.opportunity import Opportunity
            
            # Get opportunities attributed to this campaign
            estimated_revenue = Opportunity.objects.filter(
                source__icontains=campaign.name,
                tenant=campaign.tenant
            ).aggregate(
                total=Sum(F('value') * F('probability') / 100)
            )['total'] or 0
            
            return float(estimated_revenue)
        except:
            return 0
    
    def _get_campaign_conversions_count(self, campaign):
        """Get count of conversions from campaign."""
        try:
            # Count members who converted (responded or generated opportunities)
            converted_members = campaign.members.filter(
                Q(has_responded=True) | 
                Q(opportunities_generated__gt=0)
            ).count()
            
            return converted_members
        except:
            return 0
    
    def _get_industry_benchmarks(self, campaign_type):
        """Get industry benchmarks for campaign type."""
        # This would typically come from a database or external service
        # For now, return some default benchmarks
        return {
            'avg_roi': 400,  # 400% ROI
            'avg_cost_per_acquisition': 50,
            'avg_engagement_rate': 25,
            'avg_conversion_rate': 3
        }
    
    def _generate_roi_recommendations(self, roi, cost_per_acquisition, benchmarks):
        """Generate ROI-specific recommendations."""
        recommendations = []
        
        benchmark_roi = benchmarks.get('avg_roi', 400)
        if roi < benchmark_roi:
            recommendations.append({
                'priority': 'high',
                'message': f'ROI ({roi:.1f}%) is below industry average ({benchmark_roi}%)',
                'action': 'Optimize targeting and reduce acquisition costs'
            })
        
        benchmark_cpa = benchmarks.get('avg_cost_per_acquisition', 50)
        if cost_per_acquisition > benchmark_cpa:
            recommendations.append({
                'priority': 'medium',
                'message': f'Cost per acquisition (${cost_per_acquisition:.2f}) exceeds benchmark (${benchmark_cpa})',
                'action': 'Improve conversion rates and reduce marketing spend'
            })
        
        return recommendations
    
    def _calculate_avg_roi(self, campaigns):
        """Calculate average ROI across campaigns."""
        try:
            rois = []
            for campaign in campaigns:
                cost = float(campaign.actual_cost or campaign.budget or 0)
                revenue = float(campaign.actual_revenue or 0)
                if cost > 0:
                    roi = (revenue - cost) / cost * 100
                    rois.append(roi)
            
            return sum(rois) / len(rois) if rois else 0
        except:
            return 0
    
    def _get_top_performing_campaigns(self, campaigns, limit=5):
        """Get top performing campaigns by ROI."""
        try:
            campaign_performance = []
            
            for campaign in campaigns:
                cost = float(campaign.actual_cost or campaign.budget or 0)
                revenue = float(campaign.actual_revenue or 0)
                
                if cost > 0:
                    roi = (revenue - cost) / cost * 100
                    campaign_performance.append({
                        'id': campaign.id,
                        'name': campaign.name,
                        'roi': round(roi, 2),
                        'revenue': revenue,
                        'cost': cost
                    })
            
            # Sort by ROI descending
            campaign_performance.sort(key=lambda x: x['roi'], reverse=True)
            
            return campaign_performance[:limit]
        except:
            return []
    
    def _get_campaign_types_performance(self, campaigns):
        """Get performance by campaign type."""
        try:
            type_performance = {}
            
            for campaign in campaigns:
                type_name = campaign.type.name if campaign.type else 'Unknown'
                
                if type_name not in type_performance:
                    type_performance[type_name] = {
                        'count': 0,
                        'total_cost': 0,
                        'total_revenue': 0,
                        'avg_roi': 0
                    }
                
                type_performance[type_name]['count'] += 1
                type_performance[type_name]['total_cost'] += float(campaign.actual_cost or campaign.budget or 0)
                type_performance[type_name]['total_revenue'] += float(campaign.actual_revenue or 0)
            
            # Calculate average ROI for each type
            for type_name, data in type_performance.items():
                if data['total_cost'] > 0:
                    roi = (data['total_revenue'] - data['total_cost']) / data['total_cost'] * 100
                    data['avg_roi'] = round(roi, 2)
            
            return type_performance
        except:
            return {}
    
    def _get_monthly_campaign_trends(self, campaigns):
        """Get monthly campaign performance trends."""
        try:
            # Group campaigns by month
            monthly_data = campaigns.filter(
                actual_start_date__isnull=False
            ).extra(
                select={'month': "DATE_TRUNC('month', actual_start_date)"}
            ).values('month').annotate(
                campaigns_count=Count('id'),
                total_cost=Sum('actual_cost'),
                total_revenue=Sum('actual_revenue')
            ).order_by('month')
            
            return list(monthly_data)
        except:
            return []
    
    def _get_recent_campaign_activities(self, campaigns):
        """Get recent campaign activities."""
        try:
            from crm.models.activity import Activity
            
            recent_activities = Activity.objects.filter(
                related_object_type='campaign',
                related_to_id__in=campaigns.values_list('id', flat=True),
                tenant=get_tenant_from_request(self.request)
            ).select_related('assigned_to').order_by('-created_at')[:10]
            
            activities_data = []
            for activity in recent_activities:
                activities_data.append({
                    'date': activity.created_at.isoformat(),
                    'type': activity.type,
                    'subject': activity.subject,
                    'user': activity.assigned_to.get_full_name() if activity.assigned_to else 'System',
                    'campaign_id': activity.related_to_id
                })
            
            return activities_data
        except:
            return []
    
    def _generate_dashboard_insights(self, dashboard_data):
        """Generate insights for campaign dashboard."""
        insights = []
        
        active_campaigns = dashboard_data.get('active_campaigns_count', 0)
        if active_campaigns == 0:
            insights.append({
                'type': 'info',
                'message': 'No active campaigns running',
                'action': 'Consider launching new campaigns to maintain momentum'
            })
        elif active_campaigns > 10:
            insights.append({
                'type': 'warning',
                'message': f'{active_campaigns} active campaigns may be overwhelming',
                'action': 'Review campaign priorities and consider consolidation'
            })
        
        avg_roi = dashboard_data.get('avg_campaign_roi', 0)
        if avg_roi > 300:
            insights.append({
                'type': 'success',
                'message': f'Excellent average ROI: {avg_roi:.1f}%',
                'action': 'Scale successful campaign strategies'
            })
        elif avg_roi < 100:
            insights.append({
                'type': 'attention',
                'message': f'Average ROI below break-even: {avg_roi:.1f}%',
                'action': 'Review campaign targeting and optimization'
            })
        
        return insights


class CampaignMemberViewSet(CRMBaseViewSet):
    """
    ViewSet for Campaign Member management and analytics.
    """
    
    queryset = CampaignMember.objects.select_related('campaign')
    serializer_class = CampaignMemberSerializer
    filterset_fields = ['campaign', 'status', 'segment_name', 'is_unsubscribed']
    search_fields = ['first_name', 'last_name', 'email', 'company']
    ordering = ['-joined_at']
    
    @action(detail=True, methods=['post'])
    def unsubscribe(self, request, pk=None):
        """Unsubscribe member from campaign."""
        try:
            member = self.get_object()
            
            if member.is_unsubscribed:
                return Response(
                    {'error': 'Member is already unsubscribed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            unsubscribe_reason = request.data.get('reason', '')
            
            # Update member
            member.is_unsubscribed = True
            member.unsubscribed_at = timezone.now()
            member.unsubscribe_reason = unsubscribe_reason
            member.save()
            
            # Log unsubscribe event
            from crm.models.activity import Activity
            Activity.objects.create(
                tenant=member.tenant,
                type='UNSUBSCRIBE',
                subject=f'Campaign Unsubscribe: {member.email}',
                description=f'Member unsubscribed from campaign "{member.campaign.name}". Reason: {unsubscribe_reason}',
                related_object_type='campaign',
                related_to_id=member.campaign.id
            )
            
            return Response({
                'message': 'Member unsubscribed successfully',
                'member': CampaignMemberSerializer(member).data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def engagement_history(self, request, pk=None):
        """Get engagement history for member."""
        try:
            member = self.get_object()
            
            # Get email logs for this member
            email_logs = EmailLog.objects.filter(
                recipient_email=member.email,
                campaign_id=member.campaign.id,
                tenant=member.tenant
            ).order_by('-sent_at')
            
            engagement_history = []
            for log in email_logs:
                engagement_history.append({
                    'date': log.sent_at.isoformat() if log.sent_at else None,
                    'event_type': 'email_sent',
                    'subject': log.subject,
                    'opened': log.opened_at is not None,
                    'clicked': log.click_count > 0,
                    'open_date': log.opened_at.isoformat() if log.opened_at else None,
                    'click_count': log.click_count or 0
                })
            
            return Response({
                'member': CampaignMemberSerializer(member).data,
                'engagement_history': engagement_history,
                'summary': {
                    'total_emails_sent': len(engagement_history),
                    'total_opens': sum(1 for e in engagement_history if e['opened']),
                    'total_clicks': sum(e['click_count'] for e in engagement_history),
                    'engagement_score': member.engagement_score
                }
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignEmailViewSet(CRMBaseViewSet):
    """
    ViewSet for Campaign Email management and tracking.
    """
    
    queryset = CampaignEmail.objects.select_related('campaign')
    serializer_class = CampaignEmailSerializer
    filterset_fields = ['campaign', 'status', 'template_name']
    search_fields = ['subject', 'template_name']
    ordering = ['-created_at']
    
    def get_model_permission(self):
        """Get campaign email-specific permission class."""
        return CampaignEmailPermission
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get detailed performance metrics for campaign email."""
        try:
            campaign_email = self.get_object()
            
            # Get email statistics
            email_stats = get_email_statistics(
                tenant=campaign_email.tenant,
                campaign_id=campaign_email.campaign.id,
                start_date=campaign_email.sent_at,
                end_date=campaign_email.sent_at + timedelta(days=1) if campaign_email.sent_at else None
            )
            
            # Performance analysis
            performance_data = {
                'email_details': CampaignEmailSerializer(campaign_email).data,
                'delivery_stats': {
                    'target_count': campaign_email.target_count,
                    'sent_count': campaign_email.sent_count,
                    'failed_count': campaign_email.failed_count,
                    'delivery_rate': (campaign_email.sent_count / campaign_email.target_count * 100) 
                                   if campaign_email.target_count > 0 else 0
                },
                'engagement_stats': email_stats,
                'performance_rating': self._calculate_email_performance_rating(email_stats)
            }
            
            return Response(performance_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_email_performance_rating(self, email_stats):
        """Calculate performance rating for email."""
        score = 0
        
        # Open rate scoring
        open_rate = email_stats.get('open_rate', 0)
        if open_rate >= 25:
            score += 40
        elif open_rate >= 20:
            score += 30
        elif open_rate >= 15:
            score += 20
        
        # Click rate scoring
        click_rate = email_stats.get('click_rate', 0)
        if click_rate >= 5:
            score += 35
        elif click_rate >= 3:
            score += 25
        elif click_rate >= 2:
            score += 15
        
        # Bounce rate penalty
        bounce_rate = email_stats.get('bounce_rate', 0)
        if bounce_rate > 5:
            score -= 20
        elif bounce_rate > 2:
            score -= 10
        
        # Base score
        score += 25
        
        score = max(0, min(100, score))
        
        if score >= 80:
            return {'rating': 'Excellent', 'score': score}
        elif score >= 60:
            return {'rating': 'Good', 'score': score}
        elif score >= 40:
            return {'rating': 'Average', 'score': score}
        else:
            return {'rating': 'Needs Improvement', 'score': score}


class CampaignAnalyticsViewSet(CRMReadOnlyViewSet):
    """
    Dedicated ViewSet for campaign analytics and reporting.
    """
    
    queryset = Campaign.objects.all()
    
    @action(detail=False, methods=['get'])
    @cache_response(timeout=1800)
    def comparative_analysis(self, request):
        """Compare campaign performance across different dimensions."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Compare by campaign type
            type_comparison = self._compare_by_campaign_type(queryset)
            
            # Compare by time period
            time_comparison = self._compare_by_time_period(queryset)
            
            # Compare by budget range
            budget_comparison = self._compare_by_budget_range(queryset)
            
            return Response({
                'campaign_type_comparison': type_comparison,
                'time_period_comparison': time_comparison,
                'budget_range_comparison': budget_comparison,
                'insights': self._generate_comparative_insights(
                    type_comparison, time_comparison, budget_comparison
                )
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _compare_by_campaign_type(self, campaigns):
        """Compare performance by campaign type."""
        try:
            type_performance = {}
            
            for campaign in campaigns:
                type_name = campaign.type.name if campaign.type else 'Unknown'
                
                if type_name not in type_performance:
                    type_performance[type_name] = {
                        'campaign_count': 0,
                        'total_members': 0,
                        'total_cost': 0,
                        'total_revenue': 0,
                        'avg_roi': 0,
                        'campaigns': []
                    }
                
                metrics = self._calculate_campaign_metrics(campaign)
                
                type_performance[type_name]['campaign_count'] += 1
                type_performance[type_name]['total_members'] += metrics.get('total_members', 0)
                type_performance[type_name]['total_cost'] += metrics.get('total_cost', 0)
                type_performance[type_name]['total_revenue'] += metrics.get('total_revenue', 0)
                type_performance[type_name]['campaigns'].append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'roi': metrics.get('roi_percentage', 0)
                })
            
            # Calculate averages
            for type_name, data in type_performance.items():
                if data['total_cost'] > 0:
                    roi = (data['total_revenue'] - data['total_cost']) / data['total_cost'] * 100
                    data['avg_roi'] = round(roi, 2)
                
                data['avg_members_per_campaign'] = (
                    data['total_members'] / data['campaign_count']
                ) if data['campaign_count'] > 0 else 0
            
            return type_performance
        except:
            return {}
    
    def _compare_by_time_period(self, campaigns):
        """Compare performance by time period."""
        try:
            # Group by quarter
            quarterly_performance = {}
            
            for campaign in campaigns:
                if not campaign.actual_start_date:
                    continue
                
                year = campaign.actual_start_date.year
                quarter = (campaign.actual_start_date.month - 1) // 3 + 1
                period_key = f"Q{quarter} {year}"
                
                if period_key not in quarterly_performance:
                    quarterly_performance[period_key] = {
                        'campaign_count': 0,
                        'total_cost': 0,
                        'total_revenue': 0,
                        'avg_roi': 0
                    }
                
                metrics = self._calculate_campaign_metrics(campaign)
                quarterly_performance[period_key]['campaign_count'] += 1
                quarterly_performance[period_key]['total_cost'] += metrics.get('total_cost', 0)
                quarterly_performance[period_key]['total_revenue'] += metrics.get('total_revenue', 0)
            
            # Calculate ROI for each period
            for period, data in quarterly_performance.items():
                if data['total_cost'] > 0:
                    roi = (data['total_revenue'] - data['total_cost']) / data['total_cost'] * 100
                    data['avg_roi'] = round(roi, 2)
            
            return quarterly_performance
        except:
            return {}
    
    def _compare_by_budget_range(self, campaigns):
        """Compare performance by budget range."""
        try:
            budget_ranges = {
                'Small (< $1K)': {'min': 0, 'max': 1000},
                'Medium ($1K - $10K)': {'min': 1000, 'max': 10000},
                'Large ($10K - $50K)': {'min': 10000, 'max': 50000},
                'Enterprise (> $50K)': {'min': 50000, 'max': float('inf')}
            }
            
            budget_performance = {}
            
            for range_name, range_values in budget_ranges.items():
                budget_performance[range_name] = {
                    'campaign_count': 0,
                    'avg_roi': 0,
                    'avg_cost_per_member': 0,
                    'total_campaigns': []
                }
            
            for campaign in campaigns:
                budget = float(campaign.actual_cost or campaign.budget or 0)
                
                for range_name, range_values in budget_ranges.items():
                    if range_values['min'] <= budget < range_values['max']:
                        metrics = self._calculate_campaign_metrics(campaign)
                        
                        budget_performance[range_name]['campaign_count'] += 1
                        budget_performance[range_name]['total_campaigns'].append({
                            'roi': metrics.get('roi_percentage', 0),
                            'cost_per_member': metrics.get('cost_per_member', 0)
                        })
                        break
            
            # Calculate averages
            for range_name, data in budget_performance.items():
                if data['total_campaigns']:
                    data['avg_roi'] = sum(c['roi'] for c in data['total_campaigns']) / len(data['total_campaigns'])
                    data['avg_cost_per_member'] = sum(c['cost_per_member'] for c in data['total_campaigns']) / len(data['total_campaigns'])
                
                # Remove detailed campaign data from response
                data.pop('total_campaigns', None)
            
            return budget_performance
        except:
            return {}
    
    def _generate_comparative_insights(self, type_comparison, time_comparison, budget_comparison):
        """Generate insights from comparative analysis."""
        insights = []
        
        # Best performing campaign type
        if type_comparison:
            best_type = max(type_comparison.items(), key=lambda x: x[1].get('avg_roi', 0))
            insights.append({
                'type': 'success',
                'message': f'Best performing campaign type: {best_type[0]} (ROI: {best_type[1].get("avg_roi", 0):.1f}%)',
                'action': f'Consider focusing more resources on {best_type[0]} campaigns'
            })
        
        # Budget efficiency insight
        if budget_comparison:
            budget_rois = {k: v.get('avg_roi', 0) for k, v in budget_comparison.items() if v.get('campaign_count', 0) > 0}
            if budget_rois:
                best_budget_range = max(budget_rois.items(), key=lambda x: x[1])
                insights.append({
                    'type': 'efficiency',
                    'message': f'Most efficient budget range: {best_budget_range[0]} (ROI: {best_budget_range[1]:.1f}%)',
                    'action': 'Optimize budget allocation based on this range'
                })
        
        return insights
    
    def _calculate_campaign_metrics(self, campaign):
        """Calculate metrics for a single campaign (helper method)."""
        # This is a simplified version of the method from CampaignViewSet
        total_members = campaign.members.count()
        total_cost = float(campaign.actual_cost or campaign.budget or 0)
        total_revenue = float(campaign.actual_revenue or 0)
        roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_members': total_members,
            'total_cost': total_cost,
            'total_revenue': total_revenue,
            'roi_percentage': roi,
            'cost_per_member': total_cost / total_members if total_members > 0 else 0
        }