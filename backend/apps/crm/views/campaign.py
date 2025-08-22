# ============================================================================
# backend/apps/crm/views/campaign.py - Campaign Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, Http404
from django.views import View
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from decimal import Decimal
import json
import csv

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import (
    Campaign, CampaignTeamMember, CampaignMember, CampaignEmail,
    Lead, Contact, Account, EmailTemplate, EmailLog
)
from ..serializers import (
    CampaignSerializer, CampaignDetailSerializer, CampaignMemberSerializer,
    CampaignEmailSerializer, CampaignTeamMemberSerializer
)
from ..filters import CampaignFilter
from ..permissions import CampaignPermission
from ..services import CampaignService, EmailService


class CampaignDashboardView(CRMBaseMixin, View):
    """Campaign performance dashboard"""
    
    def get(self, request):
        user = request.user
        
        # Get campaigns based on user permissions
        campaigns = Campaign.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).select_related('owner').prefetch_related('team_memberships')
        
        # Filter by user access
        if not user.has_perm('crm.view_all_campaigns'):
            campaigns = campaigns.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        # Active campaigns
        active_campaigns = campaigns.filter(
            status='ACTIVE',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        
        # Recent campaigns
        recent_campaigns = campaigns.order_by('-created_at')[:10]
        
        # Campaign performance summary
        campaign_stats = self.get_campaign_stats(campaigns)
        
        # ROI Analysis
        roi_analysis = self.get_roi_analysis(campaigns)
        
        # Email performance
        email_performance = self.get_email_performance(campaigns)
        
        # Lead generation performance
        lead_performance = self.get_lead_performance(campaigns)
        
        context = {
            'active_campaigns': active_campaigns,
            'recent_campaigns': recent_campaigns,
            'campaign_stats': campaign_stats,
            'roi_analysis': roi_analysis,
            'email_performance': email_performance,
            'lead_performance': lead_performance,
            'total_campaigns': campaigns.count(),
        }
        
        return render(request, 'crm/campaign/dashboard.html', context)
    
    def get_campaign_stats(self, campaigns):
        """Get overall campaign statistics"""
        today = timezone.now().date()
        
        stats = {
            'total_campaigns': campaigns.count(),
            'active_campaigns': campaigns.filter(status='ACTIVE').count(),
            'completed_campaigns': campaigns.filter(status='COMPLETED').count(),
            'total_budget': campaigns.aggregate(Sum('budget_allocated'))['budget_allocated__sum'] or 0,
            'total_spent': campaigns.aggregate(Sum('budget_spent'))['budget_spent__sum'] or 0,
            'total_leads': campaigns.aggregate(Sum('total_leads'))['total_leads__sum'] or 0,
            'total_revenue': campaigns.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0,
            'average_roi': 0,
        }
        
        # Calculate average ROI
        campaigns_with_spend = campaigns.filter(budget_spent__gt=0)
        if campaigns_with_spend.exists():
            total_roi = sum([c.roi for c in campaigns_with_spend])
            stats['average_roi'] = total_roi / campaigns_with_spend.count()
        
        # Performance trends
        this_month = campaigns.filter(
            start_date__month=today.month,
            start_date__year=today.year
        )
        last_month = campaigns.filter(
            start_date__month=today.month - 1 if today.month > 1 else 12,
            start_date__year=today.year if today.month > 1 else today.year - 1
        )
        
        stats['monthly_comparison'] = {
            'this_month_count': this_month.count(),
            'last_month_count': last_month.count(),
            'this_month_leads': this_month.aggregate(Sum('total_leads'))['total_leads__sum'] or 0,
            'last_month_leads': last_month.aggregate(Sum('total_leads'))['total_leads__sum'] or 0,
        }
        
        return stats
    
    def get_roi_analysis(self, campaigns):
        """Get ROI analysis data"""
        roi_campaigns = campaigns.filter(
            budget_spent__gt=0,
            total_revenue__gt=0
        ).annotate(
            calculated_roi=((F('total_revenue') - F('budget_spent')) / F('budget_spent')) * 100
        ).order_by('-calculated_roi')
        
        return {
            'top_performing': list(roi_campaigns[:5].values(
                'name', 'total_revenue', 'budget_spent', 'calculated_roi'
            )),
            'lowest_performing': list(roi_campaigns.reverse()[:5].values(
                'name', 'total_revenue', 'budget_spent', 'calculated_roi'
            )),
            'average_roi': roi_campaigns.aggregate(Avg('calculated_roi'))['calculated_roi__avg'] or 0,
        }
    
    def get_email_performance(self, campaigns):
        """Get email performance metrics"""
        email_campaigns = campaigns.filter(campaign_type='EMAIL')
        
        total_sent = email_campaigns.aggregate(Sum('emails_sent'))['emails_sent__sum'] or 0
        total_opened = email_campaigns.aggregate(Sum('emails_opened'))['emails_opened__sum'] or 0
        total_clicked = email_campaigns.aggregate(Sum('emails_clicked'))['emails_clicked__sum'] or 0
        
        return {
            'total_sent': total_sent,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'open_rate': (total_opened / max(total_sent, 1)) * 100,
            'click_rate': (total_clicked / max(total_sent, 1)) * 100,
            'click_through_rate': (total_clicked / max(total_opened, 1)) * 100,
            'top_performing_emails': list(email_campaigns.filter(
                emails_sent__gt=0
            ).annotate(
                open_rate_calc=(F('emails_opened') / F('emails_sent')) * 100
            ).order_by('-open_rate_calc')[:5].values(
                'name', 'emails_sent', 'emails_opened', 'open_rate_calc'
            )),
        }
    
    def get_lead_performance(self, campaigns):
        """Get lead generation performance"""
        lead_campaigns = campaigns.exclude(total_leads=0)
        
        return {
            'total_leads_generated': campaigns.aggregate(Sum('total_leads'))['total_leads__sum'] or 0,
            'total_qualified_leads': campaigns.aggregate(Sum('qualified_leads'))['qualified_leads__sum'] or 0,
            'total_converted_leads': campaigns.aggregate(Sum('converted_leads'))['converted_leads__sum'] or 0,
            'average_cost_per_lead': self.calculate_average_cost_per_lead(campaigns),
            'top_lead_generators': list(lead_campaigns.order_by('-total_leads')[:5].values(
                'name', 'total_leads', 'qualified_leads', 'converted_leads'
            )),
            'best_conversion_rates': list(lead_campaigns.filter(
                total_leads__gt=0
            ).annotate(
                conversion_rate_calc=(F('converted_leads') / F('total_leads')) * 100
            ).order_by('-conversion_rate_calc')[:5].values(
                'name', 'total_leads', 'converted_leads', 'conversion_rate_calc'
            )),
        }
    
    def calculate_average_cost_per_lead(self, campaigns):
        """Calculate average cost per lead across campaigns"""
        campaigns_with_leads = campaigns.filter(total_leads__gt=0, budget_spent__gt=0)
        if not campaigns_with_leads.exists():
            return 0
        
        total_cost = campaigns_with_leads.aggregate(Sum('budget_spent'))['budget_spent__sum'] or 0
        total_leads = campaigns_with_leads.aggregate(Sum('total_leads'))['total_leads__sum'] or 0
        
        return total_cost / max(total_leads, 1)


class CampaignListView(CRMBaseMixin, ListView):
    """Campaign list view with filtering and analytics"""
    
    model = Campaign
    template_name = 'crm/campaign/list.html'
    context_object_name = 'campaigns'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Campaign.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'owner'
        ).prefetch_related(
            'team_memberships__user'
        ).annotate(
            team_size=Count('team_members'),
            members_count=Count('members'),
            emails_count=Count('emails')
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_campaigns'):
            queryset = queryset.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        # Apply filters
        campaign_filter = CampaignFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        return campaign_filter.qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = CampaignFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Campaign statistics
        queryset = self.get_queryset()
        context['stats'] = self.get_campaign_list_stats(queryset)
        
        # Quick filters
        context['quick_filters'] = self.get_quick_filters()
        
        return context
    
    def get_campaign_list_stats(self, queryset):
        """Get statistics for the campaign list"""
        return {
            'total_count': queryset.count(),
            'active_count': queryset.filter(status='ACTIVE').count(),
            'completed_count': queryset.filter(status='COMPLETED').count(),
            'planned_count': queryset.filter(status='PLANNING').count(),
            'total_budget': queryset.aggregate(Sum('budget_allocated'))['budget_allocated__sum'] or 0,
            'total_spent': queryset.aggregate(Sum('budget_spent'))['budget_spent__sum'] or 0,
            'total_leads': queryset.aggregate(Sum('total_leads'))['total_leads__sum'] or 0,
            'total_revenue': queryset.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0,
            'by_type': list(queryset.values('campaign_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'by_status': list(queryset.values('status').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
    
    def get_quick_filters(self):
        """Get quick filter options"""
        return [
            {'name': 'My Campaigns', 'filter': 'owner=me'},
            {'name': 'Active', 'filter': 'status=ACTIVE'},
            {'name': 'Email Campaigns', 'filter': 'type=EMAIL'},
            {'name': 'High ROI', 'filter': 'roi__gte=200'},
            {'name': 'This Month', 'filter': 'date_range=this_month'},
            {'name': 'Needs Attention', 'filter': 'needs_attention=true'},
        ]


class CampaignDetailView(CRMBaseMixin, DetailView):
    """Comprehensive campaign detail view"""
    
    model = Campaign
    template_name = 'crm/campaign/detail.html'
    context_object_name = 'campaign'
    
    def get_queryset(self):
        return Campaign.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'owner'
        ).prefetch_related(
            'team_memberships__user',
            'members',
            'emails',
            'leads',
            'opportunities'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.get_object()
        
        # Team members
        context['team_members'] = campaign.team_memberships.filter(
            is_active=True
        ).select_related('user')
        
        # Campaign members
        context['members_sample'] = campaign.members.filter(
            status='ACTIVE'
        ).order_by('-created_at')[:10]
        context['total_members'] = campaign.members.count()
        
        # Email campaigns
        context['emails'] = campaign.emails.order_by('-created_at')
        
        # Performance metrics
        context['performance'] = self.get_campaign_performance(campaign)
        
        # ROI analysis
        context['roi_analysis'] = self.get_detailed_roi_analysis(campaign)
        
        # Lead analysis
        context['lead_analysis'] = self.get_lead_analysis(campaign)
        
        # Timeline
        context['timeline'] = self.get_campaign_timeline(campaign)
        
        # Comparison with similar campaigns
        context['similar_campaigns'] = self.get_similar_campaigns(campaign)
        
        # Action recommendations
        context['recommendations'] = self.get_campaign_recommendations(campaign)
        
        return context
    
    def get_campaign_performance(self, campaign):
        """Get detailed campaign performance metrics"""
        days_running = 0
        if campaign.start_date <= timezone.now().date():
            if campaign.status == 'COMPLETED' and campaign.end_date:
                days_running = (campaign.end_date - campaign.start_date).days
            else:
                days_running = (timezone.now().date() - campaign.start_date).days
        
        performance = {
            'days_running': days_running,
            'days_remaining': 0,
            'progress_percentage': 0,
            'budget_utilization': 0,
            'daily_spend_rate': 0,
            'projected_total_spend': 0,
        }
        
        # Calculate remaining days
        if campaign.end_date and campaign.end_date >= timezone.now().date():
            performance['days_remaining'] = (campaign.end_date - timezone.now().date()).days
        
        # Calculate progress percentage
        if campaign.start_date and campaign.end_date:
            total_days = (campaign.end_date - campaign.start_date).days
            if total_days > 0:
                performance['progress_percentage'] = (days_running / total_days) * 100
        
        # Budget analysis
        if campaign.budget_allocated and campaign.budget_allocated > 0:
            performance['budget_utilization'] = (campaign.budget_spent / campaign.budget_allocated) * 100
            
            if days_running > 0:
                performance['daily_spend_rate'] = campaign.budget_spent / days_running
                
                if performance['days_remaining'] > 0:
                    performance['projected_total_spend'] = (
                        campaign.budget_spent + 
                        (performance['daily_spend_rate'] * performance['days_remaining'])
                    )
        
        return performance
    
    def get_detailed_roi_analysis(self, campaign):
        """Get detailed ROI analysis"""
        analysis = {
            'roi': campaign.roi,
            'cost_per_lead': campaign.cost_per_lead,
            'revenue_per_lead': 0,
            'break_even_analysis': {},
            'projections': {},
        }
        
        # Revenue per lead
        if campaign.total_leads > 0:
            analysis['revenue_per_lead'] = campaign.total_revenue / campaign.total_leads
        
        # Break-even analysis
        if campaign.cost_per_lead > 0:
            analysis['break_even_analysis'] = {
                'break_even_revenue_per_lead': campaign.cost_per_lead,
                'current_revenue_per_lead': analysis['revenue_per_lead'],
                'leads_needed_to_break_even': campaign.budget_spent / campaign.cost_per_lead if campaign.cost_per_lead > 0 else 0,
            }
        
        # Projections based on current performance
        performance = self.get_campaign_performance(campaign)
        if performance['days_remaining'] > 0 and performance['days_running'] > 0:
            daily_lead_rate = campaign.total_leads / performance['days_running']
            daily_revenue_rate = campaign.total_revenue / performance['days_running']
            
            analysis['projections'] = {
                'projected_total_leads': campaign.total_leads + (daily_lead_rate * performance['days_remaining']),
                'projected_total_revenue': campaign.total_revenue + (daily_revenue_rate * performance['days_remaining']),
                'projected_final_roi': 0,
            }
            
            if performance['projected_total_spend'] > 0:
                analysis['projections']['projected_final_roi'] = (
                    (analysis['projections']['projected_total_revenue'] - performance['projected_total_spend']) 
                    / performance['projected_total_spend']
                ) * 100
        
        return analysis
    
    def get_lead_analysis(self, campaign):
        """Get lead generation analysis"""
        leads = campaign.leads.filter(is_active=True)
        
        # Lead status breakdown
        status_breakdown = list(leads.values('status').annotate(
            count=Count('id')
        ).order_by('-count'))
        
        # Lead source analysis (if leads have source tracking)
        source_breakdown = list(leads.filter(
            source__isnull=False
        ).values(
            'source__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
        
        # Lead scoring analysis
        score_ranges = [
            {'range': '80-100', 'count': leads.filter(score__gte=80).count()},
            {'range': '60-79', 'count': leads.filter(score__range=(60, 79)).count()},
            {'range': '40-59', 'count': leads.filter(score__range=(40, 59)).count()},
            {'range': '20-39', 'count': leads.filter(score__range=(20, 39)).count()},
            {'range': '0-19', 'count': leads.filter(score__lt=20).count()},
        ]
        
        return {
            'total_leads': leads.count(),
            'average_score': leads.aggregate(Avg('score'))['score__avg'] or 0,
            'status_breakdown': status_breakdown,
            'source_breakdown': source_breakdown,
            'score_distribution': score_ranges,
            'recent_leads': leads.order_by('-created_at')[:5],
        }
    
    def get_campaign_timeline(self, campaign):
        """Get campaign timeline events"""
        timeline = []
        
        # Campaign creation
        timeline.append({
            'date': campaign.created_at.date(),
            'type': 'campaign_created',
            'title': 'Campaign Created',
            'description': f'Campaign "{campaign.name}" was created',
            'icon': 'plus-circle',
            'color': 'success'
        })
        
        # Campaign start
        if campaign.start_date:
            timeline.append({
                'date': campaign.start_date,
                'type': 'campaign_started',
                'title': 'Campaign Started',
                'description': f'Campaign went live',
                'icon': 'play-circle',
                'color': 'primary'
            })
        
        # Email sends
        for email in campaign.emails.order_by('sent_datetime'):
            if email.sent_datetime:
                timeline.append({
                    'date': email.sent_datetime.date(),
                    'type': 'email_sent',
                    'title': 'Email Sent',
                    'description': f'"{email.subject}" sent to {email.total_recipients} recipients',
                    'icon': 'mail',
                    'color': 'info'
                })
        
        # Major milestones
        if campaign.total_leads >= campaign.target_leads if campaign.target_leads else False:
            timeline.append({
                'date': timezone.now().date(),
                'type': 'target_reached',
                'title': 'Lead Target Reached',
                'description': f'Reached lead generation target of {campaign.target_leads}',
                'icon': 'target',
                'color': 'success'
            })
        
        # Campaign end
        if campaign.end_date and campaign.end_date <= timezone.now().date():
            timeline.append({
                'date': campaign.end_date,
                'type': 'campaign_ended',
                'title': 'Campaign Ended',
                'description': 'Campaign completed',
                'icon': 'stop-circle',
                'color': 'secondary'
            })
        
        return sorted(timeline, key=lambda x: x['date'], reverse=True)
    
    def get_similar_campaigns(self, campaign):
        """Get similar campaigns for comparison"""
        similar = Campaign.objects.filter(
            tenant=self.request.tenant,
            campaign_type=campaign.campaign_type,
            is_active=True
        ).exclude(
            id=campaign.id
        ).annotate(
            similarity_score=Case(
                When(target_audience__icontains=campaign.target_audience[:20], then=2),
                default=0
            ) + Case(
                When(budget_allocated__range=(
                    campaign.budget_allocated * 0.8,
                    campaign.budget_allocated * 1.2
                ), then=1),
                default=0
            )
        ).order_by('-similarity_score', '-created_at')[:5]
        
        return similar
    
    def get_campaign_recommendations(self, campaign):
        """Get AI-powered campaign recommendations"""
        recommendations = []
        
        # Budget recommendations
        performance = self.get_campaign_performance(campaign)
        if performance['budget_utilization'] > 80 and performance['days_remaining'] > 7:
            recommendations.append({
                'type': 'budget',
                'priority': 'high',
                'title': 'Budget Alert',
                'description': 'Campaign is consuming budget faster than planned. Consider reallocating or increasing budget.',
                'action': 'Review budget allocation'
            })
        
        # Performance recommendations
        if campaign.roi < 100 and campaign.budget_spent > campaign.budget_allocated * 0.5:
            recommendations.append({
                'type': 'performance',
                'priority': 'medium',
                'title': 'ROI Optimization',
                'description': 'Campaign ROI is below 100%. Consider optimizing targeting or messaging.',
                'action': 'Analyze and optimize'
            })
        
        # Email performance recommendations
        if campaign.campaign_type == 'EMAIL':
            if campaign.email_open_rate < 20:
                recommendations.append({
                    'type': 'email',
                    'priority': 'medium',
                    'title': 'Low Open Rate',
                    'description': f'Email open rate ({campaign.email_open_rate:.1f}%) is below industry average. Consider A/B testing subject lines.',
                    'action': 'Improve subject lines'
                })
            
            if campaign.email_click_rate < 3:
                recommendations.append({
                    'type': 'email',
                    'priority': 'medium',
                    'title': 'Low Click Rate',
                    'description': f'Email click rate ({campaign.email_click_rate:.1f}%) needs improvement. Review email content and CTAs.',
                    'action': 'Optimize email content'
                })
        
        # Lead quality recommendations
        lead_analysis = self.get_lead_analysis(campaign)
        if lead_analysis['average_score'] < 50 and campaign.total_leads > 10:
            recommendations.append({
                'type': 'leads',
                'priority': 'medium',
                'title': 'Lead Quality',
                'description': 'Average lead score is low. Consider refining targeting criteria.',
                'action': 'Improve targeting'
            })
        
        return recommendations


class CampaignCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new campaign"""
    
    model = Campaign
    template_name = 'crm/campaign/form.html'
    permission_required = 'crm.add_campaign'
    fields = [
        'name', 'description', 'campaign_type', 'status', 'start_date', 'end_date',
        'target_audience', 'budget_allocated', 'target_leads', 'target_revenue',
        'target_conversion_rate', 'owner', 'landing_page_url', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Set default values
        form.initial['owner'] = self.request.user
        form.initial['start_date'] = timezone.now().date()
        form.initial['end_date'] = timezone.now().date() + timedelta(days=30)
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        
        # Add creator as team member
        CampaignTeamMember.objects.create(
            tenant=self.request.tenant,
            campaign=self.object,
            user=self.request.user,
            role='MANAGER',
            can_edit=True,
            can_view_analytics=True,
            can_manage_content=True,
            created_by=self.request.user
        )
        
        messages.success(
            self.request,
            f'Campaign "{form.instance.name}" created successfully.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('crm:campaign-detail', kwargs={'pk': self.object.pk})


class CampaignUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update campaign"""
    
    model = Campaign
    template_name = 'crm/campaign/form.html'
    permission_required = 'crm.change_campaign'
    fields = [
        'name', 'description', 'campaign_type', 'status', 'start_date', 'end_date',
        'target_audience', 'budget_allocated', 'target_leads', 'target_revenue',
        'target_conversion_rate', 'owner', 'landing_page_url', 'tags'
    ]
    
    def get_queryset(self):
        return Campaign.objects.filter(tenant=self.request.tenant)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            f'Campaign "{form.instance.name}" updated successfully.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('crm:campaign-detail', kwargs={'pk': self.object.pk})


class CampaignMembersView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage campaign members"""
    
    permission_required = 'crm.change_campaign'
    
    def get(self, request, pk):
        campaign = get_object_or_404(
            Campaign,
            pk=pk,
            tenant=request.tenant
        )
        
        # Get members with pagination
        members = campaign.members.select_related(
            'lead', 'contact', 'account'
        ).order_by('-created_at')
        
        paginator = Paginator(members, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Member statistics
        member_stats = {
            'total_members': members.count(),
            'active_members': members.filter(status='ACTIVE').count(),
            'responded_members': members.filter(responded=True).count(),
            'unsubscribed_members': members.filter(status='UNSUBSCRIBED').count(),
            'bounced_members': members.filter(status='BOUNCED').count(),
            'by_type': list(members.values('member_type').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
        
        context = {
            'campaign': campaign,
            'members': page_obj,
            'member_stats': member_stats,
        }
        
        return render(request, 'crm/campaign/members.html', context)
    
    def post(self, request, pk):
        campaign = get_object_or_404(
            Campaign,
            pk=pk,
            tenant=request.tenant
        )
        
        action = request.POST.get('action')
        
        if action == 'add_members':
            return self.add_members(request, campaign)
        elif action == 'import_members':
            return self.import_members(request, campaign)
        elif action == 'remove_members':
            return self.remove_members(request, campaign)
        elif action == 'update_member_status':
            return self.update_member_status(request, campaign)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def add_members(self, request, campaign):
        """Add members to campaign"""
        try:
            member_type = request.POST.get('member_type', 'LEAD')
            member_ids = request.POST.getlist('member_ids')
            
            added_count = 0
            
            for member_id in member_ids:
                if member_type == 'LEAD':
                    try:
                        lead = Lead.objects.get(
                            id=member_id,
                            tenant=request.tenant
                        )
                        
                        member, created = CampaignMember.objects.get_or_create(
                            campaign=campaign,
                            email=lead.email,
                            defaults={
                                'tenant': request.tenant,
                                'first_name': lead.first_name,
                                'last_name': lead.last_name,
                                'phone': lead.phone or lead.mobile,
                                'company': lead.company,
                                'member_type': 'LEAD',
                                'lead': lead,
                                'created_by': request.user
                            }
                        )
                        
                        if created:
                            added_count += 1
                    
                    except Lead.DoesNotExist:
                        continue
                
                elif member_type == 'CONTACT':
                    try:
                        contact = Contact.objects.get(
                            id=member_id,
                            tenant=request.tenant
                        )
                        
                        member, created = CampaignMember.objects.get_or_create(
                            campaign=campaign,
                            email=contact.email,
                            defaults={
                                'tenant': request.tenant,
                                'first_name': contact.first_name,
                                'last_name': contact.last_name,
                                'phone': contact.phone or contact.mobile,
                                'company': contact.account.name,
                                'member_type': 'CONTACT',
                                'contact': contact,
                                'account': contact.account,
                                'created_by': request.user
                            }
                        )
                        
                        if created:
                            added_count += 1
                    
                    except Contact.DoesNotExist:
                        continue
            
            # Update campaign totals
            campaign.total_leads = campaign.members.count()
            campaign.save(update_fields=['total_leads'])
            
            return JsonResponse({
                'success': True,
                'message': f'Added {added_count} members to campaign',
                'added_count': added_count
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def import_members(self, request, campaign):
        """Import members from CSV file"""
        try:
            csv_file = request.FILES.get('csv_file')
            
            if not csv_file:
                return JsonResponse({
                    'success': False,
                    'message': 'No CSV file provided'
                })
            
            # Process CSV
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(decoded_file.splitlines())
            
            added_count = 0
            errors = []
            
            for row in csv_reader:
                try:
                    email = row.get('email', '').strip().lower()
                    if not email:
                        continue
                    
                    first_name = row.get('first_name', '').strip()
                    last_name = row.get('last_name', '').strip()
                    company = row.get('company', '').strip()
                    phone = row.get('phone', '').strip()
                    
                    member, created = CampaignMember.objects.get_or_create(
                        campaign=campaign,
                        email=email,
                        defaults={
                            'tenant': request.tenant,
                            'first_name': first_name,
                            'last_name': last_name,
                            'phone': phone,
                            'company': company,
                            'member_type': 'PROSPECT',
                            'created_by': request.user
                        }
                    )
                    
                    if created:
                        added_count += 1
                
                except Exception as e:
                    errors.append(f"Row error: {str(e)}")
            
            # Update campaign totals
            campaign.total_leads = campaign.members.count()
            campaign.save(update_fields=['total_leads'])
            
            response_data = {
                'success': True,
                'message': f'Imported {added_count} members',
                'added_count': added_count
            }
            
            if errors:
                response_data['errors'] = errors[:10]  # Show first 10 errors
            
            return JsonResponse(response_data)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class CampaignEmailView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Manage campaign emails"""
    
    permission_required = 'crm.manage_campaigns'
    
    def get(self, request, pk):
        campaign = get_object_or_404(
            Campaign,
            pk=pk,
            tenant=request.tenant
        )
        
        emails = campaign.emails.order_by('-created_at')
        
        # Email statistics
        email_stats = {
            'total_emails': emails.count(),
            'draft_emails': emails.filter(status='DRAFT').count(),
            'sent_emails': emails.filter(status='SENT').count(),
            'scheduled_emails': emails.filter(status='SCHEDULED').count(),
            'total_recipients': emails.aggregate(Sum('total_recipients'))['total_recipients__sum'] or 0,
            'total_opened': emails.aggregate(Sum('opened_count'))['opened_count__sum'] or 0,
            'total_clicked': emails.aggregate(Sum('clicked_count'))['clicked_count__sum'] or 0,
        }
        
        # Calculate rates
        if email_stats['total_recipients'] > 0:
            email_stats['overall_open_rate'] = (email_stats['total_opened'] / email_stats['total_recipients']) * 100
            email_stats['overall_click_rate'] = (email_stats['total_clicked'] / email_stats['total_recipients']) * 100
        else:
            email_stats['overall_open_rate'] = 0
            email_stats['overall_click_rate'] = 0
        
        # Available templates
        templates = EmailTemplate.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('template_type', 'name')
        
        context = {
            'campaign': campaign,
            'emails': emails,
            'email_stats': email_stats,
            'templates': templates,
        }
        
        return render(request, 'crm/campaign/emails.html', context)
    
    def post(self, request, pk):
        campaign = get_object_or_404(
            Campaign,
            pk=pk,
            tenant=request.tenant
        )
        
        action = request.POST.get('action')
        
        if action == 'create_email':
            return self.create_email(request, campaign)
        elif action == 'send_email':
            return self.send_email(request, campaign)
        elif action == 'schedule_email':
            return self.schedule_email(request, campaign)
        elif action == 'test_email':
            return self.send_test_email(request, campaign)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def create_email(self, request, campaign):
        """Create new campaign email"""
        try:
            template_id = request.POST.get('template_id')
            template = None
            
            if template_id:
                template = EmailTemplate.objects.get(
                    id=template_id,
                    tenant=request.tenant
                )
            
            email = CampaignEmail.objects.create(
                tenant=request.tenant,
                campaign=campaign,
                subject=request.POST.get('subject', ''),
                from_name=request.POST.get('from_name', ''),
                from_email=request.POST.get('from_email', ''),
                reply_to_email=request.POST.get('reply_to_email', ''),
                html_content=request.POST.get('html_content', ''),
                text_content=request.POST.get('text_content', ''),
                template=template,
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Email created successfully',
                'email_id': email.id
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def send_email(self, request, campaign):
        """Send campaign email immediately"""
        try:
            email_id = request.POST.get('email_id')
            email = CampaignEmail.objects.get(
                id=email_id,
                campaign=campaign,
                tenant=request.tenant
            )
            
            if email.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'message': 'Only draft emails can be sent'
                })
            
            # Use campaign service to send email
            campaign_service = CampaignService(request.tenant)
            result = campaign_service.send_campaign_email(email, request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'Email queued for sending to {result["recipient_count"]} recipients',
                'recipients': result['recipient_count']
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def send_test_email(self, request, campaign):
        """Send test email"""
        try:
            email_id = request.POST.get('email_id')
            test_email = request.POST.get('test_email')
            
            email = CampaignEmail.objects.get(
                id=email_id,
                campaign=campaign,
                tenant=request.tenant
            )
            
            # Use email service to send test
            email_service = EmailService(request.tenant)
            email_service.send_test_email(email, test_email)
            
            return JsonResponse({
                'success': True,
                'message': f'Test email sent to {test_email}'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class CampaignAnalyticsView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Campaign analytics and reporting"""
    
    permission_required = 'crm.view_campaign_analytics'
    
    def get(self, request, pk):
        campaign = get_object_or_404(
            Campaign,
            pk=pk,
            tenant=request.tenant
        )
        
        # Time-based analytics
        analytics_data = self.get_comprehensive_analytics(campaign)
        
        context = {
            'campaign': campaign,
            'analytics': analytics_data,
        }
        
        return render(request, 'crm/campaign/analytics.html', context)
    
    def get_comprehensive_analytics(self, campaign):
        """Get comprehensive campaign analytics"""
        analytics = {}
        
        # Overall performance
        analytics['overview'] = {
            'total_members': campaign.members.count(),
            'active_members': campaign.members.filter(status='ACTIVE').count(),
            'response_rate': campaign.conversion_rate,
            'roi': campaign.roi,
            'cost_per_lead': campaign.cost_per_lead,
            'revenue_per_lead': campaign.total_revenue / max(campaign.total_leads, 1),
        }
        
        # Email performance
        if campaign.campaign_type == 'EMAIL':
            analytics['email_performance'] = {
                'emails_sent': campaign.emails_sent,
                'emails_delivered': campaign.emails_delivered,
                'emails_opened': campaign.emails_opened,
                'emails_clicked': campaign.emails_clicked,
                'emails_bounced': campaign.emails_bounced,
                'emails_unsubscribed': campaign.emails_unsubscribed,
                'delivery_rate': campaign.email_open_rate,  # This should be delivery rate
                'open_rate': campaign.email_open_rate,
                'click_rate': campaign.email_click_rate,
                'bounce_rate': campaign.bounce_rate,
                'unsubscribe_rate': (campaign.emails_unsubscribed / max(campaign.emails_sent, 1)) * 100,
            }
        
        # Engagement over time
        analytics['engagement_timeline'] = self.get_engagement_timeline(campaign)
        
        # Geographic breakdown
        analytics['geographic'] = self.get_geographic_breakdown(campaign)
        
        # Device/platform breakdown
        analytics['device_breakdown'] = self.get_device_breakdown(campaign)
        
        # Conversion funnel
        analytics['conversion_funnel'] = self.get_conversion_funnel(campaign)
        
        return analytics
    
    def get_engagement_timeline(self, campaign):
        """Get engagement metrics over time"""
        # This would typically involve analyzing email logs and activity data
        # For now, return sample data structure
        return {
            'dates': [],
            'opens': [],
            'clicks': [],
            'conversions': [],
        }
    
    def get_geographic_breakdown(self, campaign):
        """Get geographic performance breakdown"""
        # Analyze member locations if available
        return {}
    
    def get_device_breakdown(self, campaign):
        """Get device/platform breakdown"""
        # Analyze email opens by device if tracking is available
        return {}
    
    def get_conversion_funnel(self, campaign):
        """Get conversion funnel data"""
        members = campaign.members.all()
        
        return {
            'total_members': members.count(),
            'emails_delivered': campaign.emails_delivered,
            'emails_opened': campaign.emails_opened,
            'emails_clicked': campaign.emails_clicked,
            'responses': members.filter(responded=True).count(),
            'conversions': campaign.converted_leads,
        }


# ============================================================================
# API ViewSets
# ============================================================================

class CampaignViewSet(CRMBaseViewSet):
    """Campaign API ViewSet with comprehensive functionality"""
    
    queryset = Campaign.objects.all()
    permission_classes = [CampaignPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CampaignFilter
    search_fields = ['name', 'description', 'target_audience']
    ordering_fields = ['name', 'start_date', 'total_revenue', 'total_leads', 'roi']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CampaignDetailSerializer
        return CampaignSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'owner'
        ).prefetch_related(
            'team_memberships__user'
        ).annotate(
            team_size=Count('team_members'),
            members_count=Count('members'),
            emails_count=Count('emails')
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_campaigns'):
            queryset = queryset.filter(
                Q(owner=user) | Q(team_members=user)
            ).distinct()
        
        return queryset
    
    @action(detail=True, methods=['get', 'post'])
    def members(self, request, pk=None):
        """Manage campaign members"""
        campaign = self.get_object()
        
        if request.method == 'GET':
            members = campaign.members.all().order_by('-created_at')
            page = self.paginate_queryset(members)
            
            if page is not None:
                serializer = CampaignMemberSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = CampaignMemberSerializer(members, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = CampaignMemberSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(
                    tenant=request.tenant,
                    campaign=campaign,
                    created_by=request.user
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get campaign analytics"""
        campaign = self.get_object()
        
        analytics = {
            'overview': {
                'total_members': campaign.members.count(),
                'total_leads': campaign.total_leads,
                'converted_leads': campaign.converted_leads,
                'total_revenue': float(campaign.total_revenue),
                'budget_spent': float(campaign.budget_spent),
                'roi': float(campaign.roi),
                'conversion_rate': float(campaign.conversion_rate),
            },
            'email_metrics': {
                'emails_sent': campaign.emails_sent,
                'emails_delivered': campaign.emails_delivered,
                'emails_opened': campaign.emails_opened,
                'emails_clicked': campaign.emails_clicked,
                'open_rate': float(campaign.email_open_rate),
                'click_rate': float(campaign.email_click_rate),
            } if campaign.campaign_type == 'EMAIL' else None,
            'timeline': self.get_campaign_timeline_data(campaign),
        }
        
        return Response(analytics)
    
    @action(detail=True, methods=['post'])
    def add_members_bulk(self, request, pk=None):
        """Add multiple members to campaign"""
        campaign = self.get_object()
        
        members_data = request.data.get('members', [])
        
                {'error': 'No members data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            added_count = 0
            errors = []:
                    serializer = CampaignMemberSerializer(data=member_data)
                    if serializer.is_valid():
                        # Check for duplicates
                        existing = campaign.members.filter(
                            email=member_data.get('email')
                        ).first()
                        
                        if not existing:
                            serializer.save(
                                tenant=request.tenant,
                                campaign=campaign,
                                created_by=request.user
                            )
                            added_count += 1
                    else:
                        errors.append({
                            'email': member_data.get('email'),
                            'errors': serializer.errors
                        })
                
                except Exception as e:
                    errors.append({
                        'email': member_data.get('email'),
                        'error': str(e)
                    })
            
            # Update campaign totals
            campaign.total_leads = campaign.members.count()
            campaign.save(update_fields=['total_leads'])
            
            response_data = {
                'success': True,
                'added_count': added_count,
                'total_members': campaign.members.count()
            }
            
            if errors:
                response_data['errors'] = errors[:10]  # Limit errors shown
            
            return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def performance_comparison(self, request, pk=None):
        """Compare campaign performance with similar campaigns"""
        campaign = self.get_object()
        
        # Find similar campaigns
        similar_campaigns = self.get_queryset().filter(
            campaign_type=campaign.campaign_type
        ).exclude(id=campaign.id).order_by('-total_leads')[:5]
        
        comparison_data = {
            'current_campaign': {
                'name': campaign.name,
                'roi': float(campaign.roi),
                'conversion_rate': float(campaign.conversion_rate),
                'cost_per_lead': float(campaign.cost_per_lead),
                'total_leads': campaign.total_leads,
            },
            'similar_campaigns': [
                {
                    'name': c.name,
                    'roi': float(c.roi),
                    'conversion_rate': float(c.conversion_rate),
                    'cost_per_lead': float(c.cost_per_lead),
                    'total_leads': c.total_leads,
                }
                for c in similar_campaigns
            ],
            'industry_benchmarks': {
                'average_roi': 150.0,  # This would come from industry data
                'average_conversion_rate': 3.5,
                'average_cost_per_lead': 50.0,
            }
        }
        
        return Response(comparison_data)
    
    def get_campaign_timeline_data(self, campaign):
        """Get timeline data for API"""
        timeline = []
        
        # Campaign milestones
        timeline.append({
            'date': campaign.created_at.isoformat(),
            'event': 'Campaign Created',
            'description': f'Campaign "{campaign.name}" was created'
        })
        
        if campaign.start_date:
            timeline.append({
                'date': campaign.start_date.isoformat(),
                'event': 'Campaign Started',
                'description': 'Campaign went live'
            })
        
        # Add email sends
        for email in campaign.emails.filter(sent_datetime__isnull=False):
            timeline.append({
                'date': email.sent_datetime.isoformat(),
                'event': 'Email Sent',
                'description': f'"{email.subject}" sent to {email.total_recipients} recipients'
            })
        
        return sorted(timeline, key=lambda x: x['date'])


class CampaignMemberViewSet(CRMBaseViewSet):
    """Campaign Member API ViewSet"""
    
    queryset = CampaignMember.objects.all()
    serializer_class = CampaignMemberSerializer
    permission_classes = [CampaignPermission]
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'campaign', 'lead', 'contact', 'account'
        )


class CampaignEmailViewSet(CRMBaseViewSet):
    """Campaign Email API ViewSet"""
    
    queryset = CampaignEmail.objects.all()
    serializer_class = CampaignEmailSerializer
    permission_classes = [CampaignPermission]
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'campaign', 'template'
        )
    
    @action(detail=True, methods=['post'])
    def send_test(self, request, pk=None):
        """Send test email"""
        email = self.get_object()
        test_email_address = request.data.get('email')
        
        if not test_email_address:
            return Response(
                {'error': 'Email address is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            email_service = EmailService(request.tenant)
            email_service.send_test_email(email, test_email_address)
            
            return Response({
                'success': True,
                'message': f'Test email sent to {test_email_address}'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def send_campaign(self, request, pk=None):
        """Send campaign email to all members"""
        email = self.get_object()
        
        if email.status != 'DRAFT':
            return Response(
                {'error': 'Only draft emails can be sent'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign_service = CampaignService(request.tenant)
            result = campaign_service.send_campaign_email(email, request.user)
            
            return Response({
                'success': True,
                'message': f'Email queued for {result["recipient_count"]} recipients',
                'recipients': result['recipient_count'],
                'job_id': result.get('job_id')
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )