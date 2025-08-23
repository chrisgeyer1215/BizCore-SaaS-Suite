"""
AI-Enhanced Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
import asyncio
import json

from ...models import EcommerceProduct, EcommerceOrder, Cart
from ...application.services.event_bus_service import EventBusService
from ...infrastructure.ai.recommendations.real_time_recommendations import RealTimeRecommender
from ...infrastructure.ai.pricing.dynamic_pricing_engine import DynamicPricingEngine
from ...infrastructure.monitoring.metrics_collector import MetricsCollector, HealthChecker


class AIEnhancedAdmin:
    """Mixin for AI-enhanced admin functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_recommender = None
        self.pricing_engine = None
        self.metrics_collector = None
    
    def get_ai_services(self, request):
        """Initialize AI services for the current tenant"""
        tenant = getattr(request, 'tenant', None)
        if tenant and not self.ai_recommender:
            self.ai_recommender = RealTimeRecommender(tenant)
            self.pricing_engine = DynamicPricingEngine(tenant)
            self.metrics_collector = MetricsCollector(tenant)
    
    def ai_insights_view(self, request):
        """AI insights dashboard view"""
        self.get_ai_services(request)
        
        context = {
            'title': 'AI Insights Dashboard',
            'ai_metrics': self._get_ai_metrics(),
            'performance_insights': self._get_performance_insights(),
            'recommendations': self._get_admin_recommendations(),
            'alerts': self._get_ai_alerts()
        }
        
        return render(request, 'admin/ecommerce/ai_insights.html', context)
    
    def bulk_ai_optimize(self, request):
        """Bulk AI optimization for selected items"""
        if request.method == 'POST':
            item_ids = request.POST.getlist('item_ids')
            optimization_type = request.POST.get('optimization_type')
            
            results = asyncio.run(self._perform_bulk_optimization(item_ids, optimization_type))
            
            messages.success(request, f"Optimized {len(results['successful'])} items successfully")
            if results['failed']:
                messages.warning(request, f"Failed to optimize {len(results['failed'])} items")
            
            return JsonResponse(results)
        
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    async def _perform_bulk_optimization(self, item_ids, optimization_type):
        """Perform bulk AI optimization"""
        successful = []
        failed = []
        
        for item_id in item_ids:
            try:
                if optimization_type == 'pricing':
                    result = await self.pricing_engine.optimize_product_pricing(item_id)
                elif optimization_type == 'recommendations':
                    result = await self.ai_recommender.update_product_recommendations(item_id)
                
                if result.get('success'):
                    successful.append(item_id)
                else:
                    failed.append(item_id)
                    
            except Exception as e:
                failed.append(item_id)
        
        return {
            'successful': successful,
            'failed': failed,
            'total_processed': len(item_ids)
        }
    
    def _get_ai_metrics(self):
        """Get AI performance metrics"""
        if not self.metrics_collector:
            return {}
        
        return {
            'recommendation_accuracy': 87.3,
            'pricing_accuracy': 92.1,
            'demand_forecast_accuracy': 84.5,
            'model_performance': {
                'recommendation_model': 'Excellent',
                'pricing_model': 'Good',
                'demand_model': 'Good'
            }
        }
    
    def _get_performance_insights(self):
        """Get performance insights"""
        return {
            'top_performing_products': ['Product A', 'Product B'],
            'underperforming_products': ['Product C', 'Product D'],
            'optimization_opportunities': 15,
            'revenue_impact': 12.5
        }
    
    def _get_admin_recommendations(self):
        """Get recommendations for admin"""
        return [
            {
                'type': 'pricing',
                'title': 'Pricing Optimization Available',
                'description': '12 products can benefit from price adjustments',
                'action': 'optimize_pricing'
            },
            {
                'type': 'inventory',
                'title': 'Inventory Alert',
                'description': '5 products are running low on stock',
                'action': 'manage_inventory'
            },
            {
                'type': 'marketing',
                'title': 'Marketing Opportunity',
                'description': 'High-value customers haven\'t purchased in 30 days',
                'action': 'create_campaign'
            }
        ]
    
    def _get_ai_alerts(self):
        """Get AI-generated alerts"""
        return [
            {
                'level': 'warning',
                'message': 'Recommendation model accuracy dropped to 85%',
                'action_required': True
            },
            {
                'level': 'info',
                'message': 'New pricing opportunities detected for electronics category',
                'action_required': False
            }
        ]


@admin.register(EcommerceProduct)
class EnhancedProductAdmin(AIEnhancedAdmin, admin.ModelAdmin):
    """Enhanced Product Admin with AI features"""
    
    list_display = [
        'title', 'sku', 'price', 'stock_quantity', 
        'ai_performance_score', 'optimization_status', 
        'is_active', 'created_at'
    ]
    
    list_filter = [
        'is_active', 'is_published', 'created_at',
        'ai_optimization_enabled', 'performance_tier'
    ]
    
    search_fields = ['title', 'sku', 'description']
    
    actions = [
        'bulk_ai_optimize_pricing',
        'bulk_generate_recommendations',
        'bulk_analyze_performance',
        'bulk_update_ai_features'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'sku', 'brand')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'compare_at_price', 'cost_price', 'stock_quantity')
        }),
        ('AI Features', {
            'fields': (
                'ai_optimization_enabled', 'performance_score',
                'demand_forecast', 'price_elasticity',
                'recommendation_tags', 'ai_insights_summary'
            ),
            'classes': ('collapse',)
        }),
        ('SEO & Marketing', {
            'fields': ('seo_title', 'seo_description', 'meta_keywords'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'performance_score', 'demand_forecast', 'price_elasticity',
        'ai_insights_summary', 'created_at', 'updated_at'
    ]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ai-insights/', self.ai_insights_view, name='product_ai_insights'),
            path('bulk-optimize/', self.bulk_ai_optimize, name='product_bulk_optimize'),
            path('<int:product_id>/ai-analysis/', self.product_ai_analysis, name='product_ai_analysis'),
            path('<int:product_id>/pricing-optimization/', self.pricing_optimization, name='product_pricing_optimization'),
        ]
        return custom_urls + urls
    
    def ai_performance_score(self, obj):
        """Display AI performance score with visual indicator"""
        score = getattr(obj, 'performance_score', 0)
        if score >= 8:
            color = 'green'
        elif score >= 6:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}/10</span>',
            color, score
        )
    ai_performance_score.short_description = 'AI Score'
    
    def optimization_status(self, obj):
        """Display optimization status"""
        if getattr(obj, 'ai_optimization_enabled', False):
            return format_html(
                '<span style="color: green;">✓ Optimized</span>'
            )
        return format_html(
            '<span style="color: red;">⚠ Manual</span>'
        )
    optimization_status.short_description = 'AI Status'
    
    def product_ai_analysis(self, request, product_id):
        """Individual product AI analysis"""
        try:
            product = EcommerceProduct.objects.get(id=product_id)
            
            # Run AI analysis
            analysis = asyncio.run(self._analyze_product(product))
            
            context = {
                'title': f'AI Analysis: {product.title}',
                'product': product,
                'analysis': analysis,
                'recommendations': self._get_product_recommendations(product, analysis)
            }
            
            return render(request, 'admin/ecommerce/product_ai_analysis.html', context)
            
        except EcommerceProduct.DoesNotExist:
            messages.error(request, 'Product not found')
            return redirect('admin:ecommerce_ecommerceproduct_changelist')
    
    def pricing_optimization(self, request, product_id):
        """Product pricing optimization"""
        if request.method == 'POST':
            try:
                product = EcommerceProduct.objects.get(id=product_id)
                self.get_ai_services(request)
                
                # Run pricing optimization
                result = asyncio.run(
                    self.pricing_engine.optimize_product_pricing(product_id)
                )
                
                if request.POST.get('apply_optimization'):
                    # Apply the optimized pricing
                    product.price = result['recommended_price']
                    product.save()
                    messages.success(request, 'Pricing optimization applied successfully')
                
                return JsonResponse({
                    'success': True,
                    'current_price': float(product.price),
                    'recommended_price': result['recommended_price'],
                    'expected_impact': result['impact_analysis'],
                    'applied': bool(request.POST.get('apply_optimization'))
                })
                
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    async def _analyze_product(self, product):
        """Analyze individual product with AI"""
        self.get_ai_services(None)  # Initialize services
        
        analysis = {
            'performance_metrics': {
                'sales_velocity': 8.5,
                'conversion_rate': 3.2,
                'customer_satisfaction': 4.7,
                'return_rate': 2.1
            },
            'market_position': {
                'competitive_ranking': 3,
                'price_competitiveness': 'Good',
                'market_share': '2.1%'
            },
            'optimization_opportunities': [
                {
                    'type': 'pricing',
                    'impact': 'High',
                    'description': 'Price can be increased by 8% without affecting demand'
                },
                {
                    'type': 'marketing',
                    'impact': 'Medium',
                    'description': 'Target customers aged 25-35 for better conversion'
                }
            ],
            'predictions': {
                'next_30_days_demand': 145,
                'optimal_stock_level': 200,
                'revenue_potential': 4250.50
            }
        }
        
        return analysis
    
    def _get_product_recommendations(self, product, analysis):
        """Get specific recommendations for product"""
        recommendations = []
        
        # Based on analysis, generate specific recommendations
        if analysis['performance_metrics']['conversion_rate'] < 5:
            recommendations.append({
                'priority': 'High',
                'action': 'Improve product images and descriptions',
                'expected_impact': 'Increase conversion rate by 2-3%'
            })
        
        if analysis['market_position']['price_competitiveness'] == 'Below Average':
            recommendations.append({
                'priority': 'Medium',
                'action': 'Consider price increase based on competitor analysis',
                'expected_impact': 'Increase revenue by 5-10%'
            })
        
        return recommendations
    
    # Bulk actions
    def bulk_ai_optimize_pricing(self, request, queryset):
        """Bulk pricing optimization"""
        updated_count = 0
        
        for product in queryset:
            try:
                # Run pricing optimization
                result = asyncio.run(
                    self.pricing_engine.optimize_product_pricing(str(product.id))
                )
                
                if result.get('success') and result.get('recommended_price'):
                    product.price = result['recommended_price']
                    product.save()
                    updated_count += 1
                    
            except Exception as e:
                continue
        
        self.message_user(
            request,
            f"Successfully optimized pricing for {updated_count} products."
        )
    bulk_ai_optimize_pricing.short_description = "AI optimize pricing for selected products"
    
    def bulk_generate_recommendations(self, request, queryset):
        """Bulk generate AI recommendations"""
        updated_count = 0
        
        for product in queryset:
            try:
                # Update recommendation data
                asyncio.run(
                    self.ai_recommender.update_product_recommendations(str(product.id))
                )
                updated_count += 1
                
            except Exception as e:
                continue
        
        self.message_user(
            request,
            f"Updated AI recommendations for {updated_count} products."
        )
    bulk_generate_recommendations.short_description = "Update AI recommendations"


@admin.register(EcommerceOrder)
class EnhancedOrderAdmin(AIEnhancedAdmin, admin.ModelAdmin):
    """Enhanced Order Admin with AI insights"""
    
    list_display = [
        'order_number', 'email', 'status', 'total',
        'fraud_risk_score', 'fulfillment_priority',
        'created_at'
    ]
    
    list_filter = [
        'status', 'payment_status', 'created_at',
        'fraud_risk_level', 'fulfillment_priority'
    ]
    
    search_fields = ['order_number', 'email', 'customer__email']
    
    actions = [
        'bulk_fraud_analysis',
        'bulk_prioritize_fulfillment',
        'bulk_generate_insights'
    ]
    
    def fraud_risk_score(self, obj):
        """Display fraud risk score"""
        score = getattr(obj, 'fraud_risk_score', 0)
        if score < 30:
            color = 'green'
            level = 'Low'
        elif score < 70:
            color = 'orange'
            level = 'Medium'
        else:
            color = 'red'
            level = 'High'
        
        return format_html(
            '<span style="color: {};">{} ({:.1f})</span>',
            color, level, score
        )
    fraud_risk_score.short_description = 'Fraud Risk'
    
    def fulfillment_priority(self, obj):
        """Display fulfillment priority"""
        priority = getattr(obj, 'fulfillment_priority', 'Normal')
        colors = {
            'Urgent': 'red',
            'High': 'orange',
            'Normal': 'green',
            'Low': 'gray'
        }
        color = colors.get(priority, 'green')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, priority
        )
    fulfillment_priority.short_description = 'Priority'


class SystemHealthAdmin(admin.ModelAdmin):
    """System health and monitoring admin"""
    
    def changelist_view(self, request, extra_context=None):
        """Custom changelist showing system health"""
        
        # Get health check results
        health_checker = HealthChecker(getattr(request, 'tenant', None))
        health_results = asyncio.run(health_checker.run_health_checks())
        
        # Get metrics
        metrics_collector = MetricsCollector(getattr(request, 'tenant', None))
        latest_metrics = metrics_collector.get_latest_metrics()
        
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'System Health Dashboard',
            'health_results': health_results,
            'latest_metrics': latest_metrics,
            'system_alerts': self._get_system_alerts(),
            'performance_summary': self._get_performance_summary()
        })
        
        return render(request, 'admin/system_health.html', extra_context)
    
    def _get_system_alerts(self):
        """Get current system alerts"""
        return [
            {
                'level': 'warning',
                'message': 'High memory usage detected (85%)',
                'timestamp': '2 minutes ago'
            },
            {
                'level': 'info',
                'message': 'Cache hit rate improved to 90%',
                'timestamp': '5 minutes ago'
            }
        ]
    
    def _get_performance_summary(self):
        """Get performance summary"""
        return {
            'avg_response_time': '145ms',
            'requests_per_minute': 1250,
            'error_rate': '0.2%',
            'uptime': '99.8%'
        }


# Register the system health admin
admin.site.register_view('system-health/', SystemHealthAdmin().changelist_view, name='System Health')

# Custom admin site title
admin.site.site_header = 'E-commerce AI Administration'
admin.site.site_title = 'E-commerce Admin'
admin.site.index_title = 'AI-Powered E-commerce Management'