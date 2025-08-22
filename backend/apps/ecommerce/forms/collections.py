from django import forms

from ..models import (
    Collection,
    CollectionProduct,
    CollectionRule,
    CollectionImage,
    CollectionSEO,
    CollectionMetrics,
)


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = [
            'title', 'description', 'handle', 'collection_type',
            'parent', 'level', 'display_order', 'products_per_page', 'default_sort_order',
            'collection_rules', 'featured_image', 'banner_image', 'icon_class', 'color_code',
            'status', 'is_active', 'is_published', 'is_featured',
            'publish_date', 'unpublish_date', 'is_visible_in_search', 'is_visible_in_storefront',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'collection_rules': forms.Textarea(attrs={'rows': 3}),
        }


class CollectionProductForm(forms.ModelForm):
    class Meta:
        model = CollectionProduct
        fields = [
            'collection', 'product', 'position', 'is_featured',
            'custom_title', 'custom_description', 'custom_image', 'added_by'
        ]
        widgets = {
            'custom_description': forms.Textarea(attrs={'rows': 2}),
        }


class CollectionRuleForm(forms.ModelForm):
    class Meta:
        model = CollectionRule
        fields = ['collection', 'field', 'condition', 'value', 'operator', 'position', 'is_active']


class CollectionImageForm(forms.ModelForm):
    class Meta:
        model = CollectionImage
        fields = ['collection', 'image', 'alt_text', 'caption', 'position', 'image_type', 'is_active']


class CollectionSEOForm(forms.ModelForm):
    class Meta:
        model = CollectionSEO
        fields = [
            'collection', 'focus_keyword', 'meta_robots',
            'og_title', 'og_description', 'og_image',
            'twitter_title', 'twitter_description', 'twitter_image',
            'collection_schema', 'breadcrumb_schema',
        ]
        widgets = {
            'og_description': forms.Textarea(attrs={'rows': 2}),
            'twitter_description': forms.Textarea(attrs={'rows': 2}),
            'collection_schema': forms.Textarea(attrs={'rows': 3}),
            'breadcrumb_schema': forms.Textarea(attrs={'rows': 3}),
        }


class CollectionMetricsForm(forms.ModelForm):
    """Form for managing collection metrics."""
    class Meta:
        model = CollectionMetrics
        fields = ['collection', 'metric_type', 'value', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


