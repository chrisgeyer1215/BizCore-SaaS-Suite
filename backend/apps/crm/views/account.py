# ============================================================================
# backend/apps/crm/views/account.py - Account & Contact Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F, Prefetch
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views import View
from django.db import transaction
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import Industry, Account, Contact
from ..serializers import (
    IndustrySerializer, AccountSerializer, ContactSerializer,
    AccountDetailSerializer, ContactDetailSerializer
)
from ..filters import AccountFilter, ContactFilter
from ..permissions import AccountPermission, ContactPermission


# ============================================================================
# Industry Views
# ============================================================================

class IndustryListView(CRMBaseMixin, ListView):
    """Industry management and hierarchy view"""
    
    model = Industry
    template_name = 'crm/industry/list.html'
    context_object_name = 'industries'
    
    def get_queryset(self):
        return Industry.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).annotate(
            accounts_count=Count('accounts'),
            total_revenue=Sum('accounts__total_revenue')
        ).order_by('level', 'sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Industry hierarchy for tree view
        industries = self.get_queryset()
        context['industry_tree'] = self.build_industry_tree(industries)
        
        # Industry statistics
        context['stats'] = {
            'total_industries': industries.count(),
            'top_level_industries': industries.filter(parent_industry__isnull=True).count(),
            'total_accounts': industries.aggregate(Sum('accounts_count'))['accounts_count__sum'] or 0,
            'total_revenue': industries.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0,
        }
        
        return context
    
    def build_industry_tree(self, industries):
        """Build hierarchical industry tree"""
        industry_dict = {industry.id: industry for industry in industries}
        tree = []
        
        for industry in industries:
            if industry.parent_industry_id is None:
                industry.children = []
                tree.append(industry)
        
        for industry in industries:
            if industry.parent_industry_id:
                parent = industry_dict.get(industry.parent_industry_id)
                if parent and not hasattr(parent, 'children'):
                    parent.children = []
                if parent:
                    parent.children.append(industry)
        
        return tree


class IndustryViewSet(CRMBaseViewSet):
    """Industry API ViewSet"""
    
    queryset = Industry.objects.all()
    serializer_class = IndustrySerializer
    permission_classes = [AccountPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'sort_order', 'total_accounts']
    ordering = ['level', 'sort_order', 'name']
    
    def get_queryset(self):
        return super().get_queryset().annotate(
            accounts_count=Count('accounts'),
            total_revenue=Sum('accounts__total_revenue')
        )
    
    @action(detail=False, methods=['get'])
    def hierarchy(self, request):
        """Get industry hierarchy tree"""
        industries = self.get_queryset()
        tree = self.build_hierarchy_tree(industries)
        return Response(tree)
    
    @action(detail=True, methods=['get'])
    def accounts(self, request, pk=None):
        """Get accounts in this industry"""
        industry = self.get_object()
        accounts = Account.objects.filter(
            tenant=request.tenant,
            industry=industry,
            is_active=True
        ).select_related('owner', 'territory')
        
        # Apply pagination
        page = self.paginate_queryset(accounts)
        if page is not None:
            serializer = AccountSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = AccountSerializer(accounts, many=True, context={'request': request})
        return Response(serializer.data)
    
    def build_hierarchy_tree(self, industries):
        """Build hierarchical tree structure"""
        industry_dict = {industry.id: {
            'id': industry.id,
            'name': industry.name,
            'code': industry.code,
            'level': industry.level,
            'accounts_count': getattr(industry, 'accounts_count', 0),
            'total_revenue': float(getattr(industry, 'total_revenue', 0) or 0),
            'children': []
        } for industry in industries}
        
        tree = []
        for industry_data in industry_dict.values():
            industry_obj = next(i for i in industries if i.id == industry_data['id'])
            if industry_obj.parent_industry_id is None:
                tree.append(industry_data)
            else:
                parent = industry_dict.get(industry_obj.parent_industry_id)
                if parent:
                    parent['children'].append(industry_data)
        
        return tree


# ============================================================================
# Account Views
# ============================================================================

class AccountListView(CRMBaseMixin, ListView):
    """Enhanced account listing with advanced filtering"""
    
    model = Account
    template_name = 'crm/account/list.html'
    context_object_name = 'accounts'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'industry', 'owner', 'territory', 'parent_account'
        ).prefetch_related(
            'contacts',
            Prefetch(
                'opportunities',
                queryset=self.request.tenant.opportunities.filter(is_active=True)
            )
        ).annotate(
            contacts_count=Count('contacts', filter=Q(contacts__is_active=True)),
            opportunities_count=Count('opportunities', filter=Q(opportunities__is_active=True)),
            open_opportunities_count=Count(
                'opportunities', 
                filter=Q(opportunities__is_active=True, opportunities__is_closed=False)
            ),
            recent_activity_count=Count(
                'activities',
                filter=Q(activities__created_at__gte=timezone.now() - timezone.timedelta(days=30))
            )
        )
        
        # Apply filters
        account_filter = AccountFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        return account_filter.qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = AccountFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Account statistics
        queryset = self.get_queryset()
        context['stats'] = {
            'total_accounts': queryset.count(),
            'total_revenue': queryset.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0,
            'average_deal_size': queryset.aggregate(Avg('average_deal_size'))['average_deal_size__avg'] or 0,
            'accounts_by_type': self.get_accounts_by_type(queryset),
            'top_industries': self.get_top_industries(queryset),
        }
        
        # View preferences
        context['view_mode'] = self.request.GET.get('view', 'list')
        context['sort_by'] = self.request.GET.get('sort', '-created_at')
        
        return context
    
    def get_accounts_by_type(self, queryset):
        """Get account distribution by type"""
        return list(queryset.values('account_type').annotate(
            count=Count('id'),
            revenue=Sum('total_revenue')
        ).order_by('-count'))
    
    def get_top_industries(self, queryset):
        """Get top industries by account count"""
        return list(queryset.filter(
            industry__isnull=False
        ).values(
            'industry__name'
        ).annotate(
            count=Count('id'),
            revenue=Sum('total_revenue')
        ).order_by('-count')[:10])


class AccountDetailView(CRMBaseMixin, DetailView):
    """Comprehensive account detail view with related data"""
    
    model = Account
    template_name = 'crm/account/detail.html'
    context_object_name = 'account'
    
    def get_queryset(self):
        return Account.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'industry', 'owner', 'parent_account', 'territory'
        ).prefetch_related(
            'contacts',
            'opportunities__stage',
            'opportunities__owner',
            'activities__activity_type',
            'activities__assigned_to',
            'tickets',
            'documents'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_object()
        
        # Related data
        context['contacts'] = account.contacts.filter(is_active=True).order_by('is_primary', 'last_name')
        context['primary_contact'] = account.contacts.filter(is_primary=True, is_active=True).first()
        
        # Opportunities
        context['opportunities'] = account.opportunities.filter(
            is_active=True
        ).select_related('stage', 'owner').order_by('-created_at')[:10]
        
        context['opportunity_stats'] = {
            'total': account.opportunities.filter(is_active=True).count(),
            'open': account.opportunities.filter(is_active=True, is_closed=False).count(),
            'won': account.opportunities.filter(is_active=True, is_won=True).count(),
            'lost': account.opportunities.filter(is_active=True, is_closed=True, is_won=False).count(),
            'pipeline_value': account.opportunities.filter(
                is_active=True, is_closed=False
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        # Recent activities
        context['recent_activities'] = account.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')[:10]
        
        # Activity summary
        context['activity_stats'] = self.get_activity_stats(account)
        
        # Financial summary
        context['financial_summary'] = {
            'total_revenue': account.total_revenue,
            'average_deal_size': account.average_deal_size,
            'payment_terms': account.payment_terms,
            'credit_limit': account.credit_limit,
            'last_purchase_date': account.last_purchase_date,
        }
        
        # Relationship timeline
        context['timeline'] = self.get_relationship_timeline(account)
        
        # Documents
        context['recent_documents'] = account.documents.filter(
            is_active=True
        ).order_by('-created_at')[:5]
        
        # Child accounts
        context['child_accounts'] = account.child_accounts.filter(
            is_active=True
        ).select_related('industry', 'owner')[:10]
        
        # Performance metrics
        context['performance_metrics'] = self.get_performance_metrics(account)
        
        return context
    
    def get_activity_stats(self, account):
        """Get activity statistics for account"""
        activities = account.activities.filter(is_active=True)
        
        return {
            'total_activities': activities.count(),
            'completed_activities': activities.filter(status='COMPLETED').count(),
            'overdue_activities': activities.filter(
                status='PLANNED',
                start_datetime__lt=timezone.now()
            ).count(),
            'activities_this_month': activities.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
            'by_type': list(activities.values(
                'activity_type__name'
            ).annotate(count=Count('id')).order_by('-count')[:5])
        }
    
    def get_relationship_timeline(self, account):
        """Build relationship timeline"""
        timeline = []
        
        # Account creation
        timeline.append({
            'date': account.created_at,
            'type': 'account_created',
            'title': 'Account Created',
            'description': f'Account {account.name} was created',
            'icon': 'building',
            'user': account.created_by.get_full_name() if account.created_by else 'System'
        })
        
        # Customer conversion
        if account.customer_since:
            timeline.append({
                'date': account.customer_since,
                'type': 'became_customer',
                'title': 'Became Customer',
                'description': 'Account converted to customer status',
                'icon': 'star',
                'user': 'System'
            })
        
        # Major opportunities
        major_opps = account.opportunities.filter(
            is_active=True,
            amount__gte=10000  # Configurable threshold
        ).order_by('-amount')[:5]
        
        for opp in major_opps:
            timeline.append({
                'date': opp.created_at,
                'type': 'opportunity_created',
                'title': f'Major Opportunity: {opp.name}',
                'description': f'${opp.amount:,.2f} opportunity created',
                'icon': 'target',
                'user': opp.owner.get_full_name() if opp.owner else 'System'
            })
        
        # Recent activities
        recent_activities = account.activities.filter(
            is_active=True,
            activity_type__category='MEETING'
        ).order_by('-created_at')[:3]
        
        for activity in recent_activities:
            timeline.append({
                'date': activity.created_at,
                'type': 'meeting',
                'title': activity.subject,
                'description': f'{activity.activity_type.name} with {account.name}',
                'icon': 'calendar',
                'user': activity.assigned_to.get_full_name() if activity.assigned_to else 'System'
            })
        
        # Sort timeline by date (newest first)
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        return timeline[:20]  # Limit to recent 20 events
    
    def get_performance_metrics(self, account):
        """Calculate account performance metrics"""
        # Deal velocity
        won_opportunities = account.opportunities.filter(
            is_active=True,
            is_won=True
        )
        
        if won_opportunities.exists():
            avg_sales_cycle = won_opportunities.aggregate(
                avg_cycle=Avg('days_in_pipeline')
            )['avg_cycle'] or 0
        else:
            avg_sales_cycle = 0
        
        # Engagement score
        recent_activities = account.activities.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=90)
        ).count()
        
        engagement_score = min(100, recent_activities * 5)  # Simple scoring
        
        return {
            'win_rate': account.win_rate,
            'average_sales_cycle': avg_sales_cycle,
            'engagement_score': engagement_score,
            'customer_lifetime_value': account.total_revenue,
            'days_as_customer': account.days_as_customer if hasattr(account, 'days_as_customer') else 0,
        }


class AccountCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new account with enhanced features"""
    
    model = Account
    template_name = 'crm/account/form.html'
    permission_required = 'crm.add_account'
    fields = [
        'name', 'legal_name', 'account_type', 'status', 'industry',
        'website', 'company_size', 'annual_revenue', 'employee_count',
        'phone', 'email', 'billing_address', 'shipping_address',
        'owner', 'parent_account', 'territory',
        'preferred_contact_method', 'do_not_call', 'do_not_email',
        'description', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter choices based on tenant
        form.fields['industry'].queryset = Industry.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['owner'].queryset = self.request.tenant.users.filter(
            is_active=True
        )
        
        form.fields['parent_account'].queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=getattr(self.object, 'id', None))
        
        # Pre-populate from lead if converting
        if 'lead_id' in self.request.GET:
            try:
                from ..models import Lead
                lead = Lead.objects.get(
                    id=self.request.GET['lead_id'],
                    tenant=self.request.tenant
                )
                form.initial.update({
                    'name': lead.company or f"{lead.first_name} {lead.last_name}",
                    'phone': lead.phone,
                    'website': lead.website,
                    'industry': lead.industry,
                    'annual_revenue': lead.annual_revenue,
                    'owner': lead.owner,
                })
            except Lead.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        # Auto-assign owner if not specified
        if not form.instance.owner:
            form.instance.owner = self.request.user
        
        # Auto-generate account number
        form.instance.account_number = form.instance.generate_account_number()
        
        with transaction.atomic():
            response = super().form_valid(form)
            
            # Create primary contact if converting from lead
            if 'lead_id' in self.request.GET:
                self.create_contact_from_lead()
            
            # Log account creation activity
            self.log_account_creation()
        
        messages.success(
            self.request,
            f'Account "{form.instance.name}" created successfully.'
        )
        
        return response
    
    def create_contact_from_lead(self):
        """Create primary contact from lead data"""
        try:
            from ..models import Lead
            lead = Lead.objects.get(
                id=self.request.GET['lead_id'],
                tenant=self.request.tenant
            )
            
            Contact.objects.create(
                tenant=self.request.tenant,
                account=self.object,
                first_name=lead.first_name,
                last_name=lead.last_name,
                email=lead.email,
                phone=lead.phone,
                mobile=lead.mobile,
                job_title=lead.job_title,
                is_primary=True,
                owner=self.object.owner,
                created_by=self.request.user
            )
        except Lead.DoesNotExist:
            pass
    
    def log_account_creation(self):
        """Log account creation activity"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Account Created',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Account "{self.object.name}" created',
            description=f'New account {self.object.name} was created in the system',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Account),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:account-detail', kwargs={'pk': self.object.pk})


class AccountUpdateView(CRMBaseMixin, PermissionRequiredMixin, UpdateView):
    """Update existing account"""
    
    model = Account
    template_name = 'crm/account/form.html'
    permission_required = 'crm.change_account'
    fields = [
        'name', 'legal_name', 'account_type', 'status', 'industry',
        'website', 'company_size', 'annual_revenue', 'employee_count',
        'phone', 'email', 'billing_address', 'shipping_address',
        'owner', 'parent_account', 'territory',
        'preferred_contact_method', 'do_not_call', 'do_not_email',
        'description', 'tags'
    ]
    
    def get_queryset(self):
        return Account.objects.filter(tenant=self.request.tenant)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter choices based on tenant
        form.fields['industry'].queryset = Industry.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        form.fields['owner'].queryset = self.request.tenant.users.filter(
            is_active=True
        )
        
        form.fields['parent_account'].queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).exclude(id=self.object.id)
        
        return form
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Track significant changes
        changed_fields = form.changed_data
        if 'status' in changed_fields:
            self.log_status_change(form.instance.status)
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            f'Account "{form.instance.name}" updated successfully.'
        )
        
        return response
    
    def log_status_change(self, new_status):
        """Log account status change"""
        from ..models import ActivityType, Activity
        
        activity_type, _ = ActivityType.objects.get_or_create(
            tenant=self.request.tenant,
            name='Account Status Changed',
            defaults={
                'category': 'SALES',
                'created_by': self.request.user
            }
        )
        
        Activity.objects.create(
            tenant=self.request.tenant,
            activity_type=activity_type,
            subject=f'Account status changed to {new_status}',
            description=f'Account "{self.object.name}" status was changed to {new_status}',
            assigned_to=self.object.owner or self.request.user,
            start_datetime=timezone.now(),
            end_datetime=timezone.now(),
            status='COMPLETED',
            content_type=ContentType.objects.get_for_model(Account),
            object_id=str(self.object.id),
            created_by=self.request.user
        )
    
    def get_success_url(self):
        return reverse_lazy('crm:account-detail', kwargs={'pk': self.object.pk})


class AccountViewSet(CRMBaseViewSet):
    """Account API ViewSet with comprehensive functionality"""
    
    queryset = Account.objects.all()
    permission_classes = [AccountPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AccountFilter
    search_fields = ['name', 'legal_name', 'email', 'phone', 'description']
    ordering_fields = ['name', 'created_at', 'total_revenue', 'last_activity_date']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AccountDetailSerializer
        return AccountSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'industry', 'owner', 'territory', 'parent_account'
        ).prefetch_related(
            'contacts',
            'opportunities__stage',
            'activities'
        ).annotate(
            contacts_count=Count('contacts', filter=Q(contacts__is_active=True)),
            opportunities_count=Count('opportunities', filter=Q(opportunities__is_active=True)),
            activities_count=Count('activities', filter=Q(activities__is_active=True))
        )
        
        # Filter by user permissions
        user = self.request.user
        if not user.has_perm('crm.view_all_accounts'):
            queryset = queryset.filter(
                Q(owner=user) | Q(territory__assignments__user=user, territory__assignments__is_active=True)
            )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Get account contacts"""
        account = self.get_object()
        contacts = account.contacts.filter(is_active=True).order_by('is_primary', 'last_name')
        
        page = self.paginate_queryset(contacts)
        if page is not None:
            serializer = ContactSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ContactSerializer(contacts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def opportunities(self, request, pk=None):
        """Get account opportunities"""
        account = self.get_object()
        opportunities = account.opportunities.filter(
            is_active=True
        ).select_related('stage', 'owner', 'pipeline')
        
        # Filter by status if specified
        status_filter = request.query_params.get('status')
        if status_filter == 'open':
            opportunities = opportunities.filter(is_closed=False)
        elif status_filter == 'won':
            opportunities = opportunities.filter(is_won=True)
        elif status_filter == 'lost':
            opportunities = opportunities.filter(is_closed=True, is_won=False)
        
        page = self.paginate_queryset(opportunities)
        if page is not None:
            from ..serializers import OpportunitySerializer
            serializer = OpportunitySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import OpportunitySerializer
        serializer = OpportunitySerializer(opportunities, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get account activities"""
        account = self.get_object()
        activities = account.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            from ..serializers import ActivitySerializer
            serializer = ActivitySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import ActivitySerializer
        serializer = ActivitySerializer(activities, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def merge_accounts(self, request, pk=None):
        """Merge current account with another account"""
        primary_account = self.get_object()
        secondary_account_id = request.data.get('secondary_account_id')
        
        if not secondary_account_id:
            return Response(
                {'error': 'secondary_account_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            secondary_account = Account.objects.get(
                id=secondary_account_id,
                tenant=request.tenant
            )
        except Account.DoesNotExist:
            return Response(
                {'error': 'Secondary account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Perform merge
        with transaction.atomic():
            # Move contacts
            secondary_account.contacts.update(account=primary_account)
            
            # Move opportunities
            secondary_account.opportunities.update(account=primary_account)
            
            # Move activities
            secondary_account.activities.update(
                content_type=ContentType.objects.get_for_model(Account),
                object_id=str(primary_account.id)
            )
            
            # Update financial data
            primary_account.total_revenue += secondary_account.total_revenue
            primary_account.total_opportunities += secondary_account.total_opportunities
            primary_account.save()
            
            # Deactivate secondary account
            secondary_account.is_active = False
            secondary_account.save()
        
        return Response({
            'success': True,
            'message': f'Account {secondary_account.name} merged into {primary_account.name}',
            'primary_account_id': primary_account.id
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export accounts data"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get export format
        export_format = request.query_params.get('format', 'csv')
        
        if export_format == 'csv':
            return self.export_csv(queryset)
        elif export_format == 'excel':
            return self.export_excel(queryset)
        else:
            return Response(
                {'error': 'Unsupported export format'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def export_csv(self, queryset):
        """Export accounts as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="accounts_{timezone.now().date()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Account Type', 'Industry', 'Phone', 'Email', 'Owner',
            'Total Revenue', 'Status', 'Created Date'
        ])
        
        for account in queryset:
            writer.writerow([
                account.name,
                account.get_account_type_display(),
                account.industry.name if account.industry else '',
                account.phone,
                account.email,
                account.owner.get_full_name() if account.owner else '',
                account.total_revenue,
                account.get_status_display(),
                account.created_at.strftime('%Y-%m-%d')
            ])
        
        return response


# ============================================================================
# Contact Views
# ============================================================================

class ContactListView(CRMBaseMixin, ListView):
    """Enhanced contact listing"""
    
    model = Contact
    template_name = 'crm/contact/list.html'
    context_object_name = 'contacts'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Contact.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        ).select_related(
            'account__industry',
            'account__owner',
            'owner',
            'reports_to'
        ).annotate(
            activities_count=Count('activities', filter=Q(activities__is_active=True)),
            opportunities_count=Count('opportunities', filter=Q(opportunities__is_active=True))
        )
        
        # Apply filters
        contact_filter = ContactFilter(
            self.request.GET,
            queryset=queryset,
            tenant=self.request.tenant
        )
        
        return contact_filter.qs.order_by('account__name', 'last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter form
        context['filter'] = ContactFilter(
            self.request.GET,
            tenant=self.request.tenant
        )
        
        # Contact statistics
        queryset = self.get_queryset()
        context['stats'] = {
            'total_contacts': queryset.count(),
            'primary_contacts': queryset.filter(is_primary=True).count(),
            'decision_makers': queryset.filter(is_decision_maker=True).count(),
            'contacts_by_type': list(queryset.values('contact_type').annotate(
                count=Count('id')
            ).order_by('-count')),
        }
        
        return context


class ContactDetailView(CRMBaseMixin, DetailView):
    """Comprehensive contact detail view"""
    
    model = Contact
    template_name = 'crm/contact/detail.html'
    context_object_name = 'contact'
    
    def get_queryset(self):
        return Contact.objects.filter(
            tenant=self.request.tenant
        ).select_related(
            'account__industry',
            'account__owner',
            'owner',
            'reports_to'
        ).prefetch_related(
            'direct_reports',
            'opportunities',
            'activities__activity_type'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.get_object()
        
        # Direct reports
        context['direct_reports'] = contact.direct_reports.filter(
            is_active=True
        ).select_related('account')
        
        # Opportunities as primary contact
        context['opportunities'] = contact.opportunities.filter(
            is_active=True
        ).select_related('stage', 'owner').order_by('-created_at')[:10]
        
        # Recent activities
        context['recent_activities'] = contact.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')[:10]
        
        # Communication history
        context['communication_stats'] = self.get_communication_stats(contact)
        
        # Contact performance
        context['performance_metrics'] = self.get_contact_performance(contact)
        
        return context
    
    def get_communication_stats(self, contact):
        """Get communication statistics"""
        activities = contact.activities.filter(is_active=True)
        
        return {
            'total_communications': activities.count(),
            'emails_sent': activities.filter(activity_type__category='EMAIL').count(),
            'calls_made': activities.filter(activity_type__category='CALL').count(),
            'meetings_held': activities.filter(activity_type__category='MEETING').count(),
            'last_contact': activities.order_by('-created_at').first(),
            'communication_frequency': activities.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
        }
    
    def get_contact_performance(self, contact):
        """Calculate contact performance metrics"""
        opportunities = contact.opportunities.filter(is_active=True)
        
        return {
            'total_opportunities': opportunities.count(),
            'won_opportunities': opportunities.filter(is_won=True).count(),
            'total_influenced_revenue': opportunities.filter(is_won=True).aggregate(
                Sum('amount'))['amount__sum'] or 0,
            'average_opportunity_size': opportunities.aggregate(
                Avg('amount'))['amount__avg'] or 0,
            'conversion_rate': (opportunities.filter(is_won=True).count() / 
                             max(opportunities.count(), 1)) * 100,
        }


class ContactCreateView(CRMBaseMixin, PermissionRequiredMixin, CreateView):
    """Create new contact"""
    
    model = Contact
    template_name = 'crm/contact/form.html'
    permission_required = 'crm.add_contact'
    fields = [
        'account', 'salutation', 'first_name', 'last_name', 'middle_name',
        'email', 'secondary_email', 'phone', 'mobile', 'job_title',
        'department', 'reports_to', 'contact_type', 'is_primary',
        'is_decision_maker', 'preferred_contact_method', 'do_not_call',
        'do_not_email', 'linkedin_url', 'birthday', 'description', 'tags'
    ]
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filter accounts
        form.fields['account'].queryset = Account.objects.filter(
            tenant=self.request.tenant,
            is_active=True
        )
        
        # Pre-populate account if specified
        if 'account_id' in self.request.GET:
            try:
                account = Account.objects.get(
                    id=self.request.GET['account_id'],
                    tenant=self.request.tenant
                )
                form.initial['account'] = account
                
                # Filter reports_to by same account
                form.fields['reports_to'].queryset = Contact.objects.filter(
                    account=account,
                    is_active=True
                )
            except Account.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        form.instance.owner = form.instance.account.owner
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            f'Contact "{form.instance.full_name}" created successfully.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('crm:contact-detail', kwargs={'pk': self.object.pk})


class ContactViewSet(CRMBaseViewSet):
    """Contact API ViewSet"""
    
    queryset = Contact.objects.all()
    permission_classes = [ContactPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ContactFilter
    search_fields = ['first_name', 'last_name', 'email', 'job_title', 'company']
    ordering_fields = ['last_name', 'first_name', 'created_at', 'last_contact_date']
    ordering = ['last_name', 'first_name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ContactDetailSerializer
        return ContactSerializer
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'account', 'owner', 'reports_to'
        ).prefetch_related(
            'direct_reports',
            'opportunities',
            'activities'
        )
    
    @action(detail=True, methods=['get'])
    def opportunities(self, request, pk=None):
        """Get contact's opportunities"""
        contact = self.get_object()
        opportunities = contact.opportunities.filter(
            is_active=True
        ).select_related('stage', 'owner')
        
        page = self.paginate_queryset(opportunities)
        if page is not None:
            from ..serializers import OpportunitySerializer
            serializer = OpportunitySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import OpportunitySerializer
        serializer = OpportunitySerializer(opportunities, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get contact's activities"""
        contact = self.get_object()
        activities = contact.activities.filter(
            is_active=True
        ).select_related('activity_type', 'assigned_to').order_by('-created_at')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            from ..serializers import ActivitySerializer
            serializer = ActivitySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        from ..serializers import ActivitySerializer
        serializer = ActivitySerializer(activities, many=True, context={'request': request})
        return Response(serializer.data)


# ============================================================================
# Bulk Operations
# ============================================================================

class AccountBulkActionView(CRMBaseMixin, PermissionRequiredMixin, View):
    """Handle bulk actions on accounts"""
    
    permission_required = 'crm.change_account'
    
    def post(self, request):
        action = request.POST.get('action')
        account_ids = request.POST.getlist('account_ids')
        
        if not account_ids:
            return JsonResponse({
                'success': False,
                'message': 'No accounts selected'
            })
        
        try:
            with transaction.atomic():
                if action == 'bulk_update_owner':
                    return self.bulk_update_owner(account_ids, request)
                elif action == 'bulk_update_status':
                    return self.bulk_update_status(account_ids, request)
                elif action == 'bulk_add_tags':
                    return self.bulk_add_tags(account_ids, request)
                elif action == 'bulk_delete':
                    return self.bulk_delete(account_ids, request)
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
    
    def bulk_update_owner(self, account_ids, request):
        """Bulk update account owners"""
        new_owner_id = request.POST.get('new_owner_id')
        
        if not new_owner_id:
            return JsonResponse({
                'success': False,
                'message': 'New owner is required'
            })
        
        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid owner selected'
            })
        
        updated_count = Account.objects.filter(
            tenant=request.tenant,
            id__in=account_ids
        ).update(owner=new_owner, updated_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Updated owner for {updated_count} accounts'
        })
    
    def bulk_update_status(self, account_ids, request):
        """Bulk update account status"""
        new_status = request.POST.get('new_status')
        
        if not new_status:
            return JsonResponse({
                'success': False,
                'message': 'New status is required'
            })
        
        updated_count = Account.objects.filter(
            tenant=request.tenant,
            id__in=account_ids
        ).update(status=new_status, updated_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Updated status for {updated_count} accounts'
        })
    
    def bulk_add_tags(self, account_ids, request):
        """Bulk add tags to accounts"""
        tags_to_add = request.POST.get('tags', '').split(',')
        tags_to_add = [tag.strip() for tag in tags_to_add if tag.strip()]
        
        if not tags_to_add:
            return JsonResponse({
                'success': False,
                'message': 'No tags provided'
            })
        
        accounts = Account.objects.filter(
            tenant=request.tenant,
            id__in=account_ids
        )
        
        for account in accounts:
            current_tags = account.tags or []
            new_tags = list(set(current_tags + tags_to_add))
            account.tags = new_tags
            account.updated_by = request.user
            account.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Added tags to {accounts.count()} accounts'
        })
    
    def bulk_delete(self, account_ids, request):
        """Bulk soft delete accounts"""
        updated_count = Account.objects.filter(
            tenant=request.tenant,
            id__in=account_ids
        ).update(is_active=False, updated_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted {updated_count} accounts'
        })