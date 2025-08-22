# ============================================================================
# backend/apps/crm/views/lead.py - Lead Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views import View
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import Lead, LeadSource, LeadScoringRule, Account, Contact, Opportunity
from ..serializers import (
    LeadSerializer, LeadDetailSerializer, LeadSourceSerializer,
    LeadScoringRuleSerializer, LeadConversionSerializer, LeadBulkUpdateSerializer
)
from ..filters import LeadFilter
from ..permissions import LeadPermission
from ..services import LeadService, LeadScoringService


class LeadSourceListView(CRMBaseMixin, ListView):
    """Lead source management with performance tracking"""
    
    model = LeadSource
    template_name = 'crm/lead/sources.html'
    context_object_name = 'sources'
    
    def get_queryset(self):
        return LeadSource.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).annotate(
            leads_count=Count('leads'),
            qualified_leads_count=Count('leads', filter=Q(leads__status='QUALIFIED')),
            converted_leads_count=Count('leads', filter=Q(leads__converted_account__isnull=False))
        ).order_by('-total_leads')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Source performance analysis
        sources = self.get_queryset()
        context['performance_summary'] = {
            'total_sources': sources.count(),
            'total_leads': sources.aggregate(Sum('leads_count'))['leads_count__sum'] or 0,
            'best_converting_source': sources.filter(converted_leads_count__gt=0).order_by('-conversion_rate').first(),
            'roi_analysis': self.get_roi_analysis(sources),
        }
        
        return context
    
    def get_roi_analysis(self, sources):
        """Calculate ROI analysis for sources"""
        roi_data = []
        for source in sources:
            if source.cost > 0:
                roi_data.append({
                    'source': source,
                    'roi': source.roi,
                    'cost_per_lead': source.cost_per_lead,
                    'efficiency_rating': 'High' if source.roi > 200 else 'Medium' if source.roi > 100 else 'Low'
                })
        
        return sorted(roi_data, key=lambda x: x['roi'], reverse=True)


class LeadListView(CRMBaseMixin, ListView):
    """Enhanced lead listing with scoring and filtering"""
    
    model = Lead
    template_name = 'crm/lead/list.html'
    context_object_name = 'leads'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Lead.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'industry', 'source', 'owner', 'campaign'
        ).prefetch_related(
            'activities'
        ).annotate(
            activities_count=Count('activities', filter=Q(activities__is_active=True)),
            last_activity_date_calc=Max('activities__created_at')
        )
        
        # Apply filters
        lead_filter = LeadFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_leads'):
            lead_filter.qs = lead_filter.qs.filter(
                Q(owner=user) | Q(owner__isnull=True)
            )
        
        return lead_filter.qs.order_by('-score', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = LeadFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Lead statistics
        queryset = self.get_queryset()
        context['stats'] = {
            'total_leads': queryset.count(),
            'hot_leads': queryset.filter(rating='HOT').count(),
            'qualified_leads': queryset.filter(status='QUALIFIED').count(),
            'unassigned_leads': queryset.filter(owner__isnull=True).count(),
            'converted_leads': queryset.filter(status='CONVERTED').count(),
            'average_score': queryset.aggregate(Avg('score'))['score__avg'] or 0,
            'leads_by_source': self.get_leads_by_source(queryset),
            'leads_by_status': self.get_leads_by_status(queryset),
        }
        
        # Scoring insights
        context['scoring_insights'] = self.get_scoring_insights(queryset)
        
        # Quick actions
        context['quick_actions'] = self.get_quick_actions()
        
        return context
    
    def get_leads_by_source(self, queryset):
        """Get lead distribution by source"""
        return list(queryset.filter(
            source__isnull=False
        ).values(
            'source__name'
        ).annotate(
            count=Count('id'),
            avg_score=Avg('score')
        ).order_by('-count')[:10])
    
    def get_leads_by_status(self, queryset):
        """Get lead distribution by status"""
        return list(queryset.values('status').annotate(
            count=Count('id'),
            avg_score=Avg('score')
        ).order_by('-count'))
    
    def get_scoring_insights(self, queryset):
        """Get lead scoring insights"""
        high_score_leads = queryset.filter(score__gte=80).count()
        medium_score_leads = queryset.filter(score__range=(50, 79)).count()
        low_score_leads = queryset.filter(score__lt=50).count()
        
        return {
            'high_score_count': high_score_leads,
            'medium_score_count': medium_score_leads,
            'low_score_count': low_score_leads,
            'score_distribution': [
                {'range': '80-100', 'count': high_score_leads},
                {'range': '50-79', 'count': medium_score_leads},
                {'range': '0-49', 'count': low_score_leads},
            ]
        }
    
    def get_quick_actions(self):
        """Get available quick actions"""
        actions = []
        user = self.request.user
        
        if user.has_perm('crm.change_lead'):
            actions.extend([
                {
                    'title': 'Assign Leads',
                    'action': 'bulk_assign',
                    'icon': 'user-check',
                    'class': 'btn-primary'
                },
                {
                    'title': 'Update Status',
                    'action': 'bulk_status',
                    'icon': 'edit',
                    'class': 'btn-info'
                },
                {
                    'title': 'Add Tags',
                    'action': 'bulk_tags',
                    'icon': 'tag',
                    'class': 'btn-secondary'
                }
            ])
        
        if user.has_perm('crm.delete_lead'):
            actions.append({
                'title': 'Delete Leads',
                'action': 'bulk_delete',
                'icon': 'trash',
                'class': 'btn-danger'
            })
        
        return actions


class LeadDetailView(CRMBaseMixin, DetailView):
    """Comprehensive lead detail with conversion tracking"""
    
    model = Lead
    template_name = 'crm/lead/detail.html'
    context_object_name = 'lead'
    
    def get_queryset(self):
        return Lead.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'industry', 'source', 'owner', 'campaign',
            'converted_account', 'converted_contact', 'converted_opportunity'
        ).prefetch_related(
            'activities__activity_type',
            'activities__assigned_to'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.get_object()
        
        # Score breakdown
        context['score_breakdown'] = lead.score_breakdown
        context['score_status'] = self.get_score_status(lead.score)
        
        # Activities
        context['recent_activities'] = lead.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')[:10]
        
        context['activity_stats'] = {
            'total_activities': lead.total_activities,
            'last_activity': lead.last_activity_date,
            'days_since_last_activity': lead.days_since_last_activity,
        }
        
        # Conversion information
        if lead.status == 'CONVERTED':
            context['conversion_data'] = {
                'account': lead.converted_account,
                'contact': lead.converted_contact,
                'opportunity': lead.converted_opportunity,
                'conversion_date': lead.converted_date,
            }
        
        # Similar leads
        context['similar_leads'] = self.get_similar_leads(lead)
        
        # Next actions
        context['suggested_actions'] = self.get_suggested_actions(lead)
        
        # Qualification status
        context['qualification_status'] = self.get_qualification_status(lead)
        
        # Communication preferences
        context['communication_preferences'] = {
            'preferred_method': lead.preferred_contact_method,
            'can_call': not lead.do_not_call,
            'can_email': not lead.do_not_email,
        }
        
        return context
    
    def get_score_status(self, score):
        """Get descriptive score status"""
        if score >= 80:
            return {'level': 'Hot', 'color': 'red', 'description': 'High priority lead'}
        elif score >= 50:
            return {'level': 'Warm', 'color': 'orange', 'description': 'Medium priority lead'}
        else:
            return {'level': 'Cold', 'color': 'blue', 'description': 'Low priority lead'}
    
    def get_similar_leads(self, lead):
        """Find similar leads for reference"""
        similar = Lead.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=lead.id)
        
        # Similar by company
        if lead.company:
            similar = similar.filter(
                Q(company__icontains=lead.company) |
                Q(email__icontains=lead.company.lower())
            )
        
        # Similar by industry
        if lead.industry:
            similar = similar.filter(industry=lead.industry)
        
        return similar.select_related('owner', 'source')[:5]
    
    def get_suggested_actions(self, lead):
        """Get suggested next actions based on lead data"""
        actions = []
        
        # Based on score
        if lead.score >= 80:
            actions.append({
                'type': 'call',
                'title': 'Call immediately',
                'description': 'High-score lead should be contacted ASAP',
                'priority': 'high'
            })
        elif lead.score >= 50:
            actions.append({
                'type': 'email',
                'title': 'Send follow-up email',
                'description': 'Medium-score lead needs nurturing',
                'priority': 'medium'
            })
        
        # Based on last activity
        if lead.days_since_last_activity > 7:
            actions.append({
                'type': 'follow_up',
                'title': 'Schedule follow-up',
                'description': f'{lead.days_since_last_activity} days since last activity',
                'priority': 'medium'
            })
        
        # Based on qualification
        if lead.status == 'NEW':
            actions.append({
                'type': 'qualify',
                'title': 'Qualify lead',
                'description': 'Lead needs qualification assessment',
                'priority': 'high'
            })
        
        # Conversion opportunity
        if lead.status == 'QUALIFIED' and not lead.converted_account:
            actions.append({
                'type': 'convert',
                'title': 'Convert to opportunity',
                'description': 'Qualified lead ready for conversion',
                'priority': 'high'
            })
        
        return actions
    
    def get_qualification_status(self, lead):
        """Assess lead qualification status"""
        criteria_met = 0
        total_criteria = 4
        
        criteria = {
            'budget': bool(lead.budget),
            'authority': lead.decision_maker,
            'need': bool(lead.description),  # Simplified need assessment
            'timeline': bool(lead.timeframe)
        }
        
        criteria_met = sum(criteria.values())
        
        return {
            'criteria': criteria,
            'criteria_met': criteria_met,
            'total_criteria': total_criteria,
            'qualification_score': (criteria_met / total_criteria) * 100,
            'qualification_level': (
                'Highly Qualified' if criteria_met >= 3 else
                'Partially Qualified' if criteria_met >= 2 else
                'Unqualified'
            )
        }


class LeadCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new lead with auto-scoring"""
    
    model = Lead
    template_name = 'crm/lead/form.html'
    permission_required = 'crm.add_lead'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'mobile', 'company',
        'job_title', 'industry', 'company_size', 'annual_revenue', 'website',
        'status', 'rating', 'source', 'campaign', 'budget', 'timeframe',
        'decision_maker', 'preferred_contact_method', 'do_not_call',
        'do_not_email', 'address', 'linkedin_url', 'description', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter choices
        form.fields['industry'].queryset = Industry.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['source'].queryset = LeadSource.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['campaign'].queryset = Campaign.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Pre-populate from campaign if specified
        if 'campaign_id' in self.request.GET:
            try:
                campaign = Campaign.objects.get(
                    id=self.request.GET['campaign_id'],
                    tenant=self.request.tenant
                )
                form.initial['campaign'] = campaign
            except Campaign.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        # Auto-assign if configured
        crm_config = self.get_crm_config()
        if crm_config and crm_config.lead_auto_assignment:
            form.instance.owner = self.get_auto_assigned_owner(form.instance)
            form.instance.assigned_date = timezone.now()
        
        with transaction.atomic():
            response = super().form_valid(form)
            
            # Calculate initial score
            if crm_config and crm_config.lead_scoring_enabled:
                self.calculate_lead_score()
            
            # Check for duplicates
            if crm_config and crm_config.duplicate_lead_detection:
                self.check_duplicates()
            
            # Log creation activity
            self.log_lead_creation()
        
        messages.success(
            self.request,
            f'Lead "{form.instance.full_name}" created successfully.'
        )
        
        return response
    
    def get_auto_assigned_owner(self, lead):
        """Auto-assign lead owner based on configuration"""
        crm_config = self.get_crm_config()
        
        if crm_config.lead_assignment_method == 'ROUND_ROBIN':
            return self.get_round_robin_owner()
        elif crm_config.lead_assignment_method == 'TERRITORY':
            return self.get_territory_owner(lead)
        elif crm_config.lead_assignment_method == 'SCORING':
            return self.get_score_based_owner(lead)
        
        return self.request.user
    
    def get_round_robin_owner(self):
        """Get next owner in round-robin assignment"""
        # Simplified round-robin logic
        eligible_users = User.objects.filter(
            tenant=self.request.tenant,
            is_active=True,
            groups__name='Sales Team'  # Assuming sales team group
        ).order_by('id')
        
        if eligible_users.exists():
            # Get user with least recent lead assignment
            last_assigned = Lead.objects.filter(
                tenant=self.request.tenant,
                owner__in=eligible_users
            ).order_by('-assigned_date').first()
            
            if last_assigned and last_assigned.owner:
                # Get next user in rotation
                current_index = list(eligible_users).index(last_assigned.owner)
                next_index = (current_index + 1) % len(eligible_users)
                return eligible_users[next_index]
            else:
                return eligible_users.first()
        
        return self.request.user
    
    def get_territory_owner(self, lead):
        """Get territory-based owner"""
        # This would implement territory-based assignment
        # For now, return current user
        return self.request.user
    
    def get_score_based_owner(self, lead):
        """Get owner based on lead score"""
        # This would implement score-based assignment
        # For now, return current user
        return self.request.user
    
    def calculate_lead_score(self):
        """Calculate initial lead score"""
        try:
            scoring_service = LeadScoringService(self.request.tenant)
            score = scoring_service.calculate_lead_score(self.object)
            
            self.object.score = score
            self.object.last_score_update = timezone.now()
            self.object.save(update_fields=['score', 'last_score_update'])
        except Exception as e:
            # Log error but don't fail lead creation
            messages.warning(
                self.request,
                f'Lead created but scoring failed: {str(e)}'
            )
    
    def check_duplicates(self):
        """Check for potential duplicate leads"""
        duplicates = Lead.objects.filter(
            tenant=self.request.tenant,
            email=self.object.email,
            is_active=True
        ).exclude(id=self.object.id)
        
        if duplicates.exists():
            duplicate = duplicates.first()
            duplicate.duplicates.add(self.object)
            
            messages.warning(
                self.request,
                f'Potential duplicate detected: Similar lead exists ({duplicate.full_name})'
            )
    
    def log_lead_creation(self):
        """Log lead creation activity"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Lead Created',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Lead "{self.object.full_name}" created',
            description=f'New lead {self.object.full_name} from {self.object.source.name if self.object.source else "Unknown source"}',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:lead-detail', kwargs={'pk': self.object.pk})


class LeadUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update lead with score recalculation"""
    
    model = Lead
    template_name = 'crm/lead/form.html'
    permission_required = 'crm.change_lead'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'mobile', 'company',
        'job_title', 'industry', 'company_size', 'annual_revenue', 'website',
        'status', 'rating', 'source', 'owner', 'budget', 'timeframe',
        'decision_maker', 'preferred_contact_method', 'do_not_call',
        'do_not_email', 'address', 'linkedin_url', 'description', 'tags'
    ]
    
    def get_queryset(self):
        return Lead.objects.filter(tenant=self.request.tenant)
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Track significant changes
        changed_fields = form.changed_data
        significant_changes = ['status', 'rating', 'owner', 'budget', 'decision_maker']
        
        has_significant_changes = any(field in changed_fields for field in significant_changes)
        
        response = super().form_valid(form)
        
        # Recalculate score if significant changes
        if has_significant_changes:
            crm_config = self.get_crm_config()
            if crm_config and crm_config.lead_scoring_enabled:
                self.recalculate_score()
        
        # Log status change
        if 'status' in changed_fields:
            self.log_status_change(form.instance.status)
        
        messages.success(
            self.request,
            f'Lead "{form.instance.full_name}" updated successfully.'
        )
        
        return response
    
    def recalculate_score(self):
        """Recalculate lead score after updates"""
        try:
            scoring_service = LeadScoringService(self.request.tenant)
            score = scoring_service.calculate_lead_score(self.object)
            
            self.object.score = score
            self.object.last_score_update = timezone.now()
            self.object.save(update_fields=['score', 'last_score_update'])
        except Exception:
            pass  # Fail silently
    
    def log_status_change(self, new_status):
        """Log lead status change"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Lead Status Changed',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Lead status changed to {new_status}',
            description=f'Lead "{self.object.full_name}" status was changed to {new_status}',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:lead-detail', kwargs={'pk': self.object.pk})


class LeadConversionView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Convert lead to account/contact/opportunity"""
    
    permission_required = 'crm.convert_lead'
    
    def get(self, request, pk):
        lead = get_object_or_404(
            Lead,
            tenant=request.tenant,
            pk=pk
        )
        
        if lead.status == 'CONVERTED':
            messages.warning(request, 'Lead is already converted.')
            return redirect('crm:lead-detail', pk=pk)
        
        # Pre-populate conversion form
        context = {
            'lead': lead,
            'suggested_account_name': lead.company or f"{lead.first_name} {lead.last_name}",
            'existing_accounts': Account.objects.filter(
                tenant=request.tenant,
                is_active=True
            ).filter(
                Q(name__icontains=lead.company) if lead.company else Q()
            )[:10],
        }
        
        return render(request, 'crm/lead/convert.html', context)
    
    def post(self, request, pk):
        lead = get_object_or_404(
            Lead,
            tenant=request.tenant,
            pk=pk
        )
        
        if lead.status == 'CONVERTED':
            messages.error(request, 'Lead is already converted.')
            return redirect('crm:lead-detail', pk=pk)
        
        try:
            with transaction.atomic():
                conversion_data = {
                    'create_account': request.POST.get('create_account') == 'true',
                    'create_contact': request.POST.get('create_contact') == 'true',
                    'create_opportunity': request.POST.get('create_opportunity') == 'true',
                    'account_name': request.POST.get('account_name', ''),
                    'opportunity_name': request.POST.get('opportunity_name', ''),
                    'opportunity_amount': request.POST.get('opportunity_amount', 0),
                    'opportunity_close_date': request.POST.get('opportunity_close_date'),
                }
                
                # Use service to handle conversion
                lead_service = LeadService(request.tenant)
                result = lead_service.convert_lead(lead, request.user, conversion_data)
                
                messages.success(
                    request,
                    f'Lead "{lead.full_name}" converted successfully! '
                    f'Created: {", ".join(result["created"])}'
                )
                
                # Redirect to appropriate record
                if result.get('account'):
                    return redirect('crm:account-detail', pk=result['account'].pk)
                elif result.get('opportunity'):
                    return redirect('crm:opportunity-detail', pk=result['opportunity'].pk)
                else:
                    return redirect('crm:lead-detail', pk=pk)
        
        except Exception as e:
            messages.error(request, f'Conversion failed: {str(e)}')
            return redirect('crm:lead-convert', pk=pk)


class LeadScoringView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Lead scoring management and rules"""
    
    permission_required = 'crm.manage_lead_scoring'
    
    def get(self, request):
        # Get scoring rules
        rules = LeadScoringRule.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('priority', 'rule_type')
        
        # Get scoring statistics
        leads = Lead.objects.filter(
            tenant=request.tenant,
            is_active=True
        )
        
        context = {
            'scoring_rules': rules,
            'scoring_stats': {
                'total_leads': leads.count(),
                'scored_leads': leads.filter(score__gt=0).count(),
                'high_score_leads': leads.filter(score__gte=80).count(),
                'medium_score_leads': leads.filter(score__range=(50, 79)).count(),
                'low_score_leads': leads.filter(score__lt=50).count(),
                'average_score': leads.aggregate(Avg('score'))['score__avg'] or 0,
            },
            'score_distribution': self.get_score_distribution(leads),
        }
        
        return render(request, 'crm/lead/scoring.html', context)
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'recalculate_all':
            return self.recalculate_all_scores(request)
        elif action == 'create_rule':
            return self.create_scoring_rule(request)
        elif action == 'update_rule':
            return self.update_scoring_rule(request)
        
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    def get_score_distribution(self, leads):
        """Get score distribution for visualization"""
        distribution = []
        for i in range(0, 101, 10):
            count = leads.filter(score__range=(i, i+9)).count()
            distribution.append({
                'range': f'{i}-{i+9}',
                'count': count
            })
        return distribution
    
    def recalculate_all_scores(self, request):
        """Recalculate scores for all leads"""
        try:
            scoring_service = LeadScoringService(request.tenant)
            updated_count = scoring_service.recalculate_all_lead_scores()
            
            return JsonResponse({
                'success': True,
                'message': f'Recalculated scores for {updated_count} leads'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })


class LeadViewSet(CRMBaseViewSet):
    """Lead API ViewSet with comprehensive functionality"""
    
    queryset = Lead.objects.all()
    permission_classes = [LeadPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LeadFilter
    search_fields = ['first_name', 'last_name', 'email', 'company', 'job_title']
    ordering_fields = ['score', 'created_at', 'last_activity_date', 'rating']
    ordering = ['-score', '-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeadDetailSerializer
        elif self.action == 'convert':
            return LeadConversionSerializer
        elif self.action == 'bulk_update':
            return LeadBulkUpdateSerializer
        return LeadSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'industry', 'source', 'owner', 'campaign'
        ).prefetch_related(
            'activities'
        ).annotate(
            activities_count=Count('activities', filter=Q(activities__is_active=True))
        )
        
        # User-based filtering
        user = self.request.user
        if not user.has_perm('crm.view_all_leads'):
            queryset = queryset.filter(
                Q(owner=user) | Q(owner__isnull=True)
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert lead to account/contact/opportunity"""
        lead = self.get_object()
        
        if lead.status == 'CONVERTED':
            return Response(
                {'error': 'Lead is already converted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                lead_service = LeadService(request.tenant)
                result = lead_service.convert_lead(
                    lead, 
                    request.user, 
                    serializer.validated_data
                )
                
                return Response({
                    'success': True,
                    'message': 'Lead converted successfully',
                    'created': result['created'],
                    'account_id': result.get('account').id if result.get('account') else None,
                    'contact_id': result.get('contact').id if result.get('contact') else None,
                    'opportunity_id': result.get('opportunity').id if result.get('opportunity') else None,
                })
            
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def calculate_score(self, request, pk=None):
        """Recalculate lead score"""
        lead = self.get_object()
        
        try:
            scoring_service = LeadScoringService(request.tenant)
            old_score = lead.score
            new_score = scoring_service.calculate_lead_score(lead)
            
            lead.score = new_score
            lead.last_score_update = timezone.now()
            lead.save(update_fields=['score', 'last_score_update'])
            
            return Response({
                'success': True,
                'old_score': old_score,
                'new_score': new_score,
                'score_change': new_score - old_score
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Bulk assign leads to owner"""
        lead_ids = request.data.get('lead_ids', [])
        owner_id = request.data.get('owner_id')
        
        if not lead_ids or not owner_id:
            return Response(
                {'error': 'lead_ids and owner_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            owner = User.objects.get(id=owner_id)
            updated_count = self.get_queryset().filter(
                id__in=lead_ids
            ).update(
                owner=owner,
                assigned_date=timezone.now(),
                updated_by=request.user
            )
            
            return Response({
                'success': True,
                'updated_count': updated_count,
                'message': f'Assigned {updated_count} leads to {owner.get_full_name()}'
            })
        
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid owner'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_score_update(self, request):
        """Bulk recalculate scores for selected leads"""
        lead_ids = request.data.get('lead_ids', [])
        
        if not lead_ids:
            # Recalculate all if no specific leads provided
            lead_ids = list(self.get_queryset().values_list('id', flat=True))
        
        try:
            scoring_service = LeadScoringService(request.tenant)
            leads = self.get_queryset().filter(id__in=lead_ids)
            
            updated_count = 0
            for lead in leads:
                new_score = scoring_service.calculate_lead_score(lead)
                lead.score = new_score
                lead.last_score_update = timezone.now()
                lead.save(update_fields=['score', 'last_score_update'])
                updated_count += 1
            
            return Response({
                'success': True,
                'updated_count': updated_count,
                'message': f'Recalculated scores for {updated_count} leads'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def scoring_rules(self, request):
        """Get lead scoring rules"""
        rules = LeadScoringRule.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).order_by('priority')
        
        serializer = LeadScoringRuleSerializer(rules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def duplicate_detection(self, request):
        """Detect potential duplicate leads"""
        duplicates = []
        
        # Find leads with same email
        email_duplicates = Lead.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).values('email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for dup in email_duplicates:
            leads = Lead.objects.filter(
                tenant=request.tenant,
                email=dup['email'],
                is_active=True
            ).order_by('-created_at')
            
            duplicates.append({
                'email': dup['email'],
                'count': dup['count'],
                'leads': LeadSerializer(leads, many=True, context={'request': request}).data
            })
        
        return Response({
            'duplicates': duplicates,
            'total_duplicate_groups': len(duplicates)
        })


class LeadSourceViewSet(CRMBaseViewSet):
    """Lead Source API ViewSet"""
    
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer
    permission_classes = [LeadPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'source_type', 'description']
    ordering_fields = ['name', 'total_leads', 'conversion_rate', 'roi']
    ordering = ['-total_leads']
    
    def get_queryset(self):
        return super().get_queryset().annotate(
            leads_count=Count('leads'),
            active_leads_count=Count('leads', filter=Q(leads__is_active=True))
        )
    
    @action(detail=True, methods=['get'])
    def leads(self, request, pk=None):
        """Get leads from this source"""
        source = self.get_object()
        leads = source.leads.filter(
            is_active=True
        ).select_related('owner', 'industry').order_by('-created_at')
        
        page = self.paginate_queryset(leads)
        if page is not None:
            serializer = LeadSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = LeadSerializer(leads, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get source performance metrics"""
        source = self.get_object()
        
        # Calculate performance metrics
        total_leads = source.leads.filter(is_active=True).count()
        converted_leads = source.leads.filter(
            is_active=True,
            status='CONVERTED'
        ).count()
        
        total_revenue = source.leads.filter(
            is_active=True,
            converted_opportunity__isnull=False,
            converted_opportunity__is_won=True
        ).aggregate(
            revenue=Sum('converted_opportunity__amount')
        )['revenue'] or 0
        
        return Response({
            'total_leads': total_leads,
            'converted_leads': converted_leads,
            'conversion_rate': (converted_leads / max(total_leads, 1)) * 100,
            'total_revenue': float(total_revenue),
            'cost_per_lead': float(source.cost_per_lead),
            'roi': float(source.roi),
            'roi_rating': 'Excellent' if source.roi > 300 else 'Good' if source.roi > 150 else 'Poor'
        })


# ============================================================================
# Bulk Operations View
# ============================================================================

class LeadBulkActionView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Handle bulk actions on leads"""
    
    permission_required = 'crm.change_lead'
    
    def post(self, request):
        action = request.POST.get('action')
        lead_ids = request.POST.getlist('lead_ids')
        
        if not lead_ids:
            return JsonResponse({
                'success': False,
                'message': 'No leads selected'
            })
        
        try:
            with transaction.atomic():
                if action == 'bulk_assign':
                    return self.bulk_assign(lead_ids, request)
                elif action == 'bulk_status':
                    return self.bulk_update_status(lead_ids, request)
                elif action == 'bulk_tags':
                    return self.bulk_add_tags(lead_ids, request)
                elif action == 'bulk_score':
                    return self.bulk_recalculate_scores(lead_ids, request)
                elif action == 'bulk_convert':
                    return self.bulk_convert(lead_ids, request)
                elif action == 'bulk_delete':
                    return self.bulk_delete(lead_ids, request)
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid action'
                    })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def bulk_assign(self, lead_ids, request):
        """Bulk assign leads to owner"""
        owner_id = request.POST.get('owner_id')
        
        if not owner_id:
            return JsonResponse({
                'success': False,
                'message': 'Owner is required'
            })
        
        try:
            owner = User.objects.get(id=owner_id)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid owner selected'
            })
        
        updated_count = Lead.objects.filter(
            tenant=request.tenant,
            id__in=lead_ids
        ).update(
            owner=owner,
            assigned_date=timezone.now(),
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Assigned {updated_count} leads to {owner.get_full_name()}'
        })
    
    def bulk_update_status(self, lead_ids, request):
        """Bulk update lead status"""
        new_status = request.POST.get('new_status')
        
        if not new_status:
            return JsonResponse({
                'success': False,
                'message': 'New status is required'
            })
        
        updated_count = Lead.objects.filter(
            tenant=request.tenant,
            id__in=lead_ids
        ).update(status=new_status, updated_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Updated status for {updated_count} leads'
        })
    
    def bulk_recalculate_scores(self, lead_ids, request):
        """Bulk recalculate lead scores"""
        try:
            scoring_service = LeadScoringService(request.tenant)
            leads = Lead.objects.filter(
                tenant=request.tenant,
                id__in=lead_ids
            )
            
            updated_count = 0
            for lead in leads:
                new_score = scoring_service.calculate_lead_score(lead)
                lead.score = new_score
                lead.last_score_update = timezone.now()
                lead.save(update_fields=['score', 'last_score_update'])
                updated_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Recalculated scores for {updated_count} leads'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Score calculation failed: {str(e)}'
            })
    
    def bulk_convert(self, lead_ids, request):
        """Bulk convert qualified leads"""
        converted_count = 0
        failed_count = 0
        
        qualified_leads = Lead.objects.filter(
            tenant=request.tenant,
            id__in=lead_ids,
            status='QUALIFIED'
        )
        
        lead_service = LeadService(request.tenant)
        
        for lead in qualified_leads:
            try:
                conversion_data = {
                    'create_account': True,
                    'create_contact': True,
                    'create_opportunity': False,  # Don't auto-create opportunities
                    'account_name': lead.company or f"{lead.first_name} {lead.last_name}",
                }
                
                lead_service.convert_lead(lead, request.user, conversion_data)
                converted_count += 1
            
            except Exception:
                failed_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Converted {converted_count} leads. {failed_count} failed.'
        })
    
    def bulk_delete(self, lead_ids, request):
        """Bulk soft delete leads"""
        updated_count = Lead.objects.filter(
            tenant=request.tenant,
            id__in=lead_ids
        ).update(is_active=False, updated_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted {updated_count} leads'
        })
    
    def bulk_add_tags(self, lead_ids, request):
        """Bulk add tags to leads"""
        tags_to_add = request.POST.get('tags', '').split(',')
        tags_to_add = [tag.strip() for tag in tags_to_add if tag.strip()]
        
        if not tags_to_add:
            return JsonResponse({
                'success': False,
                'message': 'No tags provided'
            })
        
        leads = Lead.objects.filter(
            tenant=request.tenant,
            id__in=lead_ids
        )
        
        for lead in leads:
            current_tags = lead.tags or []
            new_tags = list(set(current_tags + tags_to_add))
            lead.tags = new_tags
            lead.updated_by = request.user
            lead.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Added tags to {leads.count()} leads'
        })