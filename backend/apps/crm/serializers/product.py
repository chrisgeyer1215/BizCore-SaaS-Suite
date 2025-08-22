# ============================================================================
# backend/apps/crm/serializers/product.py - Product Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from ..models import (
    ProductCategory, Product, PricingModel, ProductBundle, 
    ProductBundleItem, ProductVariant
)
from .user import UserBasicSerializer


class ProductCategorySerializer(serializers.ModelSerializer):
    """Product category serializer with hierarchy"""
    
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    full_path = serializers.ReadOnlyField()
    subcategories_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    category_performance = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductCategory
        fields = [
            'id', 'name', 'code', 'description', 'parent', 'parent_name',
            'level', 'full_path', 'sort_order', 'icon', 'color',
            # SEO
            'slug', 'meta_title', 'meta_description', 'keywords',
            # Business rules
            'commission_rate', 'default_markup_percentage',
            # Settings
            'is_visible', 'requires_approval', 'subcategories_count',
            'products_count', 'category_performance',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_name', 'level', 'full_path', 'slug',
            'subcategories_count', 'products_count', 'category_performance',
            'created_at', 'updated_at'
        ]
    
    def get_subcategories_count(self, obj):
        """Get count of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    
    def get_products_count(self, obj):
        """Get count of products in category"""
        return obj.products.filter(is_active=True).count()
    
    def get_category_performance(self, obj):
        """Get category performance metrics"""
        products = obj.products.filter(is_active=True)
        return {
            'total_products': products.count(),
            'active_products': products.filter(status='ACTIVE').count(),
            'total_revenue': float(products.aggregate(
                total=models.Sum('total_revenue')
            )['total'] or 0),
            'average_price': float(products.aggregate(
                avg=models.Avg('base_price')
            )['avg'] or 0)
        }


class ProductVariantSerializer(serializers.ModelSerializer):
    """Product variant serializer"""
    
    parent_product_name = serializers.CharField(source='parent_product.name', read_only=True)
    effective_price = serializers.ReadOnlyField()
    effective_cost = serializers.ReadOnlyField()
    effective_weight = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'parent_product', 'parent_product_name', 'name', 'sku',
            'description', 'attributes', 'price_adjustment', 'cost_adjustment',
            'effective_price', 'effective_cost', 'stock_quantity',
            'weight_adjustment', 'effective_weight', 'image_url',
            'additional_images', 'is_available',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'parent_product_name', 'effective_price', 'effective_cost',
            'effective_weight', 'created_at', 'updated_at'
        ]
    
    def validate_sku(self, value):
        """Validate SKU uniqueness"""
        if self.instance:
            if ProductVariant.objects.filter(
                tenant=self.context['request'].user.tenant,
                sku=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("SKU must be unique")
        return value


class PricingModelSerializer(serializers.ModelSerializer):
    """Pricing model serializer"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    approved_by_details = UserBasicSerializer(source='approved_by', read_only=True)
    
    # Pricing analysis
    is_valid_now = serializers.SerializerMethodField()
    pricing_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = PricingModel
        fields = [
            'id', 'name', 'description', 'pricing_type', 'product',
            'product_name', 'pricing_rules', 'valid_from', 'valid_until',
            'is_valid_now', 'customer_segments', 'geographic_regions',
            'minimum_order_quantity', 'is_active', 'requires_approval',
            'approved_by', 'approved_by_details', 'priority',
            'pricing_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'product_name', 'approved_by_details', 'is_valid_now',
            'pricing_summary', 'created_at', 'updated_at'
        ]
    
    def get_is_valid_now(self, obj):
        """Check if pricing model is currently valid"""
        return obj.is_valid_now()
    
    def get_pricing_summary(self, obj):
        """Get pricing model summary"""
        return {
            'type': obj.pricing_type,
            'currently_valid': obj.is_valid_now(),
            'validity_period': f"{obj.valid_from} to {obj.valid_until or 'No end date'}",
            'has_segments': bool(obj.customer_segments),
            'geographic_restrictions': bool(obj.geographic_regions),
            'minimum_quantity': obj.minimum_order_quantity
        }
    
    def validate(self, data):
        """Validate pricing model"""
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        if valid_from and valid_until:
            if valid_from >= valid_until:
                raise serializers.ValidationError({
                    'valid_until': 'End date must be after start date'
                })
        
        return data


class ProductSerializer(serializers.ModelSerializer):
    """Comprehensive product serializer"""
    
    category_details = ProductCategorySerializer(source='category', read_only=True)
    approved_by_details = UserBasicSerializer(source='approved_by', read_only=True)
    
    # Calculated properties
    profit_margin = serializers.ReadOnlyField()
    markup_percentage = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()
    
    # Variants and pricing
    variants = ProductVariantSerializer(many=True, read_only=True)
    pricing_models = PricingModelSerializer(many=True, read_only=True)
    variants_count = serializers.SerializerMethodField()
    
    # Performance metrics
    performance_metrics = serializers.SerializerMethodField()
    inventory_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'code', 'description', 'short_description',
            'product_type', 'status', 'category', 'category_details',
            # Pricing
            'base_price', 'cost_price', 'currency', 'profit_margin', 'markup_percentage',
            # Tax
            'is_taxable', 'tax_category', 'tax_rate',
            # Sales
            'sales_account', 'commission_rate', 'discount_eligible',
            # Physical properties
            'weight', 'weight_unit', 'dimensions',
            # Digital properties
            'download_url', 'license_type', 'usage_restrictions',
            # Service properties
            'service_duration_minutes', 'requires_scheduling', 'service_location',
            # Subscription properties
            'billing_cycle', 'trial_period_days', 'auto_renewal',
            # Inventory
            'track_inventory', 'current_stock', 'reorder_level', 'reorder_quantity',
            'is_in_stock', 'needs_reorder', 'inventory_status',
            # Media
            'primary_image', 'gallery_images', 'brochure_url', 'manual_url', 'video_url',
            # SEO
            'slug', 'meta_title', 'meta_description', 'keywords',
            # Analytics
            'view_count', 'sales_count', 'total_revenue', 'performance_metrics',
            # Custom fields
            'custom_fields',
            # Approval
            'approved_by', 'approved_by_details', 'approved_at',
            # Lifecycle
            'launch_date', 'discontinue_date',
            # Related data
            'variants', 'variants_count', 'pricing_models',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'category_details', 'approved_by_details', 'profit_margin',
            'markup_percentage', 'is_in_stock', 'needs_reorder', 'slug',
            'view_count', 'sales_count', 'total_revenue', 'performance_metrics',
            'inventory_status', 'variants', 'variants_count', 'pricing_models',
            'created_at', 'updated_at'
        ]
    
    def get_variants_count(self, obj):
        """Get count of active variants"""
        return obj.variants.filter(is_active=True).count()
    
    def get_performance_metrics(self, obj):
        """Get product performance metrics"""
        return {
            'total_views': obj.view_count,
            'total_sales': obj.sales_count,
            'total_revenue': float(obj.total_revenue),
            'average_sale_value': float(obj.total_revenue / max(obj.sales_count, 1)),
            'conversion_rate': (obj.sales_count / max(obj.view_count, 1)) * 100,
            'profit_margin': float(obj.profit_margin),
            'performance_rating': self._calculate_performance_rating(obj)
        }
    
    def get_inventory_status(self, obj):
        """Get inventory status details"""
        if not obj.track_inventory:
            return {'status': 'Not Tracked', 'message': 'Inventory tracking disabled'}
        
        if obj.current_stock <= 0:
            return {'status': 'Out of Stock', 'message': 'Product is out of stock'}
        elif obj.needs_reorder:
            return {
                'status': 'Low Stock',
                'message': f'Stock level ({obj.current_stock}) is below reorder point ({obj.reorder_level})'
            }
        else:
            return {'status': 'In Stock', 'message': f'{obj.current_stock} units available'}
    
    def _calculate_performance_rating(self, obj):
        """Calculate overall performance rating"""
        score = 0
        
        # Revenue performance (40% weight)
        if obj.total_revenue > 10000:
            score += 40
        elif obj.total_revenue > 5000:
            score += 30
        elif obj.total_revenue > 1000:
            score += 20
        
        # Sales volume (30% weight)
        if obj.sales_count > 100:
            score += 30
        elif obj.sales_count > 50:
            score += 25
        elif obj.sales_count > 10:
            score += 15
        
        # Profit margin (30% weight)
        margin = obj.profit_margin
        if margin > 50:
            score += 30
        elif margin > 30:
            score += 25
        elif margin > 15:
            score += 15
        
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Average'
        else:
            return 'Poor'
    
    def validate_code(self, value):
        """Validate product code uniqueness"""
        if self.instance:
            if Product.objects.filter(
                tenant=self.context['request'].user.tenant,
                code=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Product code must be unique")
        return value


class ProductBundleItemSerializer(serializers.ModelSerializer):
    """Product bundle item serializer"""
    
    product_details = serializers.SerializerMethodField()
    effective_price = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductBundleItem
        fields = [
            'id', 'product', 'product_details', 'quantity', 'custom_price',
            'effective_price', 'total_price', 'is_required', 'is_substitutable',
            'substitute_products', 'sort_order', 'description_override'
        ]
        read_only_fields = ['id', 'product_details', 'effective_price', 'total_price']
    
    def get_product_details(self, obj):
        """Get basic product details"""
        return {
            'id': obj.product.id,
            'name': obj.product.name,
            'code': obj.product.code,
            'base_price': float(obj.product.base_price),
            'product_type': obj.product.product_type,
            'is_active': obj.product.is_active
        }


class ProductBundleSerializer(serializers.ModelSerializer):
    """Product bundle serializer with savings analysis"""
    
    bundle_items = ProductBundleItemSerializer(many=True, read_only=True)
    
    # Calculated properties
    individual_total = serializers.ReadOnlyField()
    bundle_savings = serializers.ReadOnlyField()
    savings_percentage = serializers.ReadOnlyField()
    effective_price = serializers.SerializerMethodField()
    is_valid_now = serializers.SerializerMethodField()
    
    # Performance metrics
    bundle_performance = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductBundle
        fields = [
            'id', 'name', 'description', 'bundle_type', 'bundle_price',
            'discount_percentage', 'individual_total', 'bundle_savings',
            'savings_percentage', 'effective_price', 'is_active', 'is_featured',
            'valid_from', 'valid_until', 'is_valid_now', 'promotional_text',
            'image_url', 'sales_count', 'total_revenue', 'bundle_items',
            'bundle_performance',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'individual_total', 'bundle_savings', 'savings_percentage',
            'effective_price', 'is_valid_now', 'sales_count', 'total_revenue',
            'bundle_items', 'bundle_performance', 'created_at', 'updated_at'
        ]
    
    def get_effective_price(self, obj):
        """Get effective bundle price"""
        return float(obj.get_effective_price())
    
    def get_is_valid_now(self, obj):
        """Check if bundle is currently valid"""
        return obj.is_valid_now()
    
    def get_bundle_performance(self, obj):
        """Get bundle performance metrics"""
        return {
            'total_sales': obj.sales_count,
            'total_revenue': float(obj.total_revenue),
            'average_sale_value': float(obj.total_revenue / max(obj.sales_count, 1)),
            'savings_appeal': float(obj.savings_percentage),
            'performance_rating': 'High' if obj.savings_percentage > 20 else 'Medium' if obj.savings_percentage > 10 else 'Low'
        }


class ProductAnalyticsSerializer(serializers.Serializer):
    """Product analytics serializer"""
    
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    date_range = serializers.CharField(required=False, default='30d')
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'sales', 'revenue', 'profit', 'inventory', 'performance',
            'pricing', 'variants', 'bundles'
        ]),
        required=False,
        default=['sales', 'revenue', 'profit']
    )
    
    def validate_date_range(self, value):
        """Validate date range"""
        valid_ranges = ['7d', '30d', '90d', '180d', '1y']
        if value not in valid_ranges:
            raise serializers.ValidationError(f"Date range must be one of: {', '.join(valid_ranges)}")
        return value


class ProductBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk product updates"""
    
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    # Fields that can be bulk updated
    status = serializers.ChoiceField(
        choices=Product.STATUS_CHOICES,
        required=False
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.all(),
        required=False
    )
    commission_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    discount_eligible = serializers.BooleanField(required=False)
    
    def validate_product_ids(self, value):
        """Validate product IDs"""
        tenant = self.context['request'].user.tenant
        existing_products = Product.objects.filter(
            tenant=tenant,
            id__in=value,
            is_active=True
        ).count()
        
        if existing_products != len(value):
            raise serializers.ValidationError("Some product IDs are invalid")
        
        return value