from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class GuestOrderLookupForm(forms.Form):
    """Form for guests to look up their orders."""
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your order number'
        }),
        help_text='Order number from your confirmation email'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address used for the order'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number (optional)'
        })
    )


class CancelOrderForm(forms.Form):
    """Form for canceling orders."""
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    reason = forms.ChoiceField(
        choices=[
            ('', 'Select a reason'),
            ('changed_mind', 'Changed my mind'),
            ('found_better_price', 'Found a better price elsewhere'),
            ('ordered_wrong_item', 'Ordered wrong item'),
            ('duplicate_order', 'Duplicate order'),
            ('shipping_too_long', 'Shipping takes too long'),
            ('item_out_of_stock', 'Item is out of stock'),
            ('personal_emergency', 'Personal emergency'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    other_reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Please specify if you selected "Other"...'
        })
    )
    refund_method = forms.ChoiceField(
        choices=[
            ('original_payment', 'Refund to original payment method'),
            ('store_credit', 'Store credit'),
            ('gift_card', 'Gift card'),
        ],
        widget=forms.RadioSelect
    )
    comments = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Additional comments (optional)'
        }),
        required=False
    )


class OrderModificationForm(forms.Form):
    """Form for modifying existing orders."""
    modification_type = forms.ChoiceField(
        choices=[
            ('', 'Select modification type'),
            ('add_items', 'Add items to order'),
            ('remove_items', 'Remove items from order'),
            ('change_quantity', 'Change item quantities'),
            ('change_shipping', 'Change shipping address'),
            ('change_shipping_method', 'Change shipping method'),
            ('change_payment', 'Change payment method'),
            ('split_order', 'Split into multiple orders'),
            ('other', 'Other modification'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Please describe the modification you need...'
        }),
        help_text='Detailed description of the requested modification'
    )
    urgency = forms.ChoiceField(
        choices=[
            ('low', 'Low - Can wait'),
            ('medium', 'Medium - Soon'),
            ('high', 'High - Urgent'),
            ('critical', 'Critical - Immediately'),
        ],
        widget=forms.RadioSelect
    )
    contact_preference = forms.ChoiceField(
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
        ],
        widget=forms.RadioSelect
    )


class OrderTrackingForm(forms.Form):
    """Form for tracking order status."""
    tracking_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tracking number'
        })
    )
    carrier = forms.ChoiceField(
        choices=[
            ('', 'Select carrier'),
            ('ups', 'UPS'),
            ('fedex', 'FedEx'),
            ('usps', 'USPS'),
            ('dhl', 'DHL'),
            ('amazon', 'Amazon Logistics'),
            ('other', 'Other'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    email_updates = forms.BooleanField(
        initial=True,
        required=False,
        help_text='Send me email updates about my shipment'
    )


class OrderFeedbackForm(forms.Form):
    """Form for providing feedback about orders."""
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    overall_satisfaction = forms.ChoiceField(
        choices=[
            (5, '⭐⭐⭐⭐⭐ Very Satisfied'),
            (4, '⭐⭐⭐⭐ Satisfied'),
            (3, '⭐⭐⭐ Neutral'),
            (2, '⭐⭐ Dissatisfied'),
            (1, '⭐ Very Dissatisfied'),
        ],
        widget=forms.RadioSelect
    )
    delivery_speed = forms.ChoiceField(
        choices=[
            (5, '⭐⭐⭐⭐⭐ Excellent'),
            (4, '⭐⭐⭐⭐ Good'),
            (3, '⭐⭐⭐ Average'),
            (2, '⭐⭐ Slow'),
            (1, '⭐ Very Slow'),
        ],
        widget=forms.RadioSelect
    )
    product_quality = forms.ChoiceField(
        choices=[
            (5, '⭐⭐⭐⭐⭐ Excellent'),
            (4, '⭐⭐⭐⭐ Good'),
            (3, '⭐⭐⭐ Average'),
            (2, '⭐⭐ Poor'),
            (1, '⭐ Very Poor'),
        ],
        widget=forms.RadioSelect
    )
    customer_service = forms.ChoiceField(
        choices=[
            (5, '⭐⭐⭐⭐⭐ Excellent'),
            (4, '⭐⭐⭐⭐ Good'),
            (3, '⭐⭐⭐ Average'),
            (2, '⭐⭐ Poor'),
            (1, '⭐ Very Poor'),
        ],
        widget=forms.RadioSelect
    )
    comments = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Additional comments about your experience...'
        }),
        required=False
    )
    would_recommend = forms.ChoiceField(
        choices=[
            ('yes', 'Yes, definitely'),
            ('maybe', 'Maybe'),
            ('no', 'No'),
        ],
        widget=forms.RadioSelect
    )


