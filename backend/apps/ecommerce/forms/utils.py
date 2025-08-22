from django import forms
from django.core.exceptions import ValidationError


class ProductSearchForm(forms.Form):
    """Form for product search functionality."""
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search products...',
            'aria-label': 'Search products'
        })
    )
    category = forms.CharField(max_length=100, required=False)
    brand = forms.CharField(max_length=100, required=False)
    price_min = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min price',
            'step': '0.01',
            'min': '0'
        })
    )
    price_max = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max price',
            'step': '0.01',
            'min': '0'
        })
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('relevance', 'Relevance'),
            ('price_low', 'Price: Low to High'),
            ('price_high', 'Price: High to Low'),
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('name_az', 'Name: A to Z'),
            ('name_za', 'Name: Z to A'),
            ('rating', 'Highest Rated'),
            ('popularity', 'Most Popular'),
        ],
        initial='relevance',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    in_stock_only = forms.BooleanField(required=False, initial=False)
    on_sale_only = forms.BooleanField(required=False, initial=False)
    
    def clean(self):
        cleaned_data = super().clean()
        price_min = cleaned_data.get('price_min')
        price_max = cleaned_data.get('price_max')
        
        if price_min and price_max and price_min > price_max:
            raise ValidationError('Minimum price cannot be greater than maximum price.')
        
        return cleaned_data


class ProductFilterForm(forms.Form):
    """Form for advanced product filtering."""
    collections = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Filter by collections'
    )
    product_types = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Filter by product types'
    )
    brands = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Filter by brands'
    )
    availability = forms.ChoiceField(
        choices=[
            ('', 'Any Availability'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
            ('pre_order', 'Pre-order'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    rating = forms.ChoiceField(
        choices=[
            ('', 'Any Rating'),
            ('4', '4+ Stars'),
            ('3', '3+ Stars'),
            ('2', '2+ Stars'),
            ('1', '1+ Stars'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    weight_min = forms.DecimalField(
        max_digits=8,
        decimal_places=3,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min weight (kg)',
            'step': '0.001',
            'min': '0'
        })
    )
    weight_max = forms.DecimalField(
        max_digits=8,
        decimal_places=3,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max weight (kg)',
            'step': '0.001',
            'min': '0'
        })
    )
    
    def __init__(self, *args, **kwargs):
        collection_choices = kwargs.pop('collection_choices', [])
        product_type_choices = kwargs.pop('product_type_choices', [])
        brand_choices = kwargs.pop('brand_choices', [])
        super().__init__(*args, **kwargs)
        
        if collection_choices:
            self.fields['collections'].choices = collection_choices
        if product_type_choices:
            self.fields['product_types'].choices = product_type_choices
        if brand_choices:
            self.fields['brands'].choices = brand_choices


class BulkActionForm(forms.Form):
    """Form for bulk actions on products."""
    action = forms.ChoiceField(
        choices=[
            ('', 'Select Action'),
            ('publish', 'Publish Selected'),
            ('unpublish', 'Unpublish Selected'),
            ('activate', 'Activate Selected'),
            ('deactivate', 'Deactivate Selected'),
            ('delete', 'Delete Selected'),
            ('move_to_collection', 'Move to Collection'),
            ('remove_from_collection', 'Remove from Collection'),
            ('apply_discount', 'Apply Discount'),
            ('update_status', 'Update Status'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    products = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        help_text='Select products to perform action on'
    )
    target_collection = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Collection name or ID'
        })
    )
    discount_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Discount %',
            'step': '0.01'
        })
    )
    new_status = forms.ChoiceField(
        choices=[
            ('', 'Select Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('draft', 'Draft'),
            ('archived', 'Archived'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        product_choices = kwargs.pop('product_choices', [])
        super().__init__(*args, **kwargs)
        
        if product_choices:
            self.fields['products'].choices = product_choices
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'move_to_collection' and not cleaned_data.get('target_collection'):
            raise ValidationError('Target collection is required for move action.')
        
        if action == 'apply_discount' and not cleaned_data.get('discount_percentage'):
            raise ValidationError('Discount percentage is required for discount action.')
        
        if action == 'update_status' and not cleaned_data.get('new_status'):
            raise ValidationError('New status is required for status update action.')
        
        return cleaned_data


class ImportExportForm(forms.Form):
    """Form for product import/export operations."""
    operation_type = forms.ChoiceField(
        choices=[
            ('import', 'Import Products'),
            ('export', 'Export Products'),
        ],
        widget=forms.RadioSelect
    )
    file_format = forms.ChoiceField(
        choices=[
            ('csv', 'CSV'),
            ('xlsx', 'Excel (XLSX)'),
            ('json', 'JSON'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    import_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.json'
        }),
        help_text='Select file to import (CSV, Excel, or JSON)'
    )
    export_collections = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select collections to export'
    )
    include_variants = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Include product variants in export'
    )
    include_images = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Include image URLs in export'
    )
    
    def __init__(self, *args, **kwargs):
        collection_choices = kwargs.pop('collection_choices', [])
        super().__init__(*args, **kwargs)
        
        if collection_choices:
            self.fields['export_collections'].choices = collection_choices
    
    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        import_file = cleaned_data.get('import_file')
        
        if operation_type == 'import' and not import_file:
            raise ValidationError('Import file is required for import operations.')
        
        return cleaned_data


class AnalyticsFilterForm(forms.Form):
    """Form for filtering analytics data."""
    date_range = forms.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_90_days', 'Last 90 Days'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_year', 'This Year'),
            ('last_year', 'Last Year'),
            ('custom', 'Custom Range'),
        ],
        initial='last_30_days',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    group_by = forms.ChoiceField(
        choices=[
            ('day', 'Day'),
            ('week', 'Week'),
            ('month', 'Month'),
            ('quarter', 'Quarter'),
            ('year', 'Year'),
        ],
        initial='day',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    collections = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Filter by collections'
    )
    product_types = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Filter by product types'
    )
    
    def __init__(self, *args, **kwargs):
        collection_choices = kwargs.pop('collection_choices', [])
        product_type_choices = kwargs.pop('product_type_choices', [])
        super().__init__(*args, **kwargs)
        
        if collection_choices:
            self.fields['collections'].choices = collection_choices
        if product_type_choices:
            self.fields['product_types'].choices = product_type_choices
