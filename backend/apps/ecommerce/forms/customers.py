from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomerRegistrationForm(UserCreationForm):
    """Form for customer registration during checkout or account creation."""
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    accept_terms = forms.BooleanField(required=True)
    subscribe_newsletter = forms.BooleanField(required=False, initial=True)
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class CustomerProfileForm(forms.ModelForm):
    """Form for updating customer profile information."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class CustomerAddressForm(forms.Form):
    """Form for managing customer addresses."""
    address_type = forms.ChoiceField(choices=[
        ('billing', 'Billing Address'),
        ('shipping', 'Shipping Address'),
    ])
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=100, required=False)
    address_line1 = forms.CharField(max_length=255)
    address_line2 = forms.CharField(max_length=255, required=False)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20)
    country = forms.CharField(max_length=2)
    phone = forms.CharField(max_length=20, required=False)
    is_default = forms.BooleanField(required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, 'widget'):
                field.widget.attrs.update({'class': 'form-control'})


class CustomerPreferencesForm(forms.Form):
    """Form for customer preferences and settings."""
    email_notifications = forms.MultipleChoiceField(
        choices=[
            ('order_updates', 'Order Updates'),
            ('shipping_notifications', 'Shipping Notifications'),
            ('promotional_offers', 'Promotional Offers'),
            ('product_releases', 'New Product Releases'),
            ('newsletter', 'Newsletter'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    sms_notifications = forms.BooleanField(required=False)
    language = forms.ChoiceField(choices=[
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
    ])
    currency = forms.ChoiceField(choices=[
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ])
    timezone = forms.ChoiceField(choices=[
        ('UTC', 'UTC'),
        ('America/New_York', 'Eastern Time'),
        ('America/Chicago', 'Central Time'),
        ('America/Denver', 'Mountain Time'),
        ('America/Los_Angeles', 'Pacific Time'),
    ])
