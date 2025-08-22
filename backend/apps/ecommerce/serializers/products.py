"""
Product serializers for e-commerce functionality
"""

from rest_framework import serializers
from django.db.models import Avg, Count, Q
from django.utils import timezone
from decimal import Decimal

from .base import (
    EcommerceModelSerializer, TenantAwareSerializer, AuditSerializer,
    StatusSerializer, SEOSerializer, PricingSerializer, InventorySerializer,
    ImageSerializer, CustomFieldSerializer
)
from ..models import (
    EcommerceProduct, ProductVariant, ProductImage, ProductTag,
    ProductMetric, Collection, CollectionProduct
)


class ProductTagSerializer(EcommerceModelSerializer):
    """Serializer for product tags"""
    
    class Meta:
        model = ProductTag
        fields = [
            'id', 'name', 'slug', 'description', 'color', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductImageSerializer(ImageSerializer):
    """Serializer for product images"""
    
    class Meta:
        model = ProductImage
        fields = [
            'id', 'image', 'alt_text', 'caption', 'is_featured',
            'position', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductVariantSerializer(EcommerceModelSerializer):
    """Serializer for product variants"""
    
    price_formatted = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'title', 'sku', 'barcode', 'price', 'price_formatted',
            'compare_at_price', 'cost_price', 'weight', 'dimensions',
            'stock_quantity', 'stock_status', 'track_quantity',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_price_formatted(self, obj):
        """Get formatted price"""
        if hasattr(obj, 'format_currency'):
            return obj.format_currency()
        return f"${obj.price:,.2f}" if obj.price else "N/A"
    
    def get_stock_status(self, obj):
        """Get stock status"""
        if not obj.track_quantity:
            return 'unlimited'
        if obj.stock_quantity <= 0:
            return 'out_of_stock'
        if obj.stock_quantity <= getattr(obj, 'low_stock_threshold', 5):
            return 'low_stock'
        return 'in_stock'


class ProductMetricSerializer(EcommerceModelSerializer):
    """Serializer for product metrics"""
    
    class Meta:
        model = ProductMetric
        fields = [
            'id', 'view_count', 'purchase_count', 'wishlist_count',
            'review_count', 'average_rating', 'last_viewed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CollectionSerializer(EcommerceModelSerializer):
    """Serializer for collections"""
    
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Collection
        fields = [
            'id', 'title', 'handle', 'description', 'collection_type',
            'is_active', 'is_published', 'is_featured',
            'is_visible_in_search', 'is_visible_in_storefront',
            'display_order', 'product_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_product_count(self, obj):
        """Get count of products in collection"""
        return getattr(obj, 'product_count', 0)


class ProductListSerializer(EcommerceModelSerializer):
    """Serializer for product listing (minimal data)"""
    
    primary_image = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()
    collection_names = serializers.SerializerMethodField()
    tag_names = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EcommerceProduct
        fields = [
            'id', 'title', 'handle', 'short_description', 'primary_image',
            'price', 'compare_at_price', 'price_range', 'currency',
            'is_on_sale', 'is_featured', 'is_new', 'collection_names',
            'tag_names', 'average_rating', 'review_count', 'stock_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_primary_image(self, obj):
        """Get primary product image"""
        if hasattr(obj, 'primary_image') and obj.primary_image:
            return {
                'id': obj.primary_image.id,
                'image': obj.primary_image.image.url if obj.primary_image.image else None,
                'alt_text': obj.primary_image.alt_text
            }
        return None
    
    def get_price_range(self, obj):
        """Get price range for product variants"""
        if hasattr(obj, 'variants') and obj.variants.exists():
            prices = [v.price for v in obj.variants.all() if v.price]
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                if min_price == max_price:
                    return f"${min_price:,.2f}"
                return f"${min_price:,.2f} - ${max_price:,.2f}"
        return f"${obj.price:,.2f}" if obj.price else "N/A"
    
    def get_collection_names(self, obj):
        """Get collection names"""
        if hasattr(obj, 'collections'):
            return [c.title for c in obj.collections.all()]
        return []
    
    def get_tag_names(self, obj):
        """Get tag names"""
        if hasattr(obj, 'tags'):
            return [t.name for t in obj.tags.all()]
        return []
    
    def get_average_rating(self, obj):
        """Get average rating"""
        if hasattr(obj, 'average_rating'):
            return obj.average_rating
        return 0.0
    
    def get_review_count(self, obj):
        """Get review count"""
        if hasattr(obj, 'review_count'):
            return obj.review_count
        return 0


class ProductDetailSerializer(EcommerceModelSerializer):
    """Serializer for product detail (full data)"""
    
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = ProductTagSerializer(many=True, read_only=True)
    collections = CollectionSerializer(many=True, read_only=True)
    metrics = ProductMetricSerializer(read_only=True)
    related_products = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    price_formatted = serializers.SerializerMethodField()
    compare_at_price_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = EcommerceProduct
        fields = [
            'id', 'title', 'handle', 'description', 'short_description',
            'sku', 'barcode', 'brand', 'vendor', 'product_type',
            'price', 'price_formatted', 'compare_at_price', 'compare_at_price_formatted',
            'cost_price', 'currency', 'weight', 'dimensions',
            'stock_quantity', 'stock_status', 'track_quantity',
            'low_stock_threshold', 'out_of_stock_threshold',
            'is_on_sale', 'is_featured', 'is_new', 'is_digital_product',
            'requires_authentication', 'is_visible_in_search',
            'is_visible_in_storefront', 'is_active', 'is_published',
            'variants', 'images', 'tags', 'collections', 'metrics',
            'related_products', 'custom_fields', 'seo_title',
            'seo_description', 'seo_keywords', 'canonical_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_related_products(self, obj):
        """Get related products"""
        # Get products from same collections
        collection_ids = obj.collections.values_list('id', flat=True)
        related = EcommerceProduct.objects.filter(
            collections__id__in=collection_ids,
            is_active=True,
            is_published=True
        ).exclude(id=obj.id).distinct()[:6]
        
        return ProductListSerializer(related, many=True).data
    
    def get_stock_status(self, obj):
        """Get stock status"""
        if not obj.track_quantity:
            return 'unlimited'
        if obj.stock_quantity <= 0:
            return 'out_of_stock'
        if obj.stock_quantity <= getattr(obj, 'low_stock_threshold', 5):
            return 'low_stock'
        return 'in_stock'
    
    def get_price_formatted(self, obj):
        """Get formatted price"""
        if hasattr(obj, 'format_currency'):
            return obj.format_currency()
        return f"${obj.price:,.2f}" if obj.price else "N/A"
    
    def get_compare_at_price_formatted(self, obj):
        """Get formatted compare at price"""
        if obj.compare_at_price:
            if hasattr(obj, 'format_currency'):
                return obj.format_currency(obj.compare_at_price)
            return f"${obj.compare_at_price:,.2f}"
        return None


class ProductSearchSerializer(serializers.Serializer):
    """Serializer for product search results"""
    
    query = serializers.CharField(help_text="Search query")
    total_results = serializers.IntegerField(help_text="Total number of results")
    page = serializers.IntegerField(help_text="Current page number")
    page_size = serializers.IntegerField(help_text="Number of results per page")
    total_pages = serializers.IntegerField(help_text="Total number of pages")
    results = ProductListSerializer(many=True, help_text="Search results")
    filters = serializers.DictField(help_text="Applied filters")
    suggestions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Search suggestions"
    )


class ProductFilterSerializer(serializers.Serializer):
    """Serializer for product filtering"""
    
    categories = serializers.ListField(
        child=serializers.CharField(),
        help_text="Available categories"
    )
    brands = serializers.ListField(
        child=serializers.CharField(),
        help_text="Available brands"
    )
    price_range = serializers.DictField(
        help_text="Price range (min, max)"
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        help_text="Available tags"
    )
    availability = serializers.ListField(
        child=serializers.CharField(),
        help_text="Availability options"
    )
    ratings = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Available rating values"
    )


class ProductBulkSerializer(serializers.Serializer):
    """Serializer for bulk product operations"""
    
    action = serializers.ChoiceField(choices=[
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('publish', 'Publish'),
        ('unpublish', 'Unpublish'),
        ('delete', 'Delete'),
        ('update_collections', 'Update Collections'),
        ('update_tags', 'Update Tags'),
        ('update_pricing', 'Update Pricing'),
        ('export', 'Export'),
    ])
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of product IDs to perform action on"
    )
    update_data = serializers.DictField(
        required=False,
        help_text="Data to update products with"
    )
    filters = serializers.DictField(
        required=False,
        help_text="Additional filters to apply"
    )


class ProductImportSerializer(serializers.Serializer):
    """Serializer for product import"""
    
    file = serializers.FileField(help_text="Import file (CSV, Excel)")
    import_type = serializers.ChoiceField(choices=[
        ('create', 'Create New'),
        ('update', 'Update Existing'),
        ('create_update', 'Create or Update'),
    ], default='create_update')
    update_existing = serializers.BooleanField(
        default=True,
        help_text="Update existing products"
    )
    skip_errors = serializers.BooleanField(
        default=False,
        help_text="Skip rows with errors"
    )
    validate_only = serializers.BooleanField(
        default=False,
        help_text="Validate without importing"
    )


class ProductExportSerializer(serializers.Serializer):
    """Serializer for product export"""
    
    format = serializers.ChoiceField(choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ], default='csv')
    fields = serializers.ListField(
        child=serializers.CharField(),
        help_text="Fields to export"
    )
    filters = serializers.DictField(
        required=False,
        help_text="Filters to apply"
    )
    include_variants = serializers.BooleanField(
        default=False,
        help_text="Include product variants"
    )
    include_images = serializers.BooleanField(
        default=False,
        help_text="Include image URLs"
    )


class ProductAnalyticsSerializer(serializers.Serializer):
    """Serializer for product analytics"""
    
    product_id = serializers.IntegerField(help_text="Product ID")
    period = serializers.ChoiceField(choices=[
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Year'),
    ], default='month')
    start_date = serializers.DateField(help_text="Start date")
    end_date = serializers.DateField(help_text="End date")
    metrics = serializers.ListField(
        child=serializers.CharField(),
        help_text="Metrics to include"
    )
    data = serializers.DictField(help_text="Analytics data")


class ProductRecommendationSerializer(serializers.Serializer):
    """Serializer for product recommendations"""
    
    product_id = serializers.IntegerField(help_text="Product ID")
    recommendation_type = serializers.ChoiceField(choices=[
        ('similar', 'Similar Products'),
        ('frequently_bought', 'Frequently Bought Together'),
        ('trending', 'Trending Products'),
        ('personalized', 'Personalized Recommendations'),
    ], default='similar')
    limit = serializers.IntegerField(
        min_value=1,
        max_value=20,
        default=6,
        help_text="Number of recommendations"
    )
    recommendations = ProductListSerializer(many=True, help_text="Recommended products")


class ProductReviewSummarySerializer(serializers.Serializer):
    """Serializer for product review summary"""
    
    product_id = serializers.IntegerField(help_text="Product ID")
    total_reviews = serializers.IntegerField(help_text="Total number of reviews")
    average_rating = serializers.FloatField(help_text="Average rating")
    rating_distribution = serializers.DictField(help_text="Rating distribution")
    recent_reviews = serializers.ListField(help_text="Recent reviews")
    review_highlights = serializers.ListField(help_text="Review highlights")


class ProductInventorySerializer(InventorySerializer):
    """Serializer for product inventory management"""
    
    variants = ProductVariantSerializer(many=True, read_only=True)
    low_stock_alerts = serializers.SerializerMethodField()
    inventory_history = serializers.SerializerMethodField()
    
    class Meta:
        model = EcommerceProduct
        fields = [
            'id', 'title', 'sku', 'stock_quantity', 'low_stock_threshold',
            'out_of_stock_threshold', 'track_quantity', 'inventory_policy',
            'variants', 'low_stock_alerts', 'inventory_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_low_stock_alerts(self, obj):
        """Get low stock alerts"""
        alerts = []
        if obj.track_quantity and obj.stock_quantity <= obj.low_stock_threshold:
            alerts.append({
                'type': 'low_stock',
                'message': f'Product {obj.title} is running low on stock',
                'current_quantity': obj.stock_quantity,
                'threshold': obj.low_stock_threshold
            })
        return alerts
    
    def get_inventory_history(self, obj):
        """Get inventory history"""
        # TODO: Implement inventory history tracking
        return []


class ProductSEOUpdateSerializer(serializers.Serializer):
    """Serializer for updating product SEO"""
    
    seo_title = serializers.CharField(max_length=60, required=False)
    seo_description = serializers.CharField(max_length=160, required=False)
    seo_keywords = serializers.CharField(max_length=255, required=False)
    canonical_url = serializers.URLField(required=False)
    og_title = serializers.CharField(max_length=60, required=False)
    og_description = serializers.CharField(max_length=160, required=False)
    og_image = serializers.ImageField(required=False)
    meta_robots = serializers.CharField(max_length=50, required=False)
    structured_data = serializers.JSONField(required=False)


class ProductPricingUpdateSerializer(serializers.Serializer):
    """Serializer for updating product pricing"""
    
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    compare_at_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    cost_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    bulk_pricing = serializers.JSONField(required=False)
    tiered_pricing = serializers.JSONField(required=False)
    volume_discounts = serializers.JSONField(required=False)
