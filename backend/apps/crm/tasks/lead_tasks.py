# ============================================================================
# backend/apps/crm/tasks/lead_tasks.py - Lead Management and Automation Tasks
# ============================================================================

from celery import group, chain
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta
import logging

from apps.core.celery import app
from .base import AuditableTask
from ..models import Lead, LeadScoringRule, LeadSource, Account, Territory, User
from ..services.lead_service import LeadService
from ..services.activity_service import ActivityService

logger = logging.getLogger(__name__)


@app.task(base=AuditableTask, bind=True)
def calculate_lead_scores(self, lead_ids: List[int] = None, security_context: Dict = None):
    """
    Calculate or recalculate lead scores using AI and business rules
    
    Args:
        lead_ids: Specific leads to score (all leads if None)
        security_context: Security context
    """
    try:
        # Initialize lead service
        lead_service = LeadService(
            tenant_id=security_context['tenant_id'],
            user_id=security_context['user_id']
        )
        
        # Get leads to score
        if lead_ids:
            leads = Lead.objects.filter(
                id__in=lead_ids,
                tenant_id=security_context['tenant_id'],
                is_active=True
            )
        else:
            # Score all leads that need scoring (new or updated)
            leads = Lead.objects.filter(
                tenant_id=security_context['tenant_id'],
                is_active=True
            ).filter(
                Q(score__isnull=True) |
                Q(last_scored_at__lt=timezone.now() - timedelta(hours=24))
            )
        
        scored_count = 0
        updated_count = 0
        errors = []
        
        # Get scoring rules for tenant
        scoring_rules = LeadScoringRule.objects.filter(
            tenant_id=security_context['tenant_id'],
            is_active=True
        ).order_by('priority')
        
        for lead in leads:
            try:
                # Calculate new score
                new_score = self._calculate_individual_lead_score(lead, scoring_rules)
                old_score = lead.score
                
                # Update lead score
                lead.score = new_score
                lead.last_scored_at = timezone.now()
                lead.scoring_history = lead.scoring_history or []
                lead.scoring_history.append({
                    'timestamp': timezone.now().isoformat(),
                    'old_score': old_score,
                    'new_score': new_score,
                    'score_change': new_score - (old_score or 0)
                })
                
                # Keep only last 10 scoring history entries
                lead.scoring_history = lead.scoring_history[-10:]
                lead.save(update_fields=['score', 'last_scored_at', 'scoring_history'])
                
                scored_count += 1
                
                # Check if score changed significantly
                if old_score and abs(new_score - old_score) >= 10:
                    updated_count += 1
                    
                    # Trigger follow-up actions for score changes
                    self._handle_score_change(lead, old_score, new_score, security_context)
                
            except Exception as e:
                logger.error(f"Failed to score lead {lead.id}: {e}")
                errors.append({
                    'lead_id': lead.id,
                    'error': str(e)
                })
        
        return {
            'total_leads_processed': scored_count,
            'leads_with_score_changes': updated_count,
            'errors_count': len(errors),
            'errors': errors[:10],  # Return first 10 errors
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Lead scoring batch failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_leads_processed': 0
        }
    
    def _calculate_individual_lead_score(self, lead: Lead, scoring_rules) -> int:
        """Calculate score for individual lead based on rules"""
        try:
            total_score = 0
            
            for rule in scoring_rules:
                rule_score = 0
                
                # Apply scoring rule based on type
                if rule.rule_type == 'DEMOGRAPHIC':
                    rule_score = self._apply_demographic_scoring(lead, rule)
                elif rule.rule_type == 'BEHAVIORAL':
                    rule_score = self._apply_behavioral_scoring(lead, rule)
                elif rule.rule_type == 'FIRMOGRAPHIC':
                    rule_score = self._apply_firmographic_scoring(lead, rule)
                elif rule.rule_type == 'ENGAGEMENT':
                    rule_score = self._apply_engagement_scoring(lead, rule)
                elif rule.rule_type == 'SOURCE':
                    rule_score = self._apply_source_scoring(lead, rule)
                
                # Apply rule weight
                weighted_score = rule_score * (rule.weight / 100.0)
                total_score += weighted_score
            
            # Ensure score is within bounds (0-100)
            return max(0, min(100, int(total_score)))
            
        except Exception as e:
            logger.error(f"Individual lead scoring failed: {e}")
            return lead.score or 0  # Return existing score on error
    
    def _apply_demographic_scoring(self, lead: Lead, rule: LeadScoringRule) -> int:
        """Apply demographic-based scoring rules"""
        score = 0
        criteria = rule.criteria
        
        # Job title scoring
        if 'job_titles' in criteria and lead.job_title:
            high_value_titles = criteria['job_titles'].get('high_value', [])
            medium_value_titles = criteria['job_titles'].get('medium_value', [])
            
            job_title_lower = lead.job_title.lower()
            
            if any(title.lower() in job_title_lower for title in high_value_titles):
                score += 25
            elif any(title.lower() in job_title_lower for title in medium_value_titles):
                score += 15
        
        # Company size scoring
        if 'company_size' in criteria and hasattr(lead, 'company_size'):
            size_scores = criteria['company_size']
            lead_size = getattr(lead, 'company_size', '')
            score += size_scores.get(lead_size, 0)
        
        return score
    
    def _apply_behavioral_scoring(self, lead: Lead, rule: LeadScoringRule) -> int:
        """Apply behavioral-based scoring rules"""
        score = 0
        criteria = rule.criteria
        
        # Website activity scoring
        if 'website_activity' in criteria:
            # Get lead's recent activities
            recent_activities = lead.activities.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            activity_score = min(recent_activities.count() * 5, 30)  # Max 30 points
            score += activity_score
        
        # Email engagement scoring
        if 'email_engagement' in criteria:
            # Check email open/click rates from email logs
            email_logs = lead.email_logs.filter(
                sent_at__gte=timezone.now() - timedelta(days=90)
            )
            
            if email_logs.exists():
                open_rate = email_logs.filter(opened_at__isnull=False).count() / email_logs.count()
                click_rate = email_logs.filter(clicked_at__isnull=False).count() / email_logs.count()
                
                score += int(open_rate * 20)  # Max 20 points for opens
                score += int(click_rate * 15)  # Max 15 points for clicks
        
        return score
    
    def _handle_score_change(self, lead: Lead, old_score: int, new_score: int, security_context: Dict):
        """Handle significant lead score changes with automated actions"""
        try:
            score_change = new_score - old_score
            
            # Hot lead threshold (score >= 80)
            if new_score >= 80 and (not old_score or old_score < 80):
                # Lead became hot - trigger immediate follow-up
                self._trigger_hot_lead_workflow(lead, security_context)
            
            # Cold lead threshold (score <= 30)
            elif new_score <= 30 and (not old_score or old_score > 30):
                # Lead became cold - add to nurturing campaign
                self._trigger_nurturing_workflow(lead, security_context)
            
            # Significant improvement (score increased by 20+)
            elif score_change >= 20:
                # Score improved significantly - schedule follow-up
                self._schedule_follow_up_activity(lead, 'Score improved significantly', security_context)
                
        except Exception as e:
            logger.error(f"Score change handling failed for lead {lead.id}: {e}")


@app.task(base=AuditableTask, bind=True)
def auto_assign_leads(self, assignment_criteria: Dict, security_context: Dict):
    """
    Automatically assign leads to sales representatives based on criteria
    
    Args:
        assignment_criteria: Criteria for assignment (territory, score, source, etc.)
        security_context: Security context
    """
    try:
        tenant_id = security_context['tenant_id']
        
        # Get unassigned leads matching criteria
        leads_query = Lead.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            assigned_to__isnull=True
        )
        
        # Apply criteria filters
        if 'min_score' in assignment_criteria:
            leads_query = leads_query.filter(score__gte=assignment_criteria['min_score'])
        
        if 'max_age_days' in assignment_criteria:
            cutoff_date = timezone.now() - timedelta(days=assignment_criteria['max_age_days'])
            leads_query = leads_query.filter(created_at__gte=cutoff_date)
        
        if 'sources' in assignment_criteria:
            leads_query = leads_query.filter(source__name__in=assignment_criteria['sources'])
        
        unassigned_leads = leads_query.order_by('-score', '-created_at')
        
        assignment_results = {
            'total_leads': unassigned_leads.count(),
            'assigned_count': 0,
            'failed_count': 0,
            'assignments': []
        }
        
        # Get available sales reps
        available_reps = self._get_available_sales_reps(tenant_id, assignment_criteria)
        
        if not available_reps:
            return {
                **assignment_results,
                'error': 'No available sales representatives found'
            }
        
        # Assign leads using round-robin or workload-based algorithm
        assignment_method = assignment_criteria.get('method', 'round_robin')
        
        for lead in unassigned_leads[:100]:  # Process max 100 leads per task
            try:
                assigned_rep = self._select_rep_for_assignment(
                    lead, available_reps, assignment_method
                )
                
                if assigned_rep:
                    # Assign lead
                    lead.assigned_to = assigned_rep
                    lead.assigned_at = timezone.now()
                    lead.assignment_method = assignment_method
                    lead.save(update_fields=['assigned_to', 'assigned_at', 'assignment_method'])
                    
                    assignment_results['assigned_count'] += 1
                    assignment_results['assignments'].append({
                        'lead_id': lead.id,
                        'lead_name': lead.full_name,
                        'assigned_to_id': assigned_rep.id,
                        'assigned_to_name': assigned_rep.get_full_name(),
                        'score': lead.score
                    })
                    
                    # Update rep workload tracking
                    self._update_rep_workload(assigned_rep, 1)
                    
                    # Create follow-up activity
                    self._create_assignment_activity(lead, assigned_rep, security_context)
                    
                else:
                    assignment_results['failed_count'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to assign lead {lead.id}: {e}")
                assignment_results['failed_count'] += 1
        
        return {
            **assignment_results,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Auto lead assignment failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'assigned_count': 0
        }
    
    def _get_available_sales_reps(self, tenant_id: int, criteria: Dict) -> List[User]:
        """Get available sales representatives for assignment"""
        try:
            # Get users with sales roles
            from apps.auth.models import Membership
            
            sales_memberships = Membership.objects.filter(
                tenant_id=tenant_id,
                is_active=True,
                role__in=['SALES_REP', 'SALES_MANAGER']
            ).select_related('user')
            
            available_reps = []
            
            for membership in sales_memberships:
                user = membership.user
                
                # Check if user is active and available
                if not user.is_active:
                    continue
                
                # Check workload limits
                current_leads = Lead.objects.filter(
                    assigned_to=user,
                    tenant_id=tenant_id,
                    status__in=['NEW', 'CONTACTED', 'QUALIFIED']
                ).count()
                
                max_leads = getattr(user, 'max_lead_capacity', 50)  # Default 50 leads
                
                if current_leads >= max_leads:
                    continue
                
                # Check territory restrictions if specified
                if 'territory_id' in criteria:
                    user_territories = getattr(user, 'territories', [])
                    if criteria['territory_id'] not in [t.id for t in user_territories]:
                        continue
                
                available_reps.append(user)
            
            return available_reps
            
        except Exception as e:
            logger.error(f"Getting available reps failed: {e}")
            return []
    
    def _select_rep_for_assignment(self, lead: Lead, available_reps: List[User], 
                                 method: str) -> Optional[User]:
        """Select sales rep for lead assignment based on method"""
        try:
            if not available_reps:
                return None
            
            if method == 'round_robin':
                # Simple round-robin based on last assignment
                # This would be more sophisticated in production
                return available_reps[lead.id % len(available_reps)]
            
            elif method == 'workload_based':
                # Assign to rep with lowest current workload
                rep_workloads = []
                
                for rep in available_reps:
                    current_leads = Lead.objects.filter(
                        assigned_to=rep,
                        tenant_id=self.tenant_id,
                        status__in=['NEW', 'CONTACTED', 'QUALIFIED']
                    ).count()
                    
                    rep_workloads.append((rep, current_leads))
                
                # Sort by workload and return rep with lowest
                rep_workloads.sort(key=lambda x: x[1])
                return rep_workloads[0][0]
            
            elif method == 'score_based':
                # Assign high-score leads to senior reps
                if lead.score >= 80:
                    # High score - assign to manager if available
                    managers = [rep for rep in available_reps if 'MANAGER' in rep.role]
                    if managers:
                        return managers[0]
                
                # Default to round-robin
                return available_reps[lead.id % len(available_reps)]
            
            else:
                # Default to first available rep
                return available_reps[0]
                
        except Exception as e:
            logger.error(f"Rep selection failed: {e}")
            return available_reps[0] if available_reps else None


@app.task(base=AuditableTask, bind=True)
def process_lead_import(self, import_config: Dict, 
                       security_context: Dict):
    """
    Process bulk lead import with validation, deduplication, and scoring
    
    Args:
         dictionaries
        import_config: Import configuration (validation rules, field mapping, etc.)
        security_context: Security context
    """
    try:
        tenant_id = security_context['tenant_id']
        user_id = security_context['user_id']
        
        # Initialize lead service
        lead_service = LeadService(tenant_id=tenant_id, user_id=user_id)
        
        import_results = {
            'total_records': len(import_data),
            'successful_imports': 0,
            'duplicates_found': 0,
            'validation_failures': 0,
            'errors': []
        }
        
        # Process each lead record
        for i, lead_data in enumerate(import_data):
            try:
                # Validate lead data
                validation_result = self._validate_lead_data(lead_data, import_config)
                
                if not validation_result['valid']:
                    import_results['validation_failures'] += 1
                    import_results['errors'].append({
                        'row': i + 1,
                        'type': 'validation_error',
                        'errors': validation_result['errors']
                    })
                    continue
                
                # Check for duplicates
                duplicate_check = self._check_lead_duplicate(lead_data, tenant_id)
                
                if duplicate_check['is_duplicate']:
                    import_results['duplicates_found'] += 1
                    
                    # Handle duplicate based on config
                    if import_config.get('duplicate_handling') == 'skip':
                        continue
                    elif import_config.get('duplicate_handling') == 'update':
                        # Update existing lead
                        existing_lead = duplicate_check['existing_lead']
                        self._update_existing_lead(existing_lead, lead_data)
                        import_results['successful_imports'] += 1
                        continue
                
                # Create new lead
                normalized_data = self._normalize_lead_data(lead_data, import_config)
                lead = lead_service.create_lead(normalized_data)
                
                if lead:
                    import_results['successful_imports'] += 1
                    
                    # Schedule scoring for new lead
                    calculate_lead_scores.delay([lead.id], security_context)
                else:
                    import_results['errors'].append({
                        'row': i + 1,
                        'type': 'creation_failed',
                        'data': lead_data
                    })
                
            except Exception as e:
                logger.error(f"Failed to import lead at row {i + 1}: {e}")
                import_results['errors'].append({
                    'row': i + 1,
                    'type': 'exception',
                    'error': str(e)
                })
        
        # Trigger post-import processing
        if import_results['successful_imports'] > 0:
            self._trigger_post_import_processing(import_results, security_context)
        
        return {
            **import_results,
            'import_completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Lead import processing failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_records': len(import_data),
            'successful_imports': 0
        }
    
    def _: Dict) -> Dict:
        """Validate individual lead data record"""
        try:
            errors = []
            
            # Required field validation
            required_fields = config.get('required_fields', ['email', 'first_name'])
            
            for field in required_fields:
                if not lead_data.get(field):
                    errors.append(f"Required field '{field}' is missing or empty")
            
            # Email = lead_data['email']
                if email and not self._is_valid_email(email):
                    errors.append(f"Invalid email format: {email}")
            
            # Phone validation
            if 'phone' = lead_data['phone']
                if phone and not self._is_valid_phone(phone):
                    errors.append(f"Invalid phone format: {phone}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"]
            }
    
    def _check_lead_ -> Dict:
        """Check for duplicate leads"""
        try:
            email = lead_data.get('email')
            phone = lead_data.get('phone')
            
            # Check by email first
            if email:
                existing_lead = Lead.objects.filter(
                    email__iexact=email,
                    tenant_id=tenant_id
                ).first()
                
                if existing_lead:
                    return {
                        'is_duplicate': True,
                        'existing_lead': existing_lead,
                        'match_type': 'email'
                    }
            
            # Check by phone
            if phone:
                existing_lead = Lead.objects.filter(
                    phone=phone,
                    tenant_id=tenant_id
                ).first()
                
                if existing_lead:
                    return {
                        'is_duplicate': True,
                        'existing_lead': existing_lead,
                        'match_type': 'phone'
                    }
            
            # Check by name and company combination
            first_name = lead_data.get('first_name')
            last_name = lead_data.get('last_name')
            company = lead_data.get('company')
            
            if first_name and last_name and company:
                existing_lead = Lead.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    company__iexact=company,
                    tenant_id=tenant_id
                ).first()
                
                if existing_lead:
                    return {
                        'is_duplicate': True,
                        'existing_lead': existing_lead,
                        'match_type': 'name_company'
                    }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return {'is_duplicate': False}


# Lead nurturing and automation tasks
@app.task(base=AuditableTask, bind=True)
def lead_nurturing_sequence(self, lead_id: int, sequence_type: str, 
                           security_context: Dict):
    """
    Execute automated lead nurturing sequence
    
    Args:
        lead_id: Lead ID
        sequence_type: Type of nurturing sequence
        security_context: Security context
    """
    try:
        # Get lead
        lead = Lead.objects.get(id=lead_id, tenant_id=security_context['tenant_id'])
        
        # Define nurturing sequences
        sequences = {
            'new_lead': [
                {'delay_hours': 0, 'action': 'welcome_email'},
                {'delay_hours': 24, 'action': 'follow_up_call'},
                {'delay_hours': 72, 'action': 'resource_email'},
                {'delay_hours': 168, 'action': 'check_in_email'}  # 1 week
            ],
            'cold_lead': [
                {'delay_hours': 0, 'action': 'reengagement_email'},
                {'delay_hours': 168, 'action': 'value_proposition_email'},
                {'delay_hours': 336, 'action': 'case_study_email'},  # 2 weeks
                {'delay_hours': 504, 'action': 'final_attempt_email'}  # 3 weeks
            ]
        }
        
        sequence = sequences.get(sequence_type, sequences['new_lead'])
        scheduled_actions = []
        
        for step in sequence:
            # Schedule each action
            if step['delay_hours'] > 0:
                eta = timezone.now() + timedelta(hours=step['delay_hours'])
                task = execute_nurturing_action.apply_async(
                    args=[lead_id, step['action'], security_context],
                    eta=eta
                )
            else:
                task = execute_nurturing_action.delay(
                    lead_id, step['action'], security_context
                )
            
            scheduled_actions.append({
                'action': step['action'],
                'delay_hours': step['delay_hours'],
                'task_id': task.id,
                'scheduled_for': eta.isoformat() if step['delay_hours'] > 0 else 'immediate'
            })
        
        # Update lead with nurturing info
        lead.nurturing_sequence = sequence_type
        lead.nurturing_started_at = timezone.now()
        lead.save(update_fields=['nurturing_sequence', 'nurturing_started_at'])
        
        return {
            'lead_id': lead_id,
            'sequence_type': sequence_type,
            'actions_scheduled': len(scheduled_actions),
            'scheduled_actions': scheduled_actions,
            'started_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Lead nurturing sequence failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'lead_id': lead_id,
            'sequence_type': sequence_type
        }


@app.task(base=AuditableTask, bind=True)
def execute_nurturing_action(self, lead_id: int, action: str, security_context: Dict):
    """
    Execute individual nurturing action
    
    Args:
        lead_id: Lead ID
        action: Action to execute
        security_context: Security context
    """
    try:
        lead = Lead.objects.get(id=lead_id, tenant_id=security_context['tenant_id'])
        
        action_results = {
            'lead_id': lead_id,
            'action': action,
            'executed_at': timezone.now().isoformat(),
            'success': False
        }
        
        if action == 'welcome_email':
            # Send welcome email
            result = self._send_nurturing_email(lead, 'welcome', security_context)
            action_results.update(result)
            
        elif action == 'follow_up_call':
            # Schedule follow-up call activity
            result = self._schedule_follow_up_call(lead, security_context)
            action_results.update(result)
            
        elif action == 'resource_email':
            # Send resource/educational email
            result = self._send_nurturing_email(lead, 'resource', security_context)
            action_results.update(result)
            
        elif action == 'reengagement_email':
            # Send re-engagement email
            result = self._send_nurturing_email(lead, 'reengagement', security_context)
            action_results.update(result)
            
        else:
            action_results['error'] = f'Unknown action: {action}'
        
        return action_results
        
    except Exception as e:
        logger.error(f"Nurturing action execution failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'lead_id': lead_id,
            'action': action,
            'success': False
        }


# Duplicate detection and cleanup
@app.task(base=AuditableTask, bind=True)
def duplicate_lead_detection(self, security_context: Dict):
    """
    Detect and flag duplicate leads across the tenant
    
    Args:
        security_context: Security context
    """
    try:
        tenant_id = security_context['tenant_id']
        
        # Find potential duplicates by email
        email_duplicates = Lead.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            email__isnull=False
        ).values('email').annotate(
            count=Count('id'),
            lead_ids=ArrayAgg('id')
        ).filter(count__gt=1)
        
        # Find potential duplicates by phone
        phone_duplicates = Lead.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            phone__isnull=False
        ).values('phone').annotate(
            count=Count('id'),
            lead_ids=ArrayAgg('id')
        ).filter(count__gt=1)
        
        duplicate_results = {
            'email_duplicate_groups': len(email_duplicates),
            'phone_duplicate_groups': len(phone_duplicates),
            'total_duplicate_leads': 0,
            'duplicate_groups': []
        }
        
        # Process email duplicates
        for dup_group in email_duplicates:
            group_info = {
                'match_type': 'email',
                'match_value': dup_group['email'],
                'lead_count': dup_group['count'],
                'lead_ids': dup_group['lead_ids'],
                'recommended_action': 'merge'
            }
            
            duplicate_results['duplicate_groups'].append(group_info)
            duplicate_results['total_duplicate_leads'] += dup_group['count']
        
        # Process phone duplicates (avoid double counting)
        for dup_group in phone_duplicates:
            # Check if these leads were already flagged by email
            existing_group = any(
                set(dup_group['lead_ids']).intersection(set(g['lead_ids']))
                for g in duplicate_results['duplicate_groups']
            )
            
            if not existing_group:
                group_info = {
                    'match_type': 'phone',
                    'match_value': dup_group['phone'],
                    'lead_count': dup_group['count'],
                    'lead_ids': dup_group['lead_ids'],
                    'recommended_action': 'merge'
                }
                
                duplicate_results['duplicate_groups'].append(group_info)
                duplicate_results['total_duplicate_leads'] += dup_group['count']
        
        return {
            **duplicate_results,
            'detection_completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Duplicate detection failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_duplicate_leads': 0
        }