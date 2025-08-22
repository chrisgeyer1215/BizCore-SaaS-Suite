# ============================================================================
# backend/apps/crm/services/scoring_service.py - Lead & Account Scoring Service
# ============================================================================

from typing import Dict, List, Any
from django.db import models
from decimal import Decimal
import json

from .base import BaseService, CacheableMixin
from ..models import Lead, Account, LeadScoringRule


class ScoringService(BaseService, CacheableMixin):
    """Advanced scoring engine for leads and accounts"""
    
    def calculate_lead_score(self, lead: Lead) -> Dict:
        """Calculate comprehensive lead score"""
        scoring_rules = self.get_queryset(LeadScoringRule).filter(is_active=True)
        
        score_components = {
            'demographic': 0,
            'behavioral': 0,
            'firmographic': 0,
            'engagement': 0,
            'activity': 0,
        }
        
        detailed_breakdown = {}
        
        for rule in scoring_rules:
            try:
                score_change = self._apply_scoring_rule(rule, lead)
                if score_change != 0:
                    rule_type = rule.rule_type.lower()
                    score_components[rule_type] += score_change
                    detailed_breakdown[rule.name] = {
                        'score': score_change,
                        'type': rule.rule_type,
                        'description': rule.description,
                    }
                    
                    # Update rule statistics
                    rule.times_applied += 1
                    rule.last_applied = timezone.now()
                    rule.save(update_fields=['times_applied', 'last_applied'])
                    
            except Exception as e:
                self.logger.error(f"Error applying scoring rule {rule.name}: {e}")
        
        total_score = sum(score_components.values())
        total_score = max(0, min(100, total_score))  # Clamp between 0-100
        
        # Calculate score grade
        score_grade = self._calculate_score_grade(total_score)
        
        return {
            'total_score': total_score,
            'score_grade': score_grade,
            'components': score_components,
            'breakdown': detailed_breakdown,
            'recommendations': self._generate_scoring_recommendations(lead, total_score),
        }
    
    def calculate_account_score(self, account: Account) -> Dict:
        """Calculate account engagement and value score"""
        score_components = {
            'revenue_potential': self._score_revenue_potential(account),
            'engagement_level': self._score_engagement_level(account),
            'relationship_strength': self._score_relationship_strength(account),
            'growth_potential': self._score_growth_potential(account),
            'risk_factors': self._score_risk_factors(account),
        }
        
        # Weighted scoring
        weights = {
            'revenue_potential': 0.30,
            'engagement_level': 0.25,
            'relationship_strength': 0.20,
            'growth_potential': 0.15,
            'risk_factors': 0.10,
        }
        
        weighted_score = sum(
            score * weights[component] 
            for component, score in score_components.items()
        )
        
        total_score = max(0, min(100, weighted_score))
        
        return {
            'total_score': total_score,
            'score_grade': self._calculate_score_grade(total_score),
            'components': score_components,
            'tier': self._calculate_account_tier(total_score, account),
            'recommendations': self._generate_account_recommendations(account, total_score),
        }
    
    def bulk_score_leads(self, lead_ids: List[int] = None) -> Dict:
        """Bulk score multiple leads"""
        queryset = self.get_queryset(Lead)
        if lead_ids:
            queryset = queryset.filter(id__in=lead_ids)
        
        results = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'score_distribution': {'cold': 0, 'warm': 0, 'hot': 0, 'very_hot': 0},
        }
        
        for lead in queryset:
            try:
                score_result = self.calculate_lead_score(lead)
                
                old_score = lead.score
                lead.score = score_result['total_score']
                lead.score_breakdown = score_result['breakdown']
                lead.last_score_update = timezone.now()
                lead.save(update_fields=['score', 'score_breakdown', 'last_score_update'])
                
                results['processed'] += 1
                if old_score != lead.score:
                    results['updated'] += 1
                
                # Update distribution
                if lead.score < 25:
                    results['score_distribution']['cold'] += 1
                elif lead.score < 50:
                    results['score_distribution']['warm'] += 1
                elif lead.score < 75:
                    results['score_distribution']['hot'] += 1
                else:
                    results['score_distribution']['very_hot'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error scoring lead {lead.id}: {e}")
                results['errors'] += 1
        
        return results
    
    def create_scoring_rule(self, rule) -> LeadScoringRule:
        """Create new lead scoring rule"""
        self.require_permission('can_manage_scoring_rules')
        
        rule_data.update({
            'tenant': self.tenant,
            'created_by': self.user,
        })
        
        rule = LeadScoringRule.objects.create(**rule_data)
        
        # Test rule on sample leads
        test_results = self._test_scoring_rule(rule)
        
        self.logger.info(f"Scoring rule created: {rule.name}, affects {test_results['affected_leads']} leads")
        return rule
    
    def _apply_scoring_rule(self, rule: LeadScoringRule, lead: Lead) -> int:
        """Apply a specific scoring rule to a lead"""
        try:
            field_value = self._get_nested_field_value(lead, rule.field_name)
            rule_values = self._parse_rule_values(rule.value)
            
            if self._evaluate_condition(field_value, rule.operator, rule_values):
                return rule.score_change
                
        except Exception as e:
            self.logger.error(f"Error applying rule {rule.name}: {e}")
        
        return 0
    
    def _get_nested_field_value(self, obj: models.Model, field_path: str):
        """Get value from nested field path (e.g., 'industry.name')"""
        value = obj
        for field_part in field_path.split('.'):
            if hasattr(value, field_part):
                value = getattr(value, field_part)
            else:
                return None
        return value
    
    def _parse_rule_values(self, value_str: str) -> List:
        """Parse rule values from string (JSON or single value)"""
        try:
            if value_str.startswith('[') or value_str.startswith('{'):
                return json.loads(value_str)
            return [value_str]
        except:
            return [value_str]
    
    def _evaluate_condition(self, field_value: Any, operator: str, rule_values: List) -> bool:
        """Evaluate scoring condition"""
        if field_value is None and operator not in ['IS_EMPTY', 'IS_NOT_EMPTY']:
            return False
        
        field_str = str(field_value) if field_value is not None else ""
        
        if operator == 'EQUALS':
            return field_str == str(rule_values[0])
        elif operator == 'NOT_EQUALS':
            return field_str != str(rule_values[0])
        elif operator == 'CONTAINS':
            return str(rule_values[0]).lower() in field_str.lower()
        elif operator == 'NOT_CONTAINS':
            return str(rule_values[0]).lower() not in field_str.lower()
        elif operator == 'STARTS_WITH':
            return field_str.lower().startswith(str(rule_values[0]).lower())
        elif operator == 'ENDS_WITH':
            return field_str.lower().endswith(str(rule_values[0]).lower())
        elif operator == 'GREATER_THAN':
            try:
                return float(field_value) > float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif operator == 'LESS_THAN':
            try:
                return float(field_value) < float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif operator == 'GREATER_EQUAL':
            try:
                return float(field_value) >= float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif operator == 'LESS_EQUAL':
            try:
                return float(field_value) <= float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif operator == 'IN_LIST':
            return field_str in [str(val) for val in rule_values]
        elif operator == 'NOT_IN_LIST':
            return field_str not in [str(val) for val in rule_values]
        elif operator == 'IS_EMPTY':
            return field_value is None or field_str == ""
        elif operator == 'IS_NOT_EMPTY':
            return field_value is not None and field_str != ""
        
        return False
    
    def _score_revenue_potential(self, account: Account) -> float:
        """Score account revenue potential"""
        score = 0
        
        # Annual revenue scoring
        if account.annual_revenue:
            if account.annual_revenue >= 10000000:  # $10M+
                score += 30
            elif account.annual_revenue >= 1000000:  # $1M+
                score += 20
            elif account.annual_revenue >= 100000:   # $100K+
                score += 10
        
        # Employee count scoring
        if account.employee_count:
            if account.employee_count >= 1000:
                score += 20
            elif account.employee_count >= 100:
                score += 15
            elif account.employee_count >= 50:
                score += 10
        
        # Historical performance
        if account.total_revenue > 0:
            score += min(account.total_revenue / 10000, 30)  # Up to 30 points
        
        return min(score, 100)
    
    def _score_engagement_level(self, account: Account) -> float:
        """Score account engagement level"""
        score = 0
        
        # Recent activity
        if account.last_activity_date:
            days_since = (timezone.now() - account.last_activity_date).days
            if days_since <= 7:
                score += 30
            elif days_since <= 30:
                score += 20
            elif days_since <= 90:
                score += 10
        
        # Contact interactions
        contacts = account.contacts.all()
        active_contacts = contacts.filter(last_contact_date__gte=timezone.now() - timezone.timedelta(days=90))
        score += min(active_contacts.count() * 5, 25)
        
        # Email engagement
        # This would integrate with email tracking
        
        return min(score, 100)
    
    def _score_relationship_strength(self, account: Account) -> float:
        """Score relationship strength"""
        score = 0
        
        # Customer tenure
        if account.customer_since:
            years = (timezone.now().date() - account.customer_since).days / 365
            score += min(years * 5, 25)
        
        # Decision maker contact
        if account.contacts.filter(is_decision_maker=True).exists():
            score += 20
        
        # Relationship strength indicator
        strength_scores = {
            'CHAMPION': 25,
            'HOT': 20,
            'WARM': 15,
            'COLD': 5,
        }
        score += strength_scores.get(account.relationship_strength, 0)
        
        return min(score, 100)
    
    def _score_growth_potential(self, account: Account) -> float:
        """Score account growth potential"""
        score = 0
        
        # Industry growth potential
        high_growth_industries = ['TECHNOLOGY', 'HEALTHCARE', 'FINTECH']
        if account.industry and account.industry.name in high_growth_industries:
            score += 20
        
        # Recent opportunities
        recent_opps = account.opportunities.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=180)
        )
        score += min(recent_opps.count() * 10, 30)
        
        return min(score, 100)
    
    def _score_risk_factors(self, account: Account) -> float:
        """Score risk factors (negative scoring)"""
        risk_score = 0
        
        # Payment history (would integrate with finance module)
        # Long time since last contact
        if account.last_activity_date:
            days_since = (timezone.now() - account.last_activity_date).days
            if days_since > 365:
                risk_score += 30
            elif days_since > 180:
                risk_score += 15
        
        # Low engagement
        if account.total_opportunities == 0:
            risk_score += 20
        
        return max(0, 100 - risk_score)  # Invert risk to positive score
    
    def _calculate_score_grade(self, score: float) -> str:
        """Calculate score grade based on numeric score"""
        if score >= 80:
            return 'A'
        elif score >= 60:
            return 'B'
        elif score >= 40:
            return 'C'
        elif score >= 20:
            return 'D'
        else:
            return 'F'
    
    def _calculate_account_tier(self, score: float, account: Account) -> str:
        """Calculate account tier"""
        if score >= 80 and account.total_revenue >= 100000:
            return 'PLATINUM'
        elif score >= 60 and account.total_revenue >= 50000:
            return 'GOLD'
        elif score >= 40:
            return 'SILVER'
        else:
            return 'BRONZE'
    
    def _generate_scoring_recommendations(self, lead: Lead, score: float) -> List[str]:
        """Generate recommendations based on lead score"""
        recommendations = []
        
        if score < 25:
            recommendations.append("Schedule nurturing campaign")
            recommendations.append("Gather more qualification information")
        elif score < 50:
            recommendations.append("Engage with educational content")
            recommendations.append("Schedule discovery call")
        elif score < 75:
            recommendations.append("Fast-track to sales process")
            recommendations.append("Schedule product demo")
        else:
            recommendations.append("Prioritize for immediate follow-up")
            recommendations.append("Assign to senior sales rep")
        
        return recommendations
    
    def _generate_account_recommendations(self, account: Account, score: float) -> List[str]:
        """Generate recommendations based on account score"""
        recommendations = []
        
        if score < 40:
            recommendations.append("Develop re-engagement strategy")
            recommendations.append("Review account status")
        elif score < 60:
            recommendations.append("Increase touchpoint frequency")
            recommendations.append("Identify expansion opportunities")
        elif score < 80:
            recommendations.append("Develop strategic account plan")
            recommendations.append("Engage C-level contacts")
        else:
            recommendations.append("Nominate for key account program")
            recommendations.append("Explore partnership opportunities")
        
        return recommendations
    
    def _test_scoring_rule(self, rule: LeadScoringRule) -> Dict:
        """Test scoring rule on sample leads"""
        test_leads = self.get_queryset(Lead)[:100]  # Sample of 100 leads
        affected_leads = 0
        
        for lead in test_leads:
            if self._apply_scoring_rule(rule, lead) != 0:
                affected_leads += 1
        
        return {
            'affected_leads': affected_leads,
            'total_tested': test_leads.count(),
            'impact_percentage': (affected_leads / test_leads.count() * 100) if test_leads.count() > 0 else 0,
        }