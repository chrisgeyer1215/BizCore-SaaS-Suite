from django import forms

from ..models import Cart, CartItem, Wishlist, WishlistItem, SavedForLater, CartAbandonmentEvent, CartShare


class AddToCartForm(forms.Form):
    product_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        error_messages={'required': 'Product ID is required'}
    )
    variant_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    quantity = forms.IntegerField(
        min_value=1, 
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '999',
            'style': 'width: 80px;'
        }),
        error_messages={
            'min_value': 'Quantity must be at least 1',
            'required': 'Quantity is required'
        }
    )
    custom_attributes = forms.JSONField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='Custom product attributes'
    )
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity > 999:
            raise forms.ValidationError('Quantity cannot exceed 999')
        return quantity


class UpdateCartItemForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ['quantity', 'custom_attributes', 'gift_message']


class RemoveCartItemForm(forms.Form):
    cart_item_id = forms.IntegerField()


class ApplyCouponForm(forms.Form):
    coupon_code = forms.CharField(max_length=50)


class CartShippingAddressForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['shipping_address', 'shipping_method']
        widgets = {
            'shipping_address': forms.Textarea(attrs={'rows': 3}),
        }


class AddToWishlistForm(forms.Form):
    product_id = forms.IntegerField()
    variant_id = forms.IntegerField(required=False)
    wishlist_id = forms.IntegerField(required=False)


class UpdateWishlistItemForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = ['note', 'priority']


class SavedForLaterForm(forms.ModelForm):
    """Form for managing saved for later items."""
    class Meta:
        model = SavedForLater
        fields = ['note', 'priority', 'reminder_date']
        widgets = {
            'reminder_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


class CartAbandonmentEventForm(forms.ModelForm):
    """Form for tracking cart abandonment events."""
    class Meta:
        model = CartAbandonmentEvent
        fields = ['cart', 'abandonment_reason', 'recovery_attempts', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


class CartShareForm(forms.ModelForm):
    """Form for managing cart sharing."""
    class Meta:
        model = CartShare
        fields = ['cart', 'shared_by', 'shared_with', 'expires_at', 'message']
        widgets = {
            'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'message': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


