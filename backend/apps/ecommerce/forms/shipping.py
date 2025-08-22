from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ShippingMethodForm(forms.Form):
    """Form for creating and editing shipping methods."""
    name = forms.CharField(max_length=255, help_text='Name of the shipping method')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    carrier = forms.CharField(max_length=100, help_text='Shipping carrier (e.g., UPS, FedEx)')
    service_code = forms.CharField(max_length=50, help_text='Carrier service code')
    is_active = forms.BooleanField(initial=True, required=False)
    requires_address_validation = forms.BooleanField(initial=True, required=False)
    supports_tracking = forms.BooleanField(initial=True, required=False)
    supports_signature = forms.BooleanField(initial=False, required=False)
    supports_insurance = forms.BooleanField(initial=False, required=False)
    estimated_delivery_days = forms.IntegerField(
        min_value=1, 
        max_value=30,
        help_text='Estimated delivery time in days'
    )
    sort_order = forms.IntegerField(initial=0, required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('estimated_delivery_days', 0) <= 0:
            raise ValidationError('Estimated delivery days must be greater than 0.')
        return cleaned_data


class ShippingRateForm(forms.Form):
    """Form for creating and editing shipping rates."""
    shipping_method = forms.IntegerField(help_text='Shipping method ID')
    country = forms.CharField(max_length=2, help_text='ISO country code')
    state = forms.CharField(max_length=100, required=False, help_text='State/province')
    postal_code_start = forms.CharField(max_length=10, required=False)
    postal_code_end = forms.CharField(max_length=10, required=False)
    weight_min = forms.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        required=False,
        help_text='Minimum weight in kg'
    )
    weight_max = forms.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        required=False,
        help_text='Maximum weight in kg'
    )
    price_min = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Minimum order value'
    )
    price_max = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Maximum order value'
    )
    base_rate = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Base shipping cost'
    )
    per_item_rate = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Additional cost per item'
    )
    per_weight_rate = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Additional cost per kg'
    )
    free_shipping_threshold = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        help_text='Order value for free shipping'
    )
    is_active = forms.BooleanField(initial=True, required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        weight_min = cleaned_data.get('weight_min')
        weight_max = cleaned_data.get('weight_max')
        price_min = cleaned_data.get('price_min')
        price_max = cleaned_data.get('price_min')
        postal_start = cleaned_data.get('postal_code_start')
        postal_end = cleaned_data.get('postal_code_end')
        
        if weight_min and weight_max and weight_min >= weight_max:
            raise ValidationError('Maximum weight must be greater than minimum weight.')
        
        if price_min and price_max and price_min >= price_max:
            raise ValidationError('Maximum price must be greater than minimum price.')
        
        if postal_start and postal_end and postal_start >= postal_end:
            raise ValidationError('Postal code end must be greater than start.')
        
        return cleaned_data


class ShippingZoneForm(forms.Form):
    """Form for creating and editing shipping zones."""
    name = forms.CharField(max_length=255, help_text='Zone name (e.g., North America)')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    countries = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        help_text='Countries in this zone'
    )
    states = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text='States/provinces in this zone'
    )
    postal_codes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text='Postal codes (one per line or ranges like 10000-10999)'
    )
    is_active = forms.BooleanField(initial=True, required=False)
    
    def __init__(self, *args, **kwargs):
        country_choices = kwargs.pop('country_choices', [])
        state_choices = kwargs.pop('state_choices', [])
        super().__init__(*args, **kwargs)
        
        if country_choices:
            self.fields['countries'].choices = country_choices
        if state_choices:
            self.fields['states'].choices = state_choices


class FulfillmentForm(forms.Form):
    """Form for creating and updating fulfillment records."""
    tracking_number = forms.CharField(
        max_length=100, 
        required=False,
        help_text='Carrier tracking number'
    )
    tracking_url = forms.URLField(required=False, help_text='Tracking URL')
    carrier = forms.CharField(max_length=100, help_text='Shipping carrier')
    service = forms.CharField(max_length=100, help_text='Shipping service')
    shipped_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text='When the order was shipped'
    )
    estimated_delivery = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        required=False
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    items = forms.JSONField(
        help_text='JSON array of fulfilled items with quantities'
    )


class AddressValidationForm(forms.Form):
    """Form for validating shipping addresses."""
    address_line1 = forms.CharField(max_length=255)
    address_line2 = forms.CharField(max_length=255, required=False)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20)
    country = forms.CharField(max_length=2)
    
    def clean_postal_code(self):
        postal_code = self.cleaned_data.get('postal_code')
        if postal_code:
            # Remove spaces and dashes
            postal_code = postal_code.replace(' ', '').replace('-', '')
        return postal_code


class ShippingCalculatorForm(forms.Form):
    """Form for calculating shipping costs."""
    origin_address = forms.JSONField(help_text='Origin address')
    destination_address = forms.JSONField(help_text='Destination address')
    items = forms.JSONField(help_text='Items to ship with weights and dimensions')
    shipping_method = forms.CharField(max_length=100, required=False)
    insurance_value = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    signature_required = forms.BooleanField(required=False)
    residential_delivery = forms.BooleanField(initial=True, required=False)
    
    def clean_items(self):
        items = self.cleaned_data.get('items')
        if not isinstance(items, list):
            raise ValidationError('Items must be a list.')
        
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError('Each item must be a dictionary.')
            
            required_fields = ['weight', 'quantity']
            for field in required_fields:
                if field not in item:
                    raise ValidationError(f'Each item must have a {field}.')
        
        return items


class InternationalShippingForm(forms.Form):
    """Form for international shipping settings."""
    country = forms.CharField(max_length=2, help_text='Destination country')
    customs_declaration = forms.BooleanField(initial=True, required=False)
    commercial_invoice = forms.BooleanField(initial=False, required=False)
    certificate_of_origin = forms.BooleanField(initial=False, required=False)
    harmonized_code = forms.CharField(
        max_length=20, 
        required=False,
        help_text='HS/HTS code for customs'
    )
    customs_value = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Declared value for customs'
    )
    description = forms.CharField(
        max_length=255,
        help_text='Description of goods for customs'
    )
    origin_country = forms.CharField(
        max_length=2,
        help_text='Country of origin for goods'
    )
