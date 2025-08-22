# ============================================================================
# backend/apps/crm/services/analytics_service.py - Advanced Analytics and ML Insights Service
# ============================================================================

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, models, connection
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField, Max, Min, StdDev
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.cache import cache
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
import logging

from .base import BaseService, ServiceException
from ..models import (
    Report, Dashboard, ReportSchedule, DataSource, CustomMetric,
    AnalyticsQuery, Insight, Forecast, Anomaly, PerformanceMetric,
    Lead, Account, Opportunity, Activity, Campaign, Ticket, Product
)

logger = logging.getLogger(__name__)


class AnalyticsException(ServiceException):
    """Analytics service specific errors"""
    pass


class MLInsightsEngine:
    """Machine Learning insights and predictions engine"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.models = {}
        self.scalers = {}
    
    def generate_sales_forecast(self, forecast_period: int = 90, 
                              confidence_level: float = 0.8) -> Dict:
        """Generate sales forecast using ML models"""
        try:
            # Get historical sales data
            historical_data = self._get_historical_sales_data()
            
            if len(historical_data) < 30:  # Need at least 30 data points
                return {
                    'forecast': [],
                    'confidence': 0,
                    'error': 'Insufficient historical data for accurate forecasting'
                }
            
            # Prepare features
            X, y = self._prepare_sales_features(historical_data)
            
            # Train model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            model.fit(X_train, y_train)
            
            # Evaluate model
            y_pred_test = model.predict(X_test)
            r2 = r2_score(y_test, y_pred_test)
            mae = mean_absolute_error(y_test, y_pred_test)
            
            # Generate future predictions
            future_features = self._generate_future_features(forecast_period)
            predictions = model.predict(future_features)
            
            # Calculate confidence intervals
            confidence_intervals = self._calculate_confidence_intervals(
                model, future_features, confidence_level
            )
            
            # Format forecast data
            forecast_data = []
            base_date = timezone.now().date()
            
            for i, prediction in enumerate(predictions):
                forecast_data.append({
                    'date': (base_date + timedelta(days=i+1)).isoformat(),
                    'predicted_value': float(prediction),
                    'lower_bound': float(confidence_intervals['lower'][i]),
                    'upper_bound': float(confidence_intervals['upper'][i])
                })
            
            return {
                'forecast': forecast_data,
                'model_performance': {
                    'r2_score': r2,
                    'mean_absolute_error': mae,
                    'confidence': min(r2, 0.95)  # Cap at 95%
                },
                'feature_importance': dict(zip(
                    ['seasonality', 'trend', 'marketing_spend', 'lead_volume'],
                    model.feature_importances_
                )),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sales forecast generation failed: {e}", exc_info=True)
            return {
                'forecast': [],
                'confidence': 0,
                'error': str(e)
            }
    
    def detect_anomalies(self, metric_type: str, lookback_days: int = 90) -> List[Dict]:
        """Detect anomalies in business metrics using ML"""
        try:
            # Get metric data
            metric_data = self._get_metric_data(metric_type, lookback_days)
            
            if len(metric_data) < 14:  # Need at least 2 weeks of data
                return []
            
            # Prepare data for anomaly detection
            features = np.array(metric_data['values']).reshape(-1, 1)
            
            # Use Isolation Forest for anomaly detection
            isolation_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_labels = isolation_forest.fit_predict(features)
            
            # Identify anomalies
            anomalies = []
            for i, (date, value, label) in enumerate(zip(
                metric_data['dates'], metric_data['values'], anomaly_labels
            )):
                if label == -1:  # Anomaly detected
                    severity = self._calculate_anomaly_severity(value, metric_data['values'])
                    anomalies.append({
                        'date': date,
                        'value': value,
                        'expected_range': {
                            'min': np.percentile(metric_data['values'], 25),
                            'max': np.percentile(metric_data['values'], 75)
                        },
                        'severity': severity,
                        'metric_type': metric_type
                    })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            return []
    
    def _get_historical_sales_data(self) -> pd.DataFrame:
        """Get historical sales data for forecasting"""
        # Get daily sales data for the past year
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
        
        # This would be adjusted based on your actual sales data structure
        sales_data = Opportunity.objects.filter(
            tenant=self.tenant,
            is_won=True,
            closed_date__range=[start_date, end_date]
        ).extra({
            'date': "DATE(closed_date)"
        }).values('date').annotate(
            daily_revenue=Sum('amount'),
            daily_count=Count('id')
        ).order_by('date')
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(list(sales_data))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # Fill missing dates with 0
            df = df.reindex(pd.date_range(start_date, end_date, freq='D'), fill_value=0)
        
        return df


class ReportEngine:
    """Advanced report generation engine"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.chart_generators = {
            'line': self._generate_line_chart,
            'bar': self._generate_bar_chart,
            'pie': self._generate_pie_chart,
            'funnel': self._generate_funnel_chart,
            'heatmap': self._generate_heatmap,
            'scatter': self._generate_scatter_plot,
            'gauge': self._generate_gauge_chart
        }
    
    def generate_report(self, report_config: Dict) -> Dict:
        """Generate comprehensive report with visualizations"""
        try:
            report_data = {
                'title': report_config.get('title', 'CRM Report'),
                'description': report_config.get('description', ''),
                'generated_at': timezone.now().isoformat(),
                'sections': []
            }
            
            # Process each section
            for section_config in report_config.get('sections', []):
                section = self._generate_report_section(section_config)
                report_data['sections'].append(section)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise AnalyticsException(f"Report generation failed: {str(e)}")
    
    def _generate_report_section(self, section_config: Dict) -> Dict:
        """Generate individual report section"""
        section_type = section_config.get('type', 'table')
        
        section_data = {
            'title': section_config.get('title', 'Section'),
            'type': section_type,
            'data': [],
            'visualization': None
        }
        
        # Get data based on section configuration
        if section_type == 'sales_overview':
            section_data.update(self._generate_sales_overview_section(section_config))
        elif section_type == 'lead_analysis':
            section_data.update(self._generate_lead_analysis_section(section_config))
        elif section_type == 'performance_metrics':
            section_data.update(self._generate_performance_metrics_section(section_config))
        elif section_type == 'custom_query':
            section_data.update(self._generate_custom_query_section(section_config))
        
        return section_data
    [Dict], config: Dict) -> str:
        """Generate line chart using Plotly"""
        fig = go.Figure()
        
        for series in config.get('series', []):
            x_values = [item[config['x_field']] for item in data]
            y_values = [item[series['y_field']] for item in data]
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines+markers',
                name=series.get('name', series['y_field'])
            ))
        
        fig.update_layout(
            title=config.get('title', 'Line Chart'),
            xaxis_title=config.get('x_title', 'X Axis'),
            yaxis_title=config.get('y_title', 'Y Axis')
        )
        
        return json.dumps(fig, cls=PlotlyJSONEncoder)


class DashboardEngine:
    """Dynamic dashboard creation and management"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.widget_generators = {
            'kpi': self._generate_kpi_widget,
            'chart': self._generate_chart_widget,
            'table': self._generate_table_widget,
            'metric': self._generate_metric_widget,
            'progress': self._generate_progress_widget
        }
    
    def create_dashboard(self, dashboard_config: Dict) -> Dict:
        """Create dynamic dashboard with widgets"""
        try:
            dashboard_data = {
                'title': dashboard_config.get('title', 'CRM Dashboard'),
                'description': dashboard_config.get('description', ''),
                'layout': dashboard_config.get('layout', 'grid'),
                'widgets': [],
                'refresh_interval': dashboard_config.get('refresh_interval', 300),  # 5 minutes
                'created_at': timezone.now().isoformat()
            }
            
            # Generate widgets
            for widget_config in dashboard_config.get('widgets', []):
                widget = self._generate_dashboard_widget(widget_config)
                dashboard_data['widgets'].append(widget)
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Dashboard creation failed: {e}", exc_info=True)
            raise AnalyticsException(f"Dashboard creation failed: {str(e)}")
    
    def _generate_kpi_widget(self, config: Dict) -> Dict:
        """Generate KPI widget"""
        metric_type = config.get('metric_type', 'revenue')
        period = config.get('period', '30d')
        
        # Calculate current and previous period values
        current_value, previous_value = self._calculate_kpi_values(metric_type, period)
        
        # Calculate change percentage
        change_percentage = 0
        if previous_value and previous_value != 0:
            change_percentage = ((current_value - previous_value) / previous_value) * 100
        
        return {
            'type': 'kpi',
            'title': config.get('title', metric_type.title()),
            'value': current_value,
            'previous_value': previous_value,
            'change_percentage': round(change_percentage, 2),
            'trend': 'up' if change_percentage > 0 else 'down' if change_percentage < 0 else 'stable',
            'format': config.get('format', 'number'),
            'color': self._get_kpi_color(change_percentage, config.get('reverse_colors', False))
        }


class AnalyticsService(BaseService):
    """Comprehensive analytics and reporting service with ML insights"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ml_engine = MLInsightsEngine(self.tenant)
        self.report_engine = ReportEngine(self.tenant)
        self.dashboard_engine = DashboardEngine(self.tenant)
    
    # ============================================================================
    # REPORT MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_custom_report(self, report_config: Dict, save_template: bool = True) -> Dict:
        """
        Create custom report with advanced analytics
        
        Args:
            report_config: Report configuration
            save_template: Whether to save as reusable template
        
        Returns:
            Generated report data
        """
        self.context.operation = 'create_custom_report'
        
        try:
            self.validate_user_permission('crm.add_report')
            
            # Validate report configuration
            required_fields = ['title', 'sections']
            is_valid, errors = self.validate_data(report_config, {
                field: {'required': True} for field in required_fields
            })
            
            if not is_valid:
                raise AnalyticsException(f"Report validation failed: {', '.join(errors)}")
            
            # Generate report
            report_data = self.report_engine.generate_report(report_config)
            
            # Save report template if requested
            report_instance = None
            if save_template:
                report_instance = Report.objects.create(
                    tenant=self.tenant,
                    name=report_config['title'],
                    description=report_config.get('description', ''),
                    report_type='CUSTOM',
                    configuration=report_config,
                    is_template=True,
                    created_by=self.user,
                    metadata={
                        'generated_at': timezone.now().isoformat(),
                        'sections_count': len(report_config.get('sections', [])),
                        'auto_generated': False
                    }
                )
            
            # Add execution metadata
            report_data['execution_metadata'] = {
                'report_id': report_instance.id if report_instance else None,
                'execution_time': timezone.now().isoformat(),
                'generated_by': self.user.get_full_name(),
                'tenant_id': self.tenant.id
            }
            
            self.log_activity(
                'custom_report_created',
                'Report',
                report_instance.id if report_instance else None,
                {
                    'title': report_config['title'],
                    'sections_count': len(report_config.get('sections', [])),
                    'saved_as_template': save_template
                }
            )
            
            return report_data
            
        except Exception as e:
            logger.error(f"Custom report creation failed: {e}", exc_info=True)
            raise AnalyticsException(f"Custom report creation failed: {str(e)}")
    
    def generate_executive_dashboard(self, period: str = '30d', 
                                   include_forecasts: bool = True) -> Dict:
        """
        Generate comprehensive executive dashboard
        
        Args:
            period: Analysis period
            include_forecasts: Include ML forecasts
        
        Returns:
            Executive dashboard data
        """
        try:
            # Calculate date range
            period_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = period_days.get(period, 30)
            start_date = timezone.now() - timedelta(days=days)
            
            dashboard_data = {
                'title': 'Executive Dashboard',
                'period': period,
                'generated_at': timezone.now().isoformat(),
                'sections': {}
            }
            
            # Key Performance Indicators
            dashboard_data['sections']['kpis'] = self._generate_executive_kpis(start_date)
            
            # Sales Performance
            dashboard_data['sections']['sales'] = self._generate_sales_performance_section(start_date)
            
            # Pipeline Analysis
            dashboard_data['sections']['pipeline'] = self._generate_pipeline_analysis(start_date)
            
            # Team Performance
            dashboard_data['sections']['team'] = self._generate_team_performance_section(start_date)
            
            # Marketing Analytics
            dashboard_data['sections']['marketing'] = self._generate_marketing_analytics(start_date)
            
            # Customer Analytics
            dashboard_data['sections']['customers'] = self._generate_customer_analytics(start_date)
            
            # ML Insights and Forecasts
            if include_forecasts:
                dashboard_data['sections']['forecasts'] = self._generate_ml_insights_section()
            
            # Anomaly Detection
            dashboard_data['sections']['anomalies'] = self._detect_business_anomalies()
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Executive dashboard generation failed: {e}", exc_info=True)
            raise AnalyticsException(f"Executive dashboard generation failed: {str(e)}")
    
    # ============================================================================
    # ML INSIGHTS AND PREDICTIONS
    # ============================================================================
    
    def generate_sales_forecast(self, forecast_days: int = 90, 
                              models: List[str] = None) -> Dict:
        """
        Generate advanced sales forecasting with multiple ML models
        
        Args:
            forecast_days: Number of days to forecast
            models: ML models to use
        
        Returns:
            Forecast data with confidence intervals
        """
        try:
            self.validate_user_permission('crm.view_analytics')
            
            # Generate primary forecast
            primary_forecast = self.ml_engine.generate_sales_forecast(
                forecast_days, confidence_level=0.8
            )
            
            # Add business context
            business_context = self._get_forecast_business_context()
            
            # Generate recommendations based on forecast
            recommendations = self._generate_forecast_recommendations(
                primary_forecast, business_context
            )
            
            forecast_data = {
                'forecast_period_days': forecast_days,
                'primary_forecast': primary_forecast,
                'business_context': business_context,
                'recommendations': recommendations,
                'model_confidence': primary_forecast.get('model_performance', {}).get('confidence', 0),
                'generated_at': timezone.now().isoformat()
            }
            
            self.log_activity(
                'sales_forecast_generated',
                'Forecast',
                None,
                {
                    'forecast_days': forecast_days,
                    'confidence': forecast_data['model_confidence'],
                    'has_recommendations': len(recommendations) > 0
                }
            )
            
            return forecast_data
            
        except Exception as e:
            logger.error(f"Sales forecast generation failed: {e}", exc_info=True)
            raise AnalyticsException(f"Sales forecast generation failed: {str(e)}")
    
    def detect_performance_anomalies(self, metrics: List[str] = None, 
                                   sensitivity: float = 0.1) -> List[Dict]:
        """
        Detect anomalies in business performance metrics
        
        Args:
            metrics: Specific metrics to analyze
            sensitivity: Anomaly detection sensitivity
        
        Returns:
            List of detected anomalies
        """
        try:
            default_metrics = ['revenue', 'lead_count', 'conversion_rate', 'activity_count']
            metrics_to_analyze = metrics or default_metrics
            
            all_anomalies = []
            
            for metric in metrics_to_analyze:
                anomalies = self.ml_engine.detect_anomalies(metric, lookback_days=90)
                
                # Add context and recommendations
                for anomaly in anomalies:
                    anomaly['metric_name'] = metric
                    anomaly['recommendations'] = self._get_anomaly_recommendations(anomaly)
                    all_anomalies.append(anomaly)
            
            # Sort by severity
            all_anomalies.sort(key=lambda x: x.get('severity', 0), reverse=True)
            
            self.log_activity(
                'anomaly_detection_completed',
                'Anomaly',
                None,
                {
                    'metrics_analyzed': len(metrics_to_analyze),
                    'anomalies_found': len(all_anomalies),
                    'high_severity_count': sum(1 for a in all_anomalies if a.get('severity', 0) > 0.7)
                }
            )
            
            return all_anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            raise AnalyticsException(f"Anomaly detection failed: {str(e)}")
    
    # ============================================================================
    # ADVANCED ANALYTICS
    # ============================================================================
    
    def analyze_customer_lifetime_value(self, segment: str = None) -> Dict:
        """
        Analyze Customer Lifetime Value with predictive modeling
        
        Args:
            segment: Customer segment to analyze
        
        Returns:
            CLV analysis with predictions
        """
        try:
            # Get customer data
            customers_query = Account.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).annotate(
                total_revenue=Sum('opportunities__amount', filter=Q(opportunities__is_won=True)),
                total_opportunities=Count('opportunities'),
                avg_deal_size=Avg('opportunities__amount', filter=Q(opportunities__is_won=True)),
                customer_age_days=(timezone.now().date() - F('created_at__date'))
            ).filter(total_revenue__gt=0)
            
            if segment:
                customers_query = customers_query.filter(industry=segment)
            
            customers = list(customers_query)
            
            if not customers:
                return {
                    'error': 'No customer data available for analysis',
                    'clv_analysis': {}
                }
            
            # Calculate CLV metrics
            clv_data = []
            for customer in customers:
                customer_age_years = customer.customer_age_days.days / 365.25 if customer.customer_age_days else 0.1
                annual_revenue = customer.total_revenue / customer_age_years if customer_age_years > 0 else 0
                
                # Simplified CLV calculation (can be enhanced with churn prediction)
                predicted_lifespan = 3.0  # years (would be predicted by ML model)
                clv = annual_revenue * predicted_lifespan
                
                clv_data.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'total_revenue': float(customer.total_revenue or 0),
                    'avg_deal_size': float(customer.avg_deal_size or 0),
                    'customer_age_years': customer_age_years,
                    'annual_revenue': annual_revenue,
                    'predicted_clv': clv,
                    'clv_segment': self._categorize_clv(clv)
                })
            
            # Calculate summary statistics
            clv_values = [item['predicted_clv'] for item in clv_data]
            summary_stats = {
                'total_customers': len(clv_data),
                'average_clv': np.mean(clv_values),
                'median_clv': np.median(clv_values),
                'clv_std': np.std(clv_values),
                'high_value_customers': sum(1 for item in clv_data if item['clv_segment'] == 'high'),
                'segments': {
                    'high': sum(1 for item in clv_data if item['clv_segment'] == 'high'),
                    'medium': sum(1 for item in clv_data if item['clv_segment'] == 'medium'),
                    'low': sum(1 for item in clv_data if item['clv_segment'] == 'low')
                }
            }
            
            return {
                'clv_analysis': {
                    'summary_stats': summary_stats,
                    'customer_data': clv_data[:50],  # Return top 50
                    'segment_analysis': segment,
                    'generated_at': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"CLV analysis failed: {e}", exc_info=True)
            raise AnalyticsException(f"CLV analysis failed: {str(e)}")
    
    def generate_cohort_analysis(self, cohort_type: str = 'monthly', 
                               metric: str = 'revenue') -> Dict:
        """
        Generate cohort analysis for customer behavior
        
        Args:
            cohort_type: Cohort grouping ('monthly', 'quarterly')
            metric: Metric to analyze
        
        Returns:
            Cohort analysis data
        """
        try:
            # This is a simplified cohort analysis
            # In a real implementation, this would be more sophisticated
            
            cohort_data = {
                'cohort_type': cohort_type,
                'metric': metric,
                'analysis_period': '12 months',
                'cohorts': [],
                'insights': []
            }
            
            # Get customer acquisition data by cohort
            if cohort_type == 'monthly':
                cohorts = Account.objects.filter(
                    tenant=self.tenant
                ).extra({
                    'cohort_month': "DATE_TRUNC('month', created_at)"
                }).values('cohort_month').annotate(
                    customers_acquired=Count('id')
                ).order_by('cohort_month')
            
            for cohort in cohorts:
                cohort_customers = Account.objects.filter(
                    tenant=self.tenant,
                    created_at__month=cohort['cohort_month'].month,
                    created_at__year=cohort['cohort_month'].year
                )
                
                # Calculate retention and revenue by period
                retention_data = []
                for period in range(12):  # 12 months
                    period_start = cohort['cohort_month'] + timedelta(days=period*30)
                    period_end = period_start + timedelta(days=30)
                    
                    active_customers = cohort_customers.filter(
                        opportunities__created_at__range=[period_start, period_end]
                    ).distinct().count()
                    
                    retention_rate = (active_customers / cohort['customers_acquired'] * 100) if cohort['customers_acquired'] > 0 else 0
                    
                    retention_data.append({
                        'period': period,
                        'active_customers': active_customers,
                        'retention_rate': retention_rate
                    })
                
                cohort_data['cohorts'].append({
                    'cohort_period': cohort['cohort_month'].isoformat(),
                    'initial_customers': cohort['customers_acquired'],
                    'retention_data': retention_data
                })
            
            return cohort_data
            
        except Exception as e:
            logger.error(f"Cohort analysis failed: {e}", exc_info=True)
            raise AnalyticsException(f"Cohort analysis failed: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_executive_kpis(self, start_date: datetime) -> Dict:
        """Generate executive KPI section"""
        # Revenue metrics
        current_revenue = Opportunity.objects.filter(
            tenant=self.tenant,
            is_won=True,
            closed_date__gte=start_date
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Lead metrics
        total_leads = Lead.objects.filter(
            tenant=self.tenant,
            created_at__gte=start_date
        ).count()
        
        converted_leads = Lead.objects.filter(
            tenant=self.tenant,
            created_at__gte=start_date,
            converted_opportunity__isnull=False
        ).count()
        
        # Pipeline metrics
        pipeline_value = Opportunity.objects.filter(
            tenant=self.tenant,
            is_closed=False
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Activity metrics
        total_activities = Activity.objects.filter(
            tenant=self.tenant,
            created_at__gte=start_date
        ).count()
        
        return {
            'revenue': {
                'value': float(current_revenue),
                'label': f'Revenue ({start_date.strftime("%b %d")} - Today)',
                'format': 'currency'
            },
            'leads': {
                'value': total_leads,
                'label': 'Total Leads',
                'format': 'number'
            },
            'conversion_rate': {
                'value': (converted_leads / total_leads * 100) if total_leads > 0 else 0,
                'label': 'Lead Conversion Rate',
                'format': 'percentage'
            },
            'pipeline_value': {
                'value': float(pipeline_value),
                'label': 'Pipeline Value',
                'format': 'currency'
            },
            'activities': {
                'value': total_activities,
                'label': 'Total Activities',
                'format': 'number'
            }
        }
    
    def _categorize_clv(self, clv: float) -> str:
        """Categorize CLV into segments"""
        if clv >= 10000:
            return 'high'
        elif clv >= 5000:
            return 'medium'
        else:
            return 'low'
    
    def _get_anomaly_recommendations(self, anomaly: Dict) -> List[str]:
        """Get recommendations for handling detected anomaly"""
        recommendations = []
        metric_type = anomaly.get('metric_type', '')
        severity = anomaly.get('severity', 0)
        
        if metric_type == 'revenue':
            if severity > 0.8:
                recommendations.extend([
                    "Investigate potential data quality issues",
                    "Review recent sales process changes",
                    "Check for seasonal or market factors"
                ])
            else:
                recommendations.append("Monitor trend for next few days")
        
        elif metric_type == 'lead_count':
            recommendations.extend([
                "Review marketing campaign performance",
                "Check lead source attribution",
                "Analyze website traffic patterns"
            ])
        
        return recommendations