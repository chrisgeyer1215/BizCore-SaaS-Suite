# ============================================================================
# backend/apps/crm/services/lead_service.py - Lead Management Service
# ============================================================================

from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .base import BaseService, CacheableMixin, NotificationMixin, CRMServiceException
from ..models import Lead, LeadSource, LeadScoringRule, Account, Contact, Opportunity


class LeadService(BaseService, CacheableMixin, NotificationMixin):
    """Comprehensive lead management service"""
    
    @transaction.atomic
    def create_lead(self, lea lead with validation and scoring"""
        self.require_permission('can_create_leads')
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email']
        self.validate_data(lead_data, required_fields)
        
        # Check for duplicates if enabled
        if self.tenant.crm_configuration.duplicate_lead_detection:
            existing_lead = self._check_duplicate_lead(lead_data['email'])
            if existing_lead:
                raise CRMServiceException(f"Duplicate lead found: {existing_lead.lead_number}")
        
        # Create lead
        lead_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
            'updated_by': self.user,
        })
        
        lead = Lead.objects.create(**lead_data)
        
        # Auto-assign if enabled
        if self.tenant.crm_configuration.lead_auto_assignment:
            self._auto_assign_lead(lead)
        
        # Calculate initial score
        if self.tenant.crm_configuration.lead_scoring_enabled:
            self.calculate_lead_score(lead)
        
        # Create audit trail
        self.create_audit_trail('CREATE', lead)
        
        # Send notifications
        if lead.owner:
            self.send_notification(
                [lead.owner],
                f"New Lead Assigned: {lead.full_name}",
                f"A new lead has been assigned to you: {lead.full_name} from {lead.company}"
            )
        
        self.logger.info(f"Lead created: {lead.lead_number}")
        return lead
    
    @transaction.atomic
    def update_lead(self, lead_id:
        """Update lead with change tracking"""
        lead = self.get_queryset(Lead).get(id=lead_id)
        
        if not self.check_permission('can_edit_all_leads') and lead.owner != self.user:
            raise PermissionDenied("Cannot edit leads not owned by you")
        
        # Track changes
        changes = {}
        for field, new_value in update_data.items():
            if hasattr(lead, field):
                old_value = getattr(lead, field)
                if old_value != new_value:
                    changes[field] = {'old': str(old_value), 'new': str(new_value)}
                    setattr(lead, field, new_value)
        
        lead.updated_by = self.user
        lead.save()
        
        # Recalculate score if relevant fields changed
        scoring_fields = ['company_size', 'industry', 'annual_revenue', 'job_title']
        if any(field in changes for field in scoring_fields):
            self.calculate_lead_score(lead)
        
        # Create audit trail
        self.create_audit_trail('UPDATE', lead, changes)
        
        return lead
    
    def calculate_lead_score(self, lead: Lead) -> int:
        """Calculate lead score based on scoring rules"""
        if not self.tenant.crm_configuration.lead_scoring_enabled:
            return lead.score
        
        scoring_rules = self.get_queryset(LeadScoringRule).filter(is_active=True)
        total_score = 0
        score_breakdown = {}
        
        for rule in scoring_rules:
            try:
                score_change = rule.apply_to_lead(lead)
                if score_change != 0:
                    total_score += score_change
                    score_breakdown[rule.name] = score_change
                    
                    # Update rule statistics
                    rule.times_applied += 1
                    rule.last_applied = timezone.now()
                    rule.save(update_fields=['times_applied', 'last_applied'])
                    
            except Exception as e:
                self.logger.error(f"Error applying scoring rule {rule.name}: {e}")
        
        # Ensure score is within valid range
        lead.score = max(0, min(100, total_score))
        lead.score_breakdown = score_breakdown
        lead.last_score_update = timezone.now()
        lead.save(update_fields=['score', 'score_breakdown', 'last_score_update'])
        
        # Check if lead meets qualification threshold
        threshold = self.tenant.crm_configuration.lead_scoring_threshold
        if lead.score >= threshold and lead.status == 'NEW':
            self._auto_qualify_lead(lead)
        
        return lead.score
    
    def convert_lead(self, lead_i:
        """Convert lead to account, contact, and optionally opportunity"""
        self.require_permission('can_convert_leads')
        
        lead = self.get_queryset(Lead).get(id=lead_id)
        
        if lead.status == 'CONVERTED':
            raise CRMServiceException("Lead is already converted")
        
        result = {}
        
        with transaction.atomic():
            # Create Account
            account_data = {
                'tenant': self.tenant,
                'name': lead.company or f"{lead.first_name} {lead.last_name}",
                'website': lead.website,
                'industry': lead.industry,
                'annual_revenue': lead.annual_revenue,
                'phone': lead.phone,
                'email': lead.email,
                'owner': lead.owner,
                'lead_source': conversion_data.get('lead_source', ''),
                'original_lead_id': lead.id,
                'created_by': self.user,
                'updated_by': self.user,
            }
            
            account = Account.objects.create(**account_data)
            result['account'] = account
            
            # Create Contact
            contact_data = {
                'tenant': self.tenant,
                'account': account,
                'salutation': lead.salutation,
                'first_name': lead.first_name,
                'last_name': lead.last_name,
                'email': lead.email,
                'phone': lead.phone,
                'mobile': lead.mobile,
                'job_title': lead.job_title,
                'is_primary': True,
                'owner': lead.owner,
                'created_by': self.user,
                'updated_by': self.user,
            }
            
            contact = Contact.objects.create(**contact_data)
            result['contact'] = contact
            
            # Create Opportunity if requested
            if conversion_data.get('create_opportunity'):
                from .opportunity_service import OpportunityService
                opportunity_service = OpportunityService(self.tenant, self.user)
                
                opportunity_data = {
                    'name': conversion_data.get('opportunity_name', f"{account.name} - Opportunity"),
                    'account': account,
                    'primary_contact': contact,
                    'amount': conversion_data.get('opportunity_amount', Decimal('0.00')),
                    'close_date': conversion_data.get('close_date'),
                    'pipeline': conversion_data.get('pipeline'),
                    'stage': conversion_data.get('stage'),
                    'owner': lead.owner,
                    'original_lead': lead,
                }
                
                opportunity = opportunity_service.create_opportunity(opportunity_data)
                result['opportunity'] = opportunity
                lead.converted_opportunity = opportunity
            
            # Update lead status
            lead.status = 'CONVERTED'
            lead.converted_account = account
            lead.converted_contact = contact
            lead.converted_date = timezone.now()
            lead.updated_by = self.user
            lead.save()
            
            # Update lead source statistics
            if lead.source:
                lead.source.converted_leads += 1
                if result.get('opportunity'):
                    lead.source.total_revenue += result['opportunity'].amount
                lead.source.save()
            
            # Update user metrics
            if lead.owner and hasattr(lead.owner, 'crm_profile'):
                profile = lead.owner.crm_profile
                profile.total_leads_converted += 1
                profile.save()
            
            # Create audit trail
            self.create_audit_trail('CONVERT', lead, {
                'converted_to_account': account.id,
                'converted_to_contact': contact.id,
            })
            
            # Send notification
            if lead.owner:
                self.send_notification(
                    [lead.owner],
                    f"Lead Converted: {lead.full_name}",
                    f"Lead {lead.full_name} has been converted to account: {account.name}"
                )
        
        self.logger.info(f"Lead converted: {lead.lead_number} -> Account: {account.name}")
        return result
    
    def bulk_assign_leads(self, lead_ids: List[int], assignee_id: int) -> Dict:
        """Bulk assign leads to a user"""
        self.require_permission('can_assign_leads')
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        assignee = User.objects.get(id=assignee_id)
        leads = self.get_queryset(Lead).filter(id__in=lead_ids)
        
        updated_count = 0
        
        with transaction.atomic():
            for lead in leads:
                if lead.owner != assignee:
                    old_owner = lead.owner
                    lead.owner = assignee
                    lead.assigned_date = timezone.now()
                    lead.updated_by = self.user
                    lead.save()
                    
                    updated_count += 1
                    
                    # Create audit trail
                    self.create_audit_trail('UPDATE', lead, {
                        'owner': {
                            'old': str(old_owner) if old_owner else None,
                            'new': str(assignee)
                        }
                    })
        
        # Send bulk notification
        if updated_count > 0:
            self.send_notification(
                [assignee],
                f"{updated_count} Leads Assigned",
                f"You have been assigned {updated_count} new leads."
            )
        
        return {
            'updated_count': updated_count,
            'total_requested': len(lead_ids),
            'assignee': assignee.get_full_name()
        }
    
    def get_lead_analytics(self, filters: Dict = None) -> Dict:
        """Get comprehensive lead analytics"""
        queryset = self.get_queryset(Lead)
        
        # Apply filters
        if filters:
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            if filters.get('owner'):
                queryset = queryset.filter(owner=filters['owner'])
            if filters.get('source'):
                queryset = queryset.filter(source=filters['source'])
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
        
        # Calculate metrics
        total_leads = queryset.count()
        converted_leads = queryset.filter(status='CONVERTED').count()
        qualified_leads = queryset.filter(status='QUALIFIED').count()
        
        # Conversion rate
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Lead sources breakdown
        source_breakdown = queryset.values('source__name').annotate(
            count=models.Count('id'),
            converted=models.Count('id', filter=models.Q(status='CONVERTED'))
        )
        
        # Score distribution
        score_ranges = {
            'cold': queryset.filter(score__lt=25).count(),
            'warm': queryset.filter(score__gte=25, score__lt=50).count(),
            'hot': queryset.filter(score__gte=50, score__lt=75).count(),
            'very_hot': queryset.filter(score__gte=75).count(),
        }
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(count=models.Count('id'))
        
        # Monthly trend
        monthly_trend = queryset.extra(
            select={'month': 'EXTRACT(month FROM created_at)'}
        ).values('month').annotate(count=models.Count('id'))
        
        return {
            'total_leads': total_leads,
            'converted_leads': converted_leads,
            'qualified_leads': qualified_leads,
            'conversion_rate': round(conversion_rate, 2),
            'source_breakdown': list(source_breakdown),
            'score_distribution': score_ranges,
            'status_breakdown': list(status_breakdown),
            'monthly_trend': list(monthly_trend),
        }
    
    def _check_duplicate_lead(self, email: str) -> Optional[Lead]:
        """Check for duplicate lead by email"""
        return self.get_queryset(Lead).filter(email=email).first()
    
    def _auto_assign_lead(self, lead: Lead):
        """Auto-assign lead based on configuration"""
        config = self.tenant.crm_configuration
        method = config.lead_assignment_method
        
        if method == 'ROUND_ROBIN':
            self._round_robin_assignment(lead)
        elif method == 'TERRITORY':
            self._territory_assignment(lead)
        elif method == 'SCORING':
            self._scoring_assignment(lead)
        elif method == 'WORKLOAD':
            self._workload_assignment(lead)
    
    def _round_robin_assignment(self, lead: Lead):
        """Round-robin lead assignment"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get sales reps
        sales_reps = User.objects.filter(
            crm_profile__profile_type='SALES_REP',
            crm_profile__tenant=self.tenant,
            is_active=True
        ).order_by('id')
        
        if not sales_reps:
            return
        
        # Simple round-robin based on lead count
        last_assigned = Lead.objects.filter(
            tenant=self.tenant,
            owner__isnull=False
        ).order_by('-assigned_date').first()
        
        if last_assigned and last_assigned.owner in sales_reps:
            current_index = list(sales_reps).index(last_assigned.owner)
            next_index = (current_index + 1) % len(sales_reps)
            assignee = sales_reps[next_index]
        else:
            assignee = sales_reps[0]
        
        lead.owner = assignee
        lead.assigned_date = timezone.now()
        lead.save()
    
    def _territory_assignment(self, lead: Lead):
        """Territory-based lead assignment"""
        # Implementation would check lead's address against territories
        pass
    
    def _auto_qualify_lead(self, lead: Lead):
        """Auto-qualify lead based on score threshold"""
        if lead.status == 'NEW':
            lead.status = 'QUALIFIED'
            lead.save()
            
            # Notify owner
            if lead.owner:
                self.send_notification(
                    [lead.owner],
                    f"Lead Auto-Qualified: {lead.full_name}",
                    f"Lead {lead.full_name} has been automatically qualified based on scoring criteria."
                )