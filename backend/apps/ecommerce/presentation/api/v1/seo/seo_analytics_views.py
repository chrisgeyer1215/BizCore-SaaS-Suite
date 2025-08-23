"""
SEO Analytics API Views
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Avg, Count, Q
from datetime import datetime, timedelta
import asyncio

from ....serializers.seo_serializers import SEOAnalyticsSerializer, SEOAuditSerializer
from .....infrastructure.seo.seo_analyzer import AdvancedSEOAnalyzer, SEOContentOptimizer
from .....domain.services.seo_service import SEOService
from .....models import EcommerceProduct, SEOAuditLog
from ...base import AdvancedAPIView


class SEODashboardAPIView(AdvancedAPIView):
    """SEO dashboard with comprehensive analytics"""
    
    permission_classes = [IsAuthenticated]
    
    @method_decorator(cache_page(60 * 30))  # Cache for 30 minutes
    def get(self, request):
        """Get SEO dashboard data"""
        try:
            tenant = self.get_tenant()
            
            # Get overall SEO metrics
            seo_metrics = self._get_seo_metrics(tenant)
            
            # Get top performing products
            top_performers = self._get_top_seo_performers(tenant)
            
            # Get products needing attention
            needs_attention = self._get_products_needing_attention(tenant)
            
            # Get SEO trends
            trends = self._get_seo_trends(tenant)
            
            # Get recent audit results
            recent_audits = self._get_recent_audits(tenant)
            
            dashboard_data = {
                'overview': seo_metrics,
                'top_performers': top_performers,
                'needs_attention': needs_attention,
                'trends': trends,
                'recent_audits': recent_audits,
                'recommendations': self._get_dashboard_recommendations(seo_metrics)
            }
            
            return Response(dashboard_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_seo_metrics(self, tenant):
        """Get overall SEO metrics"""
        products = EcommerceProduct.objects.filter(
            tenant=tenant,
            is_active=True,
            is_published=True
        )
        
        total_products = products.count()
        if total_products == 0:
            return {
                'total_products': 0,
                'average_seo_score': 0,
                'products_with_seo': 0,
                'optimization_rate': 0
            }
        
        # Calculate metrics
        seo_optimized = products.filter(
            Q(seo_title__isnull=False) & ~Q(seo_title='')
        ).count()
        
        avg_score = products.aggregate(
            avg_score=Avg('seo_score')
        )['avg_score'] or 0
        
        return {
            'total_products': total_products,
            'average_seo_score': round(avg_score, 1),
            'products_with_seo': seo_optimized,
            'optimization_rate': round((seo_optimized / total_products) * 100, 1),
            'score_distribution': self._get_score_distribution(products),
            'common_issues': self._get_common_issues(tenant)
        }
    
    def _get_score_distribution(self, products):
        """Get SEO score distribution"""
        ranges = [
            ('90-100', 90, 100),
            ('80-89', 80, 89),
            ('70-79', 70, 79),
            ('60-69', 60, 69),
            ('0-59', 0, 59)
        ]
        
        distribution = {}
        for label, min_score, max_score in ranges:
            count = products.filter(
                seo_score__gte=min_score,
                seo_score__lte=max_score
            ).count()
            distribution[label] = count
        
        return distribution
    
    def _get_common_issues(self, tenant):
        """Get most common SEO issues"""
        recent_audits = SEOAuditLog.objects.filter(
            product__tenant=tenant,
            audited_at__gte=datetime.now() - timedelta(days=30)
        )
        
        # This would analyze audit logs for common issues
        # For now, return mock data
        return [
            {'issue': 'Missing meta description', 'count': 45, 'percentage': 35},
            {'issue': 'Title too long', 'count': 32, 'percentage': 25},
            {'issue': 'Low keyword density', 'count': 28, 'percentage': 22},
            {'issue': 'Missing alt text', 'count': 23, 'percentage': 18}
        ]
    
    def _get_top_seo_performers(self, tenant):
        """Get top SEO performing products"""
        return EcommerceProduct.objects.filter(
            tenant=tenant,
            is_active=True,
            seo_score__gte=80
        ).order_by('-seo_score')[:10].values(
            'id', 'title', 'seo_score', 'seo_title'
        )
    
    def _get_products_needing_attention(self, tenant):
        """Get products that need SEO attention"""
        return EcommerceProduct.objects.filter(
            tenant=tenant,
            is_active=True
        ).filter(
            Q(seo_score__lt=60) | 
            Q(seo_title__isnull=True) | 
            Q(seo_title='')
        ).order_by('seo_score')[:10].values(
            'id', 'title', 'seo_score', 'seo_last_analyzed'
        )
    
    def _get_seo_trends(self, tenant):
        """Get SEO performance trends"""
        # This would analyze historical SEO data
        # For now, return mock trend data
        return {
            'score_trend': [
                {'date': '2024-01-01', 'avg_score': 72.5},
                {'date': '2024-01-15', 'avg_score': 74.2},
                {'date': '2024-02-01', 'avg_score': 76.8},
                {'date': '2024-02-15', 'avg_score': 78.1},
            ],
            'optimization_trend': [
                {'date': '2024-01-01', 'optimized_products': 125},
                {'date': '2024-01-15', 'optimized_products': 142},
                {'date': '2024-02-01', 'optimized_products': 158},
                {'date': '2024-02-15', 'optimized_products': 167},
            ]
        }
    
    def _get_recent_audits(self, tenant):
        """Get recent SEO audits"""
        return SEOAuditLog.objects.filter(
            product__tenant=tenant
        ).order_by('-audited_at')[:10].values(
            'product__title', 'audit_type', 'score', 
            'audited_at', 'issues'
        )
    
    def _get_dashboard_recommendations(self, metrics):
        """Get recommendations for SEO dashboard"""
        recommendations = []
        
        if metrics['optimization_rate'] < 50:
            recommendations.append({
                'priority': 'high',
                'title': 'Improve SEO Coverage',
                'description': f"Only {metrics['optimization_rate']}% of products have SEO optimization",
                'action': 'Add SEO titles and descriptions to more products'
            })
        
        if metrics['average_seo_score'] < 70:
            recommendations.append({
                'priority': 'medium',
                'title': 'Boost SEO Scores',
                'description': f"Average SEO score is {metrics['average_seo_score']}",
                'action': 'Run comprehensive SEO audit and fix identified issues'
            })
        
        return recommendations


class ProductSEOAnalysisAPIView(AdvancedAPIView):
    """Individual product SEO analysis"""
    
    def get(self, request, product_id):
        """Get detailed SEO analysis for a product"""
        try:
            product = EcommerceProduct.objects.get(
                id=product_id,
                tenant=self.get_tenant()
            )
            
            # Run SEO analysis
            seo_service = SEOService(self.get_tenant())
            seo_analysis = seo_service.analyze_product_seo(product)
            
            # Get historical audit data
            audit_history = SEOAuditLog.objects.filter(
                product=product
            ).order_by('-audited_at')[:10]
            
            # Get content optimization suggestions
            if product.description:
                content_optimizer = SEOContentOptimizer(self.get_tenant())
                keywords = product.seo_keywords.split(',') if product.seo_keywords else [product.title]
                content_optimization = asyncio.run(
                    content_optimizer.optimize_content_for_keywords(
                        product.description, 
                        [k.strip() for k in keywords]
                    )
                )
            else:
                content_optimization = None
            
            return Response({
                'product_id': product_id,
                'product_title': product.title,
                'seo_analysis': {
                    'score': seo_analysis.score,
                    'grade': seo_analysis.grade,
                    'issues': seo_analysis.issues,
                    'recommendations': seo_analysis.recommendations,
                    'keyword_density': seo_analysis.keyword_density,
                    'readability_score': seo_analysis.readability_score
                },
                'content_optimization': content_optimization,
                'audit_history': [
                    {
                        'date': audit.audited_at,
                        'type': audit.audit_type,
                        'score': audit.score,
                        'issues_count': len(audit.issues or [])
                    }
                    for audit in audit_history
                ],
                'competitor_analysis': self._get_competitor_analysis(product),
                'optimization_opportunities': self._get_optimization_opportunities(product, seo_analysis)
            })
            
        except EcommerceProduct.DoesNotExist:
            return Response({
                'error': 'Product not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return self.handle_exception(e)
    
    def post(self, request, product_id):
        """Update product SEO based on recommendations"""
        try:
            product = EcommerceProduct.objects.get(
                id=product_id,
                tenant=self.get_tenant()
            )
            
            updates = request.data.get('seo_updates', {})
            
            # Update SEO fields
            if 'seo_title' in updates:
                product.seo_title = updates['seo_title']
            if 'seo_description' in updates:
                product.seo_description = updates['seo_description']
            if 'seo_keywords' in updates:
                product.seo_keywords = updates['seo_keywords']
            
            product.save()
            
            # Re-analyze after updates
            seo_service = SEOService(self.get_tenant())
            updated_analysis = seo_service.analyze_product_seo(product)
            
            return Response({
                'success': True,
                'message': 'SEO updated successfully',
                'updated_score': updated_analysis.score,
                'improvements': self._calculate_improvements(
                    request.data.get('previous_score', 0),
                    updated_analysis.score
                )
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_competitor_analysis(self, product):
        """Get competitor analysis for product"""
        # This would analyze competitors for the product's keywords
        return {
            'avg_competitor_score': 78.5,
            'your_ranking': 'Above Average',
            'improvement_potential': 15.2,
            'top_competitors': [
                {'domain': 'competitor1.com', 'score': 85.2},
                {'domain': 'competitor2.com', 'score': 82.7}
            ]
        }
    
    def _get_optimization_opportunities(self, product, analysis):
        """Get specific optimization opportunities"""
        opportunities = []
        
        if analysis.score < 80:
            if not product.seo_title:
                opportunities.append({
                    'type': 'title',
                    'impact': 'high',
                    'description': 'Add SEO-optimized title',
                    'potential_score_increase': 15
                })
            
            if not product.seo_description:
                opportunities.append({
                    'type': 'description',
                    'impact': 'high',
                    'description': 'Add compelling meta description',
                    'potential_score_increase': 12
                })
        
        return opportunities
    
    def _calculate_improvements(self, old_score, new_score):
        """Calculate SEO improvements"""
        improvement = new_score - old_score
        return {
            'score_change': round(improvement, 1),
            'percentage_change': round((improvement / old_score) * 100, 1) if old_score > 0 else 0,
            'status': 'improved' if improvement > 0 else 'declined' if improvement < 0 else 'unchanged'
        }