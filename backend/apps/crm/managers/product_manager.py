"""
Product Manager - Product Catalog Management
Advanced product analytics and pricing management
"""

from django.db.models import Q, Count, Sum, Avg, Max, Min, Case, When, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .base import AnalyticsManager


class ProductManager(AnalyticsManager):
    """
    Advanced Product Manager
    Product performance and sales analytics
    """
    
    def active_products(self):
        """Get active products"""
        return self.filter(is_active=True)
    
    def by_category(self, category):
        """Filter products by category"""
        return self.filter(category=category)
    
    def high_value_products(self, threshold=Decimal('1000')):
        """Get products above price threshold"""
        return self.filter(base_price__gte=threshold)
    
    def bestsellers(self, days=30):
        """Get best-selling products"""
        from ..models import OpportunityProduct
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.annotate(
            sales_count=Count('opportunityproduct', filter=Q(
                opportunityproduct__opportunity__stage__is_won=True,
                opportunityproduct__opportunity__won_date__range=[start_date, end_date]
            ))
        ).filter(sales_count__gt=0).order_by('-sales_count')
    
    def low_performers(self, days=90):
        """Get products with low sales performance"""
        from ..models import OpportunityProduct
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        return self.annotate(
            sales_count=Count('opportunityproduct', filter=Q(
                opportunityproduct__opportunity__stage__is_won=True,
                opportunityproduct__opportunity__won_date__range=[start_date, end_date]
            ))
        ).filter(sales_count__lte=1).order_by('sales_count')
    
    def get_product_performance_analytics(self, tenant, days=90):
        """Get comprehensive product performance analytics"""
        from ..models import OpportunityProduct, Opportunity
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Overall product metrics
        product_metrics = self.for_tenant(tenant).aggregate(
            total_products=Count('id'),
            active_products=Count('id', filter=Q(is_active=True)),
            avg_product_price=Avg('base_price'),
            highest_priced=Max('base_price'),
            lowest_priced=Min('base_price')
        )
        
        # Sales performance by product
        product_sales = self.for_tenant(tenant).annotate(
            # Sales metrics
            total_sales=Count('opportunityproduct', filter=Q(
                opportunityproduct__opportunity__stage__is_won=True,
                opportunityproduct__opportunity__won_date__range=[start_date, end_date]
            )),
            total_revenue=Sum('opportunityproduct__price', filter=Q(
                opportunityproduct__opportunity__stage__is_won=True,
                opportunityproduct__opportunity__won_date__range=[start_date, end_date]
            )),
            avg_selling_price=Avg('opportunityproduct__price', filter=Q(
                opportunityproduct__opportunity__stage__is_won=True,
                opportunityproduct__opportunity__won_date__range=[start_date, end_date]
            )),
            
            # Pipeline metrics
            opportunities_in_pipeline=Count('opportunityproduct', filter=Q(
                opportunityproduct__opportunity__stage__is_closed=False
            )),
            pipeline_value=Sum('opportunityproduct__price', filter=Q(
                opportunityproduct__opportunity__stage__is_closed=False
            ))
        ).order_by('-total_revenue')
        
        return {
            'overall_metrics': product_metrics,
            'product_performance': list(product_sales),
            'period': f"Last {days} days"
        }
    
    def get_pricing_analytics(self, tenant):
        """Analyze product pricing performance"""
        from ..models import OpportunityProduct
        
        pricing_data = []
        products = self.for_tenant(tenant).filter(is_active=True)
        
        for product in products:
            # Get pricing statistics from actual sales
            sales_data = OpportunityProduct.objects.filter(
                product=product,
                opportunity__stage__is_won=True
            ).aggregate(
                avg_selling_price=Avg('price'),
                min_selling_price=Min('price'),
                max_selling_price=Max('price'),
                total_sales=Count('id'),
                total_revenue=Sum('price')
            )
            
            # Calculate pricing metrics
            base_price = product.base_price
            avg_selling_price = sales_data['avg_selling_price'] or base_price
            
            price_variance = 0
            discount_rate = 0
            
            if base_price and base_price > 0:
                price_variance = abs(avg_selling_price - base_price) / base_price * 100
                if avg_selling_price < base_price:
                    discount_rate = (base_price - avg_selling_price) / base_price * 100
            
            pricing_data.append({
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'base_price': base_price
                },
                'pricing_metrics': {
                    **sales_data,
                    'price_variance_percent': round(price_variance, 2),
                    'average_discount_rate': round(discount_rate, 2),
                    'pricing_consistency': 100 - price_variance  # Higher is better
                }
            })
        
        return pricing_data
    
    def get_product_lifecycle_analysis(self, tenant):
        """Analyze product lifecycle stages"""
        from ..models import OpportunityProduct
        
        lifecycle_data = []
        products = self.for_tenant(tenant)
        
        for product in products:
            # Calculate product age
            product_age_days = (timezone.now().date() - product.created_at.date()).days
            
            # Sales velocity (sales per month)
            sales_count = OpportunityProduct.objects.filter(
                product=product,
                opportunity__stage__is_won=True
            ).count()
            
            months_active = max(1, product_age_days / 30)  # Avoid division by zero
            sales_velocity = sales_count / months_active
            
            # Recent sales trend (last 3 months vs previous 3 months)
            recent_sales = OpportunityProduct.objects.filter(
                product=product,
                opportunity__stage__is_won=True,
                opportunity__won_date__gte=timezone.now() - timedelta(days=90)
            ).count()
            
            previous_sales = OpportunityProduct.objects.filter(
                product=product,
                opportunity__stage__is_won=True,
                opportunity__won_date__range=[
                    timezone.now() - timedelta(days=180),
                    timezone.now() - timedelta(days=90)
                ]
            ).count()
            
            trend = 'stable'
            if recent_sales > previous_sales * 1.2:
                trend = 'growing'
            elif recent_sales < previous_sales * 0.8:
                trend = 'declining'
            
            # Determine lifecycle stage
            lifecycle_stage = self._determine_lifecycle_stage(
                product_age_days, sales_velocity, trend, recent_sales
            )
            
            lifecycle_data.append({
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'created_at': product.created_at
                },
                'lifecycle_metrics': {
                    'age_days': product_age_days,
                    'sales_velocity': round(sales_velocity, 2),
                    'recent_sales': recent_sales,
                    'previous_sales': previous_sales,
                    'trend': trend,
                    'lifecycle_stage': lifecycle_stage
                }
            })
        
        return lifecycle_data
    
    def _determine_lifecycle_stage(self, age_days, velocity, trend, recent_sales):
        """Determine product lifecycle stage"""
        if age_days < 90:
            return 'introduction'
        elif trend == 'growing' and velocity > 1:
            return 'growth'
        elif velocity >= 0.5 and recent_sales > 5:
            return 'maturity'
        elif trend == 'declining' or velocity < 0.2:
            return 'decline'
        else:
            return 'maturity'
    
    def get_competitive_analysis(self, tenant):
        """Analyze product competitiveness"""
        from ..models import OpportunityProduct, Opportunity
        
        competitive_data = []
        products = self.for_tenant(tenant).filter(is_active=True)
        
        for product in products:
            # Win rate analysis
            opportunities_with_product = Opportunity.objects.filter(
                tenant=tenant,
                opportunityproduct__product=product
            ).distinct()
            
            total_opportunities = opportunities_with_product.count()
            won_opportunities = opportunities_with_product.filter(
                stage__is_won=True
            ).count()
            
            win_rate = (won_opportunities / total_opportunities * 100) if total_opportunities > 0 else 0
            
            # Average deal size
            avg_deal_size = opportunities_with_product.filter(
                stage__is_won=True
            ).aggregate(
                avg_value=Avg('value')
            )['avg_value'] or 0
            
            # Sales cycle length
            avg_sales_cycle = opportunities_with_product.filter(
                stage__is_won=True,
                won_date__isnull=False
            ).aggregate(
                avg_cycle=Avg(F('won_date') - F('created_at'))
            )['avg_cycle']
            
            avg_cycle_days = avg_sales_cycle.days if avg_sales_cycle else 0
            
            # Competitive score (0-100)
            competitive_score = self._calculate_competitive_score(
                win_rate, avg_deal_size, avg_cycle_days, product.base_price
            )
            
            competitive_data.append({
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'base_price': product.base_price
                },
                'competitive_metrics': {
                    'win_rate': round(win_rate, 2),
                    'avg_deal_size': round(avg_deal_size, 2),
                    'avg_sales_cycle_days': avg_cycle_days,
                    'competitive_score': competitive_score,
                    'competitiveness_level': self._get_competitiveness_level(competitive_score)
                }
            })
        
        return sorted(competitive_data, key=lambda x: x['competitive_metrics']['competitive_score'], reverse=True)
    
    def _calculate_competitive_score(self, win_rate, deal_size, cycle_days, base_price):
        """Calculate competitive score (0-100)"""
        score = 0
        
        # Win rate component (40 points)
        score += min(win_rate * 0.4, 40)
        
        # Deal size component (30 points)
        if base_price and base_price > 0:
            deal_size_multiplier = deal_size / base_price
            score += min(deal_size_multiplier * 10, 30)
        
        # Sales cycle component (30 points) - shorter cycle is better
        if cycle_days > 0:
            # Assume 90 days is ideal cycle
            ideal_cycle = 90
            cycle_score = max(0, 30 - (abs(cycle_days - ideal_cycle) / ideal_cycle * 30))
            score += cycle_score
        
        return round(min(score, 100), 2)
    
    def _get_competitiveness_level(self, score):
        """Convert competitive score to level"""
        if score >= 80:
            return 'Highly Competitive'
        elif score >= 60:
            return 'Competitive'
        elif score >= 40:
            return 'Moderately Competitive'
        else:
            return 'Needs Improvement'
    
    def optimize_product_portfolio(self, tenant, optimization_criteria):
        """
        Provide product portfolio optimization recommendations
        
        optimization_criteria format:
        {
            'min_win_rate': 30,
            'max_sales_cycle': 120,
            'min_revenue_contribution': 1000,
            'lifecycle_focus': ['growth', 'maturity']
        }
        """
        # Get comprehensive product data
        performance_data = self.get_product_performance_analytics(tenant, 180)
        competitive_data = self.get_competitive_analysis(tenant)
        lifecycle_data = self.get_product_lifecycle_analysis(tenant)
        
        # Create lookup dictionaries
        competitive_lookup = {item['product']['id']: item for item in competitive_data}
        lifecycle_lookup = {item['product']['id']: item for item in lifecycle_data}
        
        recommendations = []
        
        for product_perf in performance_data['product_performance']:
            product_id = product_perf.id
            competitive_info = competitive_lookup.get(product_id, {})
            lifecycle_info = lifecycle_lookup.get(product_id, {})
            
            # Analyze against criteria
            competitive_metrics = competitive_info.get('competitive_metrics', {})
            lifecycle_metrics = lifecycle_info.get('lifecycle_metrics', {})
            
            win_rate = competitive_metrics.get('win_rate', 0)
            sales_cycle = competitive_metrics.get('avg_sales_cycle_days', 0)
            revenue_contribution = product_perf.total_revenue or 0
            lifecycle_stage = lifecycle_metrics.get('lifecycle_stage', 'unknown')
            
            recommendation = {
                'product': {
                    'id': product_id,
                    'name': product_perf.name,
                    'sku': product_perf.sku
                },
                'current_metrics': {
                    'win_rate': win_rate,
                    'sales_cycle': sales_cycle,
                    'revenue_contribution': revenue_contribution,
                    'lifecycle_stage': lifecycle_stage
                },
                'recommendations': []
            }
            
            # Generate recommendations based on criteria
            if win_rate < optimization_criteria.get('min_win_rate', 30):
                recommendation['recommendations'].append({
                    'type': 'improve_competitiveness',
                    'priority': 'high',
                    'action': 'Review pricing, features, or positioning'
                })
            
            if sales_cycle > optimization_criteria.get('max_sales_cycle', 120):
                recommendation['recommendations'].append({
                    'type': 'reduce_sales_cycle',
                    'priority': 'medium',
                    'action': 'Simplify sales process or improve sales training'
                })
            
            if revenue_contribution < optimization_criteria.get('min_revenue_contribution', 1000):
                recommendation['recommendations'].append({
                    'type': 'low_revenue_contribution',
                    'priority': 'medium',
                    'action': 'Consider discontinuation or repositioning'
                })
            
            if lifecycle_stage == 'decline':
                recommendation['recommendations'].append({
                    'type': 'product_decline',
                    'priority': 'high',
                    'action': 'Plan phase-out or major refresh'
                })
            elif lifecycle_stage in optimization_criteria.get('lifecycle_focus', ['growth', 'maturity']):
                recommendation['recommendations'].append({
                    'type': 'strategic_focus',
                    'priority': 'high',
                    'action': 'Increase marketing and sales focus'
                })
            
            if recommendation['recommendations']:
                recommendations.append(recommendation)
        
        return {
            'optimization_recommendations': recommendations,
            'summary': {
                'products_analyzed': len(performance_data['product_performance']),
                'products_needing_attention': len(recommendations),
                'criteria_applied': optimization_criteria
            }
        }
    
    def bulk_update_pricing(self, tenant, pricing_rules):
        """
        Bulk update product pricing based on rules
        
        pricing_rules format:
        {
            'category_adjustments': {
                'category_id': {'adjustment_type': 'percentage', 'value': 10},
                'category_id': {'adjustment_type': 'fixed', 'value': 100}
            },
            'performance_based': {
                'high_performers': {'adjustment_type': 'percentage', 'value': 15},
                'low_performers': {'adjustment_type': 'percentage', 'value': -10}
            }
        }
        """
        updated_products = []
        
        # Category-based pricing adjustments
        for category_id, adjustment in pricing_rules.get('category_adjustments', {}).items():
            products = self.for_tenant(tenant).filter(
                category_id=category_id,
                is_active=True
            )
            
            for product in products:
                old_price = product.base_price
                new_price = self._apply_pricing_adjustment(old_price, adjustment)
                
                product.base_price = new_price
                product.save(update_fields=['base_price', 'modified_at'])
                
                updated_products.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'old_price': old_price,
                    'new_price': new_price,
                    'adjustment_reason': f"Category adjustment ({adjustment['adjustment_type']})"
                })
        
        # Performance-based adjustments
        performance_rules = pricing_rules.get('performance_based', {})
        if performance_rules:
            # Get product performance data
            bestsellers = self.bestsellers(90)
            low_performers = self.low_performers(90)
            
            # Adjust high performers
            if 'high_performers' in performance_rules:
                adjustment = performance_rules['high_performers']
                for product in bestsellers[:10]:  # Top 10
                    old_price = product.base_price
                    new_price = self._apply_pricing_adjustment(old_price, adjustment)
                    
                    product.base_price = new_price
                    product.save(update_fields=['base_price', 'modified_at'])
                    
                    updated_products.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'old_price': old_price,
                        'new_price': new_price,
                        'adjustment_reason': 'High performer price increase'
                    })
            
            # Adjust low performers
            if 'low_performers' in performance_rules:
                adjustment = performance_rules['low_performers']
                for product in low_performers[:5]:  # Bottom 5
                    old_price = product.base_price
                    new_price = self._apply_pricing_adjustment(old_price, adjustment)
                    
                    product.base_price = new_price
                    product.save(update_fields=['base_price', 'modified_at'])
                    
                    updated_products.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'old_price': old_price,
                        'new_price': new_price,
                        'adjustment_reason': 'Low performer price reduction'
                    })
        
        return {
            'updated_products': updated_products,
            'total_updated': len(updated_products)
        }
    
    def _apply_pricing_adjustment(self, base_price, adjustment):
        """Apply pricing adjustment based on type and value"""
        if adjustment['adjustment_type'] == 'percentage':
            multiplier = 1 + (adjustment['value'] / 100)
            return base_price * Decimal(str(multiplier))
        elif adjustment['adjustment_type'] == 'fixed':
            return base_price + Decimal(str(adjustment['value']))
        else:
            return base_price