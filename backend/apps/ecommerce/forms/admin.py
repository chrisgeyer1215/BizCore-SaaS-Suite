from django import forms
from django.core.exceptions import ValidationError

from ..models import EcommerceSettings


class EcommerceSettingsForm(forms.ModelForm):
    """Form for managing ecommerce settings."""
    class Meta:
        model = EcommerceSettings
        exclude = ['tenant']
        widgets = {
            'store_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Store Name'}),
            'store_description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'default_currency': forms.Select(attrs={'class': 'form-control'}),
            'default_language': forms.Select(attrs={'class': 'form-control'}),
            'timezone': forms.Select(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'support_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'business_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'shipping_policy': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'return_policy': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'privacy_policy': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'terms_of_service': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def clean_tax_rate(self):
        tax_rate = self.cleaned_data.get('tax_rate')
        if tax_rate and (tax_rate < 0 or tax_rate > 100):
            raise ValidationError('Tax rate must be between 0 and 100 percent.')
        return tax_rate


class StoreAppearanceForm(forms.Form):
    """Form for managing store appearance settings."""
    primary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        initial='#007bff'
    )
    secondary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        initial='#6c757d'
    )
    accent_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        initial='#28a745'
    )
    logo = forms.ImageField(required=False, help_text='Store logo (recommended: 200x80px)')
    favicon = forms.ImageField(required=False, help_text='Favicon (recommended: 32x32px)')
    hero_image = forms.ImageField(required=False, help_text='Hero banner image')
    custom_css = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 8, 'class': 'form-control'}),
        required=False,
        help_text='Custom CSS for store styling'
    )


class NotificationSettingsForm(forms.Form):
    """Form for managing notification settings."""
    email_notifications = forms.BooleanField(initial=True, required=False)
    sms_notifications = forms.BooleanField(required=False)
    order_confirmation = forms.BooleanField(initial=True, required=False)
    shipping_updates = forms.BooleanField(initial=True, required=False)
    low_stock_alerts = forms.BooleanField(initial=True, required=False)
    abandoned_cart_reminders = forms.BooleanField(initial=True, required=False)
    newsletter_subscriptions = forms.BooleanField(initial=True, required=False)
    marketing_emails = forms.BooleanField(required=False)
    review_requests = forms.BooleanField(initial=True, required=False)


