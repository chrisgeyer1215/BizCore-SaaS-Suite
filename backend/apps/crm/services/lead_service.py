# ============================================================================
# backend/apps/crm/services/lead_service.py - Advanced Lead Management Service
# ============================================================================

from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max, Min
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Dict, List, Optional, Tuple, Union
import json
import statistics
import re
from datetime import timedelta
from collections import defaultdict
import numpy as np
from sklearn.preprocessing import StandardScaler
import pickle

from .base import BaseService, ServiceException, ServiceContext
from ..models import Lead, LeadSource, LeadScoringRule, Opportunity, Account, Contact


class LeadIntelligenceEngine:
    """Advanced AI engine for lead intelligence and predictions"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._model_cache = {}
        
    def predict_conversion_probability(self, lead_data: Dict) -> float:
        """Predict lead conversion probability using ML model"""
        try:
            # Feature extraction
            features = self._extract_features(lead_data)
            
            # Load or train model
            model = self._get_conversion_model()
            
            # Predict probability
            probability = model.predict_proba([features])[0][1]  # Probability of conversion
            
            return min(1.0, max(0.0, probability))
            
        except Exception as e:
            # Fallback to rule-based scoring
            return self._fallback_conversion_score(lead_data) / 100
    
    def _extract_features) -> List[float]:
        """Extract numerical features for ML model"""
        features = []
        
        # Basic score
        features.append(lead_data.get('score', 0) / 100)
        
        # Industry encoding (simplified)
        industry_scores = {
            'technology': 0.8, 'healthcare': 0.7, 'finance': 0.9,
            'education': 0.5, 'retail': 0.4, 'manufacturing': 0.6
        }
        industry = (lead_data.get('industry', '') or '').lower()
        features.append(industry_scores.get(industry, 0.3))
        
        # Company size factor
        company_size_scores = {
            'STARTUP': 0.3, 'SMALL': 0.4, 'MEDIUM': 0.7, 'LARGE': 0.8, 'ENTERPRISE': 0.9
        }
        company_size = lead_data.get('company_size', 'SMALL')
        features.append(company_size_scores.get(company_size, 0.4))
        
        # Source quality
        source_quality = {
            'WEBSITE': 0.6, 'REFERRAL': 0.8, 'SOCIAL_MEDIA': 0.4,
            'EMAIL_CAMPAIGN': 0.5, 'WEBINAR': 0.7, 'TRADE_SHOW': 0.8
        }
        source = lead_data.get('source', 'WEBSITE')
        features.append(source_quality.get(source, 0.5))
        
        # Engagement factors
        features.append(min(1.0, lead_data.get('email_opens', 0) / 10))
        features.append(min(1.0, lead_data.get('website_visits', 0) / 5))
        features.append(min(1.0, lead_data.get('content_downloads', 0) / 3))
        
        return features
    
    def _get_conversion_model(self):
        """Get or train conversion prediction model"""
        cache_key = f'conversion_model_{self.tenant_id}'
        
        if cache_key not in self._model_cache:
            # In production, load pre-trained model or train new one
            # For now, using mock model
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            
            # Mock training data (in production, use historical data)
            X_mock = np.random.rand(1000, 7)
            y_mock = np.random.choice([0, 1], 1000, p=[0.7, 0.3])
            model.fit(X_mock, y_mock)
            
            self._model_cache[cache_key] = model
        
        return self._model_cache[cache_key]
    
    def _fallback_conversion_score(self float:
        """Fallback scoring when ML model is unavailable"""
        score = 50  # Base score
        
        if lead_data.get('score', 0) > 70:
            score += 30
        elif lead_data.get('score', 0) > 40:
            score += 15
        
        if lead_data.get('industry') in ['technology', 'finance', 'healthcare']:
            score += 20
        
        return min(100, score)
    
    def analyze_lead_journey(self, lead_id: int) -> Dict:
        """Analyze lead journey and engagement patterns"""
        from ..models import Activity
        
        try:
            lead = Lead.objects.get(id=lead_id)
            activities = Activity.objects.filter(
                related_to_model='lead',
                related_to_id=lead_id
            ).order_by('created_at')
            
            journey_analysis = {
                'total_touchpoints': activities.count(),
                'engagement_timeline': [],
                'engagement_score': 0,
                'journey_stage': 'UNKNOWN',
                'next_best_action': 'CONTACT',
                'velocity_score': 0
            }
            
            # Analyze engagement timeline
            for activity in activities:
                journey_analysis['engagement_timeline'].append({
                    'date': activity.created_at.isoformat(),
                    'type': activity.activity_type.name,
                    'subject': activity.subject,
                    'outcome': activity.outcome or 'PENDING'
                })
            
            # Calculate engagement metrics
            if activities.exists():
                # Recency factor
                latest_activity = activities.last()
                days_since_last = (timezone.now() - latest_activity.created_at).days
                recency_score = max(0, 100 - days_since_last * 2)
                
                # Frequency factor
                frequency_score = min(100, activities.count() * 10)
                
                # Engagement score
                journey_analysis['engagement_score'] = (recency_score + frequency_score) / 2
                
                # Journey stage determination
                recent_activities = activities.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                )
                
                if recent_activities.filter(activity_type__name__icontains='DEMO').exists():
                    journey_analysis['journey_stage'] = 'EVALUATION'
                    journey_analysis['next_best_action'] = 'PROPOSAL'
                elif recent_activities.filter(activity_type__name__icontains='CALL').exists():
                    journey_analysis['journey_stage'] = 'QUALIFICATION'
                    journey_analysis['next_best_action'] = 'DEMO'
                elif recent_activities.exists():
                    journey_analysis['journey_stage'] = 'ENGAGEMENT'
                    journey_analysis['next_best_action'] = 'QUALIFICATION_CALL'
                else:
                    journey_analysis['journey_stage'] = 'AWARENESS'
                    journey_analysis['next_best_action'] = 'INITIAL_CONTACT'
            
            return journey_analysis
            
        except Exception as e:
            return {'error': str(e)}


class LeadService(BaseService):
    """Advanced lead management service with AI-powered insights"""
    
    def __init__(self, tenant=None, user=None, context: ServiceContext = None):
        super().__init__(tenant, user, context)
        self.intelligence_engine = LeadIntelligenceEngine(tenant.id if tenant else 0)
        self._scoring_cache_timeout = 1800  # 30 minutes
        
    def create_intelligent_lead(self, lea: Dict = None,
                              auto_enrich: bool = True, auto_score: bool = True) -> Lead:
        """Create lead with intelligent enrichment and scoring"""
        operation_start = time.time()
        
        try:
            with transaction.atomic():
                # Data validation and sanitization
                is_valid, validation_errors = self.validate_data_integrity(lead_data, self._get_lead_schema())
                if not is_valid:
                    raise ServiceException(
                        f"Lead data validation failed: {', '.join(validation_errors)}",
                        code='INVALID_LEAD_DATA',
                        details={'validation_errors': validation_errors}
                    )
                
                # Duplicate detection with fuzzy matching
                potential_duplicate = self._find_intelligent_duplicate(lead_data)
                if potential_duplicate:
                    return self._handle_duplicate_lead(potential_duplicate, lead_data)
                
                # Data enrichment
                if auto_enrich:
                    enriched_data = self.enrich_lead_data(lead_data)
                    lead_data.update(enriched_data)
                
                # Create lead
                lead = Lead.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **lead_data
                )
                
                # AI-powered scoring
                if auto_score:
                    score = self.calculate_intelligent_lead_score(lead)
                    lead.score = score
                    lead.save(update_fields=['score'])
                
                # Source attribution tracking
                if source_attribution:
                    self._track_source_attribution(lead, source_attribution)
                
                # Auto-assignment with intelligent routing
                assigned_user = self.intelligent_lead_assignment(lead)
                if assigned_user:
                    lead.owner = assigned_user
                    lead.save(update_fields=['owner'])
                
                # Initialize lead tracking
                self._initialize_lead_tracking(lead)
                
                # Create initial activity suggestions
                self._create_activity_suggestions(lead)
                
                # Update lead source performance metrics
                self._update_source_metrics(lead)
                
                operation_duration = time.time() - operation_start
                self.metrics.track_operation('create_intelligent_lead', operation_duration)
                
                self.log_activity('CREATE_INTELLIGENT_LEAD', 'Lead', lead.id, {
                    'lead_name': lead.full_name,
                    'initial_score': lead.score,
                    'auto_assigned': assigned_user is not None,
                    'enrichment_applied': auto_enrich,
                    'source': lead.source.name if lead.source else None,
                    'operation_duration': operation_duration
                })
                
                return lead
                
        except Exception as e:
            if isinstance(e, ServiceException):
                raise
            raise ServiceException(f"Failed to create intelligent lead: {str(e)}")
    
    def _get_lead_schema(self) -> Dict:
        """Get lead validation schema"""
        return {
            'first_name': {'required': True, 'min_length': 1},
            'last_name': {'required': True, 'min_length': 1},
            'email': {'required': True, 'validator': self.validator.validate_email},
            'phone': {'validator': self.validator.validate_phone},
            'company': {'min_length': 2}
        }
    
    def enrich_lead_data(self,:
        """Enrich lead data using external APIs and internal intelligence"""
        enriched_data = {}
        
        try:
            # Company enrichment
            if 'company' in lead_data and lead_data['company']:
                company_data = self._enrich_company_data(lead_data['company'])
                enriched_data.update(company_data)
            
            # Email domain analysis
            if 'email' in lead_data and lead_data['email']:
                domain_data = self._analyze_email_domain(lead_data['email'])
                enriched_data.update(domain_data)
            
            # Geographic enrichment
            if any(field in lead_data for field in ['city', 'state', 'country']):
                geo_data = self._enrich_geographic_data(lead_data)
                enriched_data.update(geo_data)
            
            # Social media enrichment
            social_data = self._enrich_social_data(lead_data)
            enriched_data.update(social_data)
            
        except Exception as e:
            logger.warning(f"Lead data enrichment failed: {e}")
        
        return enriched_data
    
    def _enrich_company_data(self, company_name: str) -> Dict:
        """Enrich company data using business intelligence"""
        enriched = {}
        
        try:
            # Check internal database first
            existing_accounts = Account.objects.filter(
                name__icontains=company_name,
                tenant=self.tenant
            ).first()
            
            if existing_accounts:
                enriched.update({
                    'industry': existing_accounts.industry.name if existing_accounts.industry else None,
                    'annual_revenue': existing_accounts.annual_revenue,
                    'number_of_employees': existing_accounts.number_of_employees,
                    'website': existing_accounts.website
                })
            
            # External API enrichment (mock implementation)
            # In production, integrate with Clearbit, ZoomInfo, etc.
            external_data = self._fetch_external_company_data(company_name)
            enriched.update(external_data)
            
        except Exception as e:
            logger.warning(f"Company enrichment failed for {company_name}: {e}")
        
        return enriched
    
    def _fetch_external_company_data(self, company_name: str) -> Dict:
        """Fetch company data from external APIs"""
        # Mock implementation - replace with real API calls
        mock_data = {
            'company_size': 'MEDIUM',
            'industry': 'Technology',
            'employee_count_estimate': 250
        }
        
        # Add some variation based on company name
        if 'corp' in company_name.lower() or 'inc' in company_name.lower():
            mock_data['company_size'] = 'LARGE'
        
        return mock_data
    
    def _analyze_email_domain(self, email: str) -> Dict:
        """Analyze email domain for business intelligence"""
        try:
            domain = email.split('@')[1].lower()
            
            # Free email providers
            free_providers = {
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
                'aol.com', 'icloud.com', 'protonmail.com'
            }
            
            analysis = {
                'email_domain': domain,
                'is_business_email': domain not in free_providers,
                'domain_authority_estimate': 50  # Mock score
            }
            
            # Business email bonus
            if analysis['is_business_email']:
                analysis['email_quality_score'] = 80
            else:
                analysis['email_quality_score'] = 40
            
            return analysis
            
        except Exception:
            return {'email_quality_score': 30}
    
    def calculate_intelligent_lead_score(self, lead: Lead) -> int:
        """Calculate lead score using AI and rule-based engines"""
        cache_key = f"lead_score_{lead.id}"
        
        def compute_score():
            # Start with base score
            score = 0
            scoring_factors = []
            
            # AI-based conversion probability
            lead_data = {
                'score': getattr(lead, 'score', 0),
                'industry': getattr(lead, 'industry', ''),
                'company_size': getattr(lead, 'company_size', 'SMALL'),
                'source': getattr(lead.source, 'name', 'UNKNOWN') if lead.source else 'UNKNOWN',
                'email_opens': 0,  # Would come from email tracking
                'website_visits': 0,  # Would come from web analytics
                'content_downloads': 0  # Would come from content management
            }
            
            ai_probability = self.intelligence_engine.predict_conversion_probability(lead_data)
            ai_score = int(ai_probability * 100)
            score += ai_score * 0.4  # 40% weight for AI prediction
            scoring_factors.append(f"AI Prediction: {ai_score} (weight: 40%)")
            
            # Rule-based scoring
            rule_score = self._calculate_rule_based_score(lead)
            score += rule_score * 0.3  # 30% weight for rules
            scoring_factors.append(f"Rules Engine: {rule_score} (weight: 30%)")
            
            # Behavioral scoring
            behavioral_score = self._calculate_behavioral_score(lead)
            score += behavioral_score * 0.2  # 20% weight for behavior
            scoring_factors.append(f"Behavioral: {behavioral_score} (weight: 20%)")
            
            # Demographic scoring
            demographic_score = self._calculate_demographic_score(lead)
            score += demographic_score * 0.1  # 10% weight for demographics
            scoring_factors.append(f"Demographic: {demographic_score} (weight: 10%)")
            
            # Normalize to 0-100 scale
            final_score = max(0, min(100, int(score)))
            
            # Store scoring breakdown
            self.cache.set(f"scoring_factors_{lead.id}", scoring_factors, 3600)
            
            return final_score
        
        return self.get_cached_or_compute(cache_key, compute_score, self._scoring_cache_timeout)
    
    def _calculate_rule_based_score(self, lead: Lead) -> int:
        """Calculate score based on configured rules"""
        try:
            score = 0
            
            # Get active scoring rules
            rules = LeadScoringRule.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).order_by('priority')
            
            for rule in rules:
                try:
                    conditions = json.loads(rule.conditions) if rule.conditions else []
                    
                    if self._evaluate_scoring_conditions(lead, conditions):
                        score += rule.points
                        
                except Exception as e:
                    logger.warning(f"Error evaluating scoring rule {rule.id}: {e}")
                    continue
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.warning(f"Rule-based scoring failed: {e}")
            return 50  # Default score
    
    def _calculate_behavioral_score(self, lead: Lead) -> int:
        """Calculate behavioral engagement score"""
        score = 0
        
        try:
            # Recent activity engagement
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_activities = lead.activities.filter(
                created_at__gte=thirty_days_ago
            )
            
            activity_score = min(30, recent_activities.count() * 5)
            score += activity_score
            
            # Email engagement (if tracked)
            email_score = getattr(lead, 'email_engagement_score', 0)
            score += min(25, email_score)
            
            # Website engagement (if tracked)
            website_score = getattr(lead, 'website_engagement_score', 0)
            score += min(25, website_score)
            
            # Content engagement
            content_score = getattr(lead, 'content_engagement_score', 0)
            score += min(20, content_score)
            
        except Exception as e:
            logger.warning(f"Behavioral scoring failed: {e}")
        
        return score
    
    def _calculate_demographic_score(self, lead: Lead) -> int:
        """Calculate demographic fit score"""
        score = 0
        
        try:
            # Industry alignment
            if lead.industry:
                high_value_industries = self._get_high_value_industries()
                if lead.industry in high_value_industries:
                    score += 30
                else:
                    score += 10
            
            # Company size factor
            if lead.company_size:
                size_scores = {
                    'STARTUP': 10, 'SMALL': 15, 'MEDIUM': 25, 
                    'LARGE': 35, 'ENTERPRISE': 40
                }
                score += size_scores.get(lead.company_size, 15)
            
            # Geographic factor
            if lead.country:
                primary_markets = self._get_primary_markets()
                if lead.country in primary_markets:
                    score += 20
                else:
                    score += 5
            
            # Job title relevance
            if lead.job_title:
                decision_maker_score = self._calculate_decision_maker_score(lead.job_title)
                score += decision_maker_score
            
        except Exception as e:
            logger.warning(f"Demographic scoring failed: {e}")
        
        return score
    
    def intelligent_lead_assignment(self, lead: Lead) -> Optional['User']:
        """Intelligent lead assignment using AI and optimization"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get assignment configuration
            assignment_config = self._get_assignment_config()
            
            if not assignment_config.get('auto_assignment_enabled', True):
                return None
            
            # Get eligible assignees
            eligible_users = self._get_eligible_assignees()
            
            if not eligible_users:
                return None
            
            # Calculate assignment scores for each user
            assignment_scores = {}
            
            for user in eligible_users:
                score = self._calculate_assignment_score(user, lead)
                assignment_scores[user] = score
            
            # Select best assignee
            best_assignee = max(assignment_scores.items(), key=lambda x: x[1])
            
            if best_assignee[1] > assignment_config.get('minimum_assignment_score', 50):
                return best_assignee[0]
            
            return None
            
        except Exception as e:
            logger.warning(f"Intelligent assignment failed: {e}")
            return None
    
    def _calculate_assignment_score(self, user, lead: Lead) -> float:
        """Calculate assignment score for user-lead pair"""
        score = 100  # Base score
        
        try:
            # Workload factor
            current_leads = user.owned_leads.filter(
                status__in=['NEW', 'CONTACTED', 'QUALIFIED'],
                tenant=self.tenant
            ).count()
            
            max_leads = getattr(user.crm_profile, 'max_leads', 50) if hasattr(user, 'crm_profile') else 50
            workload_factor = 1 - (current_leads / max_leads)
            score *= max(0.1, workload_factor)
            
            # Expertise matching
            expertise_score = self._calculate_expertise_match(user, lead)
            score += expertise_score * 0.3
            
            # Historical performance
            performance_score = self._get_user_performance_score(user)
            score *= (performance_score / 100)
            
            # Availability factor
            availability_score = self._calculate_availability_score(user)
            score *= availability_score
            
            # Geographic/territory alignment
            territory_score = self._calculate_territory_alignment(user, lead)
            score += territory_score * 0.2
            
        except Exception as e:
            logger.warning(f"Assignment score calculation failed: {e}")
            return 50
        
        return score
    
    def convert_lead_with_intelligence(self, lead: Lead,_enrich_opportunity: bool = True) -> Opportunity:
        """Convert lead to opportunity with intelligent data transfer"""
        self.validate_tenant_access(lead)
        self.validate_user_permission('crm.add_opportunity')
        
        if lead.converted_opportunity:
            raise ServiceException(
                "Lead already converted",
                code='ALREADY_CONVERTED',
                details={'existing_opportunity_id': lead.converted_opportunity.id}
            )
        
        try:
            with transaction.atomic():
                # Intelligent account creation/matching
                account = self._create_or_match_account_intelligently(lead)
                
                # Enhance opportunity data with AI insights
                if auto_enrich_opportunity:
                    enhanced_data = self._enhance_opportunity_data(lead, opportunity_data)
                    opportunity_data.update(enhanced_data)
                
                # Create opportunity
                opportunity = Opportunity.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    account=account,
                    source_lead=lead,
                    owner=lead.owner or self.user,
                    **opportunity_data
                )
                
                # Transfer lead intelligence to opportunity
                self._transfer_lead_intelligence(lead, opportunity)
                
                # Update lead status
                lead.converted_opportunity = opportunity
                lead.status = 'CONVERTED'
                lead.converted_date = timezone.now()
                lead.save()
                
                # Create conversion activity
                self._create_conversion_activity(lead, opportunity)
                
                # Update lead source conversion metrics
                self._update_source_conversion_metrics(lead)
                
                self.log_activity('CONVERT_LEAD_INTELLIGENT', 'Lead', lead.id, {
                    'opportunity_id': opportunity.id,
                    'opportunity_name': opportunity.name,
                    'opportunity_amount': opportunity.amount,
                    'account_created': account.created_at == timezone.now().date(),
                    'conversion_score': lead.score
                })
                
                return opportunity
                
        except Exception as e:
            if isinstance(e, ServiceException):
                raise
            raise ServiceException(f"Failed to convert lead intelligently: {str(e)}")
    
    def _create_or_match_account_intelligently(self, lead: Lead) -> Account:
        """Create or intelligently match account for lead conversion"""
        from ..models import Account, Contact
        
        # Try intelligent account matching
        matched_account = self._find_matching_account(lead)
        
        if matched_account:
            # Update account with lead data if needed
            self._update_account_from_lead(matched_account, lead)
            return matched_account
        
        # Create new account with intelligent data mapping
        account_data = self._extract_account_data_from_lead(lead)
        
        account = Account.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            **account_data
        )
        
        # Create primary contact from lead
        contact = Contact.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            account=account,
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            job_title=lead.job_title,
            is_primary=True
        )
        
        return account
    
    def analyze_lead_performance_comprehensive(self, date_from=None, date_to=None,
                                             include_predictions: bool = True) -> Dict:
        """Comprehensive lead performance analysis with AI insights"""
        queryset = Lead.objects.filter(tenant=self.tenant)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        analysis = {
            'overview_metrics': self._get_overview_metrics(queryset),
            'conversion_analysis': self._analyze_conversion_patterns(queryset),
            'source_performance': self._analyze_source_performance(queryset),
            'scoring_effectiveness': self._analyze_scoring_effectiveness(queryset),
            'geographic_distribution': self._analyze_geographic_distribution(queryset),
            'industry_analysis': self._analyze_industry_performance(queryset),
            'velocity_metrics': self._calculate_velocity_metrics(queryset),
            'quality_metrics': self._analyze_lead_quality(queryset)
        }
        
        if include_predictions:
            analysis['predictions'] = {
                'volume_forecast': self._forecast_lead_volume(),
                'conversion_predictions': self._predict_future_conversions(queryset),
                'quality_trends': self._predict_quality_trends(queryset),
                'source_recommendations': self._recommend_source_optimization()
            }
        
        return analysis
    
    def _analyze_conversion_patterns(self, queryset) -> Dict:
        """Analyze lead conversion patterns and trends"""
        converted_leads = queryset.filter(converted_opportunity__isnull=False)
        
        analysis = {
            'total_conversions': converted_leads.count(),
            'conversion_rate': (converted_leads.count() / queryset.count() * 100) if queryset.count() > 0 else 0,
            'avg_conversion_time': self._calculate_avg_conversion_time(converted_leads),
            'conversion_by_score': self._analyze_conversion_by_score(queryset),
            'conversion_velocity': self._calculate_conversion_velocity(converted_leads),
            'seasonal_patterns': self._analyze_seasonal_conversion_patterns(converted_leads)
        }
        
        return analysis
    
    def _predict_future_conversions(self, queryset) -> Dict:
        """Predict future conversions using AI"""
        try:
            current_leads = queryset.filter(
                status__in=['NEW', 'CONTACTED', 'QUALIFIED'],
                converted_opportunity__isnull=True
            )
            
            predictions = []
            total_predicted_value = 0
            
            for lead in current_leads:
                lead_data = {
                    'score': lead.score or 0,
                    'industry': lead.industry or '',
                    'company_size': lead.company_size or 'SMALL',
                    'source': lead.source.name if lead.source else 'UNKNOWN'
                }
                
                conversion_prob = self.intelligence_engine.predict_conversion_probability(lead_data)
                predicted_value = self._estimate_lead_value(lead)
                
                predictions.append({
                    'lead_id': lead.id,
                    'lead_name': lead.full_name,
                    'conversion_probability': round(conversion_prob * 100, 1),
                    'predicted_value': predicted_value,
                    'expected_value': predicted_value * conversion_prob,
                    'recommended_action': self._recommend_lead_action(lead, conversion_prob)
                })
                
                total_predicted_value += predicted_value * conversion_prob
            
            # Sort by expected value
            predictions.sort(key=lambda x: x['expected_value'], reverse=True)
            
            return {
                'total_leads_analyzed': len(predictions),
                'total_expected_value': round(total_predicted_value, 2),
                'high_probability_leads': [p for p in predictions if p['conversion_probability'] > 70],
                'predictions': predictions[:50]  # Top 50 predictions
            }
            
        except Exception as e:
            logger.warning(f"Conversion prediction failed: {e}")
            return {'error': str(e)}
    
    def bulk_lead_intelligence_update(self, lead_ids: List[int]) -> Dict:
        """Bulk update lead intelligence scores and insights"""
        results = {
            'updated_leads': 0,
            'errors': [],
            'score_changes': [],
            'assignment_changes': []
        }
        
        try:
            leads = Lead.objects.filter(
                id__in=lead_ids,
                tenant=self.tenant
            )
            
            with transaction.atomic():
                for lead in leads:
                    try:
                        # Store old score for comparison
                        old_score = lead.score or 0
                        
                        # Recalculate score
                        new_score = self.calculate_intelligent_lead_score(lead)
                        
                        # Update score if changed significantly
                        if abs(new_score - old_score) >= 5:
                            lead.score = new_score
                            lead.save(update_fields=['score'])
                            
                            results['score_changes'].append({
                                'lead_id': lead.id,
                                'old_score': old_score,
                                'new_score': new_score,
                                'change': new_score - old_score
                            })
                        
                        # Check for reassignment opportunities
                        if not lead.owner or new_score > old_score + 20:
                            new_assignee = self.intelligent_lead_assignment(lead)
                            if new_assignee and new_assignee != lead.owner:
                                old_owner = lead.owner
                                lead.owner = new_assignee
                                lead.save(update_fields=['owner'])
                                
                                results['assignment_changes'].append({
                                    'lead_id': lead.id,
                                    'old_owner': old_owner.get_full_name() if old_owner else None,
                                    'new_owner': new_assignee.get_full_name(),
                                    'reason': 'Score improvement' if new_score > old_score else 'Unassigned'
                                })
                        
                        results['updated_leads'] += 1
                        
                    except Exception as e:
                        results['errors'].append({
                            'lead_id': lead.id,
                            'error': str(e)
                        })
            
        except Exception as e:
            raise ServiceException(f"Bulk intelligence update failed: {str(e)}")
        
        return results
    
    # Helper methods
    def _get_high_value_industries(self) -> List[str]:
        """Get list of high-value industries based on historical data"""
        # This would analyze conversion rates and deal sizes by industry
        return ['Technology', 'Healthcare', 'Finance', 'Manufacturing']
    
    def _get_primary_markets(self) -> List[str]:
        """Get primary target markets"""
        return ['United States', 'Canada', 'United Kingdom', 'Australia']
    
    def _estimate_lead_value(self, lead: Lead) -> float:
        """Estimate potential value of lead"""
        base_value = 5000  # Default deal size
        
        # Industry multipliers
        industry_multipliers = {
            'Technology': 1.5,
            'Healthcare': 1.3,
            'Finance': 1.4,
            'Manufacturing': 1.2
        }
        
        multiplier = industry_multipliers.get(lead.industry, 1.0)
        
        # Company size multipliers
        size_multipliers = {
            'STARTUP': 0.5,
            'SMALL': 0.8,
            'MEDIUM': 1.2,
            'LARGE': 1.8,
            'ENTERPRISE': 2.5
        }
        
        size_multiplier = size_multipliers.get(lead.company_size, 1.0)
        
        return base_value * multiplier * size_multiplier
    
    def _recommend_lead_action(self, lead: Lead, conversion_prob: float) -> str:
        """Recommend next best action for lead"""
        if conversion_prob > 0.8:
            return "SCHEDULE_DEMO"
        elif conversion_prob > 0.6:
            return "QUALIFICATION_CALL"
        elif conversion_prob > 0.4:
            return "NURTURE_SEQUENCE"
        else:
            return "EDUCATIONAL_CONTENT"