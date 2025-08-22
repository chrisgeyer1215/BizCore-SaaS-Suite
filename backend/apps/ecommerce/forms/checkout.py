from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class CheckoutCustomerForm(forms.Form):
    """Form for customer information during checkout."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        })
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number (optional)'
        })
    )
    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company (optional)'
        })
    )
    create_account = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Create an account to track orders and save information'
    )
    password = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Password for new account (if creating account)'
    )

    def clean(self):
        cleaned_data = super().clean()
        create_account = cleaned_data.get('create_account')
        password = cleaned_data.get('password')
        
        if create_account and not password:
            raise ValidationError('Password is required when creating an account.')
        
        return cleaned_data


class AddressForm(forms.Form):
    """Form for address information."""
    address_type = forms.ChoiceField(
        choices=[
            ('shipping', 'Shipping Address'),
            ('billing', 'Billing Address'),
        ],
        widget=forms.RadioSelect
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address_line1 = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Street Address'
        })
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apartment, suite, etc. (optional)'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    postal_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    country = forms.ChoiceField(
        choices=[
            ('US', 'United States'),
            ('CA', 'Canada'),
            ('GB', 'United Kingdom'),
            ('DE', 'Germany'),
            ('FR', 'France'),
            ('AU', 'Australia'),
            ('JP', 'Japan'),
            ('IN', 'India'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    is_default = forms.BooleanField(required=False, initial=False)


class CheckoutShippingForm(forms.Form):
    """Form for shipping information during checkout."""
    shipping_address = forms.JSONField(
        help_text='Shipping address data'
    )
    shipping_method = forms.ChoiceField(
        choices=[
            ('standard', 'Standard Shipping (3-5 business days)'),
            ('express', 'Express Shipping (1-2 business days)'),
            ('overnight', 'Overnight Shipping'),
            ('pickup', 'Store Pickup'),
        ],
        widget=forms.RadioSelect
    )
    delivery_instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Special delivery instructions (optional)'
        }),
        required=False
    )
    signature_required = forms.BooleanField(required=False)
    insurance = forms.BooleanField(required=False)


class CheckoutPaymentForm(forms.Form):
    """Form for payment information during checkout."""
    payment_method = forms.ChoiceField(
        choices=[
            ('credit_card', 'Credit Card'),
            ('debit_card', 'Debit Card'),
            ('paypal', 'PayPal'),
            ('apple_pay', 'Apple Pay'),
            ('google_pay', 'Google Pay'),
            ('bank_transfer', 'Bank Transfer'),
            ('cod', 'Cash on Delivery'),
        ],
        widget=forms.RadioSelect
    )
    
    # Credit Card Fields
    card_number = forms.CharField(
        max_length=19,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'pattern': '[0-9\s]{13,19}'
        })
    )
    card_holder_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Name on Card'
        })
    )
    expiry_month = forms.ChoiceField(
        choices=[(str(i), f'{i:02d}') for i in range(1, 13)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    expiry_year = forms.ChoiceField(
        choices=[(str(i), str(i)) for i in range(2024, 2035)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    cvv = forms.CharField(
        max_length=4,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CVV',
            'pattern': '[0-9]{3,4}'
        })
    )
    
    # PayPal Fields
    paypal_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'PayPal Email'
        })
    )
    
    # Bank Transfer Fields
    account_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    routing_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Billing Address
    use_shipping_address = forms.BooleanField(initial=True, required=False)
    billing_address = forms.JSONField(required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        if payment_method == 'credit_card':
            required_fields = ['card_number', 'card_holder_name', 'expiry_month', 'expiry_year', 'cvv']
            for field in required_fields:
                if not cleaned_data.get(field):
                    raise ValidationError(f'{field.replace("_", " ").title()} is required for credit card payments.')
        
        elif payment_method == 'paypal':
            if not cleaned_data.get('paypal_email'):
                raise ValidationError('PayPal email is required for PayPal payments.')
        
        elif payment_method == 'bank_transfer':
            required_fields = ['account_number', 'routing_number']
            for field in required_fields:
                if not cleaned_data.get(field):
                    raise ValidationError(f'{field.replace("_", " ").title()} is required for bank transfer payments.')
        
        return cleaned_data


class OrderReviewForm(forms.Form):
    """Form for final order review and confirmation."""
    accept_terms = forms.BooleanField(
        error_messages={'required': 'You must accept the terms and conditions to proceed.'}
    )
    accept_privacy_policy = forms.BooleanField(
        error_messages={'required': 'You must accept the privacy policy to proceed.'}
    )
    subscribe_newsletter = forms.BooleanField(required=False, initial=False)
    subscribe_marketing = forms.BooleanField(required=False, initial=False)
    special_instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Special instructions for your order (optional)'
        }),
        required=False
    )
    gift_wrapping = forms.BooleanField(required=False, initial=False)
    gift_message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': 'Gift message (optional)'
        }),
        required=False
    )


