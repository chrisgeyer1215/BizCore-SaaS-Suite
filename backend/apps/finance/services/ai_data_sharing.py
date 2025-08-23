"""
Cross-Module AI Data Sharing Service

Provides intelligent data sharing and synchronization between finance and other modules,
enabling unified AI insights and cross-functional intelligence.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
import json

from django.db import transaction, connection
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Sum, Count, Avg, Max, Min
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder

from apps.core.models import TenantBaseModel

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class AIDataPoint:
    """Represents a shared AI data point."""
    module: str
    entity_type: str
    entity_id: int
    data_type: str
    value: Any
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossModuleInsight:
    """Represents cross-module AI insight."""
    insight_type: str
    primary_module: str
    related_modules: List[str]
    confidence: float
    data: Dict[str, Any]
    recommendations: List[str] = field(default_factory=list)
    impact_score: float = 0.0
    timestamp: datetime = field(default_factory=timezone.now)


class AIDataSharingService:
    """
    Comprehensive AI data sharing service for cross-module intelligence.
    
    Features:
    - Centralized AI data repository
    - Cross-module insight generation
    - Intelligent data synchronization
    - Predictive correlation analysis
    - Real-time AI data streaming
    - Module performance analytics
    - Unified customer intelligence
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = logging.getLogger(f'{__name__}.{tenant.schema_name}')
        self.cache_timeout = 3600  # 1 hour
    
    # ==================== Data Collection & Storage ====================
    
    def collect_finance_ai_data(self) -> Dict[str, Any]:
        """Collect AI data from finance module."""
        try:
            finance_data = {}
            
            # Customer financial intelligence
            finance_data['customer_financial_profiles'] = self._collect_customer_financial_data()
            
            # Revenue and payment patterns
            finance_data['revenue_patterns'] = self._collect_revenue_patterns()
            
            # Risk assessments
            finance_data['risk_assessments'] = self._collect_financial_risk_data()
            
            # Cash flow insights
            finance_data['cash_flow_insights'] = self._collect_cash_flow_data()
            
            # Invoice and payment behavior
            finance_data['payment_behavior'] = self._collect_payment_behavior_data()
            
            return {
                'success': True,
                'module': 'finance',
                'data': finance_data,
                'collection_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting finance AI data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _collect_customer_financial_data(self) -> List[Dict[str, Any]]:
        """Collect customer financial intelligence data."""
        try:
            from apps.finance.models.invoicing import Invoice
            from apps.finance.models.payments import Payment
            
            customer_data = []
            
            # Get customer financial metrics
            customer_metrics = Invoice.objects.filter(
                tenant=self.tenant
            ).values('customer_id').annotate(
                total_revenue=Sum('total_amount'),
                invoice_count=Count('id'),
                avg_invoice_value=Avg('total_amount'),
                last_invoice_date=Max('created_at'),
                first_invoice_date=Min('created_at')
            )
            
            for metrics in customer_metrics:
                if metrics['customer_id']:
                    # Calculate payment behavior
                    paid_invoices = Invoice.objects.filter(
                        tenant=self.tenant,
                        customer_id=metrics['customer_id'],
                        status='PAID'
                    ).count()
                    
                    payment_rate = (paid_invoices / metrics['invoice_count']) * 100 if metrics['invoice_count'] > 0 else 0
                    
                    # Calculate average payment time
                    avg_payment_time = self._calculate_avg_payment_time(metrics['customer_id'])
                    
                    customer_data.append({
                        'customer_id': metrics['customer_id'],
                        'total_revenue': float(metrics['total_revenue'] or 0),
                        'invoice_count': metrics['invoice_count'],
                        'avg_invoice_value': float(metrics['avg_invoice_value'] or 0),
                        'payment_rate': payment_rate,
                        'avg_payment_days': avg_payment_time,
                        'customer_tenure_days': (timezone.now().date() - metrics['first_invoice_date'].date()).days if metrics['first_invoice_date'] else 0,
                        'last_activity_days': (timezone.now().date() - metrics['last_invoice_date'].date()).days if metrics['last_invoice_date'] else 0,
                        'risk_score': self._calculate_customer_risk_score(metrics['customer_id']),
                        'lifetime_value': self._calculate_customer_ltv(metrics['customer_id'])
                    })
            
            return customer_data
            
        except Exception as e:
            self.logger.error(f"Error collecting customer financial data: {e}")
            return []
    
    def _collect_revenue_patterns(self) -> Dict[str, Any]:
        """Collect revenue pattern data."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            # Monthly revenue trends
            monthly_revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID',
                paid_date__gte=timezone.now().date() - timedelta(days=365)
            ).extra(
                select={'month': "DATE_TRUNC('month', paid_date)"}
            ).values('month').annotate(
                revenue=Sum('total_amount'),
                invoice_count=Count('id')
            ).order_by('month')
            
            # Seasonal patterns
            seasonal_data = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID'
            ).extra(
                select={'quarter': "EXTRACT('quarter' FROM paid_date)"}
            ).values('quarter').annotate(
                avg_revenue=Avg('total_amount'),
                total_revenue=Sum('total_amount')
            )
            
            return {
                'monthly_trends': list(monthly_revenue),
                'seasonal_patterns': list(seasonal_data),
                'growth_rate': self._calculate_revenue_growth_rate(),
                'predictive_factors': self._identify_revenue_factors()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting revenue patterns: {e}")
            return {}
    
    def _collect_financial_risk_data(self) -> Dict[str, Any]:
        """Collect financial risk assessment data."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            # Overdue invoice analysis
            overdue_analysis = {
                'overdue_count': Invoice.objects.filter(
                    tenant=self.tenant,
                    status='OVERDUE'
                ).count(),
                'overdue_amount': float(Invoice.objects.filter(
                    tenant=self.tenant,
                    status='OVERDUE'
                ).aggregate(total=Sum('total_amount'))['total'] or 0),
                'avg_overdue_days': self._calculate_avg_overdue_days()
            }
            
            # Customer risk distribution
            risk_distribution = self._analyze_customer_risk_distribution()
            
            # Cash flow risks
            cash_flow_risks = self._analyze_cash_flow_risks()
            
            return {
                'overdue_analysis': overdue_analysis,
                'customer_risk_distribution': risk_distribution,
                'cash_flow_risks': cash_flow_risks,
                'overall_risk_score': self._calculate_overall_financial_risk()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting financial risk data: {e}")
            return {}
    
    def _collect_cash_flow_data(self) -> Dict[str, Any]:
        """Collect cash flow insights."""
        try:
            from apps.finance.services.ai_cash_flow_forecasting import AICashFlowForecastingService
            
            cash_flow_service = AICashFlowForecastingService(self.tenant)
            
            # Get current cash flow forecast
            forecast = cash_flow_service.generate_cash_flow_forecast(
                forecast_months=6,
                scenarios=['most_likely', 'optimistic', 'pessimistic']
            )
            
            # Extract key insights
            cash_flow_insights = {
                'current_runway_months': forecast.get('runway_analysis', {}).get('months_of_runway', 0),
                'seasonal_variations': forecast.get('seasonal_analysis', {}),
                'stress_test_results': forecast.get('stress_testing', {}),
                'confidence_intervals': forecast.get('confidence_analysis', {}),
                'key_risk_factors': forecast.get('risk_assessment', {}).get('primary_risks', [])
            }
            
            return cash_flow_insights
            
        except Exception as e:
            self.logger.error(f"Error collecting cash flow data: {e}")
            return {}
    
    def _collect_payment_behavior_data(self) -> Dict[str, Any]:
        """Collect payment behavior patterns."""
        try:
            from apps.finance.models.payments import Payment
            from apps.finance.models.invoicing import Invoice
            
            # Payment method preferences
            payment_methods = Payment.objects.filter(
                tenant=self.tenant
            ).values('payment_method').annotate(
                count=Count('id'),
                avg_amount=Avg('amount')
            )
            
            # Payment timing patterns
            payment_timing = self._analyze_payment_timing_patterns()
            
            # Success rates by method
            success_rates = self._calculate_payment_success_rates()
            
            return {
                'payment_methods': list(payment_methods),
                'timing_patterns': payment_timing,
                'success_rates': success_rates,
                'fraud_indicators': self._detect_payment_fraud_patterns()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting payment behavior data: {e}")
            return {}
    
    # ==================== Cross-Module Integration ====================
    
    def share_data_with_crm(self, customer_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Share finance data with CRM module."""
        try:
            shared_count = 0
            
            for customer_info in customer_data:
                # Create or update shared AI data
                self._store_shared_data_point(
                    module='finance',
                    entity_type='customer',
                    entity_id=customer_info['customer_id'],
                    data_type='financial_profile',
                    value=customer_info,
                    confidence=0.95
                )
                shared_count += 1
            
            # Generate CRM insights
            crm_insights = self._generate_crm_finance_insights(customer_data)
            
            return {
                'success': True,
                'shared_records': shared_count,
                'insights_generated': len(crm_insights),
                'insights': crm_insights
            }
            
        except Exception as e:
            self.logger.error(f"Error sharing data with CRM: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def share_data_with_inventory(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Share finance data with inventory module."""
        try:
            # Share revenue patterns for demand forecasting
            revenue_patterns = financial_data.get('revenue_patterns', {})
            
            self._store_shared_data_point(
                module='finance',
                entity_type='global',
                entity_id=0,
                data_type='revenue_patterns',
                value=revenue_patterns,
                confidence=0.90
            )
            
            # Share customer purchasing power data
            customer_purchasing_power = self._calculate_customer_purchasing_power()
            
            self._store_shared_data_point(
                module='finance',
                entity_type='global',
                entity_id=0,
                data_type='customer_purchasing_power',
                value=customer_purchasing_power,
                confidence=0.85
            )
            
            # Generate inventory insights
            inventory_insights = self._generate_inventory_finance_insights(financial_data)
            
            return {
                'success': True,
                'shared_data_types': ['revenue_patterns', 'customer_purchasing_power'],
                'insights_generated': len(inventory_insights),
                'insights': inventory_insights
            }
            
        except Exception as e:
            self.logger.error(f"Error sharing data with inventory: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def share_data_with_ecommerce(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Share finance data with e-commerce module."""
        try:
            # Share payment behavior for checkout optimization
            payment_behavior = financial_data.get('payment_behavior', {})
            
            self._store_shared_data_point(
                module='finance',
                entity_type='global',
                entity_id=0,
                data_type='payment_behavior',
                value=payment_behavior,
                confidence=0.92
            )
            
            # Share customer financial profiles for personalization
            customer_profiles = financial_data.get('customer_financial_profiles', [])
            
            for profile in customer_profiles:
                self._store_shared_data_point(
                    module='finance',
                    entity_type='customer',
                    entity_id=profile['customer_id'],
                    data_type='purchasing_capacity',
                    value={
                        'avg_order_value': profile['avg_invoice_value'],
                        'payment_reliability': profile['payment_rate'],
                        'lifetime_value': profile['lifetime_value'],
                        'risk_level': 'low' if profile['risk_score'] < 30 else 'medium' if profile['risk_score'] < 70 else 'high'
                    },
                    confidence=0.88
                )
            
            # Generate e-commerce insights
            ecommerce_insights = self._generate_ecommerce_finance_insights(financial_data)
            
            return {
                'success': True,
                'shared_customer_profiles': len(customer_profiles),
                'insights_generated': len(ecommerce_insights),
                'insights': ecommerce_insights
            }
            
        except Exception as e:
            self.logger.error(f"Error sharing data with e-commerce: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==================== Cross-Module Insight Generation ====================
    
    def _generate_crm_finance_insights(self, customer_data: List[Dict[str, Any]]) -> List[CrossModuleInsight]:
        """Generate insights for CRM-Finance integration."""
        insights = []
        
        try:
            # High-value customer insight
            high_value_customers = [c for c in customer_data if c['lifetime_value'] > 50000]
            if high_value_customers:
                insights.append(CrossModuleInsight(
                    insight_type='high_value_customers',
                    primary_module='finance',
                    related_modules=['crm'],
                    confidence=0.95,
                    data={
                        'count': len(high_value_customers),
                        'avg_ltv': sum(c['lifetime_value'] for c in high_value_customers) / len(high_value_customers),
                        'customer_ids': [c['customer_id'] for c in high_value_customers]
                    },
                    recommendations=[
                        'Prioritize these customers in CRM for premium support',
                        'Create VIP customer segments in marketing campaigns',
                        'Assign dedicated account managers'
                    ],
                    impact_score=8.5
                ))
            
            # At-risk customer insight
            at_risk_customers = [c for c in customer_data if c['risk_score'] > 70]
            if at_risk_customers:
                insights.append(CrossModuleInsight(
                    insight_type='at_risk_customers',
                    primary_module='finance',
                    related_modules=['crm'],
                    confidence=0.88,
                    data={
                        'count': len(at_risk_customers),
                        'total_revenue_at_risk': sum(c['total_revenue'] for c in at_risk_customers),
                        'customer_ids': [c['customer_id'] for c in at_risk_customers]
                    },
                    recommendations=[
                        'Create retention campaigns for these customers',
                        'Implement payment reminder workflows',
                        'Offer payment plan options'
                    ],
                    impact_score=7.2
                ))
            
            # Payment behavior insight
            slow_payers = [c for c in customer_data if c['avg_payment_days'] > 45]
            if slow_payers:
                insights.append(CrossModuleInsight(
                    insight_type='slow_payment_customers',
                    primary_module='finance',
                    related_modules=['crm'],
                    confidence=0.92,
                    data={
                        'count': len(slow_payers),
                        'avg_payment_delay': sum(c['avg_payment_days'] for c in slow_payers) / len(slow_payers),
                        'customer_ids': [c['customer_id'] for c in slow_payers]
                    },
                    recommendations=[
                        'Adjust payment terms for these customers',
                        'Implement early payment incentives',
                        'Increase follow-up frequency'
                    ],
                    impact_score=6.8
                ))
            
        except Exception as e:
            self.logger.error(f"Error generating CRM-Finance insights: {e}")
        
        return insights
    
    def _generate_inventory_finance_insights(self, financial_data: Dict[str, Any]) -> List[CrossModuleInsight]:
        """Generate insights for Inventory-Finance integration."""
        insights = []
        
        try:
            revenue_patterns = financial_data.get('revenue_patterns', {})
            
            if revenue_patterns.get('seasonal_patterns'):
                insights.append(CrossModuleInsight(
                    insight_type='seasonal_demand_correlation',
                    primary_module='finance',
                    related_modules=['inventory'],
                    confidence=0.85,
                    data={
                        'seasonal_patterns': revenue_patterns['seasonal_patterns'],
                        'peak_quarters': [p for p in revenue_patterns['seasonal_patterns'] if p.get('total_revenue', 0) > 0]
                    },
                    recommendations=[
                        'Adjust inventory levels based on revenue seasonality',
                        'Plan procurement around peak revenue periods',
                        'Optimize working capital for seasonal variations'
                    ],
                    impact_score=7.5
                ))
            
            # Cash flow correlation with inventory
            cash_flow_data = financial_data.get('cash_flow_insights', {})
            if cash_flow_data.get('current_runway_months', 0) < 6:
                insights.append(CrossModuleInsight(
                    insight_type='inventory_cash_flow_risk',
                    primary_module='finance',
                    related_modules=['inventory'],
                    confidence=0.90,
                    data={
                        'runway_months': cash_flow_data.get('current_runway_months', 0),
                        'risk_factors': cash_flow_data.get('key_risk_factors', [])
                    },
                    recommendations=[
                        'Reduce slow-moving inventory to improve cash flow',
                        'Implement just-in-time inventory management',
                        'Negotiate extended payment terms with suppliers'
                    ],
                    impact_score=8.2
                ))
            
        except Exception as e:
            self.logger.error(f"Error generating Inventory-Finance insights: {e}")
        
        return insights
    
    def _generate_ecommerce_finance_insights(self, financial_data: Dict[str, Any]) -> List[CrossModuleInsight]:
        """Generate insights for E-commerce-Finance integration."""
        insights = []
        
        try:
            payment_behavior = financial_data.get('payment_behavior', {})
            
            # Payment method optimization
            if payment_behavior.get('payment_methods'):
                top_method = max(payment_behavior['payment_methods'], key=lambda x: x['count'])
                insights.append(CrossModuleInsight(
                    insight_type='payment_method_optimization',
                    primary_module='finance',
                    related_modules=['ecommerce'],
                    confidence=0.88,
                    data={
                        'preferred_method': top_method,
                        'success_rates': payment_behavior.get('success_rates', {}),
                        'fraud_indicators': payment_behavior.get('fraud_indicators', [])
                    },
                    recommendations=[
                        f'Promote {top_method["payment_method"]} as primary payment option',
                        'Implement fraud detection for high-risk payment patterns',
                        'Optimize checkout flow for preferred payment methods'
                    ],
                    impact_score=7.8
                ))
            
            # Customer segmentation insight
            customer_profiles = financial_data.get('customer_financial_profiles', [])
            if customer_profiles:
                high_ltv_count = len([c for c in customer_profiles if c['lifetime_value'] > 10000])
                insights.append(CrossModuleInsight(
                    insight_type='customer_value_segmentation',
                    primary_module='finance',
                    related_modules=['ecommerce'],
                    confidence=0.92,
                    data={
                        'high_value_customers': high_ltv_count,
                        'avg_order_values': [c['avg_invoice_value'] for c in customer_profiles],
                        'payment_reliability': [c['payment_rate'] for c in customer_profiles]
                    },
                    recommendations=[
                        'Create tiered pricing for high-value customers',
                        'Implement personalized product recommendations',
                        'Offer premium services to high LTV customers'
                    ],
                    impact_score=8.1
                ))
            
        except Exception as e:
            self.logger.error(f"Error generating E-commerce-Finance insights: {e}")
        
        return insights
    
    # ==================== Helper Methods ====================
    
    def _store_shared_data_point(self, module: str, entity_type: str, entity_id: int,
                               data_type: str, value: Any, confidence: float) -> None:
        """Store shared AI data point."""
        try:
            cache_key = f"ai_data:{self.tenant.schema_name}:{module}:{entity_type}:{entity_id}:{data_type}"
            
            data_point = AIDataPoint(
                module=module,
                entity_type=entity_type,
                entity_id=entity_id,
                data_type=data_type,
                value=value,
                confidence=confidence
            )
            
            # Store in cache with JSON serialization
            cache.set(
                cache_key,
                json.dumps(data_point.__dict__, cls=DjangoJSONEncoder),
                timeout=self.cache_timeout
            )
            
        except Exception as e:
            self.logger.error(f"Error storing shared data point: {e}")
    
    def _calculate_avg_payment_time(self, customer_id: int) -> float:
        """Calculate average payment time for customer."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            paid_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                customer_id=customer_id,
                status='PAID',
                paid_date__isnull=False
            )
            
            total_days = 0
            count = 0
            
            for invoice in paid_invoices:
                if invoice.due_date and invoice.paid_date:
                    days = (invoice.paid_date - invoice.due_date).days
                    total_days += max(days, 0)  # Don't count early payments as negative
                    count += 1
            
            return total_days / count if count > 0 else 0
            
        except Exception as e:
            self.logger.error(f"Error calculating average payment time: {e}")
            return 0
    
    def _calculate_customer_risk_score(self, customer_id: int) -> float:
        """Calculate customer risk score."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            # Base factors for risk calculation
            overdue_count = Invoice.objects.filter(
                tenant=self.tenant,
                customer_id=customer_id,
                status='OVERDUE'
            ).count()
            
            total_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                customer_id=customer_id
            ).count()
            
            avg_payment_days = self._calculate_avg_payment_time(customer_id)
            
            # Calculate risk score (0-100)
            risk_score = 0
            
            if total_invoices > 0:
                overdue_rate = (overdue_count / total_invoices) * 100
                risk_score += min(overdue_rate * 0.6, 60)  # Max 60 points for overdue rate
            
            # Payment delay factor
            if avg_payment_days > 30:
                risk_score += min((avg_payment_days - 30) * 0.5, 30)  # Max 30 points for delays
            
            # Recent activity factor
            recent_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                customer_id=customer_id,
                created_at__gte=timezone.now() - timedelta(days=90)
            ).count()
            
            if recent_invoices == 0:
                risk_score += 10  # Inactivity adds risk
            
            return min(risk_score, 100)
            
        except Exception as e:
            self.logger.error(f"Error calculating customer risk score: {e}")
            return 50  # Default medium risk
    
    def _calculate_customer_ltv(self, customer_id: int) -> float:
        """Calculate customer lifetime value."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            customer_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                customer_id=customer_id,
                status='PAID'
            )
            
            if not customer_invoices.exists():
                return 0
            
            total_revenue = customer_invoices.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0')
            
            # Simple LTV calculation - could be enhanced with more sophisticated modeling
            return float(total_revenue)
            
        except Exception as e:
            self.logger.error(f"Error calculating customer LTV: {e}")
            return 0
    
    def _calculate_revenue_growth_rate(self) -> float:
        """Calculate revenue growth rate."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            current_month = timezone.now().replace(day=1)
            last_month = (current_month - timedelta(days=1)).replace(day=1)
            
            current_revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID',
                paid_date__gte=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            last_revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID',
                paid_date__gte=last_month,
                paid_date__lt=current_month
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            if last_revenue > 0:
                growth_rate = ((current_revenue - last_revenue) / last_revenue) * 100
                return float(growth_rate)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error calculating revenue growth rate: {e}")
            return 0
    
    def _identify_revenue_factors(self) -> List[str]:
        """Identify key revenue driving factors."""
        factors = []
        
        try:
            from apps.finance.models.invoicing import Invoice
            
            # Top customers by revenue
            top_customers = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID'
            ).values('customer_id').annotate(
                revenue=Sum('total_amount')
            ).order_by('-revenue')[:5]
            
            if top_customers:
                factors.append(f"Top {len(top_customers)} customers contribute significant revenue")
            
            # Seasonal patterns
            current_quarter = (timezone.now().month - 1) // 3 + 1
            quarter_revenue = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID',
                paid_date__year=timezone.now().year
            ).extra(
                select={'quarter': "EXTRACT('quarter' FROM paid_date)"}
            ).values('quarter').annotate(
                revenue=Sum('total_amount')
            )
            
            if quarter_revenue:
                factors.append("Seasonal revenue patterns detected")
            
        except Exception as e:
            self.logger.error(f"Error identifying revenue factors: {e}")
        
        return factors
    
    def _calculate_avg_overdue_days(self) -> float:
        """Calculate average overdue days."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            overdue_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                status='OVERDUE',
                due_date__isnull=False
            )
            
            total_days = 0
            count = 0
            
            for invoice in overdue_invoices:
                days_overdue = (timezone.now().date() - invoice.due_date).days
                total_days += days_overdue
                count += 1
            
            return total_days / count if count > 0 else 0
            
        except Exception as e:
            self.logger.error(f"Error calculating average overdue days: {e}")
            return 0
    
    def _analyze_customer_risk_distribution(self) -> Dict[str, int]:
        """Analyze customer risk distribution."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            customers = Invoice.objects.filter(
                tenant=self.tenant
            ).values('customer_id').distinct()
            
            risk_distribution = {'low': 0, 'medium': 0, 'high': 0}
            
            for customer in customers:
                risk_score = self._calculate_customer_risk_score(customer['customer_id'])
                if risk_score < 30:
                    risk_distribution['low'] += 1
                elif risk_score < 70:
                    risk_distribution['medium'] += 1
                else:
                    risk_distribution['high'] += 1
            
            return risk_distribution
            
        except Exception as e:
            self.logger.error(f"Error analyzing customer risk distribution: {e}")
            return {'low': 0, 'medium': 0, 'high': 0}
    
    def _analyze_cash_flow_risks(self) -> List[str]:
        """Analyze cash flow risks."""
        risks = []
        
        try:
            from apps.finance.models.invoicing import Invoice
            
            # High accounts receivable
            ar_total = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['SENT', 'OVERDUE']
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            if ar_total > 100000:  # Configurable threshold
                risks.append("High accounts receivable balance")
            
            # Too many overdue invoices
            overdue_count = Invoice.objects.filter(
                tenant=self.tenant,
                status='OVERDUE'
            ).count()
            
            if overdue_count > 10:  # Configurable threshold
                risks.append("High number of overdue invoices")
            
            # Concentration risk
            customer_concentration = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID'
            ).values('customer_id').annotate(
                revenue=Sum('total_amount')
            ).order_by('-revenue')[:1]
            
            if customer_concentration:
                total_revenue = Invoice.objects.filter(
                    tenant=self.tenant,
                    status='PAID'
                ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
                
                if total_revenue > 0:
                    concentration_pct = (customer_concentration[0]['revenue'] / total_revenue) * 100
                    if concentration_pct > 30:
                        risks.append("High customer concentration risk")
            
        except Exception as e:
            self.logger.error(f"Error analyzing cash flow risks: {e}")
        
        return risks
    
    def _calculate_overall_financial_risk(self) -> float:
        """Calculate overall financial risk score."""
        try:
            risk_factors = 0
            total_weight = 0
            
            # Overdue invoice factor
            from apps.finance.models.invoicing import Invoice
            
            total_invoices = Invoice.objects.filter(tenant=self.tenant).count()
            overdue_invoices = Invoice.objects.filter(tenant=self.tenant, status='OVERDUE').count()
            
            if total_invoices > 0:
                overdue_rate = (overdue_invoices / total_invoices) * 100
                risk_factors += overdue_rate * 0.4
                total_weight += 0.4
            
            # Cash flow factor
            ar_total = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['SENT', 'OVERDUE']
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            revenue_total = Invoice.objects.filter(
                tenant=self.tenant,
                status='PAID'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            if revenue_total > 0:
                ar_ratio = (ar_total / revenue_total) * 100
                risk_factors += min(ar_ratio, 100) * 0.3
                total_weight += 0.3
            
            # Customer risk factor
            risk_distribution = self._analyze_customer_risk_distribution()
            total_customers = sum(risk_distribution.values())
            
            if total_customers > 0:
                high_risk_pct = (risk_distribution['high'] / total_customers) * 100
                risk_factors += high_risk_pct * 0.3
                total_weight += 0.3
            
            return risk_factors / total_weight if total_weight > 0 else 0
            
        except Exception as e:
            self.logger.error(f"Error calculating overall financial risk: {e}")
            return 50  # Default medium risk
    
    def _analyze_payment_timing_patterns(self) -> Dict[str, Any]:
        """Analyze payment timing patterns."""
        try:
            from apps.finance.models.payments import Payment
            
            # Payment by day of week
            day_patterns = Payment.objects.filter(
                tenant=self.tenant
            ).extra(
                select={'day_of_week': "EXTRACT('dow' FROM payment_date)"}
            ).values('day_of_week').annotate(
                count=Count('id'),
                avg_amount=Avg('amount')
            )
            
            # Payment by hour (if time data available)
            time_patterns = Payment.objects.filter(
                tenant=self.tenant
            ).extra(
                select={'hour': "EXTRACT('hour' FROM created_at)"}
            ).values('hour').annotate(
                count=Count('id')
            )
            
            return {
                'day_of_week_patterns': list(day_patterns),
                'time_patterns': list(time_patterns),
                'peak_payment_day': max(day_patterns, key=lambda x: x['count'])['day_of_week'] if day_patterns else None,
                'peak_payment_hour': max(time_patterns, key=lambda x: x['count'])['hour'] if time_patterns else None
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing payment timing patterns: {e}")
            return {}
    
    def _calculate_payment_success_rates(self) -> Dict[str, float]:
        """Calculate payment success rates by method."""
        try:
            from apps.finance.models.payments import Payment
            
            success_rates = {}
            
            payment_methods = Payment.objects.filter(
                tenant=self.tenant
            ).values('payment_method').distinct()
            
            for method in payment_methods:
                method_name = method['payment_method']
                
                total_payments = Payment.objects.filter(
                    tenant=self.tenant,
                    payment_method=method_name
                ).count()
                
                successful_payments = Payment.objects.filter(
                    tenant=self.tenant,
                    payment_method=method_name,
                    status='COMPLETED'
                ).count()
                
                if total_payments > 0:
                    success_rates[method_name] = (successful_payments / total_payments) * 100
            
            return success_rates
            
        except Exception as e:
            self.logger.error(f"Error calculating payment success rates: {e}")
            return {}
    
    def _detect_payment_fraud_patterns(self) -> List[str]:
        """Detect potential payment fraud patterns."""
        fraud_indicators = []
        
        try:
            from apps.finance.models.payments import Payment
            
            # Multiple failed payments from same source
            failed_patterns = Payment.objects.filter(
                tenant=self.tenant,
                status='FAILED'
            ).values('payment_method', 'reference').annotate(
                fail_count=Count('id')
            ).filter(fail_count__gte=3)
            
            if failed_patterns.exists():
                fraud_indicators.append("Multiple failed payments detected")
            
            # Unusual payment amounts
            avg_payment = Payment.objects.filter(
                tenant=self.tenant,
                status='COMPLETED'
            ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
            
            if avg_payment > 0:
                unusual_payments = Payment.objects.filter(
                    tenant=self.tenant,
                    amount__gt=avg_payment * 10  # 10x average
                ).count()
                
                if unusual_payments > 0:
                    fraud_indicators.append("Unusually large payments detected")
            
            # Rapid successive payments
            recent_payments = Payment.objects.filter(
                tenant=self.tenant,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_payments > 10:  # Configurable threshold
                fraud_indicators.append("High frequency payments detected")
            
        except Exception as e:
            self.logger.error(f"Error detecting fraud patterns: {e}")
        
        return fraud_indicators
    
    def _calculate_customer_purchasing_power(self) -> Dict[str, Any]:
        """Calculate customer purchasing power data."""
        try:
            from apps.finance.models.invoicing import Invoice
            
            customer_power = {}
            
            customers = Invoice.objects.filter(
                tenant=self.tenant
            ).values('customer_id').annotate(
                total_spent=Sum('total_amount'),
                avg_order=Avg('total_amount'),
                order_frequency=Count('id')
            )
            
            for customer in customers:
                customer_power[customer['customer_id']] = {
                    'total_spent': float(customer['total_spent'] or 0),
                    'avg_order_value': float(customer['avg_order'] or 0),
                    'order_frequency': customer['order_frequency'],
                    'purchasing_power_score': self._calculate_purchasing_power_score(customer)
                }
            
            return customer_power
            
        except Exception as e:
            self.logger.error(f"Error calculating customer purchasing power: {e}")
            return {}
    
    def _calculate_purchasing_power_score(self, customer_data: Dict[str, Any]) -> float:
        """Calculate purchasing power score for customer."""
        try:
            total_spent = customer_data.get('total_spent', 0)
            avg_order = customer_data.get('avg_order', 0)
            frequency = customer_data.get('order_frequency', 0)
            
            # Normalize and weight the factors
            score = 0
            
            # Total spent factor (40% weight)
            if total_spent > 0:
                score += min(total_spent / 10000, 1) * 40  # Normalize to 10k
            
            # Average order value factor (30% weight)
            if avg_order > 0:
                score += min(avg_order / 1000, 1) * 30  # Normalize to 1k
            
            # Frequency factor (30% weight)
            if frequency > 0:
                score += min(frequency / 50, 1) * 30  # Normalize to 50 orders
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating purchasing power score: {e}")
            return 0
    
    # ==================== Main Integration Method ====================
    
    def execute_complete_data_sharing(self) -> Dict[str, Any]:
        """Execute complete cross-module AI data sharing."""
        try:
            results = {}
            
            # Collect finance AI data
            finance_data = self.collect_finance_ai_data()
            
            if finance_data['success']:
                data = finance_data['data']
                
                # Share with each module
                results['crm_sharing'] = self.share_data_with_crm(
                    data.get('customer_financial_profiles', [])
                )
                
                results['inventory_sharing'] = self.share_data_with_inventory(data)
                
                results['ecommerce_sharing'] = self.share_data_with_ecommerce(data)
                
                # Generate comprehensive insights
                all_insights = []
                for module_result in results.values():
                    if module_result.get('success') and module_result.get('insights'):
                        all_insights.extend(module_result['insights'])
                
                return {
                    'success': True,
                    'modules_processed': len(results),
                    'total_insights': len(all_insights),
                    'sharing_results': results,
                    'cross_module_insights': all_insights,
                    'execution_timestamp': timezone.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to collect finance AI data',
                    'details': finance_data
                }
                
        except Exception as e:
            self.logger.error(f"Error executing complete data sharing: {e}")
            return {
                'success': False,
                'error': str(e)
            }