# crm/utils/scoring_utils.py
"""
Lead Scoring Utilities for CRM Module

Provides comprehensive lead scoring capabilities including:
- Dynamic scoring rule engine
- Behavioral scoring algorithms
- Demographic scoring factors
- Engagement scoring metrics
- Machine learning-based scoring
- Real-time score updates
- Scoring analytics and insights
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from decimal import Decimal
from dataclasses import dataclass, field
from collections import defaultdict
import math

from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.core.cache import cache
from django.conf import settings

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


@dataclass
class ScoringRule:
    """Represents a single scoring rule."""
    rule_id: str
    name: str
    category: str  # demographic, behavioral, engagement, firmographic
    field_name: str
    condition_type: str  # equals, contains, greater_than, less_than, in_range, regex
    condition_value: Any
    score_value: int
    weight: float = 1.0
    is_active: bool = True
    created_date: datetime = field(default_factory=timezone.now)


@dataclass
class ScoringResult:
    """Result of lead scoring calculation."""
    lead_id: int
    total_score: int
    max_possible_score: int
    score_percentage: float
    grade: str  # A, B, C, D, F
    category_scores: Dict[str, int]
    applied_rules: List[Dict[str, Any]]
    calculation_date: datetime
    factors: List[Dict[str, Any]]


class LeadScoringEngine:
    """
    Advanced lead scoring engine with multiple scoring strategies.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.scoring_rules = self._load_scoring_rules()
        self.grade_thresholds = {
            'A': 80,  # Hot leads
            'B': 60,  # Warm leads
            'C': 40,  # Cold leads
            'D': 20,  # Poor leads
            'F': 0    # Unqualified
        }
    
    def calculate_lead_score(self, lead, use_ml: bool = False) -> ScoringResult:
        """
        Calculate comprehensive lead score using multiple factors.
        
        Args:
            lead: Lead instance to score
            use_ml: Whether to use machine learning model
        
        Returns:
            ScoringResult: Detailed scoring result
        """
        if use_ml and self._has_ml_model():
            return self._calculate_ml_score(lead)
        else:
            return self._calculate_rule_based_score(lead)
    
    def _calculate_rule_based_score(self, lead) -> ScoringResult:
        """Calculate score using predefined rules."""
        category_scores = defaultdict(int)
        applied_rules = []
        factors = []
        total_score = 0
        max_possible_score = 0
        
        # Get lead data for scoring
        lead_data = self._extract_lead_data(lead)
        
        # Apply scoring rules
        for rule in self.scoring_rules:
            if not rule.is_active:
                continue
            
            max_possible_score += abs(rule.score_value) * rule.weight
            
            if self._evaluate_rule_condition(lead_data, rule):
                weighted_score = int(rule.score_value * rule.weight)
                category_scores[rule.category] += weighted_score
                total_score += weighted_score
                
                applied_rules.append({
                    'rule_id': rule.rule_id,
                    'name': rule.name,
                    'category': rule.category,
                    'score': weighted_score,
                    'condition': f"{rule.field_name} {rule.condition_type} {rule.condition_value}"
                })
                
                factors.append({
                    'factor': rule.name,
                    'impact': 'positive' if weighted_score > 0 else 'negative',
                    'score': weighted_score,
                    'description': f"Lead {rule.field_name} matches criteria"
                })
        
        # Add behavioral scoring
        behavioral_score = self._calculate_behavioral_score(lead)
        total_score += behavioral_score['score']
        category_scores['behavioral'] += behavioral_score['score']
        factors.extend(behavioral_score['factors'])
        
        # Add engagement scoring
        engagement_score = self._calculate_engagement_score(lead)
        total_score += engagement_score['score']
        category_scores['engagement'] += engagement_score['score']
        factors.extend(engagement_score['factors'])
        
        # Normalize score to 0-100 range
        normalized_score = min(100, max(0, total_score))
        score_percentage = (normalized_score / 100) * 100
        grade = self._calculate_grade(normalized_score)
        
        return ScoringResult(
            lead_id=lead.id,
            total_score=normalized_score,
            max_possible_score=max_possible_score,
            score_percentage=score_percentage,
            grade=grade,
            category_scores=dict(category_scores),
            applied_rules=applied_rules,
            calculation_date=timezone.now(),
            factors=factors
        )
    
    def _calculate_ml_score(self, lead) -> ScoringResult:
        """Calculate score using machine learning model."""
        # Load trained model
        model = self._load_ml_model()
        scaler = self._load_ml_scaler()
        
        # Prepare features
        features = self._extract_ml_features(lead)
        scaled_features = scaler.transform([features])
        
        # Predict probability of conversion
        conversion_probability = model.predict_proba(scaled_features)[0][1]
        ml_score = int(conversion_probability * 100)
        
        # Get feature importance
        feature_names = self._get_ml_feature_names()
        feature_importance = model.feature_importances_
        
        factors = []
        for name, importance in zip(feature_names, feature_importance):
            if importance > 0.05:  # Only show significant factors
                factors.append({
                    'factor': name,
                    'impact': 'positive',
                    'score': int(importance * ml_score),
                    'description': f"ML factor: {name}"
                })
        
        grade = self._calculate_grade(ml_score)
        
        return ScoringResult(
            lead_id=lead.id,
            total_score=ml_score,
            max_possible_score=100,
            score_percentage=conversion_probability * 100,
            grade=grade,
            category_scores={'ml_prediction': ml_score},
            applied_rules=[{
                'rule_id': 'ml_model',
                'name': 'Machine Learning Prediction',
                'category': 'ml_prediction',
                'score': ml_score,
                'condition': 'ML model prediction'
            }],
            calculation_date=timezone.now(),
            factors=factors
        )
    
    def _calculate_behavioral_score(self, lead) -> Dict[str, Any]:
        """Calculate behavioral scoring factors."""
        behavioral_score = 0
        factors = []
        
        try:
            # Website visits
            if hasattr(lead, 'website_visits'):
                visits = lead.website_visits
                if visits > 10:
                    score = min(20, visits * 2)
                    behavioral_score += score
                    factors.append({
                        'factor': 'Website Visits',
                        'impact': 'positive',
                        'score': score,
                        'description': f"{visits} website visits"
                    })
            
            # Email engagement
            if hasattr(lead, 'email_opens') and hasattr(lead, 'email_clicks'):
                email_score = 0
                if lead.email_opens > 0:
                    email_score += min(10, lead.email_opens * 2)
                if lead.email_clicks > 0:
                    email_score += min(15, lead.email_clicks * 3)
                
                if email_score > 0:
                    behavioral_score += email_score
                    factors.append({
                        'factor': 'Email Engagement',
                        'impact': 'positive',
                        'score': email_score,
                        'description': f"{lead.email_opens} opens, {lead.email_clicks} clicks"
                    })
            
            # Content downloads
            if hasattr(lead, 'content_downloads'):
                downloads = lead.content_downloads
                if downloads > 0:
                    score = min(25, downloads * 5)
                    behavioral_score += score
                    factors.append({
                        'factor': 'Content Downloads',
                        'impact': 'positive',
                        'score': score,
                        'description': f"{downloads} content downloads"
                    })
            
            # Social media engagement
            if hasattr(lead, 'social_engagement_score'):
                social_score = min(10, lead.social_engagement_score)
                if social_score > 0:
                    behavioral_score += social_score
                    factors.append({
                        'factor': 'Social Engagement',
                        'impact': 'positive',
                        'score': social_score,
                        'description': f"Social engagement score: {lead.social_engagement_score}"
                    })
        
        except Exception as e:
            print(f"Error calculating behavioral score: {e}")
        
        return {
            'score': behavioral_score,
            'factors': factors
        }
    
    def _calculate_engagement_score(self, lead) -> Dict[str, Any]:
        """Calculate engagement scoring factors."""
        engagement_score = 0
        factors = []
        
        try:
            from crm.models.activity import Activity
            
            # Recent activities (last 30 days)
            recent_activities = Activity.objects.filter(
                related_to_id=lead.id,
                tenant=self.tenant,
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            activity_counts = recent_activities.values('type').annotate(
                count=Count('id')
            )
            
            for activity in activity_counts:
                activity_type = activity['type']
                count = activity['count']
                
                # Score based on activity type
                activity_scores = {
                    'CALL': 5,
                    'MEETING': 8,
                    'EMAIL': 2,
                    'TASK': 3,
                    'NOTE': 1
                }
                
                if activity_type in activity_scores:
                    score = min(20, count * activity_scores[activity_type])
                    engagement_score += score
                    factors.append({
                        'factor': f'{activity_type.title()} Activities',
                        'impact': 'positive',
                        'score': score,
                        'description': f"{count} {activity_type.lower()} activities in last 30 days"
                    })
            
            # Response rate to outreach
            if hasattr(lead, 'outreach_response_rate'):
                response_rate = lead.outreach_response_rate
                if response_rate > 0:
                    score = int(response_rate * 20)  # Max 20 points for 100% response rate
                    engagement_score += score
                    factors.append({
                        'factor': 'Response Rate',
                        'impact': 'positive',
                        'score': score,
                        'description': f"{response_rate}% response rate"
                    })
            
            # Time since last interaction
            last_activity = recent_activities.order_by('-created_at').first()
            if last_activity:
                days_since_last = (timezone.now() - last_activity.created_at).days
                if days_since_last <= 7:
                    score = 10
                elif days_since_last <= 14:
                    score = 5
                elif days_since_last <= 30:
                    score = 2
                else:
                    score = -5  # Negative for old interactions
                
                engagement_score += score
                factors.append({
                    'factor': 'Recent Interaction',
                    'impact': 'positive' if score > 0 else 'negative',
                    'score': score,
                    'description': f"Last interaction {days_since_last} days ago"
                })
        
        except Exception as e:
            print(f"Error calculating engagement score: {e}")
        
        return {
            'score': engagement_score,
            'factors': factors
        }
    
    def _extract_lead_data(self, lead) -> Dict[str, Any]:
        """Extract lead data for scoring evaluation."""
        data = {}
        
        # Basic fields
        fields_to_extract = [
            'first_name', 'last_name', 'email', 'phone', 'company', 
            'title', 'industry', 'source', 'status', 'country', 
            'annual_revenue', 'employees', 'website'
        ]
        
        for field in fields_to_extract:
            try:
                value = getattr(lead, field, None)
                data[field] = value
            except:
                data[field] = None
        
        # Derived fields
        data['email_domain'] = self._extract_email_domain(data.get('email'))
        data['company_size'] = self._categorize_company_size(data.get('employees'))
        data['revenue_range'] = self._categorize_revenue(data.get('annual_revenue'))
        data['days_since_created'] = (timezone.now().date() - lead.created_at.date()).days
        
        return data
    
    def _evaluate_rule_condition(self, lea], rule: ScoringRule) -> bool:
        """Evaluate if lead data meets rule condition."""
        field_value = lead_data.get(rule.field_name)
        condition_value = rule.condition_value
        
        if field_value is None:
            return False
        
        try:
            if rule.condition_type == 'equals':
                return str(field_value).lower() == str(condition_value).lower()
            
            elif rule.condition_type == 'not_equals':
                return str(field_value).lower() != str(condition_value).lower()
            
            elif rule.condition_type == 'contains':
                return str(condition_value).lower() in str(field_value).lower()
            
            elif rule.condition_type == 'not_contains':
                return str(condition_value).lower() not in str(field_value).lower()
            
            elif rule.condition_type == 'starts_with':
                return str(field_value).lower().startswith(str(condition_value).lower())
            
            elif rule.condition_type == 'ends_with':
                return str(field_value).lower().endswith(str(condition_value).lower())
            
            elif rule.condition_type == 'greater_than':
                return float(field_value) > float(condition_value)
            
            elif rule.condition_type == 'less_than':
                return float(field_value) < float(condition_value)
            
            elif rule.condition_type == 'greater_than_or_equal':
                return float(field_value) >= float(condition_value)
            
            elif rule.condition_type == 'less_than_or_equal':
                return float(field_value) <= float(condition_value)
            
            elif rule.condition_type == 'in_list':
                if isinstance(condition_value, list):
                    return field_value in condition_value
                else:
                    return field_value in str(condition_value).split(',')
            
            elif rule.condition_type == 'not_in_list':
                if isinstance(condition_value, list):
                    return field_value not in condition_value
                else:
                    return field_value not in str(condition_value).split(',')
            
            elif rule.condition_type == 'in_range':
                if isinstance(condition_value, dict) and 'min' in condition_value and 'max' in condition_value:
                    return condition_value['min'] <= float(field_value) <= condition_value['max']
            
            elif rule.condition_type == 'regex':
                return bool(re.match(str(condition_value), str(field_value), re.IGNORECASE))
            
            elif rule.condition_type == 'is_empty':
                return field_value in [None, '', 0]
            
            elif rule.condition_type == 'is_not_empty':
                return field_value not in [None, '', 0]
        
        except Exception as e:
            print(f"Error evaluating rule condition: {e}")
            return False
        
        return False
    
    def _calculate_grade(self, score: int) -> str:
        """Calculate letter grade based on score."""
        for grade, threshold in self.grade_thresholds.items():
            if score >= threshold:
                return grade
        return 'F'
    
    def _extract_email_domain(self, email: Optional[str]) -> Optional[str]:
        """Extract domain from email address."""
        if not email or '@' not in email:
            return None
        return email.split('@')[1].lower()
    
    def _categorize_company_size(self, employees: Optional[int]) -> str:
        """Categorize company size based on employee count."""
        if not employees:
            return 'unknown'
        
        if employees < 10:
            return 'startup'
        elif employees < 50:
            return 'small'
        elif employees < 500:
            return 'medium'
        else:
            return 'enterprise'
    
    def _categorize_revenue(self, revenue: Optional[Decimal]) -> str:
        """Categorize revenue range."""
        if not revenue:
            return 'unknown'
        
        revenue = float(revenue)
        if revenue < 1000000:
            return 'small'
        elif revenue < 10000000:
            return 'medium'
        else:
            return 'large'
    
    def _load_scoring_rules(self) -> List[ScoringRule]:
        """Load scoring rules from database or configuration."""
        rules = []
        
        try:
            from crm.models.lead import LeadScoringRule
            
            db_rules = LeadScoringRule.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).order_by('category', 'name')
            
            for db_rule in db_rules:
                rule = ScoringRule(
                    rule_id=str(db_rule.id),
                    name=db_rule.name,
                    category=db_rule.category,
                    field_name=db_rule.field_name,
                    condition_type=db_rule.condition_type,
                    condition_value=json.loads(db_rule.condition_value) if db_rule.condition_value else None,
                    score_value=db_rule.score_value,
                    weight=float(db_rule.weight),
                    is_active=db_rule.is_active,
                    created_date=db_rule.created_at
                )
                rules.append(rule)
        
        except Exception as e:
            print(f"Error loading scoring rules from database: {e}")
            # Fallback to default rules
            rules = self._get_default_scoring_rules()
        
        return rules
    
    def _get_default_scoring_rules(self) -> List[ScoringRule]:
        """Get default scoring rules if database is unavailable."""
        return [
            # Demographic scoring
            ScoringRule('demo_001', 'Senior Title', 'demographic', 'title', 'contains', 
                       'senior,manager,director,vp,ceo,cto,cfo', 10),
            ScoringRule('demo_002', 'Enterprise Company', 'demographic', 'company_size', 'equals', 'enterprise', 15),
            ScoringRule('demo_003', 'High Revenue', 'demographic', 'revenue_range', 'equals', 'large', 12),
            ScoringRule('demo_004', 'Target Industry', 'demographic', 'industry', 'in_list', 
                       'technology,software,healthcare,finance', 8),
            
            # Behavioral scoring
            ScoringRule('behav_001', 'Multiple Visits', 'behavioral', 'website_visits', 'greater_than', 5, 10),
            ScoringRule('behav_002', 'Downloaded Content', 'behavioral', 'content_downloads', 'greater_than', 0, 15),
            ScoringRule('behav_003', 'Email Engagement', 'behavioral', 'email_opens', 'greater_than', 3, 8),
            
            # Lead source scoring
            ScoringRule('source_001', 'Referral Source', 'source', 'source', 'equals', 'referral', 20),
            ScoringRule('source_002', 'Organic Search', 'source', 'source', 'equals', 'organic', 12),
            ScoringRule('source_003', 'Direct Website', 'source', 'source', 'equals', 'website', 10),
            ScoringRule('source_004', 'Cold Call', 'source', 'source', 'equals', 'cold_call', -5),
            
            # Negative scoring
            ScoringRule('neg_001', 'Generic Email', 'negative', 'email_domain', 'in_list', 
                       'gmail.com,yahoo.com,hotmail.com', -5),
            ScoringRule('neg_002', 'Startup Company', 'negative', 'company_size', 'equals', 'startup', -3),
        ]
    
    def _has_ml_model(self) -> bool:
        """Check if ML model is available and trained."""
        cache_key = f"crm_ml_model_available_{self.tenant.id if self.tenant else 'default'}"
        return cache.get(cache_key, False)
    
    def _load_ml_model(self):
        """Load trained machine learning model."""
        # This would load a pre-trained model from storage
        # For now, return a mock model
        return RandomForestClassifier(n_estimators=100, random_state=42)
    
    def _load_ml_scaler(self):
        """Load feature scaler for ML model."""
        return StandardScaler()
    
    def _extract_ml_features(self, lead) -> List[float]:
        """Extract features for ML model."""
        features = []
        
        # Numeric features
        features.append(float(getattr(lead, 'website_visits', 0)))
        features.append(float(getattr(lead, 'email_opens', 0)))
        features.append(float(getattr(lead, 'email_clicks', 0)))
        features.append(float(getattr(lead, 'content_downloads', 0)))
        features.append(float((timezone.now().date() - lead.created_at.date()).days))
        
        # Categorical features (encoded)
        features.append(1.0 if getattr(lead, 'source', '') == 'referral' else 0.0)
        features.append(1.0 if 'director' in getattr(lead, 'title', '').lower() else 0.0)
        features.append(1.0 if getattr(lead, 'company_size', '') == 'enterprise' else 0.0)
        
        return features
    
    def _get_ml_feature_names(self) -> List[str]:
        """Get feature names for ML model."""
        return [
            'website_visits', 'email_opens', 'email_clicks', 'content_downloads',
            'days_since_created', 'is_referral', 'has_director_title', 'is_enterprise'
        ]


class ScoringAnalytics:
    """
    Analytics and insights for lead scoring.
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
    
    def get_scoring_distribution(self, date_range: Tuple[datetime, datetime] = None) -> Dict[str, Any]:
        """Get distribution of lead scores."""
        try:
            from crm.models.lead import Lead
            
            # Build base query
            leads = Lead.objects.filter(tenant=self.tenant) if self.tenant else Lead.objects.all()
            
            if date_range:
                leads = leads.filter(created_at__range=date_range)
            
            # Calculate score distribution
            score_ranges = {
                'A (80-100)': leads.filter(score__gte=80, score__lte=100).count(),
                'B (60-79)': leads.filter(score__gte=60, score__lt=80).count(),
                'C (40-59)': leads.filter(score__gte=40, score__lt=60).count(),
                'D (20-39)': leads.filter(score__gte=20, score__lt=40).count(),
                'F (0-19)': leads.filter(score__gte=0, score__lt=20).count(),
            }
            
            total_leads = sum(score_ranges.values())
            
            # Calculate percentages
            score_percentages = {}
            for range_name, count in score_ranges.items():
                score_percentages[range_name] = {
                    'count': count,
                    'percentage': (count / total_leads * 100) if total_leads > 0 else 0
                }
            
            # Calculate average score
            avg_score = leads.aggregate(avg_score=Avg('score'))['avg_score'] or 0
            
            return {
                'total_leads': total_leads,
                'average_score': round(avg_score, 1),
                'distribution': score_percentages,
                'grade_counts': score_ranges
            }
        
        except Exception as e:
            print(f"Error calculating scoring distribution: {e}")
            return {}
    
    def get_conversion_analysis(self) -> Dict[str, Any]:
        """Analyze conversion rates by score ranges."""
        try:
            from crm.models.lead import Lead
            from crm.models.opportunity import Opportunity
            
            # Get leads with conversions
            leads_with_opportunities = Lead.objects.filter(
                tenant=self.tenant,
                opportunities__isnull=False
            ).distinct() if self.tenant else Lead.objects.filter(opportunities__isnull=False).distinct()
            
            # Calculate conversion rates by score range
            score_ranges = [
                (80, 100, 'A'),
                (60, 79, 'B'),
                (40, 59, 'C'),
                (20, 39, 'D'),
                (0, 19, 'F')
            ]
            
            conversion_analysis = {}
            
            for min_score, max_score, grade in score_ranges:
                total_leads = Lead.objects.filter(
                    tenant=self.tenant,
                    score__gte=min_score,
                    score__lte=max_score
                ).count() if self.tenant else Lead.objects.filter(score__gte=min_score, score__lte=max_score).count()
                
                converted_leads = leads_with_opportunities.filter(
                    score__gte=min_score,
                    score__lte=max_score
                ).count()
                
                conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
                
                conversion_analysis[grade] = {
                    'total_leads': total_leads,
                    'converted_leads': converted_leads,
                    'conversion_rate': round(conversion_rate, 2)
                }
            
            return conversion_analysis
        
        except Exception as e:
            print(f"Error calculating conversion analysis: {e}")
            return {}
    
    def get_top_scoring_factors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top factors contributing to high scores."""
        try:
            from crm.models.lead import Lead
            
            # Get high-scoring leads (score >= 70)
            high_scoring_leads = Lead.objects.filter(
                tenant=self.tenant,
                score__gte=70
            ) if self.tenant else Lead.objects.filter(score__gte=70)
            
            # Analyze common characteristics
            factors = []
            
            # Analyze by source
            source_analysis = high_scoring_leads.values('source').annotate(
                count=Count('id')
            ).order_by('-count')[:limit]
            
            for item in source_analysis:
                if item['source']:
                    factors.append({
                        'factor': f"Source: {item['source']}",
                        'leads_count': item['count'],
                        'impact': 'High'
                    })
            
            # Analyze by industry
            industry_analysis = high_scoring_leads.values('industry').annotate(
                count=Count('id')
            ).order_by('-count')[:limit]
            
            for item in industry_analysis:
                if item['industry']:
                    factors.append({
                        'factor': f"Industry: {item['industry']}",
                        'leads_count': item['count'],
                        'impact': 'High'
                    })
            
            return factors[:limit]
        
        except Exception as e:
            print(f"Error analyzing top scoring factors: {e}")
            return []


# Convenience functions
def calculate_lead_score(lead, tenant=None, use_ml: bool = False) -> ScoringResult:
    """Calculate score for a single lead."""
    engine = LeadScoringEngine(tenant)
    return engine.calculate_lead_score(lead, use_ml)


def update_lead_scores(tenant=None, batch_size: int = 100) -> Dict[str, Any]:
    """Update scores for all leads in batches."""
    try:
        from crm.models.lead import Lead
        
        engine = LeadScoringEngine(tenant)
        leads = Lead.objects.filter(tenant=tenant) if tenant else Lead.objects.all()
        
        total_leads = leads.count()
        updated_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_leads, batch_size):
            batch_leads = leads[i:i + batch_size]
            
            for lead in batch_leads:
                try:
                    result = engine.calculate_lead_score(lead)
                    lead.score = result.total_score
                    lead.grade = result.grade
                    lead.save(update_fields=['score', 'grade', 'updated_at'])
                    updated_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"Error updating score for lead {lead.id}: {e}")
        
        return {
            'total_leads': total_leads,
            'updated_count': updated_count,
            'error_count': error_count,
            'success_rate': (updated_count / total_leads * 100) if total_leads > 0 else 0
        }
    
    except Exception as e:
        return {'error': str(e)}


def get_scoring_factors(lead, tenant=None) -> List[Dict[str, Any]]:
    """Get detailed scoring factors for a lead."""
    engine = LeadScoringEngine(tenant)
    result = engine.calculate_lead_score(lead)
    return result.factors


def analyze_conversion_probability(lead, tenant=None) -> Dict[str, Any]:
    """Analyze probability of lead conversion."""
    engine = LeadScoringEngine(tenant)
    result = engine.calculate_lead_score(lead, use_ml=True)
    
    # Calculate conversion probability based on score
    if result.total_score >= 80:
        probability = "High (70-90%)"
        confidence = "High"
    elif result.total_score >= 60:
        probability = "Medium (40-70%)"
        confidence = "Medium"
    elif result.total_score >= 40:
        probability = "Low (20-40%)"
        confidence = "Medium"
    else:
        probability = "Very Low (5-20%)"
        confidence = "Low"
    
    return {
        'lead_id': lead.id,
        'current_score': result.total_score,
        'grade': result.grade,
        'conversion_probability': probability,
        'confidence_level': confidence,
        'key_factors': result.factors[:5],  # Top 5 factors
        'recommendations': generate_lead_recommendations(result)
    }


def generate_lead_recommendations(scoring_result: ScoringResult) -> List[str]:
    """Generate recommendations based on scoring result."""
    recommendations = []
    
    if scoring_result.total_score < 40:
        recommendations.append("Consider lead nurturing campaigns to increase engagement")
        recommendations.append("Verify contact information and company details")
    
    if scoring_result.grade in ['A', 'B']:
        recommendations.append("Priority lead - schedule immediate follow-up")
        recommendations.append("Consider direct sales outreach")
    
    # Analyze category scores for specific recommendations
    category_scores = scoring_result.category_scores
    
    if category_scores.get('behavioral', 0) < 10:
        recommendations.append("Increase behavioral engagement through targeted content")
    
    if category_scores.get('engagement', 0) < 10:
        recommendations.append("Schedule more frequent touchpoints and activities")
    
    if category_scores.get('demographic', 0) > 20:
        recommendations.append("Lead matches ideal customer profile - fast-track for sales")
    
    return recommendations[:5]  #