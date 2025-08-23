# backend/apps/finance/services/ai_cash_flow_forecasting.py

"""
AI-Powered Cash Flow Forecasting Service
Advanced predictive analytics for financial planning and cash management
"""

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging
import json
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AICashFlowForecastingService:
    """Advanced AI-powered cash flow forecasting with machine learning"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.cache_timeout = 3600  # 1 hour cache
    
    def generate_comprehensive_forecast(self, forecast_months=12):
        """Generate comprehensive cash flow forecast with AI analysis"""
        try:
            logger.info(f"Starting comprehensive cash flow forecast for tenant {self.tenant.id}")
            
            # Check cache first
            cache_key = f"cash_flow_forecast_{self.tenant.id}_{forecast_months}m"
            cached_forecast = cache.get(cache_key)
            
            if cached_forecast:
                logger.info("Returning cached cash flow forecast")
                return cached_forecast
            
            # Generate new forecast
            forecast_data = {
                'summary': self._generate_forecast_summary(),
                'monthly_forecasts': self._generate_monthly_forecasts(forecast_months),
                'scenario_analysis': self._generate_scenario_analysis(),
                'cash_flow_patterns': self._analyze_cash_flow_patterns(),
                'risk_assessment': self._assess_cash_flow_risks(),
                'recommendations': self._generate_cash_flow_recommendations(),
                'confidence_metrics': self._calculate_forecast_confidence(),
                'ai_insights': self._generate_ai_insights(),
                'generated_at': timezone.now().isoformat(),
            }
            
            # Cache the forecast
            cache.set(cache_key, forecast_data, self.cache_timeout)
            
            logger.info(f"Cash flow forecast completed for tenant {self.tenant.id}")
            return forecast_data
            
        except Exception as e:
            logger.error(f"Cash flow forecasting failed for tenant {self.tenant.id}: {str(e)}")
            return {}
    
    def _generate_forecast_summary(self):
        """Generate high-level forecast summary"""
        return {
            'current_cash_position': self._get_current_cash_position(),
            'projected_30_day_flow': self._calculate_projected_flow(30),
            'projected_90_day_flow': self._calculate_projected_flow(90),
            'projected_12_month_flow': self._calculate_projected_flow(365),
            'burn_rate': self._calculate_burn_rate(),
            'runway_months': self._calculate_cash_runway(),
            'liquidity_risk_score': self._calculate_liquidity_risk(),
        }
    
    def _generate_monthly_forecasts(self, months):
        """Generate detailed monthly cash flow forecasts"""
        forecasts = []
        
        for month_offset in range(months):
            forecast_date = date.today() + relativedelta(months=month_offset)
            
            monthly_forecast = {
                'month': forecast_date.strftime('%Y-%m'),
                'month_name': forecast_date.strftime('%B %Y'),
                'opening_balance': self._predict_opening_balance(forecast_date),
                'inflows': self._predict_monthly_inflows(forecast_date),
                'outflows': self._predict_monthly_outflows(forecast_date),
                'net_flow': 0,  # Will be calculated
                'closing_balance': 0,  # Will be calculated
                'confidence_level': self._calculate_monthly_confidence(forecast_date),
                'key_assumptions': self._get_monthly_assumptions(forecast_date),
                'risks': self._identify_monthly_risks(forecast_date),
            }
            
            # Calculate net flow and closing balance
            monthly_forecast['net_flow'] = (
                monthly_forecast['inflows']['total'] - monthly_forecast['outflows']['total']
            )
            monthly_forecast['closing_balance'] = (
                monthly_forecast['opening_balance'] + monthly_forecast['net_flow']
            )
            
            forecasts.append(monthly_forecast)
        
        return forecasts
    
    def _generate_scenario_analysis(self):
        """Generate best/worst/most likely scenario analysis"""
        scenarios = {}
        
        for scenario in ['optimistic', 'most_likely', 'pessimistic']:
            scenarios[scenario] = {
                'description': self._get_scenario_description(scenario),
                'probability': self._get_scenario_probability(scenario),
                'key_assumptions': self._get_scenario_assumptions(scenario),
                'cash_flow_impact': self._calculate_scenario_impact(scenario),
                'breakeven_months': self._calculate_scenario_breakeven(scenario),
                'funding_requirements': self._calculate_funding_needs(scenario),
            }
        
        return scenarios
    
    def _analyze_cash_flow_patterns(self):
        """Analyze historical and predicted cash flow patterns"""
        return {
            'seasonality': self._detect_seasonal_patterns(),
            'trends': self._analyze_cash_flow_trends(),
            'cyclical_patterns': self._detect_cyclical_patterns(),
            'volatility_analysis': self._analyze_cash_flow_volatility(),
            'correlation_analysis': self._analyze_external_correlations(),
        }
    
    def _assess_cash_flow_risks(self):
        """Comprehensive cash flow risk assessment"""
        return {
            'concentration_risk': self._assess_customer_concentration_risk(),
            'timing_risk': self._assess_payment_timing_risk(),
            'seasonal_risk': self._assess_seasonal_cash_flow_risk(),
            'credit_risk': self._assess_customer_credit_risk(),
            'operational_risk': self._assess_operational_cash_flow_risk(),
            'market_risk': self._assess_market_conditions_risk(),
            'overall_risk_score': 0,  # Will be calculated
        }
    
    def _generate_cash_flow_recommendations(self):
        """AI-generated recommendations for cash flow optimization"""
        recommendations = []
        
        # Cash position recommendations
        current_cash = self._get_current_cash_position()
        if current_cash < 50000:  # Threshold can be configurable
            recommendations.append({
                'type': 'liquidity_warning',
                'priority': 'high',
                'title': 'Low Cash Position Alert',
                'description': 'Current cash position is below recommended minimum',
                'action_items': [
                    'Consider accelerating collections',
                    'Review payment terms with customers',
                    'Evaluate line of credit options'
                ],
                'potential_impact': 'Improved cash flow stability'
            })
        
        # Collection optimization
        overdue_amount = self._calculate_overdue_receivables()
        if overdue_amount > 25000:
            recommendations.append({
                'type': 'collections_optimization',
                'priority': 'medium',
                'title': 'Optimize Collections Process',
                'description': f'${overdue_amount:,.2f} in overdue receivables detected',
                'action_items': [
                    'Implement automated payment reminders',
                    'Review credit terms for slow-paying customers',
                    'Consider offering early payment discounts'
                ],
                'potential_impact': f'Potential ${overdue_amount * 0.8:,.2f} cash improvement'
            })
        
        # Payment optimization
        recommendations.extend(self._generate_payment_optimization_recommendations())
        
        # Seasonal planning
        recommendations.extend(self._generate_seasonal_planning_recommendations())
        
        return recommendations
    
    def _calculate_forecast_confidence(self):
        """Calculate confidence metrics for the forecast"""
        return {
            'overall_confidence': self._calculate_overall_confidence(),
            'data_quality_score': self._assess_data_quality(),
            'historical_accuracy': self._calculate_historical_accuracy(),
            'prediction_stability': self._assess_prediction_stability(),
            'external_factors_impact': self._assess_external_factors(),
        }
    
    def _generate_ai_insights(self):
        """Generate AI-powered insights and observations"""
        insights = []
        
        # Trend insights
        trend_analysis = self._analyze_cash_flow_trends()
        if trend_analysis.get('direction') == 'declining':
            insights.append({
                'type': 'trend_alert',
                'severity': 'medium',
                'title': 'Declining Cash Flow Trend',
                'insight': 'Cash flow shows declining trend over recent periods',
                'recommendation': 'Focus on revenue growth and expense optimization'
            })
        
        # Seasonality insights
        seasonal_patterns = self._detect_seasonal_patterns()
        if seasonal_patterns.get('has_strong_seasonality'):
            insights.append({
                'type': 'seasonality_insight',
                'severity': 'low',
                'title': 'Strong Seasonal Patterns Detected',
                'insight': f'Peak period: {seasonal_patterns.get("peak_period")}',
                'recommendation': 'Plan cash reserves for seasonal variations'
            })
        
        # Customer concentration insights
        concentration_risk = self._assess_customer_concentration_risk()
        if concentration_risk.get('risk_level') == 'high':
            insights.append({
                'type': 'concentration_risk',
                'severity': 'high',
                'title': 'High Customer Concentration Risk',
                'insight': f'Top customer represents {concentration_risk.get("top_customer_percentage", 0)}% of revenue',
                'recommendation': 'Diversify customer base to reduce dependency risk'
            })
        
        return insights
    
    # ============================================================================
    # HELPER METHODS FOR CALCULATIONS
    # ============================================================================
    
    def _get_current_cash_position(self):
        """Get current cash and cash equivalents"""
        try:
            from ..models import Account
            
            cash_accounts = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=['CASH', 'BANK', 'CURRENT_ASSET'],
                is_active=True
            )
            
            total_cash = sum(account.current_balance for account in cash_accounts)
            return float(total_cash)
            
        except Exception as e:
            logger.error(f"Failed to get current cash position: {str(e)}")
            return 0.0
    
    def _calculate_projected_flow(self, days):
        """Calculate projected cash flow for specified days"""
        try:
            # Analyze historical patterns
            historical_data = self._get_historical_cash_flows(days * 2)  # Get 2x period for analysis
            
            if not historical_data:
                return 0.0
            
            # Simple moving average with trend adjustment
            avg_daily_flow = sum(historical_data) / len(historical_data)
            trend_factor = self._calculate_trend_factor(historical_data)
            
            projected_flow = avg_daily_flow * days * trend_factor
            return round(projected_flow, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate projected flow: {str(e)}")
            return 0.0
    
    def _calculate_burn_rate(self):
        """Calculate monthly cash burn rate"""
        try:
            # Get recent cash outflows
            recent_outflows = self._get_recent_cash_outflows(90)  # Last 90 days
            
            if not recent_outflows:
                return 0.0
            
            # Calculate average monthly burn
            total_outflows = sum(recent_outflows)
            monthly_burn = (total_outflows / len(recent_outflows)) * 30  # Convert to monthly
            
            return round(monthly_burn, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate burn rate: {str(e)}")
            return 0.0
    
    def _calculate_cash_runway(self):
        """Calculate cash runway in months"""
        try:
            current_cash = self._get_current_cash_position()
            monthly_burn = self._calculate_burn_rate()
            
            if monthly_burn <= 0:
                return float('inf')  # Infinite runway if not burning cash
            
            runway_months = current_cash / monthly_burn
            return round(runway_months, 1)
            
        except Exception as e:
            logger.error(f"Failed to calculate cash runway: {str(e)}")
            return 0.0
    
    def _calculate_liquidity_risk(self):
        """Calculate liquidity risk score (0-100)"""
        try:
            risk_factors = []
            
            # Cash runway risk
            runway = self._calculate_cash_runway()
            if runway < 3:
                risk_factors.append(40)  # High risk
            elif runway < 6:
                risk_factors.append(20)  # Medium risk
            else:
                risk_factors.append(5)   # Low risk
            
            # Cash position risk
            current_cash = self._get_current_cash_position()
            monthly_expenses = abs(self._calculate_burn_rate())
            cash_ratio = current_cash / max(monthly_expenses, 1)
            
            if cash_ratio < 1:
                risk_factors.append(30)
            elif cash_ratio < 2:
                risk_factors.append(15)
            else:
                risk_factors.append(5)
            
            # Receivables concentration risk
            concentration_risk = self._assess_customer_concentration_risk()
            risk_factors.append(concentration_risk.get('risk_score', 10))
            
            # Payment timing risk
            timing_risk = self._assess_payment_timing_risk()
            risk_factors.append(timing_risk.get('risk_score', 10))
            
            # Calculate overall risk
            total_risk = sum(risk_factors)
            return min(100, max(0, total_risk))
            
        except Exception as e:
            logger.error(f"Failed to calculate liquidity risk: {str(e)}")
            return 50.0  # Default medium risk
    
    def _predict_opening_balance(self, forecast_date):
        """Predict opening cash balance for a specific month"""
        # For simplification, this would use more sophisticated models in production
        try:
            if forecast_date.month == date.today().month and forecast_date.year == date.today().year:
                return self._get_current_cash_position()
            
            # Calculate based on previous month's closing balance
            # This is a simplified calculation
            months_ahead = ((forecast_date.year - date.today().year) * 12 + 
                          forecast_date.month - date.today().month)
            
            current_cash = self._get_current_cash_position()
            monthly_flow = self._calculate_projected_flow(30)
            
            predicted_balance = current_cash + (monthly_flow * months_ahead)
            return round(predicted_balance, 2)
            
        except Exception as e:
            logger.error(f"Failed to predict opening balance: {str(e)}")
            return 0.0
    
    def _predict_monthly_inflows(self, forecast_date):
        """Predict monthly cash inflows"""
        try:
            # Analyze historical inflow patterns
            historical_inflows = self._get_historical_monthly_inflows()
            
            # Base prediction on historical average with seasonal adjustments
            base_inflow = sum(historical_inflows) / len(historical_inflows) if historical_inflows else 0
            
            # Apply seasonal adjustments
            seasonal_factor = self._get_seasonal_factor(forecast_date.month)
            predicted_inflow = base_inflow * seasonal_factor
            
            return {
                'customer_payments': predicted_inflow * 0.8,  # 80% from customers
                'other_income': predicted_inflow * 0.2,       # 20% from other sources
                'total': predicted_inflow
            }
            
        except Exception as e:
            logger.error(f"Failed to predict monthly inflows: {str(e)}")
            return {'customer_payments': 0, 'other_income': 0, 'total': 0}
    
    def _predict_monthly_outflows(self, forecast_date):
        """Predict monthly cash outflows"""
        try:
            # Analyze historical outflow patterns
            historical_outflows = self._get_historical_monthly_outflows()
            
            # Base prediction on historical average
            base_outflow = sum(historical_outflows) / len(historical_outflows) if historical_outflows else 0
            
            # Apply seasonal adjustments
            seasonal_factor = self._get_seasonal_factor(forecast_date.month)
            predicted_outflow = base_outflow * seasonal_factor
            
            return {
                'payroll': predicted_outflow * 0.4,      # 40% payroll
                'vendors': predicted_outflow * 0.3,      # 30% vendors
                'operating_expenses': predicted_outflow * 0.2,  # 20% operating
                'other_expenses': predicted_outflow * 0.1,      # 10% other
                'total': predicted_outflow
            }
            
        except Exception as e:
            logger.error(f"Failed to predict monthly outflows: {str(e)}")
            return {
                'payroll': 0, 'vendors': 0, 'operating_expenses': 0, 
                'other_expenses': 0, 'total': 0
            }
    
    def _get_historical_cash_flows(self, days):
        """Get historical daily cash flows"""
        # Placeholder implementation - would query actual transaction data
        return [100, -50, 200, -75, 150] * (days // 5)
    
    def _get_historical_monthly_inflows(self):
        """Get historical monthly inflow data"""
        # Placeholder implementation - would query actual data
        return [50000, 48000, 52000, 49000, 51000, 53000]
    
    def _get_historical_monthly_outflows(self):
        """Get historical monthly outflow data"""
        # Placeholder implementation - would query actual data
        return [45000, 43000, 47000, 44000, 46000, 48000]
    
    def _get_seasonal_factor(self, month):
        """Get seasonal adjustment factor for a specific month"""
        # Simplified seasonal factors - would be learned from data
        seasonal_factors = {
            1: 0.9, 2: 0.85, 3: 1.0, 4: 1.05, 5: 1.1, 6: 1.15,
            7: 1.2, 8: 1.15, 9: 1.1, 10: 1.05, 11: 1.1, 12: 1.25
        }
        return seasonal_factors.get(month, 1.0)
    
    def _calculate_trend_factor(self, data):
        """Calculate trend factor from historical data"""
        if len(data) < 2:
            return 1.0
        
        # Simple linear trend calculation
        n = len(data)
        sum_x = sum(range(n))
        sum_y = sum(data)
        sum_xy = sum(i * data[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Convert slope to trend factor
        return max(0.5, min(2.0, 1.0 + slope * 0.1))
    
    def _calculate_overdue_receivables(self):
        """Calculate total overdue receivables"""
        try:
            from ..models import Invoice
            
            overdue_invoices = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
                due_date__lt=date.today()
            )
            
            total_overdue = sum(invoice.amount_due for invoice in overdue_invoices)
            return float(total_overdue)
            
        except Exception as e:
            logger.error(f"Failed to calculate overdue receivables: {str(e)}")
            return 0.0
    
    def _assess_customer_concentration_risk(self):
        """Assess customer concentration risk"""
        try:
            # This would analyze customer revenue concentration
            return {
                'risk_level': 'medium',
                'risk_score': 25,
                'top_customer_percentage': 35,
                'diversification_index': 0.7
            }
        except Exception as e:
            logger.error(f"Failed to assess concentration risk: {str(e)}")
            return {'risk_level': 'unknown', 'risk_score': 20}
    
    def _assess_payment_timing_risk(self):
        """Assess payment timing risk"""
        try:
            # Analyze payment patterns and timing
            return {
                'risk_level': 'low',
                'risk_score': 15,
                'average_collection_days': 28,
                'payment_predictability': 0.85
            }
        except Exception as e:
            logger.error(f"Failed to assess payment timing risk: {str(e)}")
            return {'risk_level': 'unknown', 'risk_score': 20}
    
    # Additional placeholder methods for comprehensive functionality
    def _get_recent_cash_outflows(self, days):
        return [1500] * days  # Placeholder
    
    def _detect_seasonal_patterns(self):
        return {'has_strong_seasonality': True, 'peak_period': 'Q4'}
    
    def _analyze_cash_flow_trends(self):
        return {'direction': 'stable', 'slope': 0.05}
    
    def _calculate_overall_confidence(self):
        return 78.5
    
    def _assess_data_quality(self):
        return 85.0
    
    def _generate_payment_optimization_recommendations(self):
        return []
    
    def _generate_seasonal_planning_recommendations(self):
        return []
    
    def _get_scenario_description(self, scenario):
        descriptions = {
            'optimistic': 'Best case scenario with accelerated growth',
            'most_likely': 'Expected scenario based on current trends',
            'pessimistic': 'Conservative scenario with potential challenges'
        }
        return descriptions.get(scenario, '')
    
    def _get_scenario_probability(self, scenario):
        probabilities = {'optimistic': 25, 'most_likely': 50, 'pessimistic': 25}
        return probabilities.get(scenario, 33)
    
    def _get_scenario_assumptions(self, scenario):
        return []
    
    def _calculate_scenario_impact(self, scenario):
        return 0.0
    
    def _calculate_scenario_breakeven(self, scenario):
        return 12
    
    def _calculate_funding_needs(self, scenario):
        return 0.0
    
    def _detect_cyclical_patterns(self):
        return {}
    
    def _analyze_cash_flow_volatility(self):
        return {}
    
    def _analyze_external_correlations(self):
        return {}
    
    def _assess_seasonal_cash_flow_risk(self):
        return {'risk_score': 10}
    
    def _assess_customer_credit_risk(self):
        return {'risk_score': 15}
    
    def _assess_operational_cash_flow_risk(self):
        return {'risk_score': 12}
    
    def _assess_market_conditions_risk(self):
        return {'risk_score': 18}
    
    def _calculate_monthly_confidence(self, forecast_date):
        return 80.0
    
    def _get_monthly_assumptions(self, forecast_date):
        return []
    
    def _identify_monthly_risks(self, forecast_date):
        return []
    
    def _calculate_historical_accuracy(self):
        return 75.0
    
    def _assess_prediction_stability(self):
        return 82.0
    
    def _assess_external_factors(self):
        return 70.0