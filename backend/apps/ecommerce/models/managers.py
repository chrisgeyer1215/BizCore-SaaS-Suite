# apps/ecommerce/models/managers.py

"""
Custom managers and querysets for e-commerce models
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta


class PublishedProductManager(models.Manager):
    """Manager for published products only"""
    
    def get_queryset(self):
        return super().get_queryset().filter(
            is_active=True,
            is_published=True,
            status='PUBLISHED'
        )
    
    def in_stock(self):
        """Products that are in stock"""
        return self.filter(
            models.Q(track_quantity=False) | 
            models.Q(stock_quantity__gt=0) |
            models.Q(inventory_policy='CONTINUE')
        )
    
    def out_of_stock(self):
        """Products that are out of stock"""
        return self.filter(
            track_quantity=True,
            stock_quantity=0,
            inventory_policy='DENY'
        )
    
    def low_stock(self, threshold=10):
        """Products with low stock"""
        return self.filter(
            track_quantity=True,
            stock_quantity__lte=threshold,
            stock_quantity__gt=0
        )
    
    def by_collection(self, collection_slug):
        """Products in a specific collection"""
        return self.filter(collections__handle=collection_slug)
    
    def by_price_range(self, min_price, max_price):
        """Products within price range"""
        return self.filter(price__range=[min_price, max_price])
    
    def by_brand(self, brand):
        """Products by specific brand"""
        return self.filter(brand__iexact=brand)
    
    def featured(self):
        """Featured products"""
        return self.filter(is_featured=True)
    
    def on_sale(self):
        """Products on sale (have compare_at_price)"""
        return self.filter(
            compare_at_price__isnull=False,
            compare_at_price__gt=models.F('price')
        )
    
    def best_sellers(self, limit=10):
        """Best selling products"""
        return self.filter(sales_count__gt=0).order_by('-sales_count')[:limit]
    
    def new_arrivals(self, days=30):
        """New arrivals within specified days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date).order_by('-created_at')
    
    def most_viewed(self, limit=10):
        """Most viewed products"""
        return self.filter(view_count__gt=0).order_by('-view_count')[:limit]
    
    def highest_rated(self, min_rating=4.0, limit=10):
        """Highest rated products"""
        return self.filter(
            average_rating__gte=min_rating,
            review_count__gt=0
        ).order_by('-average_rating', '-review_count')[:limit]
    
    def search(self, query):
        """Search products by title, description, brand, SKU"""
        return self.filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query) |
            models.Q(brand__icontains=query) |
            models.Q(sku__icontains=query) |
            models.Q(tags__icontains=query)
        )
    
    def with_analytics(self):
        """Products with analytics data"""
        return self.select_related('metrics')
    
    def optimized(self):
        """Optimized queryset with common relations"""
        return self.select_related(
            'inventory_product',
            'primary_collection',
            'metrics'
        ).prefetch_related(
            'variants',
            'collections',
            'images'
        )
    
    def for_sitemap(self):
        """Products for sitemap generation"""
        return self.only('url_handle', 'updated_at')
    
    def trending(self, days=7, limit=10):
        """Trending products based on recent activity"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            updated_at__gte=cutoff_date
        ).order_by('-view_count', '-sales_count')[:limit]


class OrderQuerySet(models.QuerySet):
    """Custom queryset for orders with common filtering"""
    
    def pending(self):
        """Pending reviews"""
        return self.filter(status='PENDING')
    
    def rejected(self):
        """Rejected reviews"""
        return self.filter(status='REJECTED')
    
    def for_product(self, product):
        """Reviews for specific product"""
        return self.filter(product=product)
    
    def by_rating(self, rating):
        """Reviews with specific rating"""
        return self.filter(rating=rating)
    
    def high_rating(self, min_rating=4):
        """High rating reviews"""
        return self.filter(rating__gte=min_rating)
    
    def low_rating(self, max_rating=2):
        """Low rating reviews"""
        return self.filter(rating__lte=max_rating)
    
    def verified_purchase(self):
        """Reviews from verified purchases"""
        return self.filter(verified_purchase=True)
    
    def with_photos(self):
        """Reviews that include photos"""
        return self.exclude(images='[]')
    
    def recent(self, days=30):
        """Recent reviews"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)
    
    def helpful(self, min_helpful_votes=5):
        """Helpful reviews"""
        return self.filter(helpful_votes__gte=min_helpful_votes)


class WishlistManager(models.Manager):
    """Custom manager for wishlists"""
    
    def for_user(self, user):
        """Wishlists for specific user"""
        return self.filter(user=user)
    
    def public(self):
        """Public wishlists"""
        return self.filter(visibility='PUBLIC')
    
    def shared(self):
        """Shared wishlists"""
        return self.filter(visibility='SHARED')
    
    def default_for_user(self, user):
        """Get default wishlist for user"""
        try:
            return self.get(user=user, is_default=True)
        except self.model.DoesNotExist:
            return self.create(
                user=user,
                name='My Wishlist',
                is_default=True
            )


class DiscountManager(models.Manager):
    """Custom manager for discounts and coupons"""
    
    def active(self):
        """Active discounts"""
        now = timezone.now()
        return self.filter(
            is_active=True,
            starts_at__lte=now,
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
        )
    
    def expired(self):
        """Expired discounts"""
        return self.filter(
            ends_at__lt=timezone.now()
        )
    
    def by_type(self, discount_type):
        """Discounts by type"""
        return self.filter(discount_type=discount_type)
    
    def automatic(self):
        """Automatic discounts"""
        return self.filter(is_automatic=True)
    
    def coupon_codes(self):
        """Coupon code discounts"""
        return self.filter(is_automatic=False)
    
    def applicable_to_product(self, product):
        """Discounts applicable to a specific product"""
        return self.active().filter(
            models.Q(applies_to='ALL') |
            models.Q(applies_to='SPECIFIC_PRODUCTS', applicable_products=product) |
            models.Q(applies_to='SPECIFIC_COLLECTIONS', applicable_collections__in=product.collections.all())
        )
    
    def usage_remaining(self):
        """Discounts with remaining usage"""
        return self.filter(
            models.Q(usage_limit__isnull=True) |
            models.Q(usage_count__lt=models.F('usage_limit'))
        )


class CollectionManager(models.Manager):
    """Custom manager for collections"""
    
    def visible(self):
        """Visible collections"""
        return self.filter(is_visible=True)
    
    def featured(self):
        """Featured collections"""
        return self.filter(is_featured=True)
    
    def manual(self):
        """Manual collections"""
        return self.filter(collection_type='MANUAL')
    
    def automatic(self):
        """Automatic/smart collections"""
        return self.filter(collection_type='AUTOMATIC')
    
    def root_collections(self):
        """Root level collections (no parent)"""
        return self.filter(parent__isnull=True)
    
    def with_products(self):
        """Collections with products"""
        return self.filter(products_count__gt=0)
    
    def by_level(self, level):
        """Collections at specific level"""
        return self.filter(level=level)
    
    def navigation_tree(self):
        """Collections for navigation (optimized)"""
        return self.visible().select_related('parent').order_by('display_order', 'title')


class PaymentTransactionManager(models.Manager):
    """Custom manager for payment transactions"""
    
    def successful(self):
        """Successful transactions"""
        return self.filter(status='CAPTURED')
    
    def failed(self):
        """Failed transactions"""
        return self.filter(status='FAILED')
    
    def pending(self):
        """Pending transactions"""
        return self.filter(status='PENDING')
    
    def authorized(self):
        """Authorized but not captured"""
        return self.filter(status='AUTHORIZED')
    
    def refunded(self):
        """Refunded transactions"""
        return self.filter(status='REFUNDED')
    
    def by_payment_method(self, method):
        """Transactions by payment method"""
        return self.filter(payment_method=method)
    
    def by_gateway(self, gateway):
        """Transactions by payment gateway"""
        return self.filter(payment_gateway=gateway)
    
    def for_order(self, order):
        """Transactions for specific order"""
        return self.filter(order=order)
    
    def today(self):
        """Transactions from today"""
        today = timezone.now().date()
        return self.filter(created_at__date=today)
    
    def this_month(self):
        """Transactions from this month"""
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=start_of_month)
    
    def high_value(self, threshold=1000):
        """High value transactions"""
        return self.filter(amount__gte=threshold)


class ShippingMethodManager(models.Manager):
    """Custom manager for shipping methods"""
    
    def active(self):
        """Active shipping methods"""
        return self.filter(is_active=True)
    
    def for_zone(self, zone):
        """Shipping methods for specific zone"""
        return self.filter(zone=zone)
    
    def free_shipping(self):
        """Free shipping methods"""
        return self.filter(cost=0)
    
    def express(self):
        """Express shipping methods"""
        return self.filter(delivery_time_max__lte=2)  # 2 days or less
    
    def standard(self):
        """Standard shipping methods"""
        return self.filter(delivery_time_min__gte=3, delivery_time_max__lte=7)
    
    def for_weight_range(self, weight):
        """Shipping methods applicable to weight"""
        return self.filter(
            models.Q(max_weight__isnull=True) | models.Q(max_weight__gte=weight),
            models.Q(min_weight__isnull=True) | models.Q(min_weight__lte=weight)
        )


class AnalyticsQuerySet(models.QuerySet):
    """Custom queryset for analytics models"""
    
    def for_date_range(self, start_date, end_date):
        """Analytics data for date range"""
        return self.filter(date__range=[start_date, end_date])
    
    def for_product(self, product):
        """Analytics for specific product"""
        return self.filter(product=product)
    
    def summarize_by_date(self):
        """Summarize analytics by date"""
        return self.values('date').annotate(
            total_views=models.Sum('views'),
            total_orders=models.Sum('orders'),
            total_revenue=models.Sum('revenue')
        ).order_by('date')
    
    def top_performers(self, metric='revenue', limit=10):
        """Get top performing items by metric"""
        return self.order_by(f'-{metric}')[:limit]


class CustomerGroupManager(models.Manager):
    """Custom manager for customer groups"""
    
    def active(self):
        """Active customer groups"""
        return self.filter(is_active=True)
    
    def vip(self):
        """VIP customer groups"""
        return self.filter(is_vip=True)
    
    def automatic(self):
        """Automatic customer groups"""
        return self.filter(assignment_type='AUTOMATIC')
    
    def manual(self):
        """Manual customer groups"""
        return self.filter(assignment_type='MANUAL')
    
    def with_discounts(self):
        """Groups with associated discounts"""
        return self.filter(group_discounts__isnull=False).distinct()


class GiftCardManager(models.Manager):
    """Custom manager for gift cards"""
    
    def active(self):
        """Active gift cards"""
        return self.filter(is_active=True)
    
    def valid(self):
        """Valid (not expired, not fully used) gift cards"""
        now = timezone.now()
        return self.filter(
            is_active=True,
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now),
            balance__gt=0
        )
    
    def expired(self):
        """Expired gift cards"""
        return self.filter(expires_at__lt=timezone.now())
    
    def used(self):
        """Fully used gift cards"""
        return self.filter(balance=0)
    
    def by_customer(self, customer):
        """Gift cards for specific customer"""
        return self.filter(customer=customer)
    
    def purchased_today(self):
        """Gift cards purchased today"""
        today = timezone.now().date()
        return self.filter(purchased_at__date=today)


class ReturnRequestManager(models.Manager):
    """Custom manager for return requests"""
    
    def pending(self):
        """Pending return requests"""
        return self.filter(status='PENDING')
    
    def approved(self):
        """Approved return requests"""
        return self.filter(status='APPROVED')
    
    def rejected(self):
        """Rejected return requests"""
        return self.filter(status='REJECTED')
    
    def completed(self):
        """Completed return requests"""
        return self.filter(status='COMPLETED')
    
    def for_customer(self, customer):
        """Return requests for specific customer"""
        return self.filter(customer=customer)
    
    def for_order(self, order):
        """Return requests for specific order"""
        return self.filter(order=order)
    
    def within_return_window(self, days=30):
        """Return requests within return window"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(order__created_at__gte=cutoff_date)
    
    def needs_attention(self):
        """Return requests that need attention"""
        return self.filter(status='PENDING').order_by('created_at')


class SubscriptionManager(models.Manager):
    """Custom manager for subscriptions"""
    
    def active(self):
        """Active subscriptions"""
        return self.filter(status='ACTIVE')
    
    def cancelled(self):
        """Cancelled subscriptions"""
        return self.filter(status='CANCELLED')
    
    def expired(self):
        """Expired subscriptions"""
        return self.filter(status='EXPIRED')
    
    def paused(self):
        """Paused subscriptions"""
        return self.filter(status='PAUSED')
    
    def due_for_renewal(self, days=7):
        """Subscriptions due for renewal within X days"""
        cutoff_date = timezone.now() + timedelta(days=days)
        return self.active().filter(next_billing_date__lte=cutoff_date)
    
    def overdue(self):
        """Overdue subscriptions"""
        return self.filter(
            status='ACTIVE',
            next_billing_date__lt=timezone.now().date()
        )
    
    def for_customer(self, customer):
        """Subscriptions for specific customer"""
        return self.filter(customer=customer)
    
    def by_plan(self, plan):
        """Subscriptions for specific plan"""
        return self.filter(plan=plan)
    
    def high_value(self, threshold=100):
        """High value subscriptions"""
        return self.filter(plan__price__gte=threshold)
        """Pending orders"""
        return self.filter(status='PENDING')
    
    def confirmed(self):
        """Confirmed orders"""
        return self.filter(status='CONFIRMED')
    
    def processing(self):
        """Orders being processed"""
        return self.filter(status='PROCESSING')
    
    def shipped(self):
        """Shipped orders"""
        return self.filter(status='SHIPPED')
    
    def delivered(self):
        """Delivered orders"""
        return self.filter(status='DELIVERED')
    
    def cancelled(self):
        """Cancelled orders"""
        return self.filter(status='CANCELLED')
    
    def refunded(self):
        """Refunded orders"""
        return self.filter(status='REFUNDED')
    
    def paid(self):
        """Fully paid orders"""
        return self.filter(payment_status='PAID')
    
    def unpaid(self):
        """Unpaid orders"""
        return self.filter(payment_status='PENDING')
    
    def partially_paid(self):
        """Partially paid orders"""
        return self.filter(payment_status='PARTIALLY_PAID')
    
    def fulfilled(self):
        """Fulfilled orders"""
        return self.filter(fulfillment_status='FULFILLED')
    
    def unfulfilled(self):
        """Unfulfilled orders"""
        return self.filter(fulfillment_status='UNFULFILLED')
    
    def for_customer(self, customer):
        """Orders for specific customer"""
        return self.filter(customer=customer)
    
    def by_date_range(self, start_date, end_date):
        """Orders within date range"""
        return self.filter(created_at__date__range=[start_date, end_date])
    
    def today(self):
        """Orders from today"""
        today = timezone.now().date()
        return self.filter(created_at__date=today)
    
    def this_week(self):
        """Orders from this week"""
        start_of_week = timezone.now() - timedelta(days=7)
        return self.filter(created_at__gte=start_of_week)
    
    def this_month(self):
        """Orders from this month"""
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=start_of_month)
    
    def high_value(self, threshold=1000):
        """High value orders above threshold"""
        return self.filter(total_amount__gte=threshold)
    
    def with_items(self):
        """Orders with prefetched items"""
        return self.prefetch_related('items__product', 'items__variant')
    
    def with_customer_details(self):
        """Orders with customer information"""
        return self.select_related('customer', 'user')
    
    def needs_attention(self):
        """Orders that need attention"""
        return self.filter(
            models.Q(status='PENDING') |
            models.Q(payment_status='FAILED') |
            models.Q(fulfillment_status='UNFULFILLED', created_at__lt=timezone.now() - timedelta(days=2))
        )
    
    def overdue_fulfillment(self, days=3):
        """Orders with overdue fulfillment"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            status__in=['CONFIRMED', 'PROCESSING'],
            fulfillment_status='UNFULFILLED',
            created_at__lt=cutoff_date
        )


class OrderManager(models.Manager):
    """Custom manager for orders"""
    
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)
    
    def pending(self):
        return self.get_queryset().pending()
    
    def confirmed(self):
        return self.get_queryset().confirmed()
    
    def processing(self):
        return self.get_queryset().processing()
    
    def shipped(self):
        return self.get_queryset().shipped()
    
    def delivered(self):
        return self.get_queryset().delivered()
    
    def cancelled(self):
        return self.get_queryset().cancelled()
    
    def refunded(self):
        return self.get_queryset().refunded()
    
    def paid(self):
        return self.get_queryset().paid()
    
    def unpaid(self):
        return self.get_queryset().unpaid()
    
    def fulfilled(self):
        return self.get_queryset().fulfilled()
    
    def unfulfilled(self):
        return self.get_queryset().unfulfilled()
    
    def today(self):
        return self.get_queryset().today()
    
    def this_week(self):
        return self.get_queryset().this_week()
    
    def this_month(self):
        return self.get_queryset().this_month()
    
    def needs_attention(self):
        return self.get_queryset().needs_attention()
    
    def overdue_fulfillment(self):
        return self.get_queryset().overdue_fulfillment()


class CartManager(models.Manager):
    """Custom manager for carts"""
    
    def active(self):
        """Active carts"""
        return self.filter(status='ACTIVE')
    
    def abandoned(self):
        """Abandoned carts"""
        return self.filter(status='ABANDONED')
    
    def completed(self):
        """Completed carts"""
        return self.filter(status='COMPLETED')
    
    def expired(self):
        """Expired carts"""
        return self.filter(
            expires_at__lt=timezone.now(),
            status='ACTIVE'
        )
    
    def for_user(self, user):
        """Carts for specific user"""
        return self.filter(user=user)
    
    def for_session(self, session_key):
        """Carts for specific session"""
        return self.filter(session_key=session_key)
    
    def non_empty(self):
        """Non-empty carts"""
        return self.filter(item_count__gt=0)
    
    def with_items(self):
        """Carts with prefetched items"""
        return self.prefetch_related('items__product', 'items__variant')
    
    def recently_abandoned(self, hours=24):
        """Recently abandoned carts"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(
            status='ACTIVE',
            last_activity__lt=cutoff_time,
            item_count__gt=0
        )
    
    def high_value(self, threshold=100):
        """High value carts"""
        return self.filter(total_amount__gte=threshold)
    
    def get_or_create_for_user(self, user, **kwargs):
        """Get or create active cart for user"""
        cart, created = self.get_or_create(
            user=user,
            status='ACTIVE',
            defaults=kwargs
        )
        return cart, created
    
    def get_or_create_for_session(self, session_key, **kwargs):
        """Get or create active cart for session"""
        cart, created = self.get_or_create(
            session_key=session_key,
            status='ACTIVE',
            user__isnull=True,
            defaults=kwargs
        )
        return cart, created
    
    def merge_session_cart_to_user(self, session_key, user):
        """Merge session cart to user cart"""
        try:
            session_cart = self.get(
                session_key=session_key,
                status='ACTIVE',
                user__isnull=True
            )
            
            user_cart, created = self.get_or_create_for_user(
                user=user,
                defaults={'currency': session_cart.currency}
            )
            
            if not created:
                # Merge session cart into user cart
                user_cart.merge_with(session_cart)
            else:
                # Transfer session cart to user
                session_cart.user = user
                session_cart.session_key = ''
                session_cart.save()
                user_cart = session_cart
            
            return user_cart
            
        except self.model.DoesNotExist:
            # No session cart to merge
            user_cart, _ = self.get_or_create_for_user(user)
            return user_cart


class ReviewManager(models.Manager):
    """Custom manager for product reviews"""
    
    def approved(self):
        """Approved reviews"""
        return self.filter(status='APPROVED')
    
    def pending(self):
        """Pending reviews"""
        return self.filter(status='PENDING')
    