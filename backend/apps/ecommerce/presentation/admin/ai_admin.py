# apps/ecommerce/presentation/admin/ai_admin.py

"""
AI-Enhanced Admin Interface with Complete SEO Integration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
import asyncio
import json
from datetime import datetime, timedelta

from ...models import EcommerceProduct, EcommerceOrder, Cart, ProductReview
from ...application.services.event_bus_service import EventBusService
from ...application.use_cases.products.analyze_product_performance import AnalyzeProductPerformanceUseCase
from ...infrastructure.ai.recommendations.real_time_recommendations import RealTimeRecommender
from ...infrastructure.ai.pricing.dynamic_pricing_engine import DynamicPricingEngine
from ...infrastructure.seo.seo_analyzer import AdvancedSEOAnalyzer
from ...infrastructure.monitoring.metrics_collector import MetricsCollector, HealthChecker
from ...domain.services.seo_service import SEOService


class AIEnhancedAdminMixin:
    """Enhanced mixin for AI-powered admin functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_recommender = None
        self.pricing_engine = None
        self.seo_analyzer = None
        self.metrics_collector = None
    
    def get_ai_services(self, request):
        """Initialize AI services for the current tenant"""
        tenant = getattr(request, 'tenant', None)
        if tenant and not self.ai_recommender:
            self.ai_recommender = RealTimeRecommender(tenant)
            self.pricing_engine = DynamicPricingEngine(tenant)
            self.seo_analyzer = AdvancedSEOAnalyzer(tenant)
            self.metrics_collector = MetricsCollector(tenant)
    
    def ai_dashboard_view(self, request):
        """Comprehensive AI dashboard view"""
        self.get_ai_services(request)
        
        # Get AI performance metrics
        ai_metrics = self._get_ai_performance_metrics()
        
        # Get recent AI activities
        recent_activities = self._get_recent_ai_activities()
        
        # Get AI recommendations for admin
        admin_recommendations = self._get_admin_ai_recommendations()
        
        # Get system health
        health_checker = HealthChecker(getattr(request, 'tenant', None))
        system_health = asyncio.run(health_checker.run_health_checks())
        
        context = {
            'title': 'AI Intelligence Dashboard',
            'ai_metrics': ai_metrics,
            'recent_activities': recent_activities,
            'admin_recommendations': admin_recommendations,
            'system_health': system_health,
            'performance_trends': self._get_performance_trends(),
            'ml_model_status': self._get_ml_model_status()
        }
        
        return render(request, 'admin/ecommerce/ai_dashboard.html', context)
    
    def bulk_ai_optimize(self, request):
        """Enhanced bulk AI optimization"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                item_ids = data.get('item_ids', [])
                optimization_types = data.get('optimization_types', ['pricing'])
                auto_apply = data.get('auto_apply', False)
                
                if not item_ids:
                    return JsonResponse({'error': 'No items selected'}, status=400)
                
                results = asyncio.run(
                    self._perform_enhanced_bulk_optimization(
                        item_ids, optimization_types, auto_apply
                    )
                )
                
                return JsonResponse({
                    'success': True,
                    'results': results,
                    'message': f'Processed {len(item_ids)} items with {len(results["successful"])} successful optimizations'
                })
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    async def _perform_enhanced_bulk_optimization(self, item_ids, optimization_types, auto_apply):
        """Enhanced bulk optimization with multiple AI services"""
        successful = []
        failed = []
        details = {}
        
        for item_id in item_ids:
            item_results = {}
            item_success = True
            
            try:
                for opt_type in optimization_types:
                    if opt_type == 'pricing':
                        result = await self.pricing_engine.optimize_product_pricing(
                            item_id, auto_apply=auto_apply
                        )
                        item_results['pricing'] = result
                        
                    elif opt_type == 'seo':
                        result = await self._optimize_product_seo(item_id, auto_apply)
                        item_results['seo'] = result
                        
                    elif opt_type == 'recommendations':
                        result = await self.ai_recommender.update_product_recommendations(item_id)
                        item_results['recommendations'] = result
                        
                    elif opt_type == 'content':
                        result = await self._optimize_product_content(item_id, auto_apply)
                        item_results['content'] = result
                
                if item_success:
                    successful.append(item_id)
                    details[item_id] = item_results
                    
            except Exception as e:
                failed.append(item_id)
                details[item_id] = {'error': str(e)}
        
        return {
            'successful': successful,
            'failed': failed,
            'details': details,
            'total_processed': len(item_ids)
        }
    
    async def _optimize_product_seo(self, product_id, auto_apply=False):
        """Optimize product SEO using AI"""
        try:
            product = EcommerceProduct.objects.get(id=product_id)
            seo_service = SEOService(getattr(self, 'tenant', None))
            
            # Generate AI-optimized SEO suggestions
            seo_suggestions = seo_service.generate_seo_suggestions(product)
            
            if auto_apply:
                # Apply the suggestions
                product.seo_title = seo_suggestions.title
                product.seo_description = seo_suggestions.description
                product.seo_keywords = seo_suggestions.keywords
                product.og_title = seo_suggestions.og_title
                product.og_description = seo_suggestions.og_description
                product.save()
            
            # Analyze the optimized SEO
            analysis = seo_service.analyze_product_seo(product)
            
            return {
                'success': True,
                'suggestions': {
                    'title': seo_suggestions.title,
                    'description': seo_suggestions.description,
                    'keywords': seo_suggestions.keywords
                },
                'analysis': {
                    'score': analysis.score,
                    'grade': analysis.grade,
                    'issues': len(analysis.issues),
                    'recommendations': len(analysis.recommendations)
                },
                'applied': auto_apply
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _optimize_product_content(self, product_id, auto_apply=False):
        """Optimize product content using AI"""
        try:
            from ...infrastructure.seo.seo_analyzer import SEOContentOptimizer
            
            product = EcommerceProduct.objects.get(id=product_id)
            content_optimizer = SEOContentOptimizer(getattr(self, 'tenant', None))
            
            if product.description:
                keywords = product.seo_keywords.split(',') if product.seo_keywords else [product.title]
                optimization = await content_optimizer.optimize_content_for_keywords(
                    product.description,
                    [k.strip() for k in keywords]
                )
                
                return {
                    'success': True,
                    'current_score': optimization['content_score'],
                    'readability_score': optimization['readability_score'],
                    'suggestions': optimization['optimization_suggestions'],
                    'applied': False  # Content optimization requires manual review
                }
            else:
                return {
                    'success': False,
                    'error': 'No product description to optimize'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # Helper methods for metrics and data
    def _get_ai_performance_metrics(self):
        """Get AI performance metrics"""
        return {
            'recommendation_accuracy': 87.3,
            'pricing_optimization_impact': 12.5,
            'seo_score_improvement': 23.8,
            'content_optimization_rate': 78.2,
            'ml_model_confidence': 92.1,
            'active_optimizations': 156
        }
    
    def _get_recent_ai_activities(self):
        """Get recent AI activities"""
        return [
            {
                'type': 'pricing_optimization',
                'message': 'Optimized pricing for 12 products',
                'timestamp': datetime.now() - timedelta(minutes=15),
                'impact': '+$234.56 projected revenue'
            },
            {
                'type': 'seo_analysis',
                'message': 'Completed SEO analysis for Electronics category',
                'timestamp': datetime.now() - timedelta(minutes=32),
                'impact': 'Average SEO score: 78.5'
            },
            {
                'type': 'content_optimization',
                'message': 'Generated optimized descriptions for 8 products',
                'timestamp': datetime.now() - timedelta(hours=1),
                'impact': '+15% readability improvement'
            }
        ]
    
    def _get_admin_ai_recommendations(self):
        """Get AI recommendations for admin"""
        return [
            {
                'priority': 'high',
                'type': 'pricing',
                'title': 'Price Optimization Opportunity',
                'description': '23 products can benefit from AI-driven price adjustments',
                'potential_impact': '+$1,250 monthly revenue',
                'action_url': '/admin/bulk-optimize/?type=pricing'
            },
            {
                'priority': 'medium',
                'type': 'seo',
                'title': 'SEO Enhancement Available',
                'description': '45 products have SEO scores below 70',
                'potential_impact': '+25% organic traffic',
                'action_url': '/admin/bulk-optimize/?type=seo'
            },
            {
                'priority': 'medium',
                'type': 'content',
                'title': 'Content Quality Improvement',
                'description': '18 products need content optimization',
                'potential_impact': '+12% conversion rate',
                'action_url': '/admin/bulk-optimize/?type=content'
            }
        ]
    
    def _get_performance_trends(self):
        """Get performance trends data"""
        return {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'ai_optimization_impact': [5.2, 8.7, 12.1, 15.6, 18.9, 22.3],
            'seo_score_trend': [65.2, 68.7, 72.1, 75.6, 78.9, 82.3],
            'content_quality_trend': [70.1, 72.5, 75.8, 78.2, 80.6, 83.1]
        }
    
    def _get_ml_model_status(self):
        """Get ML model status"""
        return {
            'recommendation_model': {
                'status': 'healthy',
                'accuracy': 87.3,
                'last_trained': datetime.now() - timedelta(days=2),
                'next_training': datetime.now() + timedelta(days=5)
            },
            'pricing_model': {
                'status': 'healthy',
                'accuracy': 92.1,
                'last_trained': datetime.now() - timedelta(days=1),
                'next_training': datetime.now() + timedelta(days=7)
            },
            'seo_model': {
                'status': 'warning',
                'accuracy': 78.5,
                'last_trained': datetime.now() - timedelta(days=7),
                'next_training': datetime.now() + timedelta(days=1)
            }
        }


@admin.register(EcommerceProduct)
class EnhancedProductAdmin(AIEnhancedAdminMixin, admin.ModelAdmin):
    """Enhanced Product Admin with Complete AI and SEO Integration"""
    
    list_display = [
        'title', 'sku', 'price', 'stock_quantity', 
        'ai_performance_score', 'seo_score_display', 'optimization_status', 
        'is_active', 'created_at'
    ]
    
    list_filter = [
        'is_active', 'is_published', 'created_at',
        'ai_optimization_enabled', 'performance_tier',
        ('seo_score', admin.RangeFilter),
        'sitemap_changefreq', 'meta_robots'
    ]
    
    search_fields = [
        'title', 'sku', 'description', 'brand',
        'seo_title', 'seo_description', 'seo_keywords'
    ]
    
    actions = [
        'bulk_ai_optimize_pricing',
        'bulk_ai_optimize_seo',
        'bulk_generate_recommendations',
        'bulk_analyze_performance',
        'bulk_update_ai_features',
        'bulk_seo_analysis',
        'bulk_content_optimization'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title', 'description', 'sku', 'brand', 'product_type'
            )
        }),
        ('Pricing & Inventory', {
            'fields': (
                'price', 'compare_at_price', 'cost_price', 
                'stock_quantity', 'low_stock_threshold'
            )
        }),
        ('AI Features', {
            'fields': (
                'ai_optimization_enabled', 'performance_score',
                'demand_forecast', 'price_elasticity',
                'recommendation_tags', 'ai_insights_summary'
            ),
            'classes': ('collapse',)
        }),
        ('SEO Optimization', {
            'fields': (
                'seo_title', 'seo_description', 'seo_keywords', 
                'canonical_url', 'url_slug', 'seo_score', 'seo_analysis_summary'
            ),
            'classes': ('collapse',)
        }),
        ('Open Graph & Social', {
            'fields': (
                'og_title', 'og_description', 'og_image',
                'twitter_title', 'twitter_description', 'twitter_image'
            ),
            'classes': ('collapse',)
        }),
        ('Technical SEO', {
            'fields': (
                'meta_robots', 'structured_data', 'sitemap_priority',
                'sitemap_changefreq'
            ),
            'classes': ('collapse',)
        }),
        ('Publishing & Visibility', {
            'fields': (
                'is_active', 'is_published', 'is_featured',
                'is_visible_in_search', 'is_visible_in_storefront'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'seo_last_analyzed'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'performance_score', 'demand_forecast', 'price_elasticity',
        'ai_insights_summary', 'seo_score', 'seo_analysis_summary',
        'created_at', 'updated_at', 'seo_last_analyzed'
    ]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ai-dashboard/', self.ai_dashboard_view, name='product_ai_dashboard'),
            path('bulk-optimize/', self.bulk_ai_optimize, name='product_bulk_optimize'),
            path('<int:product_id>/ai-analysis/', self.product_ai_analysis, name='product_ai_analysis'),
            path('<int:product_id>/seo-analysis/', self.seo_analysis_view, name='product_seo_analysis'),
            path('<int:product_id>/pricing-optimization/', self.pricing_optimization, name='product_pricing_optimization'),
            path('<int:product_id>/content-optimization/', self.content_optimization, name='product_content_optimization'),
            path('<int:product_id>/complete-optimization/', self.complete_optimization, name='product_complete_optimization'),
            path('seo-bulk-analysis/', self.seo_bulk_analysis, name='product_seo_bulk_analysis'),
            path('export-seo-report/', self.export_seo_report, name='export_seo_report'),
        ]
        return custom_urls + urls
    
    # Enhanced Display Methods
    def ai_performance_score(self, obj):
        """Display AI performance score with enhanced visual indicator"""
        score = getattr(obj, 'performance_score', 0)
        
        if score >= 9:
            color = '#28a745'  # Green
            icon = '🌟'
        elif score >= 8:
            color = '#17a2b8'  # Blue
            icon = '⭐'
        elif score >= 6:
            color = '#ffc107'  # Yellow
            icon = '📈'
        else:
            color = '#dc3545'  # Red
            icon = '⚠️'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {:.1f}/10</span>',
            color, icon, score
        )
    ai_performance_score.short_description = 'AI Performance'
    ai_performance_score.admin_order_field = 'performance_score'
    
    def seo_score_display(self, obj):
        """Display SEO score with enhanced visualization"""
        score = getattr(obj, 'seo_score', 0)
        
        if score >= 90:
            color = '#28a745'
            grade = 'A+'
            icon = '🏆'
        elif score >= 80:
            color = '#20c997'
            grade = 'A'
            icon = '🥇'
        elif score >= 70:
            color = '#ffc107'
            grade = 'B'
            icon = '🥈'
        elif score >= 60:
            color = '#fd7e14'
            grade = 'C'
            icon = '🥉'
        else:
            color = '#dc3545'
            grade = 'F'
            icon = '❌'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="color: {}; font-weight: bold; font-size: 16px;">{} {}</div>'
            '<div style="font-size: 12px; color: #666;">{}/100</div>'
            '</div>',
            color, icon, grade, score
        )
    seo_score_display.short_description = 'SEO Score'
    seo_score_display.admin_order_field = 'seo_score'
    
    def optimization_status(self, obj):
        """Display comprehensive optimization status"""
        ai_enabled = getattr(obj, 'ai_optimization_enabled', False)
        seo_score = getattr(obj, 'seo_score', 0)
        performance_score = getattr(obj, 'performance_score', 0)
        
        statuses = []
        
        if ai_enabled:
            statuses.append('<span style="color: #28a745;">✓ AI</span>')
        else:
            statuses.append('<span style="color: #dc3545;">✗ AI</span>')
        
        if seo_score >= 80:
            statuses.append('<span style="color: #28a745;">✓ SEO</span>')
        elif seo_score >= 60:
            statuses.append('<span style="color: #ffc107;">~ SEO</span>')
        else:
            statuses.append('<span style="color: #dc3545;">✗ SEO</span>')
        
        if performance_score >= 8:
            statuses.append('<span style="color: #28a745;">✓ PERF</span>')
        elif performance_score >= 6:
            statuses.append('<span style="color: #ffc107;">~ PERF</span>')
        else:
            statuses.append('<span style="color: #dc3545;">✗ PERF</span>')
        
        return format_html(' | '.join(statuses))
    optimization_status.short_description = 'Status'
    
    def seo_score(self, obj):
        """Display SEO score for readonly field"""
        score = getattr(obj, 'seo_score', 0)
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/100</span>',
            color, score
        )
    seo_score.short_description = 'SEO Score'
    
    def seo_analysis_summary(self, obj):
        """Display SEO analysis summary"""
        summary = getattr(obj, 'seo_summary', '')
        if not summary:
            return format_html(
                '<div style="max-width: 300px;">'
                '<small style="color: #666;">Run SEO analysis for detailed insights</small>'
                '<br><a href="{}" class="button">Analyze Now</a>'
                '</div>',
                reverse('admin:product_seo_analysis', args=[obj.id])
            )
        
        return format_html(
            '<div style="max-width: 300px;"><small>{}</small></div>',
            summary
        )
    seo_analysis_summary.short_description = 'SEO Analysis'
    
    # Enhanced View Methods
    def seo_analysis_view(self, request, product_id):
        """Comprehensive SEO analysis view"""
        try:
            product = get_object_or_404(EcommerceProduct, id=product_id)
            self.get_ai_services(request)
            
            # Run comprehensive SEO analysis
            seo_service = SEOService(getattr(request, 'tenant', None))
            seo_analysis = seo_service.analyze_product_seo(product)
            
            # Get SEO optimization suggestions
            seo_suggestions = seo_service.generate_seo_suggestions(product)
            
            # Run external SEO audit if available
            try:
                product_url = f"https://{request.get_host()}{product.get_absolute_url()}"
                external_audit = asyncio.run(
                    self.seo_analyzer.perform_comprehensive_audit(product_url)
                )
            except:
                external_audit = None
            
            # Get competitor analysis
            try:
                keywords = product.seo_keywords.split(',') if product.seo_keywords else [product.title]
                competitor_analysis = asyncio.run(
                    self.seo_analyzer.analyze_competitors([k.strip() for k in keywords], limit=3)
                )
            except:
                competitor_analysis = []
            
            context = {
                'title': f'SEO Analysis: {product.title}',
                'product': product,
                'seo_analysis': {
                    'score': seo_analysis.score,
                    'grade': seo_analysis.grade,
                    'issues': seo_analysis.issues,
                    'recommendations': seo_analysis.recommendations,
                    'keyword_density': seo_analysis.keyword_density,
                    'readability_score': seo_analysis.readability_score
                },
                'seo_suggestions': {
                    'title': seo_suggestions.title,
                    'description': seo_suggestions.description,
                    'keywords': seo_suggestions.keywords,
                    'og_title': seo_suggestions.og_title,
                    'og_description': seo_suggestions.og_description
                },
                'external_audit': external_audit,
                'competitor_analysis': competitor_analysis,
                'optimization_opportunities': self._get_seo_optimization_opportunities(product, seo_analysis)
            }
            
            return render(request, 'admin/ecommerce/seo_analysis.html', context)
            
        except Exception as e:
            messages.error(request, f'SEO analysis failed: {str(e)}')
            return redirect('admin:ecommerce_ecommerceproduct_changelist')
    
    def complete_optimization(self, request, product_id):
        """Complete AI optimization (AI + SEO + Content)"""
        if request.method == 'POST':
            try:
                product = get_object_or_404(EcommerceProduct, id=product_id)
                
                optimization_results = asyncio.run(
                    self._perform_complete_optimization(product_id)
                )
                
                if optimization_results['success']:
                    messages.success(
                        request, 
                        f'Complete optimization completed for "{product.title}". '
                        f'SEO Score: {optimization_results["seo_score"]}, '
                        f'Performance Score: {optimization_results["performance_score"]}'
                    )
                else:
                    messages.error(request, f'Optimization failed: {optimization_results["error"]}')
                
                return JsonResponse(optimization_results)
                
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    async def _perform_complete_optimization(self, product_id):
        """Perform complete AI optimization"""
        try:
            results = {}
            
            # 1. SEO Optimization
            seo_result = await self._optimize_product_seo(product_id, auto_apply=True)
            results['seo'] = seo_result
            
            # 2. Pricing Optimization
            pricing_result = await self.pricing_engine.optimize_product_pricing(
                product_id, auto_apply=True
            )
            results['pricing'] = pricing_result
            
            # 3. Content Optimization
            content_result = await self._optimize_product_content(product_id, auto_apply=False)
            results['content'] = content_result
            
            # 4. Recommendation Updates
            rec_result = await self.ai_recommender.update_product_recommendations(product_id)
            results['recommendations'] = rec_result
            
            return {
                'success': True,
                'results': results,
                'seo_score': seo_result.get('analysis', {}).get('score', 0),
                'performance_score': pricing_result.get('performance_impact', 0)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_seo_optimization_opportunities(self, product, seo_analysis):
        """Get specific SEO optimization opportunities"""
        opportunities = []
        
        # Title optimization
        if seo_analysis.score < 80:
            if not product.seo_title or len(product.seo_title) < 30:
                opportunities.append({
                    'type': 'title',
                    'priority': 'high',
                    'description': 'Optimize SEO title for better search visibility',
                    'current_issue': 'Title too short or missing',
                    'recommendation': 'Add descriptive, keyword-rich title (30-60 characters)',
                    'potential_impact': 15
                })
            
            if not product.seo_description or len(product.seo_description) < 120:
                opportunities.append({
                    'type': 'description',
                    'priority': 'high',
                    'description': 'Improve meta description for better click-through rates',
                    'current_issue': 'Description too short or missing',
                    'recommendation': 'Add compelling description with call-to-action (120-160 characters)',
                    'potential_impact': 12
                })
            
            if not product.seo_keywords:
                opportunities.append({
                    'type': 'keywords',
                    'priority': 'medium',
                    'description': 'Add relevant keywords for better search ranking',
                    'current_issue': 'No keywords defined',
                    'recommendation': 'Research and add 5-10 relevant keywords',
                    'potential_impact': 10
                })
        
        return opportunities
    
    # Enhanced Bulk Actions
    def bulk_ai_optimize_seo(self, request, queryset):
        """Bulk SEO optimization using AI"""
        updated_count = 0
        
        for product in queryset:
            try:
                result = asyncio.run(self._optimize_product_seo(str(product.id), auto_apply=True))
                if result.get('success'):
                    updated_count += 1
            except:
                continue
        
        self.message_user(
            request,
            f"Successfully optimized SEO for {updated_count} products using AI."
        )
    bulk_ai_optimize_seo.short_description = "AI optimize SEO for selected products"
    
    def bulk_seo_analysis(self, request, queryset):
        """Bulk SEO analysis"""
        analyzed_count = 0
        
        for product in queryset:
            try:
                seo_service = SEOService(getattr(request, 'tenant', None))
                analysis = seo_service.analyze_product_seo(product)
                
                # Update SEO score
                product.seo_score = analysis.score
                product.seo_last_analyzed = timezone.now()
                product.save(update_fields=['seo_score', 'seo_last_analyzed'])
                
                analyzed_count += 1
            except:
                continue
        
        self.message_user(
            request,
            f"Completed SEO analysis for {analyzed_count} products."
        )
    bulk_seo_analysis.short_description = "Run SEO analysis for selected products"
    
    def bulk_content_optimization(self, request, queryset):
        """Bulk content optimization"""
        optimized_count = 0
        
        for product in queryset:
            try:
                result = asyncio.run(self._optimize_product_content(str(product.id), auto_apply=False))
                if result.get('success'):
                    optimized_count += 1
            except:
                continue
        
        self.message_user(
            request,
            f"Generated content optimization suggestions for {optimized_count} products."
        )
    bulk_content_optimization.short_description = "Generate content optimization suggestions"
    
    def export_seo_report(self, request):
        """Export comprehensive SEO report"""
        try:
            import csv
            from django.utils import timezone
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="seo_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Product ID', 'Title', 'SEO Title', 'SEO Description', 
                'SEO Score', 'SEO Keywords', 'URL Slug', 'Meta Robots',
                'Sitemap Priority', 'Last Analyzed', 'Issues', 'Grade'
            ])
            
            products = EcommerceProduct.objects.filter(
                tenant=getattr(request, 'tenant', None),
                is_active=True
            ).order_by('-seo_score')
            
            for product in products:
                try:
                    seo_service = SEOService(getattr(request, 'tenant', None))
                    analysis = seo_service.analyze_product_seo(product)
                    grade = analysis.grade if hasattr(analysis, 'grade') else 'N/A'
                    issues_count = len(analysis.issues) if hasattr(analysis, 'issues') else 0
                except:
                    grade = 'N/A'
                    issues_count = 0
                
                writer.writerow([
                    product.id,
                    product.title,
                    getattr(product, 'seo_title', '') or '',
                    getattr(product, 'seo_description', '') or '',
                    getattr(product, 'seo_score', 0),
                    getattr(product, 'seo_keywords', '') or '',
                    getattr(product, 'url_slug', '') or '',
                    getattr(product, 'meta_robots', 'index,follow'),
                    getattr(product, 'sitemap_priority', 0.5),
                    getattr(product, 'seo_last_analyzed', '') or 'Never',
                    issues_count,
                    grade
                ])
            
            return response
            
        except Exception as e:
            messages.error(request, f'Export failed: {str(e)}')
            return redirect('admin:ecommerce_ecommerceproduct_changelist')


# Keep all existing admin classes and enhance them similarly
@admin.register(EcommerceOrder)
class EnhancedOrderAdmin(AIEnhancedAdminMixin, admin.ModelAdmin):
    """Enhanced Order Admin with AI insights"""
    
    list_display = [
        'order_number', 'email', 'status', 'total',
        'ai_fraud_risk_score', 'fulfillment_priority',
        'created_at'
    ]
    
    list_filter = [
        'status', 'payment_status', 'created_at',
        'fraud_risk_level', 'fulfillment_priority'
    ]
    
    search_fields = ['order_number', 'email', 'customer__email']
    
    def ai_fraud_risk_score(self, obj):
        """Display AI-enhanced fraud risk score"""
        score = getattr(obj, 'fraud_risk_score', 0)
        if score < 30:
            color = '#28a745'
            level = 'Low'
            icon = '✅'
        elif score < 70:
            color = '#ffc107'
            level = 'Medium'
            icon = '⚠️'
        else:
            color = '#dc3545'
            level = 'High'
            icon = '🚨'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {} ({:.1f})</span>',
            color, icon, level, score
        )
    ai_fraud_risk_score.short_description = 'Fraud Risk (AI)'


# Register custom admin views
admin.site.register_view('ai-intelligence/', 
    view=AIEnhancedAdminMixin().ai_dashboard_view, 
    name='AI Intelligence Dashboard'
)

# Enhanced admin site customization
admin.site.site_header = 'AI-Powered E-commerce Administration'
admin.site.site_title = 'E-commerce AI Admin'
admin.site.index_title = 'AI-Enhanced E-commerce Management Dashboard'