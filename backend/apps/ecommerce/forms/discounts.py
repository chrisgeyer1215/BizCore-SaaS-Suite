from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta


class DiscountForm(forms.Form):
    """Form for creating and editing discounts."""
    name = forms.CharField(max_length=255, help_text='Name of the discount')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    discount_type = forms.ChoiceField(choices=[
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
        ('buy_x_get_y', 'Buy X Get Y'),
    ])
    value = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text='Discount value (percentage or amount)'
    )
    minimum_order_amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Minimum order amount to apply discount'
    )
    maximum_discount_amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Maximum discount amount (for percentage discounts)'
    )
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text='When the discount becomes active'
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text='When the discount expires'
    )
    usage_limit = forms.IntegerField(
        min_value=1, 
        required=False,
        help_text='Maximum number of times this discount can be used'
    )
    usage_limit_per_customer = forms.IntegerField(
        min_value=1, 
        required=False,
        help_text='Maximum number of times per customer'
    )
    is_active = forms.BooleanField(initial=True, required=False)
    applies_to_entire_order = forms.BooleanField(initial=True, required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        discount_type = cleaned_data.get('discount_type')
        value = cleaned_data.get('value')
        
        if start_date and end_date and start_date >= end_date:
            raise ValidationError('End date must be after start date.')
        
        if start_date and start_date < timezone.now():
            raise ValidationError('Start date cannot be in the past.')
        
        if discount_type == 'percentage' and (value <= 0 or value > 100):
            raise ValidationError('Percentage must be between 0 and 100.')
        
        if discount_type == 'fixed_amount' and value <= 0:
            raise ValidationError('Fixed amount must be greater than 0.')
        
        return cleaned_data


class CouponForm(forms.Form):
    """Form for creating and editing coupon codes."""
    code = forms.CharField(
        max_length=50, 
        help_text='Coupon code that customers will enter'
    )
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    discount_type = forms.ChoiceField(choices=[
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    ])
    value = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Discount value'
    )
    minimum_order_amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    maximum_discount_amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    usage_limit = forms.IntegerField(min_value=1, required=False)
    usage_limit_per_customer = forms.IntegerField(min_value=1, required=False)
    is_active = forms.BooleanField(initial=True, required=False)
    is_single_use = forms.BooleanField(
        required=False,
        help_text='Can only be used once per customer'
    )
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            if not code.isalnum():
                raise ValidationError('Coupon code must contain only letters and numbers.')
        return code


class ApplyCouponForm(forms.Form):
    """Form for customers to apply coupon codes."""
    coupon_code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter coupon code',
            'class': 'form-control'
        })
    )
    
    def clean_coupon_code(self):
        code = self.cleaned_data.get('coupon_code')
        if code:
            return code.upper().strip()
        return code


class BulkDiscountForm(forms.Form):
    """Form for applying bulk discounts to multiple products."""
    discount_type = forms.ChoiceField(choices=[
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ])
    value = forms.DecimalField(max_digits=10, decimal_places=2)
    products = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        help_text='Select products to apply discount to'
    )
    collections = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text='Or select entire collections'
    )
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    
    def __init__(self, *args, **kwargs):
        product_choices = kwargs.pop('product_choices', [])
        collection_choices = kwargs.pop('collection_choices', [])
        super().__init__(*args, **kwargs)
        
        if product_choices:
            self.fields['products'].choices = product_choices
        if collection_choices:
            self.fields['collections'].choices = collection_choices


class SeasonalDiscountForm(forms.Form):
    """Form for creating seasonal or holiday discounts."""
    name = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    discount_type = forms.ChoiceField(choices=[
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    ])
    value = forms.DecimalField(max_digits=10, decimal_places=2)
    season_type = forms.ChoiceField(choices=[
        ('holiday', 'Holiday'),
        ('seasonal', 'Seasonal'),
        ('clearance', 'Clearance'),
        ('flash_sale', 'Flash Sale'),
    ])
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    is_recurring = forms.BooleanField(
        required=False,
        help_text='Apply this discount annually'
    )
    minimum_order_amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
