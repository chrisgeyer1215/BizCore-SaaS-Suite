# crm/viewsets/lead.py
"""
Lead Management ViewSets

Provides REST API endpoints for:
- Lead management with advanced scoring
- Lead source tracking
- Lead scoring rule management
- Lead conversion and qualification
- Lead analytics and reporting
- Bulk lead operations
"""

from datetime import datetime, timedelta
from django.db.models import Count, Sum, Avg, Q, F, Case, When, IntegerField
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from crm.models.lead import Lead, LeadSource, LeadScoringRule
from crm.serializers.lead import (
    LeadSerializer, LeadDetailSerializer, LeadCreateSerializer,
    LeadSourceSerializer, LeadScoringRuleSerializer
)
from crm.permissions.lead import LeadPermission, LeadScoringPermission
from crm.utils.tenant_utils import get_tenant_from_request, check_tenant_limits
from crm.utils.scoring_utils import (
    calculate_lead_score, update_lead_scores, get_scoring_factors,
    analyze_conversion_probability
)
from crm.utils.pipeline_utils import get_next_stage
from crm.utils.formatters import format_percentage, format_phone_display
from crm.utils.email_utils import send_crm_email
from .base import CRMBaseViewSet, CRMReadOnlyViewSet, cache_response, require_tenant_limits


class LeadFilter(filters.FilterSet):
    """Advanced filtering for Lead ViewSet."""
    
    name = filters.CharFilter(method='filter_name')
    email = filters.CharFilter(lookup_expr='icontains')
    company = filters.CharFilter(lookup_expr='icontains')
    source = filters.ModelChoiceFilter(queryset=LeadSource.objects.all())
    status = filters.ChoiceFilter(choices=Lead.STATUS_CHOICES)
    score_min = filters.NumberFilter(field_name='score', lookup_expr='gte')
    score_max = filters.NumberFilter(field_name='score', lookup_expr='lte')
    grade = filters.ChoiceFilter(choices=Lead.GRADE_CHOICES)
    assigned_to = filters.NumberFilter(field_name='assigned_to__id')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    has_phone = filters.BooleanFilter(method='filter_has_phone')
    has_website = filters.BooleanFilter(method='filter_has_website')
    is_qualified = filters.BooleanFilter(method='filter_is_qualified')
    conversion_probability = filters.ChoiceFilter(
        method='filter_conversion_probability',
        choices=[('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    )
    
    class Meta:
        model = Lead
        fields = ['source', 'status', 'assigned_to', 'industry', 'country']
    
    def filter_name(self, queryset, name, value):
        """Filter by first name or last name."""
        return queryset.filter(
            Q(first_name__icontains=value) | Q(last_name__icontains=value)
        )
    
    def filter_has_phone(self, queryset, name, value):
        """Filter leads with/without phone."""
        if value:
            return queryset.exclude(phone__isnull=True).exclude(phone__exact='')
        else:
            return queryset.filter(Q(phone__isnull=True) | Q(phone__exact=''))
    
    def filter_has_website(self, queryset, name, value):
        """Filter leads with/without website."""
        if value:
            return queryset.exclude(website__isnull=True).exclude(website__exact='')
        else:
            return queryset.filter(Q(website__isnull=True) | Q(website__exact=''))
    
    def filter_is_qualified(self, queryset, name, value):
        """Filter qualified/unqualified leads."""
        if value:
            return queryset.filter(status__in=['QUALIFIED', 'CONVERTED'])
        else:
            return queryset.exclude(status__in=['QUALIFIED', 'CONVERTED'])
    
    def filter_conversion_probability(self, queryset, name, value):
        """Filter by conversion probability based on score."""
        if value == 'high':
            return queryset.filter(score__gte=70)
        elif value == 'medium':
            return queryset.filter(score__gte=40, score__lt=70)
        else:  # low
            return queryset.filter(score__lt=40)


class LeadViewSet(CRMBaseViewSet):
    """
    ViewSet for Lead management with advanced functionality.
    
    Provides CRUD operations, scoring, qualification, and conversion.
    """
    
    queryset = Lead.objects.select_related('source', 'assigned_to').prefetch_related('activities')
    serializer_class = LeadSerializer
    filterset_class = LeadFilter
    search_fields = [
        'first_name', 'last_name', 'email', 'phone', 'company', 
        'title', 'description', 'website'
    ]
    ordering_fields = [
        'first_name', 'last_name', 'created_at', 'score', 'last_contacted'
    ]
    ordering = ['-score', '-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return LeadCreateSerializer
        elif self.action == 'retrieve':
            return LeadDetailSerializer
        return LeadSerializer
    
    def get_model_permission(self):
        """Get lead-specific permission class."""
        return LeadPermission
    
    @require_tenant_limits('leads')
    def create(self, request, *args, **kwargs):
        """Create new lead with automatic scoring and tenant limit checking."""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            # Calculate initial lead score
            lead_id = response.data['id']
            try:
                lead = Lead.objects.get(id=lead_id)
                tenant = get_tenant_from_request(request)
                scoring_result = calculate_lead_score(lead, tenant)
                
                # Update lead with score
                lead.score = scoring_result.total_score
                lead.grade = scoring_result.grade
                lead.save(update_fields=['score', 'grade'])
                
                # Update response data
                response.data['score'] = lead.score
                response.data['grade'] = lead.grade
                
            except Exception as e:
                print(f"Error calculating lead score: {e}")
        
        return response
    
    def update(self, request, *args, **kwargs):
        """Update lead with automatic re-scoring."""
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            # Recalculate score after update
            lead = self.get_object()
            try:
                tenant = get_tenant_from_request(request)
                scoring_result = calculate_lead_score(lead, tenant)
                
                if lead.score != scoring_result.total_score:
                    lead.score = scoring_result.total_score
                    lead.grade = scoring_result.grade
                    lead.save(update_fields=['score', 'grade'])
                    
                    response.data['score'] = lead.score
                    response.data['grade'] = lead.grade
                
            except Exception as e:
                print(f"Error recalculating lead score: {e}")
        
        return response
    
    @action(detail=True, methods=['post'])
    def qualify(self, request, pk=None):
        """
        Qualify a lead and optionally convert to opportunity.
        
        Expected payload:
        {
            "qualification_notes": "string",
            "convert_to_opportunity": true/false,
            "opportunity_data": {
                "name": "string",
                "value": decimal,
                "expected_close_date": "YYYY-MM-DD"
            }
        }
        """
        try:
            lead = self.get_object()
            
            if lead.status == 'QUALIFIED':
                return Response(
                    {'error': 'Lead is already qualified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            qualification_notes = request.data.get('qualification_notes', '')
            convert_to_opportunity = request.data.get('convert_to_opportunity', False)
            
            with transaction.atomic():
                # Update lead status
                lead.status = 'QUALIFIED'
                lead.qualified_at = timezone.now()
                lead.qualified_by = request.user
                if qualification_notes:
                    lead.qualification_notes = qualification_notes
                lead.save()
                
                # Log qualification activity
                from crm.models.activity import Activity
                Activity.objects.create(
                    tenant=lead.tenant,
                    type='NOTE',
                    subject='Lead Qualified',
                    description=f'Lead qualified by {request.user.get_full_name()}. Notes: {qualification_notes}',
                    related_to_id=lead.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                )
                
                result = {
                    'message': 'Lead qualified successfully',
                    'lead': LeadSerializer(lead).data
                }
                
                # Convert to opportunity if requested
                if convert_to_opportunity:
                    opportunity_result = self._convert_to_opportunity(lead, request)
                    result['opportunity'] = opportunity_result
                
                return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def convert_to_opportunity(self, request, pk=None):
        """
        Convert qualified lead to opportunity.
        
        Expected payload:
        {
            "opportunity_name": "string",
            "value": decimal,
            "expected_close_date": "YYYY-MM-DD",
            "stage": "string",
            "probability": integer,
            "description": "string"
        }
        """
        try:
            lead = self.get_object()
            
            if lead.status != 'QUALIFIED':
                return Response(
                    {'error': 'Lead must be qualified before conversion'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if lead.status == 'CONVERTED':
                return Response(
                    {'error': 'Lead is already converted'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            opportunity_result = self._convert_to_opportunity(lead, request)
            
            return Response(opportunity_result, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def scoring_details(self, request, pk=None):
        """Get detailed scoring information for lead."""
        try:
            lead = self.get_object()
            tenant = get_tenant_from_request(request)
            
            # Get scoring factors
            factors = get_scoring_factors(lead, tenant)
            
            # Get conversion probability analysis
            conversion_analysis = analyze_conversion_probability(lead, tenant)
            
            return Response({
                'lead_id': lead.id,
                'current_score': lead.score,
                'grade': lead.grade,
                'scoring_factors': factors,
                'conversion_analysis': conversion_analysis,
                'score_history': self._get_score_history(lead)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def recalculate_score(self, request, pk=None):
        """Manually recalculate lead score."""
        try:
            lead = self.get_object()
            tenant = get_tenant_from_request(request)
            
            # Calculate new score
            scoring_result = calculate_lead_score(lead, tenant)
            
            # Update lead
            old_score = lead.score
            old_grade = lead.grade
            
            lead.score = scoring_result.total_score
            lead.grade = scoring_result.grade
            lead.save(update_fields=['score', 'grade'])
            
            return Response({
                'message': 'Score recalculated successfully',
                'old_score': old_score,
                'new_score': lead.score,
                'old_grade': old_grade,
                'new_grade': lead.grade,
                'scoring_details': scoring_result.__dict__
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def assign_to_user(self, request, pk=None):
        """Assign lead to a user with notification."""
        try:
            lead = self.get_object()
            user_id = request.data.get('user_id')
            notes = request.data.get('notes', '')
            
            if not user_id:
                return Response(
                    {'error': 'user_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                assigned_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            old_assignee = lead.assigned_to
            lead.assigned_to = assigned_user
            lead.save()
            
            # Create assignment activity
            from crm.models.activity import Activity
            Activity.objects.create(
                tenant=lead.tenant,
                type='ASSIGNMENT',
                subject=f'Lead assigned to {assigned_user.get_full_name()}',
                description=f'Lead reassigned from {old_assignee.get_full_name() if old_assignee else "Unassigned"} to {assigned_user.get_full_name()}. Notes: {notes}',
                related_to_id=lead.id,
                assigned_to=assigned_user,
                due_date=timezone.now().date()
            )
            
            # Send notification email
            try:
                send_crm_email(
                    recipient_email=assigned_user.email,
                    subject=f'New Lead Assignment: {lead.get_full_name()}',
                    template_name='lead_assignment',
                    context_data={
                        'lead': lead,
                        'assigned_by': request.user,
                        'notes': notes
                    },
                    recipient_data={
                        'first_name': assigned_user.first_name,
                        'last_name': assigned_user.last_name,
                        'email': assigned_user.email
                    },
                    tenant=lead.tenant
                )
            except Exception as e:
                print(f"Failed to send assignment notification: {e}")
            
            return Response({
                'message': f'Lead assigned to {assigned_user.get_full_name()}',
                'lead': LeadSerializer(lead).data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get all activities for this lead."""
        try:
            from crm.models.activity import Activity
            from crm.serializers.activity import ActivitySerializer
            
            lead = self.get_object()
            activities = Activity.objects.filter(
                related_to_id=lead.id,
                tenant=lead.tenant
            ).order_by('-created_at')
            
            # Apply type filtering
            activity_type = request.query_params.get('type')
            if activity_type:
                activities = activities.filter(type=activity_type)
            
            page = self.paginate_queryset(activities)
            if page is not None:
                serializer = ActivitySerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = ActivitySerializer(activities, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        """Add new activity for this lead."""
        try:
            from crm.models.activity import Activity
            from crm.serializers.activity import ActivitySerializer
            
            lead = self.get_object()
            
            activity_data = request.data.copy()
            activity_data['related_to_id'] = lead.id
            activity_data['tenant'] = lead.tenant.id
            
            # Set assignee to current user if not specified
            if 'assigned_to' not in activity_data:
                activity_data['assigned_to'] = request.user.id
            
            serializer = ActivitySerializer(data=activity_data)
            if serializer.is_valid():
                activity = serializer.save()
                
                # Update lead's last_contacted timestamp
                lead.last_contacted = timezone.now()
                lead.save(update_fields=['last_contacted'])
                
                return Response(
                    ActivitySerializer(activity).data,
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Bulk assign leads to users."""
        try:
            lead_ids = request.data.get('lead_ids', [])
            user_id = request.data.get('user_id')
            notes = request.data.get('notes', '')
            
            if not lead_ids or not user_id:
                return Response(
                    {'error': 'lead_ids and user_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                assigned_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update leads
            tenant = get_tenant_from_request(request)
            leads = Lead.objects.filter(
                id__in=lead_ids,
                tenant=tenant
            )
            
            updated_count = leads.update(assigned_to=assigned_user)
            
            # Create bulk assignment activities
            from crm.models.activity import Activity
            activities = []
            for lead in leads:
                activities.append(Activity(
                    tenant=tenant,
                    type='ASSIGNMENT',
                    subject=f'Bulk assigned to {assigned_user.get_full_name()}',
                    description=f'Lead bulk assigned to {assigned_user.get_full_name()}. Notes: {notes}',
                    related_to_id=lead.id,
                    assigned_to=assigned_user,
                    due_date=timezone.now().date()
                ))
            
            Activity.objects.bulk_create(activities)
            
            return Response({
                'message': f'{updated_count} leads assigned to {assigned_user.get_full_name()}',
                'assigned_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_update_status(self, request):
        """Bulk update lead status."""
        try:
            lead_ids = request.data.get('lead_ids', [])
            new_status = request.data.get('status')
            notes = request.data.get('notes', '')
            
            if not lead_ids or not new_status:
                return Response(
                    {'error': 'lead_ids and status are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate status
            valid_statuses = [choice[0] for choice in Lead.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'Invalid status. Valid options: {valid_statuses}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_tenant_from_request(request)
            leads = Lead.objects.filter(
                id__in=lead_ids,
                tenant=tenant
            )
            
            updated_count = leads.update(status=new_status)
            
            # Create status update activities
            from crm.models.activity import Activity
            activities = []
            for lead in leads:
                activities.append(Activity(
                    tenant=tenant,
                    type='STATUS_UPDATE',
                    subject=f'Status updated to {new_status}',
                    description=f'Lead status bulk updated to {new_status}. Notes: {notes}',
                    related_to_id=lead.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                ))
            
            Activity.objects.bulk_create(activities)
            
            return Response({
                'message': f'{updated_count} leads updated to {new_status} status',
                'updated_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def analytics_overview(self, request):
        """Get comprehensive lead analytics overview."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Basic counts
            total_leads = queryset.count()
            qualified_leads = queryset.filter(status='QUALIFIED').count()
            converted_leads = queryset.filter(status='CONVERTED').count()
            
            # Conversion rates
            qualification_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            
            # Score distribution
            score_distribution = {
                'A (80-100)': queryset.filter(score__gte=80).count(),
                'B (60-79)': queryset.filter(score__gte=60, score__lt=80).count(),
                'C (40-59)': queryset.filter(score__gte=40, score__lt=60).count(),
                'D (20-39)': queryset.filter(score__gte=20, score__lt=40).count(),
                'F (0-19)': queryset.filter(score__lt=20).count(),
            }
            
            # Source analysis
            source_performance = queryset.values(
                'source__name'
            ).annotate(
                count=Count('id'),
                avg_score=Avg('score'),
                conversion_rate=Case(
                    When(count__gt=0, then=F('converted_count') * 100.0 / F('count')),
                    default=0,
                    output_field=IntegerField()
                )
            ).annotate(
                converted_count=Count(Case(When(status='CONVERTED', then=1)))
            ).order_by('-count')
            
            # Time-based analytics
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_leads = queryset.filter(created_at__gte=thirty_days_ago).count()
            
            # Average time to qualification
            qualified_leads_with_times = queryset.filter(
                status__in=['QUALIFIED', 'CONVERTED'],
                qualified_at__isnull=False
            )
            
            avg_qualification_time = None
            if qualified_leads_with_times.exists():
                qualification_times = []
                for lead in qualified_leads_with_times:
                    time_diff = (lead.qualified_at - lead.created_at).total_seconds() / 3600  # hours
                    qualification_times.append(time_diff)
                avg_qualification_time = sum(qualification_times) / len(qualification_times)
            
            return Response({
                'overview': {
                    'total_leads': total_leads,
                    'qualified_leads': qualified_leads,
                    'converted_leads': converted_leads,
                    'recent_leads': recent_leads,
                    'qualification_rate': round(qualification_rate, 2),
                    'conversion_rate': round(conversion_rate, 2),
                    'avg_qualification_time_hours': round(avg_qualification_time, 2) if avg_qualification_time else None
                },
                'score_distribution': score_distribution,
                'source_performance': list(source_performance),
                'trends': self._get_lead_trends(queryset)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get lead performance leaderboard."""
        try:
            # Get top performing users by lead conversion
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            tenant = get_tenant_from_request(request)
            
            # Calculate user performance
            user_stats = []
            users = User.objects.filter(
                assigned_leads__tenant=tenant
            ).distinct()
            
            for user in users:
                user_leads = Lead.objects.filter(
                    assigned_to=user,
                    tenant=tenant
                )
                
                total_leads = user_leads.count()
                converted_leads = user_leads.filter(status='CONVERTED').count()
                avg_score = user_leads.aggregate(Avg('score'))['score__avg'] or 0
                
                conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
                
                user_stats.append({
                    'user_id': user.id,
                    'user_name': user.get_full_name(),
                    'total_leads': total_leads,
                    'converted_leads': converted_leads,
                    'conversion_rate': round(conversion_rate, 2),
                    'avg_lead_score': round(avg_score, 1)
                })
            
            # Sort by conversion rate, then by total conversions
            user_stats.sort(
                key=lambda x: (x['conversion_rate'], x['converted_leads']), 
                reverse=True
            )
            
            return Response({
                'leaderboard': user_stats[:10],  # Top 10
                'period': 'all_time'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _convert_to_opportunity(self, lead, request):
        """Convert lead to opportunity."""
        try:
            from crm.models.opportunity import Opportunity
            from crm.models.account import Account, Contact
            from crm.serializers.opportunity import OpportunitySerializer
            
            # Get or create account
            account = None
            if lead.company:
                account, created = Account.objects.get_or_create(
                    name=lead.company,
                    tenant=lead.tenant,
                    defaults={
                        'website': lead.website,
                        'phone': lead.phone,
                        'industry': lead.industry,
                        'assigned_to': lead.assigned_to
                    }
                )
            
            # Create contact from lead
            contact = None
            if account:
                contact, created = Contact.objects.get_or_create(
                    email=lead.email,
                    account=account,
                    tenant=lead.tenant,
                    defaults={
                        'first_name': lead.first_name,
                        'last_name': lead.last_name,
                        'phone': lead.phone,
                        'title': lead.title,
                        'is_primary': True
                    }
                )
            
            # Create opportunity
            opportunity_data = request.data.get('opportunity_data', {})
            
            opportunity = Opportunity.objects.create(
                tenant=lead.tenant,
                name=opportunity_data.get('name', f"{lead.company or lead.get_full_name()} - {lead.title or 'Opportunity'}"),
                account=account,
                contact=contact,
                value=opportunity_data.get('value'),
                expected_close_date=opportunity_data.get('expected_close_date'),
                stage=opportunity_data.get('stage', 'prospecting'),
                probability=opportunity_data.get('probability', 25),
                description=opportunity_data.get('description', lead.description),
                source=lead.source.name if lead.source else None,
                assigned_to=lead.assigned_to,
                lead=lead
            )
            
            # Update lead status
            lead.status = 'CONVERTED'
            lead.converted_at = timezone.now()
            lead.converted_to_opportunity = opportunity
            lead.save()
            
            # Create conversion activity
            from crm.models.activity import Activity
            Activity.objects.create(
                tenant=lead.tenant,
                type='CONVERSION',
                subject='Lead Converted to Opportunity',
                description=f'Lead converted to opportunity: {opportunity.name}',
                related_to_id=lead.id,
                assigned_to=request.user,
                due_date=timezone.now().date()
            )
            
            return {
                'message': 'Lead converted to opportunity successfully',
                'opportunity': OpportunitySerializer(opportunity).data,
                'account': AccountSerializer(account).data if account else None,
                'contact': ContactSerializer(contact).data if contact else None
            }
        
        except Exception as e:
            raise Exception(f"Conversion failed: {str(e)}")
    
    def _get_score_history(self, lead):
        """Get score change history for lead."""
        # This would retrieve score history from audit logs
        # For now, return current score
        return [{
            'date': lead.updated_at.isoformat(),
            'score': lead.score,
            'grade': lead.grade
        }]
    
    def _get_lead_trends(self, queryset):
        """Get lead creation and conversion trends."""
        try:
            # Last 12 months trends
            twelve_months_ago = timezone.now() - timedelta(days=365)
            
            monthly_trends = queryset.filter(
                created_at__gte=twelve_months_ago
            ).extra(
                select={'month': "DATE_TRUNC('month', created_at)"}
            ).values('month').annotate(
                created=Count('id'),
                qualified=Count(Case(When(status='QUALIFIED', then=1))),
                converted=Count(Case(When(status='CONVERTED', then=1)))
            ).order_by('month')
            
            return list(monthly_trends)
        except:
            return []


class LeadSourceViewSet(CRMBaseViewSet):
    """
    ViewSet for Lead Source management.
    """
    
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer
    search_fields = ['name', 'description']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    @cache_response(timeout=1800)
    def performance(self, request, pk=None):
        """Get performance metrics for this lead source."""
        try:
            source = self.get_object()
            tenant = get_tenant_from_request(request)
            
            source_leads = Lead.objects.filter(
                source=source,
                tenant=tenant
            )
            
            total_leads = source_leads.count()
            qualified_leads = source_leads.filter(status='QUALIFIED').count()
            converted_leads = source_leads.filter(status='CONVERTED').count()
            avg_score = source_leads.aggregate(Avg('score'))['score__avg'] or 0
            
            qualification_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            
            return Response({
                'source': LeadSourceSerializer(source).data,
                'performance': {
                    'total_leads': total_leads,
                    'qualified_leads': qualified_leads,
                    'converted_leads': converted_leads,
                    'qualification_rate': round(qualification_rate, 2),
                    'conversion_rate': round(conversion_rate, 2),
                    'avg_lead_score': round(avg_score, 1)
                },
                'grade_distribution': self._get_grade_distribution(source_leads)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_grade_distribution(self, leads):
        """Get grade distribution for leads."""
        return {
            'A': leads.filter(grade='A').count(),
            'B': leads.filter(grade='B').count(),
            'C': leads.filter(grade='C').count(),
            'D': leads.filter(grade='D').count(),
            'F': leads.filter(grade='F').count(),
        }


class LeadScoringRuleViewSet(CRMBaseViewSet):
    """
    ViewSet for Lead Scoring Rule management.
    """
    
    queryset = LeadScoringRule.objects.all()
    serializer_class = LeadScoringRuleViewSet
    search_fields = ['name', 'description']
    ordering = ['category', 'name']
    
    def get_model_permission(self):
        """Get scoring-specific permission class."""
        return LeadScoringPermission
    
    @action(detail=False, methods=['post'])
    def test_rule(self, request):
        """Test a scoring rule against sample data."""
        try:
            rule_data = request.data.get('rule', {})
            test_data = request.data.get('test_data', {})
            
            # Create temporary rule object
            from crm.utils.scoring_utils import ScoringRule, LeadScoringEngine
            
            temp_rule = ScoringRule(
                rule_id='test',
                name=rule_data.get('name', 'Test Rule'),
                category=rule_data.get('category', 'demographic'),
                field_name=rule_data.get('field_name'),
                condition_type=rule_data.get('condition_type'),
                condition_value=rule_data.get('condition_value'),
                score_value=rule_data.get('score_value', 0),
                weight=rule_data.get('weight', 1.0)
            )
            
            # Test the rule
            engine = LeadScoringEngine(get_tenant_from_request(request))
            result = engine._evaluate_rule_condition(test_data, temp_rule)
            
            applied_score = temp_rule.score_value * temp_rule.weight if result else 0
            
            return Response({
                'rule_matched': result,
                'applied_score': applied_score,
                'rule_details': {
                    'field_name': temp_rule.field_name,
                    'condition': f"{temp_rule.condition_type} {temp_rule.condition_value}",
                    'score_value': temp_rule.score_value,
                    'weight': temp_rule.weight
                },
                'test_data': test_data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_recalculate(self, request):
        """Recalculate scores for all leads using current rules."""
        try:
            tenant = get_tenant_from_request(request)
            
            # Start background task for bulk recalculation
            result = update_lead_scores(tenant, batch_size=100)
            
            return Response({
                'message': 'Bulk score recalculation completed',
                'results': result
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeadAnalyticsViewSet(CRMReadOnlyViewSet):
    """
    Dedicated ViewSet for lead analytics and reporting.
    """
    
    queryset = Lead.objects.all()
    
    @action(detail=False, methods=['get'])
    @cache_response(timeout=600)
    def conversion_funnel(self, request):
        """Get lead conversion funnel analytics."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            funnel_data = {
                'total_leads': queryset.count(),
                'contacted': queryset.exclude(last_contacted__isnull=True).count(),
                'qualified': queryset.filter(status='QUALIFIED').count(),
                'converted': queryset.filter(status='CONVERTED').count()
            }
            
            # Calculate conversion rates
            total = funnel_data['total_leads']
            if total > 0:
                funnel_data['contact_rate'] = (funnel_data['contacted'] / total) * 100
                funnel_data['qualification_rate'] = (funnel_data['qualified'] / total) * 100
                funnel_data['conversion_rate'] = (funnel_data['converted'] / total) * 100
            
            return Response(funnel_data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def score_effectiveness(self, request):
        """Analyze scoring effectiveness and conversion correlation."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Group by score ranges and analyze conversion
            score_ranges = [
                (80, 100, 'A'),
                (60, 79, 'B'), 
                (40, 59, 'C'),
                (20, 39, 'D'),
                (0, 19, 'F')
            ]
            
            effectiveness_data = []
            
            for min_score, max_score, grade in score_ranges:
                range_leads = queryset.filter(
                    score__gte=min_score,
                    score__lte=max_score
                )
                
                total = range_leads.count()
                converted = range_leads.filter(status='CONVERTED').count()
                conversion_rate = (converted / total * 100) if total > 0 else 0
                
                effectiveness_data.append({
                    'grade': grade,
                    'score_range': f"{min_score}-{max_score}",
                    'total_leads': total,
                    'converted_leads': converted,
                    'conversion_rate': round(conversion_rate, 2)
                })
            
            return Response({
                'score_effectiveness': effectiveness_data,
                'insights': self._generate_scoring_insights(effectiveness_data)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_scoring_insights(self, effectiveness_data):
        """Generate insights from scoring effectiveness data."""
        insights = []
        
        # Find best performing grade
        best_grade = max(effectiveness_data, key=lambda x: x['conversion_rate'])
        if best_grade['conversion_rate'] > 0:
            insights.append({
                'type': 'success',
                'message': f"Grade {best_grade['grade']} leads have the highest conversion rate at {best_grade['conversion_rate']}%"
            })
        
        # Check for low-performing high scores
        high_score_ranges = [item for item in effectiveness_data if item['grade'] in ['A', 'B']]
        for range_data in high_score_ranges:
            if range_data['conversion_rate'] < 30:
                insights.append({
                    'type': 'warning',
                    'message': f"Grade {range_data['grade']} leads have lower than expected conversion rate at {range_data['conversion_rate']}%"
                })
        
        return insights


class LeadBulkViewSet(CRMReadOnlyViewSet):
    """
    Specialized ViewSet for bulk lead operations.
    """
    
    queryset = Lead.objects.all()
    
    @action(detail=False, methods=['post'])
    def bulk_score_update(self, request):
        """Bulk update lead scores."""
        try:
            tenant = get_tenant_from_request(request)
            lead_ids = request.data.get('lead_ids', [])
            
            if lead_ids:
                leads = Lead.objects.filter(id__in=lead_ids, tenant=tenant)
            else:
                leads = Lead.objects.filter(tenant=tenant)
            
            updated_count = 0
            for lead in leads.iterator():
                try:
                    scoring_result = calculate_lead_score(lead, tenant)
                    lead.score = scoring_result.total_score
                    lead.grade = scoring_result.grade
                    lead.save(update_fields=['score', 'grade'])
                    updated_count += 1
                except Exception as e:
                    print(f"Error updating score for lead {lead.id}: {e}")
            
            return Response({
                'message': f'{updated_count} lead scores updated',
                'updated_count': updated_count,
                'total_requested': len(lead_ids) if lead_ids else leads.count()
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_qualification(self, request):
        """Bulk qualify leads."""
        try:
            lead_ids = request.data.get('lead_ids', [])
            qualification_notes = request.data.get('notes', '')
            
            if not lead_ids:
                return Response(
                    {'error': 'lead_ids are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant = get_tenant_from_request(request)
            leads = Lead.objects.filter(
                id__in=lead_ids,
                tenant=tenant
            ).exclude(status='QUALIFIED')
            
            updated_count = leads.update(
                status='QUALIFIED',
                qualified_at=timezone.now(),
                qualified_by=request.user,
                qualification_notes=qualification_notes
            )
            
            # Create bulk qualification activities
            from crm.models.activity import Activity
            activities = []
            for lead in leads:
                activities.append(Activity(
                    tenant=tenant,
                    type='QUALIFICATION',
                    subject='Lead Bulk Qualified',
                    description=f'Lead bulk qualified. Notes: {qualification_notes}',
                    related_to_id=lead.id,
                    assigned_to=request.user,
                    due_date=timezone.now().date()
                ))
            
            Activity.objects.bulk_create(activities)
            
            return Response({
                'message': f'{updated_count} leads qualified',
                'qualified_count': updated_count
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )