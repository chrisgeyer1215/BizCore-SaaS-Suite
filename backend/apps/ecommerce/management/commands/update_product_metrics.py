from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta
from apps.ecommerce.models import (
    EcommerceProduct, ProductAnalytics, Order, OrderItem, 
    Cart, CartItem, ReviewRating
)
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update product performance metrics and analytics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-ids',
            type=str,
            help='Comma-separated product IDs to update'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to calculate metrics for'
        )

    def handle(self, *args, **options):
        product_ids = options.get('product_ids')
        days = options.get('days')
        
        # Build queryset
        queryset = EcommerceProduct.objects.filter(is_published=True)
        
        if product_ids:
            ids = [int(id.strip()) for id in product_ids.split(',')]
            queryset = queryset.filter(id__in=ids)

        total_products = queryset.count()
        self.stdout.write(f'Updating metrics for {total_products} products...')

        date_threshold = timezone.now() - timedelta(days=days)
        updated_count = 0

        for product in queryset.iterator():
            try:
                analytics, created = ProductAnalytics.objects.get_or_create(
                    product=product,
                    defaults={'tenant': product.tenant}
                )
                
                # Update metrics
                self.update_sales_metrics(product, analytics, date_threshold)
                self.update_cart_metrics(product, analytics, date_threshold)
                self.update_review_metrics(product, analytics)
                self.update_performance_metrics(product, analytics)
                
                analytics.save()
                updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f'Processed {updated_count} products...')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error updating {product.title}: {str(e)}')
                )
                logger.error(f'Metrics update error for product {product.id}: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(f'Updated metrics for {updated_count} products')
        )

    def update_sales_metrics(self, product, analytics, date_threshold):
        """Update sales-related metrics"""
        # Total sales
        order_items = OrderItem.objects.filter(
            product=product,
            order__status__in=['COMPLETED', 'DELIVERED']
        )
        
        analytics.times_purchased = order_items.count()
        
        # Revenue metrics
        revenue_data = order_items.aggregate(
            total_revenue=Sum('line_total'),
            avg_order_value=Avg('line_total')
        )
        
        analytics.total_revenue = revenue_data['total_revenue'] or 0
        analytics.average_order_value = revenue_data['avg_order_value'] or 0
        
        # Update product-level sales count
        product.sales_count = analytics.times_purchased
        product.save(update_fields=['sales_count'])

    def update_cart_metrics(self, product, analytics, date_threshold):
        """Update cart-related metrics"""
        # Cart additions
        cart_additions = CartItem.objects.filter(
            product=product,
            created_at__gte=date_threshold
        )
        
        analytics.times_added_to_cart = cart_additions.count()
        
        # Calculate conversion rate
        if analytics.times_added_to_cart > 0:
            conversion_rate = (analytics.times_purchased / analytics.times_added_to_cart) * 100
            analytics.conversion_rate = min(conversion_rate, 100)  # Cap at 100%
        
        # Calculate abandonment rate
        abandoned_carts = cart_additions.filter(
            cart__status='abandoned'
        ).count()
        
        if analytics.times_added_to_cart > 0:
            abandonment_rate = (abandoned_carts / analytics.times_added_to_cart) * 100
            analytics.cart_abandonment_rate = min(abandonment_rate, 100)

    def update_review_metrics(self, product, analytics):
        """Update review-related metrics"""
        reviews = ReviewRating.objects.filter(
            product=product,
            is_approved=True
        )
        
        review_stats = reviews.aggregate(
            count=Count('id'),
            avg_rating=Avg('rating')
        )
        
        # Update product-level metrics
        product.review_count = review_stats['count'] or 0
        product.average_rating = review_stats['avg_rating'] or 0
        product.save(update_fields=['review_count', 'average_rating'])

    def update_performance_metrics(self, product, analytics):
        """Update performance metrics"""
        # Simple search ranking score based on multiple factors
        score = 0
        
        # Sales performance (0-40 points)
        if analytics.times_purchased > 0:
            score += min(analytics.times_purchased * 2, 40)
        
        # Review performance (0-30 points)
        if product.review_count > 0:
            score += min(product.average_rating * 6, 30)
        
        # Conversion performance (0-30 points)
        if analytics.conversion_rate > 0:
            score += min(analytics.conversion_rate * 0.3, 30)
        
        analytics.search_ranking_score = score
