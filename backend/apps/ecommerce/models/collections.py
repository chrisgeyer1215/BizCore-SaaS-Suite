# apps/ecommerce/models/collections.py

"""
AI-Powered Intelligent Product Collections System
Featuring machine learning curation, predictive analytics, and automated optimization
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from collections import Counter
import json
import logging
from typing import Dict, List, Any, Optional

from .base import (
    EcommerceBaseModel, 
    SEOMixin, 
    VisibilityMixin, 
    SortableMixin,
    AuditMixin,
    AIOptimizedPricingMixin
)

logger = logging.getLogger(__name__)


class IntelligentCollection(EcommerceBaseModel, SEOMixin, VisibilityMixin, SortableMixin, AuditMixin, AIOptimizedPricingMixin):
    """
    AI-Powered Intelligent Product Collection with advanced curation,
    predictive analytics, and automated optimization
    """
    
    class CollectionType(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual Collection'
        AUTOMATIC = 'AUTOMATIC', 'Automatic Collection'
        SMART = 'SMART', 'Smart Collection'
        AI_CURATED = 'AI_CURATED', 'AI-Curated Collection'
        PREDICTIVE = 'PREDICTIVE', 'Predictive Collection'
        BEHAVIORAL = 'BEHAVIORAL', 'Behavioral Collection'
        TRENDING = 'TRENDING', 'Trending Collection'
        PERSONALIZED = 'PERSONALIZED', 'Personalized Collection'
        CATEGORY = 'CATEGORY', 'Category'
        BRAND = 'BRAND', 'Brand Collection'
        SEASONAL = 'SEASONAL', 'Seasonal Collection'
        FEATURED = 'FEATURED', 'Featured Collection'
        SALE = 'SALE', 'Sale Collection'
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    handle = models.SlugField(max_length=255, unique=True)
    
    # Collection Type and Behavior
    collection_type = models.CharField(
        max_length=20, 
        choices=CollectionType.choices, 
        default=CollectionType.MANUAL
    )
    
    # Hierarchical Structure
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    level = models.PositiveIntegerField(default=0)
    
    # Display Settings
    display_order = models.PositiveIntegerField(default=0)
    products_per_page = models.PositiveIntegerField(default=24)
    default_sort_order = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('best_selling', 'Best Selling'),
            ('title_asc', 'Title A-Z'),
            ('title_desc', 'Title Z-A'),
            ('price_asc', 'Price Low to High'),
            ('price_desc', 'Price High to Low'),
            ('created_asc', 'Oldest First'),
            ('created_desc', 'Newest First'),
        ],
        default='manual'
    )
    
    # Smart Collection Rules (for automatic collections)
    collection_rules = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Rules for automatic collections"
    )
    
    # AI-powered features
    ai_curation_enabled = models.BooleanField(default=False)
    ai_optimization_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI optimization effectiveness score (0-100)"
    )
    machine_learning_model = models.CharField(
        max_length=50, blank=True,
        help_text="ML model used for this collection"
    )
    
    # Predictive analytics
    predicted_performance = models.JSONField(default=dict, blank=True)
    trend_analysis = models.JSONField(default=dict, blank=True)
    customer_segments = ArrayField(
        models.CharField(max_length=50), default=list, blank=True
    )
    
    # Dynamic content optimization
    personalization_rules = models.JSONField(default=list, blank=True)
    a_b_testing_config = models.JSONField(default=dict, blank=True)
    conversion_optimization = models.JSONField(default=dict, blank=True)
    
    # Performance tracking
    performance_metrics = models.JSONField(default=dict, blank=True)
    engagement_analytics = models.JSONField(default=dict, blank=True)
    revenue_analytics = models.JSONField(default=dict, blank=True)
    
    # Automated optimization
    auto_reorder_enabled = models.BooleanField(default=False)
    auto_pricing_enabled = models.BooleanField(default=False)
    dynamic_content_enabled = models.BooleanField(default=False)
    
    # AI insights
    ai_recommendations = models.JSONField(default=list, blank=True)
    optimization_suggestions = models.JSONField(default=list, blank=True)
    market_insights = models.JSONField(default=dict, blank=True)
    
    # Images and Media
    featured_image = models.ImageField(upload_to='collections/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='collections/banners/', blank=True, null=True)
    icon_class = models.CharField(max_length=50, blank=True)
    color_code = models.CharField(max_length=7, blank=True)  # Hex color
    
    # Performance (Cached)
    products_count = models.PositiveIntegerField(default=0)
    ai_curated_count = models.PositiveIntegerField(default=0)
    trending_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    last_ai_optimization = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_collections'
        ordering = ['display_order', 'title']
        indexes = [
            models.Index(fields=['tenant', 'is_visible', 'is_featured']),
            models.Index(fields=['tenant', 'collection_type']),
            models.Index(fields=['tenant', 'parent']),
            models.Index(fields=['tenant', 'handle']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'handle'], 
                name='unique_collection_handle_per_tenant'
            ),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Generate handle if not provided
        if not self.handle:
            self.handle = slugify(self.title)
            
        # Ensure handle is unique
        if self.pk:  # Updating existing collection
            existing = Collection.objects.filter(
                tenant=self.tenant, 
                handle=self.handle
            ).exclude(pk=self.pk)
        else:  # Creating new collection
            existing = Collection.objects.filter(
                tenant=self.tenant, 
                handle=self.handle
            )
            
        if existing.exists():
            base_handle = self.handle
            counter = 1
            while existing.exists():
                self.handle = f"{base_handle}-{counter}"
                existing = Collection.objects.filter(
                    tenant=self.tenant, 
                    handle=self.handle
                )
                if self.pk:
                    existing = existing.exclude(pk=self.pk)
                counter += 1
        
        # Calculate level based on parent
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        
        super().save(*args, **kwargs)
        
        # Update products count after save
        self.update_products_count()
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Prevent self-reference
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({'parent': 'Collection cannot be its own parent'})
        
        # Prevent circular references
        if self.parent_id:
            current = self.parent
            while current:
                if current.id == self.id:
                    raise ValidationError({'parent': 'Circular reference detected'})
                current = current.parent
    
    def get_absolute_url(self):
        """Get collection URL"""
        return reverse('ecommerce:collection_detail', kwargs={'handle': self.handle})
    
    def get_full_path(self):
        """Get full collection path"""
        path = [self.title]
        parent = self.parent
        while parent:
            path.insert(0, parent.title)
            parent = parent.parent
        return ' > '.join(path)
    
    @property
    def active_products_count(self):
        """Get active products count"""
        return self.products.filter(
            is_active=True, 
            is_published=True,
            status='PUBLISHED'
        ).count()
    
    def update_products_count(self):
        """Update cached products count"""
        if self.collection_type == self.CollectionType.AUTOMATIC:
            # For automatic collections, apply rules to get count
            count = self.get_automatic_products().count()
        else:
            # For manual collections, count related products
            count = self.collection_products.filter(
                product__is_active=True,
                product__is_published=True,
                product__status='PUBLISHED'
            ).count()
        
        self.products_count = count
        self.save(update_fields=['products_count'])
    
    def get_products(self, limit=None):
        """Get products in this collection"""
        if self.collection_type == self.CollectionType.AUTOMATIC:
            queryset = self.get_automatic_products()
        else:
            queryset = self.products.filter(
                is_active=True,
                is_published=True,
                status='PUBLISHED'
            )
        
        # Apply sorting
        if self.default_sort_order == 'manual':
            queryset = queryset.extra(
                select={'sort_order': 'ecommerce_collection_products.position'}
            ).order_by('sort_order')
        elif self.default_sort_order == 'best_selling':
            queryset = queryset.order_by('-sales_count')
        elif self.default_sort_order == 'title_asc':
            queryset = queryset.order_by('title')
        elif self.default_sort_order == 'title_desc':
            queryset = queryset.order_by('-title')
        elif self.default_sort_order == 'price_asc':
            queryset = queryset.order_by('price')
        elif self.default_sort_order == 'price_desc':
            queryset = queryset.order_by('-price')
        elif self.default_sort_order == 'created_asc':
            queryset = queryset.order_by('created_at')
        elif self.default_sort_order == 'created_desc':
            queryset = queryset.order_by('-created_at')
        
        if limit:
            queryset = queryset[:limit]
            
        return queryset
    
    def get_automatic_products(self):
        """Get products based on automatic collection rules"""
        from .products import EcommerceProduct
        
        if not self.collection_rules:
            return EcommerceProduct.objects.none()
        
        queryset = EcommerceProduct.published.filter(tenant=self.tenant)
        
        # Apply each rule
        for rule in self.collection_rules:
            condition = rule.get('condition', 'equals')
            field = rule.get('field')
            value = rule.get('value')
            operator = rule.get('operator', 'AND')
            
            if not field or value is None:
                continue
            
            # Build query based on rule
            if field == 'title':
                if condition == 'equals':
                    filter_kwargs = {'title__iexact': value}
                elif condition == 'contains':
                    filter_kwargs = {'title__icontains': value}
                elif condition == 'starts_with':
                    filter_kwargs = {'title__istartswith': value}
                elif condition == 'ends_with':
                    filter_kwargs = {'title__iendswith': value}
                else:
                    continue
            elif field == 'price':
                if condition == 'equals':
                    filter_kwargs = {'price': value}
                elif condition == 'greater_than':
                    filter_kwargs = {'price__gt': value}
                elif condition == 'less_than':
                    filter_kwargs = {'price__lt': value}
                elif condition == 'greater_than_or_equal':
                    filter_kwargs = {'price__gte': value}
                elif condition == 'less_than_or_equal':
                    filter_kwargs = {'price__lte': value}
                else:
                    continue
            elif field == 'brand':
                if condition == 'equals':
                    filter_kwargs = {'brand__iexact': value}
                elif condition == 'contains':
                    filter_kwargs = {'brand__icontains': value}
                else:
                    continue
            elif field == 'product_type':
                filter_kwargs = {'product_type': value}
            elif field == 'tags':
                if condition == 'contains':
                    filter_kwargs = {'tags__icontains': value}
                else:
                    continue
            elif field == 'inventory_quantity':
                if condition == 'greater_than':
                    filter_kwargs = {'stock_quantity__gt': value}
                elif condition == 'less_than':
                    filter_kwargs = {'stock_quantity__lt': value}
                elif condition == 'equals':
                    filter_kwargs = {'stock_quantity': value}
                else:
                    continue
            else:
                continue
            
            # Apply filter with operator
            if operator == 'AND':
                queryset = queryset.filter(**filter_kwargs)
            elif operator == 'OR':
                # For OR operations, we need to use Q objects
                from django.db.models import Q
                queryset = queryset.filter(Q(**filter_kwargs))
        
        return queryset
    
    def add_product(self, product, position=None, is_featured=False):
        """Add product to collection"""
        if self.collection_type != self.CollectionType.MANUAL:
            raise ValueError("Can only manually add products to manual collections")
        
        if position is None:
            # Get the highest position and add 1
            last_position = self.collection_products.aggregate(
                max_position=models.Max('position')
            )['max_position'] or 0
            position = last_position + 1
        
        collection_product, created = CollectionProduct.objects.get_or_create(
            tenant=self.tenant,
            collection=self,
            product=product,
            defaults={
                'position': position,
                'is_featured': is_featured
            }
        )
        
        if created:
            self.update_products_count()
        
        return collection_product
    
    def remove_product(self, product):
        """Remove product from collection"""
        if self.collection_type != self.CollectionType.MANUAL:
            raise ValueError("Can only manually remove products from manual collections")
        
        deleted_count, _ = CollectionProduct.objects.filter(
            tenant=self.tenant,
            collection=self,
            product=product
        ).delete()
        
        if deleted_count > 0:
            self.update_products_count()
        
        return deleted_count > 0
    
    def reorder_products(self, product_positions):
        """Reorder products in collection
        
        Args:
            product_positions: List of tuples (product_id, position)
        """
        if self.collection_type != self.CollectionType.MANUAL:
            raise ValueError("Can only reorder products in manual collections")
        
        for product_id, position in product_positions:
            CollectionProduct.objects.filter(
                tenant=self.tenant,
                collection=self,
                product_id=product_id
            ).update(position=position)
    
    def get_breadcrumbs(self):
        """Get breadcrumb navigation for this collection"""
        breadcrumbs = []
        current = self
        
        while current:
            breadcrumbs.insert(0, {
                'title': current.title,
                'url': current.get_absolute_url(),
                'is_current': current == self
            })
            current = current.parent
        
        return breadcrumbs
    
    def get_siblings(self):
        """Get sibling collections at the same level"""
        if self.parent:
            return self.parent.children.filter(is_visible=True).exclude(pk=self.pk)
        else:
            return Collection.objects.filter(
                tenant=self.tenant,
                parent__isnull=True,
                is_visible=True
            ).exclude(pk=self.pk)
    
    def get_descendants(self, include_self=False):
        """Get all descendant collections"""
        descendants = Collection.objects.filter(
            tenant=self.tenant,
            level__gt=self.level
        )
        
        if include_self:
            descendants = descendants.filter(
                models.Q(parent=self) | models.Q(pk=self.pk)
            )
        else:
            descendants = descendants.filter(parent=self)
        
        return descendants


class CollectionProduct(EcommerceBaseModel):
    """Through model for collection-product relationship with enhanced features"""
    
    collection = models.ForeignKey(
        Collection, 
        on_delete=models.CASCADE,
        related_name='collection_products'
    )
    product = models.ForeignKey(
        'EcommerceProduct', 
        on_delete=models.CASCADE,
        related_name='collection_memberships'
    )
    
    # Ordering and positioning
    position = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    
    # Metadata
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Custom settings for this product in this collection
    custom_title = models.CharField(max_length=255, blank=True)
    custom_description = models.TextField(blank=True)
    custom_image = models.ImageField(upload_to='collections/custom/', blank=True, null=True)
    
    class Meta:
        db_table = 'ecommerce_collection_products'
        ordering = ['collection', 'position']
        indexes = [
            models.Index(fields=['tenant', 'collection', 'position']),
            models.Index(fields=['tenant', 'product']),
            models.Index(fields=['tenant', 'collection', 'is_featured']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'collection', 'product'], 
                name='unique_collection_product_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.collection.title} - {self.product.title}"
    
    @property
    def display_title(self):
        """Get display title (custom or product title)"""
        return self.custom_title or self.product.title
    
    @property
    def display_description(self):
        """Get display description (custom or product description)"""
        return self.custom_description or self.product.short_description or self.product.description
    
    @property
    def display_image(self):
        """Get display image (custom or product image)"""
        return self.custom_image or self.product.featured_image


class CollectionRule(EcommerceBaseModel):
    """Individual rules for smart/automatic collections"""
    
    class FieldType(models.TextChoices):
        TITLE = 'title', 'Product Title'
        DESCRIPTION = 'description', 'Product Description'
        BRAND = 'brand', 'Brand'
        PRODUCT_TYPE = 'product_type', 'Product Type'
        PRICE = 'price', 'Price'
        COMPARE_AT_PRICE = 'compare_at_price', 'Compare at Price'
        INVENTORY_QUANTITY = 'inventory_quantity', 'Inventory Quantity'
        WEIGHT = 'weight', 'Weight'
        TAGS = 'tags', 'Tags'
        SKU = 'sku', 'SKU'
        BARCODE = 'barcode', 'Barcode'
        CREATED_AT = 'created_at', 'Creation Date'
        UPDATED_AT = 'updated_at', 'Last Updated'
    
    class ConditionType(models.TextChoices):
        EQUALS = 'equals', 'Equals'
        NOT_EQUALS = 'not_equals', 'Not Equals'
        CONTAINS = 'contains', 'Contains'
        NOT_CONTAINS = 'not_contains', 'Does Not Contain'
        STARTS_WITH = 'starts_with', 'Starts With'
        ENDS_WITH = 'ends_with', 'Ends With'
        GREATER_THAN = 'greater_than', 'Greater Than'
        LESS_THAN = 'less_than', 'Less Than'
        GREATER_THAN_OR_EQUAL = 'greater_than_or_equal', 'Greater Than or Equal'
        LESS_THAN_OR_EQUAL = 'less_than_or_equal', 'Less Than or Equal'
        IS_SET = 'is_set', 'Is Set'
        IS_NOT_SET = 'is_not_set', 'Is Not Set'
    
    class OperatorType(models.TextChoices):
        AND = 'AND', 'AND'
        OR = 'OR', 'OR'
    
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name='rules'
    )
    
    # Rule definition
    field = models.CharField(max_length=30, choices=FieldType.choices)
    condition = models.CharField(max_length=30, choices=ConditionType.choices)
    value = models.TextField(blank=True)
    operator = models.CharField(
        max_length=3, 
        choices=OperatorType.choices, 
        default=OperatorType.AND
    )
    
    # Rule metadata
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_collection_rules'
        ordering = ['collection', 'position']
    
    def __str__(self):
        return f"{self.collection.title} - {self.field} {self.condition} {self.value}"
    
    def applies_to_product(self, product):
        """Check if this rule applies to a given product"""
        from .products import EcommerceProduct
        
        if not self.is_active:
            return False
        
        # Get the field value from the product
        field_value = getattr(product, self.field, None)
        
        if field_value is None and self.condition not in ['is_not_set']:
            return self.condition == 'is_not_set'
        
        if self.condition == 'is_set':
            return field_value is not None
        elif self.condition == 'is_not_set':
            return field_value is None
        
        # Convert values for comparison
        rule_value = self.value
        
        # Handle different field types
        if self.field in ['price', 'compare_at_price', 'weight']:
            try:
                field_value = float(field_value) if field_value else 0
                rule_value = float(rule_value) if rule_value else 0
            except (ValueError, TypeError):
                return False
        elif self.field == 'inventory_quantity':
            field_value = int(field_value) if field_value else 0
            rule_value = int(rule_value) if rule_value else 0
        elif self.field in ['created_at', 'updated_at']:
            from django.utils.dateparse import parse_datetime
            if isinstance(rule_value, str):
                rule_value = parse_datetime(rule_value)
        else:
            # String comparisons
            field_value = str(field_value).lower() if field_value else ''
            rule_value = str(rule_value).lower()
        
        # Apply condition
        if self.condition == 'equals':
            return field_value == rule_value
        elif self.condition == 'not_equals':
            return field_value != rule_value
        elif self.condition == 'contains':
            return rule_value in field_value
        elif self.condition == 'not_contains':
            return rule_value not in field_value
        elif self.condition == 'starts_with':
            return field_value.startswith(rule_value)
        elif self.condition == 'ends_with':
            return field_value.endswith(rule_value)
        elif self.condition == 'greater_than':
            return field_value > rule_value
        elif self.condition == 'less_than':
            return field_value < rule_value
        elif self.condition == 'greater_than_or_equal':
            return field_value >= rule_value
        elif self.condition == 'less_than_or_equal':
            return field_value <= rule_value
        
        return False


class CollectionImage(EcommerceBaseModel):
    """Additional images for collections"""
    
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name='images'
    )
    
    image = models.ImageField(upload_to='collections/gallery/')
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    # Image types
    image_type = models.CharField(
        max_length=20,
        choices=[
            ('banner', 'Banner'),
            ('featured', 'Featured'),
            ('gallery', 'Gallery'),
            ('thumbnail', 'Thumbnail'),
            ('hero', 'Hero Image'),
        ],
        default='gallery'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ecommerce_collection_images'
        ordering = ['collection', 'position']
    
    def __str__(self):
        return f"Image for {self.collection.title}"


class CollectionSEO(EcommerceBaseModel):
    """Extended SEO settings for collections"""
    
    collection = models.OneToOneField(
        Collection,
        on_delete=models.CASCADE,
        related_name='seo_extended'
    )
    
    # Advanced SEO
    focus_keyword = models.CharField(max_length=100, blank=True)
    meta_robots = models.CharField(
        max_length=100,
        default='index,follow',
        help_text='Robot instructions'
    )
    
    # Social Media
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.TextField(max_length=300, blank=True)
    og_image = models.ImageField(upload_to='seo/og/', blank=True, null=True)
    
    twitter_title = models.CharField(max_length=255, blank=True)
    twitter_description = models.TextField(max_length=200, blank=True)
    twitter_image = models.ImageField(upload_to='seo/twitter/', blank=True, null=True)
    
    # JSON-LD Schema
    collection_schema = models.JSONField(default=dict, blank=True)
    breadcrumb_schema = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ecommerce_collection_seo'
    
    def __str__(self):
        return f"SEO for {self.collection.title}"
    
    def generate_collection_schema(self):
        """Generate Collection JSON-LD schema"""
        collection = self.collection
        
        schema = {
            "@context": "https://schema.org/",
            "@type": "CollectionPage",
            "name": collection.title,
            "description": collection.description,
            "url": collection.get_absolute_url(),
        }
        
        # Add breadcrumbs
        breadcrumbs = collection.get_breadcrumbs()
        if breadcrumbs:
            schema["breadcrumb"] = {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": idx + 1,
                        "name": crumb['title'],
                        "item": crumb['url']
                    }
                    for idx, crumb in enumerate(breadcrumbs)
                ]
            }
        
        # Add product list if available
        products = collection.get_products(limit=10)
        if products:
            schema["mainEntity"] = {
                "@type": "ItemList",
                "numberOfItems": collection.products_count,
                "itemListElement": [
                    {
                        "@type": "Product",
                        "position": idx + 1,
                        "name": product.title,
                        "url": product.get_absolute_url()
                    }
                    for idx, product in enumerate(products)
                ]
            }
        
        return schema


class CollectionMetrics(EcommerceBaseModel):
    """Performance metrics for collections"""
    
    collection = models.OneToOneField(
        Collection,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # View metrics
    total_views = models.PositiveIntegerField(default=0)
    unique_views = models.PositiveIntegerField(default=0)
    views_today = models.PositiveIntegerField(default=0)
    views_this_week = models.PositiveIntegerField(default=0)
    views_this_month = models.PositiveIntegerField(default=0)
    
    # Engagement metrics
    total_product_views = models.PositiveIntegerField(default=0)
    total_add_to_cart = models.PositiveIntegerField(default=0)
    total_purchases = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    bounce_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00
    )
    average_time_on_page = models.PositiveIntegerField(default=0)  # seconds
    conversion_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00
    )
    
    # Revenue metrics
    total_revenue = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00
    )
    average_order_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    
    # Last updated
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecommerce_collection_metrics'
    
    def __str__(self):
        return f"Metrics for {self.collection.title}"
    
    def calculate_conversion_rate(self):
        """Calculate conversion rate"""
        if self.total_views > 0:
            self.conversion_rate = (self.total_purchases / self.total_views) * 100
        else:
            self.conversion_rate = 0.00
        self.save(update_fields=['conversion_rate'])
    
    def calculate_average_order_value(self):
        """Calculate average order value"""
        if self.total_purchases > 0:
            self.average_order_value = self.total_revenue / self.total_purchases
        else:
            self.average_order_value = 0.00
        self.save(update_fields=['average_order_value'])