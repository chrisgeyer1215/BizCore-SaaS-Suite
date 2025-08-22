# ============================================================================
# backend/apps/crm/services/account_service.py - Advanced Account Management Service
# ============================================================================

from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Max, Min, Exists, OuterRef
from django.utils import timezone
from typing import Dict, List, Optional, Tuple, Union
import json
import statistics
import numpy as np
from datetime import timedelta
from collections import defaultdict
from dataclasses import dataclass
import difflib

from .base import BaseService, ServiceException, ServiceContext
from ..models import Account, Contact, Industry, Opportunity, Activity, Ticket


@dataclass
class AccountHealthMetrics:
    """Data class for account health metrics"""
    health_score: int
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    churn_probability: float
    engagement_score: int
    satisfaction_score: int
    growth_potential: str
    key_indicators: List[str]
    recommendations: List[str]


class AccountIntelligenceEngine:
    """Advanced AI engine for account intelligence and insights"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._model_cache = {}
    
    def calculate_churn_probability(self, account_Predict account churn probability using ML model"""
        try:
            # Feature extraction
            features = self._extract_churn_features(account_data)
            
            # Load or train churn prediction model
            model = self._get_churn_model()
            
            # Predict churn probability
            probability = model.predict_proba([features])[0][1]
            
            return min(1.0, max(0.0, probability))
            
        except Exception as e:
            # Fallback to rule-based assessment
            return self._fallback_churn_assessment(account_data)
    
    def _extract_churn_features( -> List[float]:
        """Extract features for churn prediction model"""
        features = []
        
        # Engagement metrics
        features.append(account_data.get('days_since_last_activity', 0) / 30)  # Normalized
        features.append(min(1.0, account_data.get('activities_last_30_days', 0) / 10))
        features.append(min(1.0, account_data.get('opportunities_last_90_days', 0) / 5))
        
        # Support metrics
        features.append(min(1.0, account_data.get('open_tickets', 0) / 5))
        features.append(account_data.get('avg_ticket_resolution_days', 0) / 10)
        features.append(account_data.get('escalated_tickets', 0) / 3)
        
        # Revenue metrics
        features.append(min(1.0, account_data.get('revenue_trend', 0)))  # -1 to 1 scale
        features.append(min(1.0, account_data.get('payment_delays', 0) / 30))
        
        # Relationship metrics
        features.append(account_data.get('contact_turnover', 0) / 5)
        features.append(1 if account_data.get('has_champion', False) else 0)
        features.append(account_data.get('relationship_depth', 1) / 10)
        
        return features
    
    def _get_churn_model(self):
        """Get or train churn prediction model"""
        cache_key = f'churn_model_{self.tenant_id}'
        
        if cache_key not in self._model_cache:
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(n_estimators=100, random_state=42)
            
            # Mock training (in production, use historical churn data)
            X_mock = np.random.rand(1000, 11)  # 11 features
            y_mock = np.random.choice([0, 1], 1000, p=[0.85, 0.15])  # 15% churn rate
            model.fit(X_mock, y_mock)
            
            self._model_cache[cache_key] = model
        
        return self._model_cache[cache_key]
    
    def analyze_expansion"""Analyze account expansion opportunities"""
        expansion_score = 0
        opportunities = []
        
        # Revenue growth potential
        if account_data.get('revenue_growth_rate', 0) > 0.1:
            expansion_score += 25
            opportunities.append({
                'type': 'UPSELL',
                'confidence': 0.8,
                'potential_value': account_data.get('current_arr', 0) * 0.3,
                'reason': 'Strong revenue growth indicates expansion potential'
            })
        
        # Usage patterns
        if account_data.get('feature_adoption_rate', 0) > 0.8:
            expansion_score += 20
            opportunities.append({
                'type': 'CROSS_SELL',
                'confidence': 0.7,
                'potential_value': 15000,
                'reason': 'High feature adoption suggests readiness for additional products'
            })
        
        # Support engagement
        if account_data.get('support_satisfaction', 0) > 4.5:
            expansion_score += 15
        
        return {
            'expansion_score': min(100, expansion_score),
            'opportunities': opportunities,
            'recommended_approach': self._get_expansion_approach(expansion_score),
            'optimal_timing': self._calculate_optimal_expansion_timing(account_data)
        }
    
    def predict) -> str:
        """Predict account lifecycle stage"""
        age_days = account_data.get('account_age_days', 0)
        revenue = account_data.get('annual_revenue', 0)
        engagement = account_data.get('engagement_score', 50)
        
        if age_days < 90:
            if engagement > 70:
                return 'ONBOARDING_SUCCESSFUL'
            else:
                return 'ONBOARDING_AT_RISK'
        elif age_days < 365:
            if revenue > 0 and engagement > 60:
                return 'GROWTH'
            else:
                return 'STABILIZATION'
        else:
            if engagement > 70 and revenue > 0:
                return 'MATURE_ADVOCATE'
            elif engagement < 40:
                return 'AT_RISK'
            else:
                return 'MATURE_STABLE'


class AccountService(BaseService):
    """Advanced account management service with AI-powered insights"""
    
    def __init__(self, tenant=None, user=None, context: ServiceContext = None):
        super().__init__(tenant, user, context)
        self.intelligence_engine = AccountIntelligenceEngine(tenant.id if tenant else 0)
        self._health_cache_timeout = 1800  # 30 minutes
        
    def create_intelligent_account(self, account_data = None,
                                 auto_enrich: bool = True, initialize_health: bool = True) -> Account:
        """Create account with intelligent enrichment and health scoring"""
        try:
            with transaction.atomic():
                # Data validation
                is_valid, validation_errors = self.validate_data_integrity(
                    account_data, self._get_account_schema()
                )
                if not is_valid:
                    raise ServiceException(
                        f"Account validation failed: {', '.join(validation_errors)}",
                        code='INVALID_ACCOUNT_DATA',
                        details={'validation_errors': validation_errors}
                    )
                
                # Duplicate detection with fuzzy matching
                potential_duplicate = self._find_intelligent_duplicate(account_data)
                if potential_duplicate and potential_duplicate['confidence'] > 0.8:
                    return self._handle_duplicate_account(potential_duplicate, account_data)
                
                # Data enrichment
                if auto_enrich:
                    enriched_data = self.enrich_account_data(account_data)
                    account_data.update(enriched_data)
                
                # Create account
                account = Account.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    **account_data
                )
                
                    self._create_intelligent_contacts(account, contacts_data)
                
                # Initialize health scoring
                if initialize_health:
                    health_metrics = self.calculate_comprehensive_health_score(account)
                    account.health_score = health_metrics.health_score
                    account.save(update_fields=['health_score'])
                
                # Set up account tracking and monitoring
                self._initialize_account_monitoring(account)
                
                # Create initial engagement opportunities
                self._create_engagement_opportunities(account)
                
                self.log_activity('CREATE_INTELLIGENT_ACCOUNT', 'Account', account.id, {
                    'account_name': account.name,
                    'initial_health_score': account.health_score,
                    'contacts_created': len(contacts_data) if contacts_data else 0,
                    'enrichment_applied': auto_enrich,
                    'industry': account.industry.name if account.industry else None
                })
                
                return account
                
        except Exception as e:
            if isinstance(e, ServiceException):
                raise
            raise ServiceException(f"Failed to create intelligent account: {str(e)}")
    
    def _get_account_schema(self) -> Dict:
        """Get account validation schema"""
        return {
            'name': {'required': True, 'min_length': 2},
            'website': {'validator': self._validate_url},
            'phone': {'validator': self.validator.validate_phone},
            'annual_revenue': {'validator': lambda x: x >= 0 if x is not None else True}
        }
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format"""
        if not url:
            return True
        import re
        pattern = r'^https?://.+'
        return bool(re.match(pattern, url))
    
    def enrich_account_data(self, account using multiple intelligence sources"""
        enriched_data = {}
        
        try:
            # Company intelligence enrichment
            company_intel = self._enrich_company_intelligence(account_data.get('name', ''))
            enriched_data.update(company_intel)
            
            # Industry classification
            if not account_data.get('industry') and account_data.get('name'):
                industry = self._classify_industry_intelligently(account_data['name'])
                if industry:
                    enriched_data['industry'] = industry
            
            # Geographic enrichment
            geo_data = self._enrich_geographic_intelligence(account_data)
            enriched_data.update(geo_data)
            
            # Financial intelligence
            financial_data = self._enrich_financial_intelligence(account_data)
            enriched_data.update(financial_data)
            
            # Technology stack analysis (if website provided)
            if account_data.get('website'):
                tech_data = self._analyze_technology_stack(account_data['website'])
                enriched_data.update(tech_data)
            
        except Exception as e:
            logger.warning(f"Account enrichment failed: {e}")
        
        return enriched_data
    
    def _enrich_company_intelligence(self, company_name: str) -> Dict:
        """Enrich company data with business intelligence"""
        enriched = {}
        
        try:
            # Check existing accounts for similar companies
            similar_accounts = Account.objects.filter(
                name__icontains=company_name[:10],
                tenant=self.tenant
            ).exclude(name__exact=company_name)
            
            if similar_accounts.exists():
                # Aggregate intelligence from similar companies
                similar_data = similar_accounts.aggregate(
                    avg_revenue=Avg('annual_revenue'),
                    avg_employees=Avg('number_of_employees'),
                    common_industry=Max('industry__name')
                )
                
                enriched.update({
                    'estimated_revenue_range': self._estimate_revenue_range(similar_data['avg_revenue']),
                    'estimated_employee_range': self._estimate_employee_range(similar_data['avg_employees']),
                    'likely_industry': similar_data['common_industry']
                })
            
            # External API enrichment (mock - replace with real APIs)
            external_data = self._fetch_external_company_intelligence(company_name)
            enriched.update(external_data)
            
        except Exception as e:
            logger.warning(f"Company intelligence enrichment failed: {e}")
        
        return enriched
    
    def calculate_comprehensive_health_score(self, account: Account) -> AccountHealthMetrics:
        """Calculate comprehensive account health with detailed insights"""
        cache_key = f"account_health_{account.id}"
        
        def compute_health():
            # Gather account data for analysis
            account_data = self._gather_account_intelligence_data(account)
            
            # Calculate individual health components
            engagement_score = self._calculate_engagement_health(account_data)
            financial_health = self._calculate_financial_health(account_data)
            relationship_health = self._calculate_relationship_health(account_data)
            support_health = self._calculate_support_health(account_data)
            growth_indicators = self._calculate_growth_indicators(account_data)
            
            # Weighted composite score
            composite_score = (
                engagement_score * 0.25 +
                financial_health * 0.25 +
                relationship_health * 0.20 +
                support_health * 0.15 +
                growth_indicators * 0.15
            )
            
            # Determine risk level
            if composite_score >= 80:
                risk_level = 'LOW'
            elif composite_score >= 60:
                risk_level = 'MEDIUM'
            elif composite_score >= 40:
                risk_level = 'HIGH'
            else:
                risk_level = 'CRITICAL'
            
            # Calculate churn probability
            churn_prob = self.intelligence_engine.calculate_churn_probability(account_data)
            
            # Generate key indicators and recommendations
            key_indicators = self._identify_key_health_indicators(account_data, composite_score)
            recommendations = self._generate_health_recommendations(account_data, composite_score, risk_level)
            
            # Determine growth potential
            expansion_analysis = self.intelligence_engine.analyze_expansion_opportunities(account_data)
            growth_potential = self._categorize_growth_potential(expansion_analysis['expansion_score'])
            
            return AccountHealthMetrics(
                health_score=int(composite_score),
                risk_level=risk_level,
                churn_probability=churn_prob,
                engagement_score=int(engagement_score),
                satisfaction_score=int(support_health),
                growth_potential=growth_potential,
                key_indicators=key_indicators,
                recommendations=recommendations
            )
        
        return self.get_cached_or_compute(cache_key, compute_health, self._health_cache_timeout)
    
    def _gather_account_intelligence_data(self, account: Account) -> Dict:
        """Gather comprehensive data for account intelligence analysis"""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        
        # Activity metrics
        recent_activities = account.activities.filter(created_at__gte=thirty_days_ago)
        days_since_last_activity = (
            (now - account.activities.order_by('-created_at').first().created_at).days
            if account.activities.exists() else 999
        )
        
        # Opportunity metrics
        recent_opportunities = account.opportunities.filter(created_at__gte=ninety_days_ago)
        pipeline_value = account.opportunities.filter(is_closed=False).aggregate(
            Sum('amount')
        )['amount__sum'] or 0
        
        # Support metrics
        open_tickets = account.tickets.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
        recent_tickets = account.tickets.filter(created_at__gte=thirty_days_ago)
        avg_resolution_time = account.tickets.filter(
            status='RESOLVED',
            resolved_date__isnull=False
        ).aggregate(
            avg_time=Avg(F('resolved_date') - F('created_at'))
        )['avg_time']
        
        # Financial metrics
        total_revenue = account.opportunities.filter(is_won=True).aggregate(
            Sum('amount')
        )['amount__sum'] or 0
        
        # Relationship metrics
        active_contacts = account.contacts.filter(is_active=True).count()
        primary_contacts = account.contacts.filter(is_primary=True, is_active=True).count()
        
        return {
            'account_age_days': (now.date() - account.created_at.date()).days,
            'activities_last_30_days': recent_activities.count(),
            'days_since_last_activity': days_since_last_activity,
            'opportunities_last_90_days': recent_opportunities.count(),
            'pipeline_value': pipeline_value,
            'total_revenue': total_revenue,
            'open_tickets': open_tickets,
            'tickets_last_30_days': recent_tickets.count(),
            'avg_ticket_resolution_days': avg_resolution_time.days if avg_resolution_time else 0,
            'escalated_tickets': recent_tickets.filter(escalated=True).count(),
            'active_contacts': active_contacts,
            'primary_contacts': primary_contacts,
            'annual_revenue': account.annual_revenue or 0,
            'has_champion': primary_contacts > 0,
            'relationship_depth': active_contacts,
            'engagement_score': getattr(account, 'engagement_score', 50),
            'current_arr': total_revenue,
            'revenue_growth_rate': self._calculate_revenue_growth_rate(account),
            'feature_adoption_rate': 0.7,  # Mock - would come from product analytics
            'support_satisfaction': 4.2,  # Mock - would come from satisfaction surveys
            'contact_turnover': self._calculate_contact_turnover(account),
            'payment_delays': 0  # Mock - would come from billing system
        }
    
    def float:
        """Calculate engagement health score"""
        score = 100
        
        # Activity recency penalty
        days_since_activity = account_data.get('days_since_last_activity', 999)
        if days_since_activity > 30:
            score -= min(50, days_since_activity - 30)
        
        # Activity frequency bonus
        recent_activities = account_data.get('activities_last_30_days', 0)
        score += min(20, recent_activities * 2)
        
        # Pipeline engagement
        pipeline_value = account_data.get('pipeline_value', 0)
        if pipeline_value > 0:
            score += min(20, pipeline_value / 10000)
        
        return max(0, min(100, score))
    
    def _calculate_financial_health(self, account
        """Calculate financial health score"""
        score = 50  # Base score
        
        # Revenue factor
        total_revenue = account_data.get('total_revenue', 0)
        if total_revenue > 0:
            score += min(30, total_revenue / 10000)
        
        # Growth rate factor
        growth_rate = account_data.get('revenue_growth_rate', 0)
        if growth_rate > 0:
            score += min(20, growth_rate * 100)
        elif growth_rate < -0.1:
            score -= 20
        
        # Payment behavior (mock)
        payment_delays = account_data.get('payment_delays', 0)
        score -= min(25, payment_delays)
        
        return max(0, min(100, score))
    
    def intelligent_account_merger(self, primary_account_id: int, 
                                 duplicate_account_ids: List[int],
                                 merge_strategy: str = 'COMPREHENSIVE') -> Dict:
        """Intelligent account merger with data preservation and conflict resolution"""
        try:
            with transaction.atomic():
                primary_account = Account.objects.get(id=primary_account_id, tenant=self.tenant)
                duplicate_accounts = Account.objects.filter(
                    id__in=duplicate_account_ids,
                    tenant=self.tenant
                )
                
                merge_results = {
                    'primary_account_id': primary_account_id,
                    'merged_accounts': [],
                    'data_conflicts': [],
                    'merged_data': {},
                    'moved_records': {
                        'contacts': 0,
                        'opportunities': 0,
                        'activities': 0,
                        'tickets': 0,
                        'documents': 0
                    },
                    'data_quality_improvements': []
                }
                
                for duplicate in duplicate_accounts:
                    account_merge_result = self._merge_single_account(
                        primary_account, duplicate, merge_strategy
                    )
                    
                    merge_results['merged_accounts'].append({
                        'account_id': duplicate.id,
                        'account_name': duplicate.name,
                        'merge_result': account_merge_result
                    })
                    
                    # Aggregate results
                    for key, value in account_merge_result['moved_records'].items():
                        merge_results['moved_records'][key] += value
                    
                    merge_results['data_conflicts'].extend(account_merge_result['data_conflicts'])
                    merge_results['data_quality_improvements'].extend(
                        account_merge_result['data_quality_improvements']
                    )
                
                # Recalculate health score for merged account
                health_metrics = self.calculate_comprehensive_health_score(primary_account)
                primary_account.health_score = health_metrics.health_score
                primary_account.save(update_fields=['health_score'])
                
                # Clear caches
                self.cache.delete(f"account_health_{primary_account.id}")
                
                self.log_activity('INTELLIGENT_ACCOUNT_MERGE', 'Account', primary_account.id, {
                    'merged_account_count': len(duplicate_accounts),
                    'merge_strategy': merge_strategy,
                    'total_records_moved': sum(merge_results['moved_records'].values()),
                    'conflicts_detected': len(merge_results['data_conflicts'])
                })
                
                return merge_results
                
        except Exception as e:
            raise ServiceException(f"Intelligent account merger failed: {str(e)}")
    
    def _merge_single_account(self, primary: Account, duplicate: Account, strategy: str) -> Dict:
        """Merge single duplicate account into primary account"""
        merge_result = {
            'moved_records': defaultdict(int),
            'data_conflicts': [],
            'data_quality_improvements': []
        }
        
        # Intelligent data merging with conflict detection
        field_conflicts = self._detect_data_conflicts(primary, duplicate)
        if field_conflicts:
            merge_result['data_conflicts'] = field_conflicts
            
            # Resolve conflicts based on strategy
            resolved_data = self._resolve_data_conflicts(primary, duplicate, field_conflicts, strategy)
            
            # Update primary account with resolved data
            for field, value in resolved_data.items():
                if hasattr(primary, field):
                    old_value = getattr(primary, field)
                    setattr(primary, field, value)
                    
                    merge_result['data_quality_improvements'].append({
                        'field': field,
                        'old_value': str(old_value),
                        'new_value': str(value),
                        'improvement_type': 'DATA_ENRICHMENT'
                    })
            
            primary.save()
        
        # Move related records
        self._move_related_records(primary, duplicate, merge_result)
        
        # Deactivate duplicate account
        duplicate.is_active = False
        duplicate.merged_into_account = primary
        duplicate.save()
        
        return merge_result
    
    def _detect_data_conflicts(self, primary: Account, duplicate: Account) -> List[Dict]:
        """Detect data conflicts between accounts"""
        conflicts = []
        
        # Fields to check for conflicts
        conflict_fields = [
            'website', 'phone', 'annual_revenue', 'number_of_employees',
            'billing_street', 'billing_city', 'billing_state', 'billing_country'
        ]
        
        for field in conflict_fields:
            primary_value = getattr(primary, field, None)
            duplicate_value = getattr(duplicate, field, None)
            
            if primary_value and duplicate_value and primary_value != duplicate_value:
                conflicts.append({
                    'field': field,
                    'primary_value': primary_value,
                    'duplicate_value': duplicate_value,
                    'confidence_primary': self._calculate_data_confidence(primary, field),
                    'confidence_duplicate': self._calculate_data_confidence(duplicate, field)
                })
        
        return conflicts
    
    def find_potential_duplicates_advanced(self, similarity_threshold: float = 0.85) -> List[Dict]:
        """Find potential duplicate accounts using advanced matching algorithms"""
        accounts = Account.objects.filter(tenant=self.tenant, is_active=True)
        potential_duplicates = []
        
        # Create account fingerprints for efficient matching
        account_fingerprints = {}
        for account in accounts:
            fingerprint = self._create_account_fingerprint(account)
            account_fingerprints[account.id] = {
                'account': account,
                'fingerprint': fingerprint
            }
        
        # Compare accounts using multiple algorithms
        processed_pairs = set()
        
        for account_id, account_data in account_fingerprints.items():
            for other_id, other_data in account_fingerprints.items():
                if account_id >= other_id:  # Avoid duplicate comparisons
                    continue
                
                pair_key = tuple(sorted([account_id, other_id]))
                if pair_key in processed_pairs:
                    continue
                
                processed_pairs.add(pair_key)
                
                # Calculate similarity using multiple methods
                similarity_scores = self._calculate_multi_similarity(
                    account_data, other_data
                )
                
                # Overall similarity score
                overall_similarity = self._calculate_weighted_similarity(similarity_scores)
                
                if overall_similarity >= similarity_threshold:
                    duplicate_info = {
                        'account_1': {
                            'id': account_id,
                            'name': account_data['account'].name,
                            'created_at': account_data['account'].created_at
                        },
                        'account_2': {
                            'id': other_id,
                            'name': other_data['account'].name,
                            'created_at': other_data['account'].created_at
                        },
                        'similarity_score': overall_similarity,
                        'similarity_breakdown': similarity_scores,
                        'merge_recommendation': self._generate_merge_recommendation(
                            account_data['account'], other_data['account'], similarity_scores
                        ),
                        'confidence_level': self._calculate_duplicate_confidence(similarity_scores)
                    }
                    
                    potential_duplicates.append(duplicate_info)
        
        # Sort by similarity score
        potential_duplicates.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return potential_duplicates
    
    def _create_account_fingerprint(self, account: Account) -> Dict:
        """Create account fingerprint for efficient matching"""
        return {
            'name_normalized': self._normalize_company_name(account.name),
            'website_domain': self._extract_domain(account.website) if account.website else None,
            'phone_normalized': self._normalize_phone(account.phone) if account.phone else None,
            'address_normalized': self._normalize_address(account),
            'industry': account.industry.name if account.industry else None,
            'size_category': self._categorize_company_size(account)
        }
    
    def _calculate_multi_similarity(self, account_data1: Dict, account_data2: Dict) -> Dict:
        """Calculate similarity using multiple algorithms"""
        fp1 = account_data1['fingerprint']
        fp2 = account_data2['fingerprint']
        
        similarities = {}
        
        # Name similarity (weighted most heavily)
        if fp1['name_normalized'] and fp2['name_normalized']:
            similarities['name'] = difflib.SequenceMatcher(
                None, fp1['name_normalized'], fp2['name_normalized']
            ).ratio()
        else:
            similarities['name'] = 0
        
        # Website domain similarity
        if fp1['website_domain'] and fp2['website_domain']:
            similarities['website'] = 1.0 if fp1['website_domain'] == fp2['website_domain'] else 0.0
        else:
            similarities['website'] = 0
        
        # Phone similarity
        if fp1['phone_normalized'] and fp2['phone_normalized']:
            similarities['phone'] = 1.0 if fp1['phone_normalized'] == fp2['phone_normalized'] else 0.0
        else:
            similarities['phone'] = 0
        
        # Address similarity
        if fp1['address_normalized'] and fp2['address_normalized']:
            similarities['address'] = difflib.SequenceMatcher(
                None, fp1['address_normalized'], fp2['address_normalized']
            ).ratio()
        else:
            similarities['address'] = 0
        
        # Industry similarity
        if fp1['industry'] and fp2['industry']:
            similarities['industry'] = 1.0 if fp1['industry'] == fp2['industry'] else 0.3
        else:
            similarities['industry'] = 0
        
        return similarities
    
    def analyze_account_portfolio_comprehensive(self, include_predictions: bool = True) -> Dict:
        """Comprehensive account portfolio analysis with AI insights"""
        accounts = Account.objects.filter(tenant=self.tenant, is_active=True)
        
        analysis = {
            'portfolio_overview': self._analyze_portfolio_overview(accounts),
            'health_distribution': self._analyze_health_distribution(accounts),
            'revenue_analysis': self._analyze_revenue_patterns(accounts),
            'growth_opportunities': self._identify_growth_opportunities(accounts),
            'risk_assessment': self._assess_portfolio_risks(accounts),
            'relationship_depth': self._analyze_relationship_depth(accounts),
            'geographic_distribution': self._analyze_geographic_distribution(accounts),
            'industry_performance': self._analyze_industry_performance(accounts)
        }
        
        if include_predictions:
            analysis['predictions'] = {
                'churn_risk_accounts': self._predict_churn_risks(accounts),
                'expansion_opportunities': self._predict_expansion_opportunities(accounts),
                'revenue_forecast': self._forecast_account_revenue(accounts),
                'health_trends': self._predict_health_trends(accounts)
            }
        
        return analysis
    
    def _predict_churn_risks(self, accounts) -> List[Dict]:
        """Predict accounts at risk of churning"""
        churn_predictions = []
        
        for account in accounts:
            try:
                account_data = self._gather_account_intelligence_data(account)
                churn_probability = self.intelligence_engine.calculate_churn_probability(account_data)
                
                if churn_probability > 0.3:  # 30% threshold
                    health_metrics = self.calculate_comprehensive_health_score(account)
                    
                    churn_predictions.append({
                        'account_id': account.id,
                        'account_name': account.name,
                        'churn_probability': round(churn_probability * 100, 1),
                        'risk_level': health_metrics.risk_level,
                        'key_risk_factors': health_metrics.key_indicators,
                        'recommended_actions': health_metrics.recommendations[:3],
                        'estimated_revenue_at_risk': account_data.get('current_arr', 0),
                        'intervention_priority': self._calculate_intervention_priority(
                            churn_probability, account_data.get('current_arr', 0)
                        )
                    })
            
            except Exception as e:
                logger.warning(f"Churn prediction failed for account {account.id}: {e}")
        
        # Sort by intervention priority
        churn_predictions.sort(key=lambda x: x['intervention_priority'], reverse=True)
        
        return churn_predictions[:20]  # Top 20 at-risk accounts
    
    def _predict_expansion_opportunities(self, accounts) -> List[Dict]:
        """Predict account expansion opportunities"""
        expansion_opportunities = []
        
        for account in accounts:
            try:
                account_data = self._gather_account_intelligence_data(account)
                expansion_analysis = self.intelligence_engine.analyze_expansion_opportunities(account_data)
                
                if expansion_analysis['expansion_score'] > 60:
                    expansion_opportunities.append({
                        'account_id': account.id,
                        'account_name': account.name,
                        'expansion_score': expansion_analysis['expansion_score'],
                        'opportunities': expansion_analysis['opportunities'],
                        'recommended_approach': expansion_analysis['recommended_approach'],
                        'optimal_timing': expansion_analysis['optimal_timing'],
                        'current_revenue': account_data.get('current_arr', 0),
                        'expansion_potential': sum(
                            opp['potential_value'] for opp in expansion_analysis['opportunities']
                        )
                    })
            
            except Exception as e:
                logger.warning(f"Expansion prediction failed for account {account.id}: {e}")
        
        # Sort by expansion potential
        expansion_opportunities.sort(key=lambda x: x['expansion_potential'], reverse=True)
        
        return expansion_opportunities[:15]  # Top 15 expansion opportunities
    
    # Helper methods
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for comparison"""
        if not name:
            return ""
        
        # Remove common legal suffixes and normalize
        suffixes = [
            'inc', 'incorporated', 'llc', 'ltd', 'limited', 'corp', 'corporation',
            'company', 'co', 'group', 'holdings', 'enterprises', 'solutions'
        ]
        
        normalized = name.lower().strip()
        
        # Remove punctuation and extra spaces
        import string
        normalized = normalized.translate(str.maketrans('', '', string.punctuation))
        normalized = ' '.join(normalized.split())
        
        # Remove suffixes
        words = normalized.split()
        if words and words[-1] in suffixes:
            words = words[:-1]
        
        return ' '.join(words)
    
    def _calculate_intervention_priority(self, churn_prob: float, revenue: float) -> float:
        """Calculate intervention priority score"""
        # Higher priority for high-value accounts with high churn risk
        return churn_prob * (1 + (revenue / 100000))