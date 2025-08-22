from django import forms

from ..models import (
    EcommerceProduct,
    ProductVariant,
    ProductOption,
    ProductOptionValue,
    ProductImage,
    ProductBundle,
    BundleItem,
    ProductSEO,
    ProductTag,
    ProductMetric,
)


class EcommerceProductForm(forms.ModelForm):
    class Meta:
        model = EcommerceProduct
        fields = [
            'title', 'description', 'short_description',
            'sku', 'barcode', 'product_code',
            'product_type', 'brand', 'manufacturer', 'model_number',
            'url_handle',
            'has_variants', 'options',
            'price', 'compare_at_price', 'cost_price', 'currency',
            'primary_collection', 'collections',
            'requires_shipping', 'is_digital_product',
            'is_taxable', 'tax_code',
            'featured_image', 'gallery_images', 'product_videos',
            'specifications', 'attributes', 'custom_fields',
            'status', 'is_active', 'is_published', 'is_featured',
            'publish_date', 'unpublish_date',
            'is_visible_in_search', 'is_visible_in_storefront', 'requires_authentication',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter product title'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Detailed product description'}),
            'short_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Brief product summary'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Stock Keeping Unit'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product barcode'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Internal product code'}),
            'product_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Physical, Digital, Service'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product brand'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manufacturer name'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Model/part number'}),
            'url_handle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'URL-friendly product name'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'compare_at_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'gallery_images': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Comma-separated image URLs'}),
            'product_videos': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Comma-separated video URLs'}),
            'specifications': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Product specifications (JSON format)'}),
            'attributes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Product attributes (JSON format)'}),
            'custom_fields': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Custom fields (JSON format)'}),
            'publish_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'unpublish_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        compare_at = cleaned.get('compare_at_price')
        price = cleaned.get('price')
        
        if compare_at is not None and price is not None and compare_at <= price:
            self.add_error('compare_at_price', 'Compare at price must be higher than regular price')
        
        if cleaned.get('is_digital_product') and cleaned.get('requires_shipping'):
            self.add_error('requires_shipping', 'Digital products cannot require shipping')
        
        if cleaned.get('url_handle'):
            # Ensure URL handle is URL-friendly
            import re
            if not re.match(r'^[a-z0-9-]+$', cleaned['url_handle']):
                self.add_error('url_handle', 'URL handle can only contain lowercase letters, numbers, and hyphens')
        
        return cleaned

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            # Check for duplicate SKU within the same tenant
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                # Updating existing product
                if EcommerceProduct.objects.filter(sku=sku, tenant=instance.tenant).exclude(pk=instance.pk).exists():
                    raise forms.ValidationError('A product with this SKU already exists.')
            else:
                # Creating new product
                if EcommerceProduct.objects.filter(sku=sku, tenant=instance.tenant).exists():
                    raise forms.ValidationError('A product with this SKU already exists.')
        return sku


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            'ecommerce_product', 'title', 'sku', 'barcode',
            'option_values',
            'price', 'compare_at_price', 'cost_price', 'currency',
            'track_quantity', 'inventory_policy',
            'stock_quantity', 'reserved_quantity', 'committed_quantity', 'incoming_quantity',
            'low_stock_threshold', 'out_of_stock_threshold',
            'weight', 'length', 'width', 'height',
            'image', 'is_active', 'position',
        ]

    def clean(self):
        cleaned = super().clean()
        compare_at = cleaned.get('compare_at_price')
        price = cleaned.get('price')
        if compare_at is not None and price is not None and compare_at <= price:
            self.add_error('compare_at_price', 'Compare at price must be higher than price')
        return cleaned


class ProductOptionForm(forms.ModelForm):
    class Meta:
        model = ProductOption
        fields = ['name', 'display_name', 'position']


class ProductOptionValueForm(forms.ModelForm):
    class Meta:
        model = ProductOptionValue
        fields = ['option', 'value', 'display_value', 'position', 'color_code', 'image']


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['product', 'variant', 'image', 'alt_text', 'caption', 'position', 'is_featured', 'is_active']


class ProductBundleForm(forms.ModelForm):
    class Meta:
        model = ProductBundle
        fields = [
            'name', 'description', 'bundle_type',
            'price', 'compare_at_price', 'cost_price', 'currency',
            'pricing_strategy', 'discount_percentage', 'discount_amount',
            'status', 'is_active', 'is_published', 'is_featured',
            'seo_title', 'seo_description', 'seo_keywords', 'canonical_url',
            'image',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'seo_description': forms.Textarea(attrs={'rows': 2}),
        }


class BundleItemForm(forms.ModelForm):
    class Meta:
        model = BundleItem
        fields = ['bundle', 'product', 'variant', 'quantity', 'is_optional', 'position', 'custom_price']


class ProductSEOForm(forms.ModelForm):
    class Meta:
        model = ProductSEO
        fields = [
            'product',
            'focus_keyword', 'meta_robots',
            'facebook_title', 'facebook_description', 'facebook_image',
            'twitter_title', 'twitter_description', 'twitter_image', 'twitter_card_type',
            'product_schema', 'breadcrumb_schema',
            'preload_images', 'lazy_load_images',
        ]
        widgets = {
            'facebook_description': forms.Textarea(attrs={'rows': 2}),
            'twitter_description': forms.Textarea(attrs={'rows': 2}),
            'product_schema': forms.Textarea(attrs={'rows': 4}),
            'breadcrumb_schema': forms.Textarea(attrs={'rows': 3}),
        }


class ProductTagForm(forms.ModelForm):
    """Form for managing product tags."""
    class Meta:
        model = ProductTag
        fields = ['name', 'description', 'color_code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tag name'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'color_code': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class ProductMetricForm(forms.ModelForm):
    """Form for managing product metrics."""
    class Meta:
        model = ProductMetric
        fields = ['product', 'metric_type', 'value', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


class ProductQuickAddForm(forms.Form):
    """Lightweight form for quickly adding a product to a collection in admin UIs."""
    product = forms.ModelChoiceField(queryset=EcommerceProduct.objects.none())

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields['product'].queryset = EcommerceProduct.objects.filter(tenant=tenant)


