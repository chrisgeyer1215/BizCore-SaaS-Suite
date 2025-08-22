"""
Checkout views for e-commerce functionality
"""

from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, Http404
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import json

from .base import EcommerceBaseMixin
from .mixins import (
    CartMixin, WishlistMixin, NotificationMixin, AJAXMixin,
    CurrencyMixin, AnalyticsMixin
)
from ..models import Cart, EcommerceProduct, ShippingAddress, BillingAddress
from ..forms import (
    CheckoutCustomerForm, AddressForm, CheckoutShippingForm, 
    CheckoutPaymentForm, OrderReviewForm
)
from ..services.order import OrderService


class CheckoutStartView(EcommerceBaseMixin, CartMixin, TemplateView):
    """Initial checkout page - customer information and account creation"""
    
    template_name = 'ecommerce/checkout/checkout_start.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check if cart has items and user is ready for checkout"""
        cart = self.get_cart()
        
        if not cart or cart.items.count() == 0:
            messages.error(request, "Your cart is empty. Please add items before checkout.")
            return redirect('ecommerce:cart')
        
        # Check if cart total meets minimum order requirements
        if cart.total_amount < Decimal('10.00'):  # Example minimum
            messages.warning(request, "Minimum order amount is $10.00")
            return redirect('ecommerce:cart')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Customer Info', 'url': 'ecommerce:checkout_start', 'active': True},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': False},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': False},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': False},
        ]
        
        return context


class CheckoutCustomerView(EcommerceBaseMixin, CartMixin, FormView):
    """Customer information and account creation during checkout"""
    
    template_name = 'ecommerce/checkout/checkout_customer.html'
    form_class = CheckoutCustomerForm
    success_url = reverse_lazy('ecommerce:checkout_shipping')
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure cart is ready for checkout"""
        cart = self.get_cart()
        if not cart or cart.items.count() == 0:
            return redirect('ecommerce:cart')
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass request and tenant to form"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['tenant'] = self.tenant
        return kwargs
    
    def form_valid(self, form):
        """Handle successful form submission"""
        try:
            with transaction.atomic():
                # Save customer information to session for later use
                customer_data = form.cleaned_data
                self.request.session['checkout_customer'] = customer_data
                
                # If creating account, create user
                if form.cleaned_data.get('create_account'):
                    user = form.save()
                    # Log user in
                    from django.contrib.auth import login
                    login(self.request, user)
                    messages.success(self.request, "Account created and logged in successfully!")
                
                # Update cart with customer information
                cart = self.get_cart()
                cart.customer_email = customer_data.get('email')
                cart.customer_phone = customer_data.get('phone')
                cart.save()
                
                messages.success(self.request, "Customer information saved successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error saving customer information: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Pre-fill form with existing data
        if self.request.user.is_authenticated:
            context['initial'] = {
                'email': self.request.user.email,
                'first_name': getattr(self.request.user, 'first_name', ''),
                'last_name': getattr(self.request.user, 'last_name', ''),
            }
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Customer Info', 'url': 'ecommerce:checkout_start', 'active': True, 'completed': True},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': False},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': False},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': False},
        ]
        
        return context


class CheckoutShippingView(EcommerceBaseMixin, CartMixin, FormView):
    """Shipping address and method selection"""
    
    template_name = 'ecommerce/checkout/checkout_shipping.html'
    form_class = CheckoutShippingForm
    success_url = reverse_lazy('ecommerce:checkout_payment')
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure customer info is completed first"""
        if 'checkout_customer' not in request.session:
            messages.error(request, "Please complete customer information first.")
            return redirect('ecommerce:checkout_start')
        
        cart = self.get_cart()
        if not cart or cart.items.count() == 0:
            return redirect('ecommerce:cart')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass request and tenant to form"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['tenant'] = self.tenant
        return kwargs
    
    def form_valid(self, form):
        """Handle successful shipping form submission"""
        try:
            with transaction.atomic():
                shipping_data = form.cleaned_data
                
                # Save shipping information to session
                self.request.session['checkout_shipping'] = shipping_data
                
                # Create or update shipping address
                if self.request.user.is_authenticated:
                    shipping_address, created = ShippingAddress.objects.get_or_create(
                        tenant=self.tenant,
                        user=self.request.user,
                        address_type='shipping',
                        defaults=shipping_data
                    )
                    if not created:
                        for key, value in shipping_data.items():
                            setattr(shipping_address, key, value)
                        shipping_address.save()
                    
                    # Update cart with shipping address
                    cart = self.get_cart()
                    cart.shipping_address = shipping_address
                    cart.save()
                
                messages.success(self.request, "Shipping information saved successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error saving shipping information: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Pre-fill with existing addresses if user is authenticated
        if self.request.user.is_authenticated:
            context['existing_addresses'] = ShippingAddress.objects.filter(
                tenant=self.tenant,
                user=self.request.user
            )
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Customer Info', 'url': 'ecommerce:checkout_start', 'active': False, 'completed': True},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': True, 'completed': False},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': False},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': False},
        ]
        
        return context


class CheckoutPaymentView(EcommerceBaseMixin, CartMixin, FormView):
    """Payment method selection and billing information"""
    
    template_name = 'ecommerce/checkout/checkout_payment.html'
    form_class = CheckoutPaymentForm
    success_url = reverse_lazy('ecommerce:checkout_review')
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure shipping is completed first"""
        if 'checkout_shipping' not in request.session:
            messages.error(request, "Please complete shipping information first.")
            return redirect('ecommerce:checkout_shipping')
        
        cart = self.get_cart()
        if not cart or cart.items.count() == 0:
            return redirect('ecommerce:cart')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass request and tenant to form"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['tenant'] = self.tenant
        return kwargs
    
    def form_valid(self, form):
        """Handle successful payment form submission"""
        try:
            with transaction.atomic():
                payment_data = form.cleaned_data
                
                # Save payment information to session
                self.request.session['checkout_payment'] = payment_data
                
                # Create or update billing address if different from shipping
                if not payment_data.get('use_shipping_address') and self.request.user.is_authenticated:
                    billing_address, created = BillingAddress.objects.get_or_create(
                        tenant=self.tenant,
                        user=self.request.user,
                        address_type='billing',
                        defaults=payment_data.get('billing_address', {})
                    )
                    if not created:
                        for key, value in payment_data.get('billing_address', {}).items():
                            setattr(billing_address, key, value)
                        billing_address.save()
                    
                    # Update cart with billing address
                    cart = self.get_cart()
                    cart.billing_address = billing_address
                    cart.save()
                
                messages.success(self.request, "Payment information saved successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error saving payment information: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Pre-fill with existing addresses if user is authenticated
        if self.request.user.is_authenticated:
            context['existing_billing_addresses'] = BillingAddress.objects.filter(
                tenant=self.tenant,
                user=self.request.user
            )
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Customer Info', 'url': 'ecommerce:checkout_start', 'active': False, 'completed': True},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': False, 'completed': True},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': True, 'completed': False},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': False},
        ]
        
        return context


class CheckoutReviewView(EcommerceBaseMixin, CartMixin, FormView):
    """Final order review and confirmation"""
    
    template_name = 'ecommerce/checkout/checkout_review.html'
    form_class = OrderReviewForm
    success_url = reverse_lazy('ecommerce:order_confirmation')
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure all previous steps are completed"""
        required_sessions = ['checkout_customer', 'checkout_shipping', 'checkout_payment']
        for session_key in required_sessions:
            if session_key not in request.session:
                messages.error(request, "Please complete all checkout steps first.")
                return redirect('ecommerce:checkout_start')
        
        cart = self.get_cart()
        if not cart or cart.items.count() == 0:
            return redirect('ecommerce:cart')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass request and tenant to form"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['tenant'] = self.tenant
        return kwargs
    
    def form_valid(self, form):
        """Handle order confirmation and creation"""
        try:
            with transaction.atomic():
                # Get all checkout data from session
                customer_data = self.request.session.get('checkout_customer', {})
                shipping_data = self.request.session.get('checkout_shipping', {})
                payment_data = self.request.session.get('checkout_payment', {})
                review_data = form.cleaned_data
                
                # Create order using service
                order_service = OrderService(self.tenant)
                cart = self.get_cart()
                
                order = order_service.create_order_from_cart(
                    cart=cart,
                    customer_data=customer_data,
                    shipping_data=shipping_data,
                    payment_data=payment_data,
                    review_data=review_data,
                    user=self.request.user if self.request.user.is_authenticated else None
                )
                
                # Clear checkout session data
                for session_key in ['checkout_customer', 'checkout_shipping', 'checkout_payment']:
                    if session_key in self.request.session:
                        del self.request.session[session_key]
                
                # Store order ID in session for confirmation page
                self.request.session['last_order_id'] = order.id
                
                # Clear cart
                cart.delete()
                
                messages.success(self.request, f"Order #{order.order_number} created successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error creating order: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Get checkout data from session for review
        context['customer_data'] = self.request.session.get('checkout_customer', {})
        context['shipping_data'] = self.request.session.get('checkout_shipping', {})
        context['payment_data'] = self.request.session.get('checkout_payment', {})
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Customer Info', 'url': 'ecommerce:checkout_start', 'active': False, 'completed': True},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': False, 'completed': True},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': False, 'completed': True},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': True, 'completed': False},
        ]
        
        return context


class OrderConfirmationView(EcommerceBaseMixin, TemplateView):
    """Order confirmation page after successful checkout"""
    
    template_name = 'ecommerce/checkout/order_confirmation.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure order was just created"""
        if 'last_order_id' not in request.session:
            messages.error(request, "No order found. Please start checkout process.")
            return redirect('ecommerce:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get order details
        order_id = self.request.session.get('last_order_id')
        if order_id:
            try:
                from ..models import Order
                order = Order.objects.get(
                    id=order_id,
                    tenant=self.tenant
                )
                context['order'] = order
                
                # Remove order ID from session
                del self.request.session['last_order_id']
                
            except Order.DoesNotExist:
                messages.error(self.request, "Order not found.")
                return redirect('ecommerce:home')
        
        return context


class CheckoutAJAXView(EcommerceBaseMixin, CartMixin, AJAXMixin):
    """AJAX view for checkout operations"""
    
    def post(self, request, *args, **kwargs):
        """Handle AJAX POST requests"""
        action = request.POST.get('action')
        
        if action == 'validate_address':
            return self.validate_address(request)
        elif action == 'calculate_shipping':
            return self.calculate_shipping(request)
        elif action == 'apply_coupon':
            return self.apply_coupon(request)
        elif action == 'remove_coupon':
            return self.remove_coupon(request)
        else:
            return self.json_error('Invalid action')
    
    def validate_address(self, request):
        """Validate shipping/billing address"""
        try:
            address_data = json.loads(request.POST.get('address_data', '{}'))
            
            # Basic validation
            required_fields = ['first_name', 'last_name', 'address_line1', 'city', 'postal_code', 'country']
            missing_fields = [field for field in required_fields if not address_data.get(field)]
            
            if missing_fields:
                return self.json_error(f'Missing required fields: {", ".join(missing_fields)}')
            
            # TODO: Implement address validation service (e.g., Google Maps API)
            
            return self.json_success('Address is valid')
            
        except json.JSONDecodeError:
            return self.json_error('Invalid address data format')
        except Exception as e:
            return self.json_error(f'Error validating address: {str(e)}')
    
    def calculate_shipping(self, request):
        """Calculate shipping costs for address"""
        try:
            address_data = json.loads(request.POST.get('address_data', '{}'))
            cart = self.get_cart()
            
            # TODO: Implement shipping calculation service
            # This would involve:
            # 1. Getting shipping rates from carriers
            # 2. Applying tenant-specific rules
            # 3. Calculating costs based on weight/dimensions
            
            # Placeholder response
            shipping_options = [
                {
                    'id': 'standard',
                    'name': 'Standard Shipping',
                    'cost': '5.99',
                    'delivery_days': '3-5 business days'
                },
                {
                    'id': 'express',
                    'name': 'Express Shipping',
                    'cost': '12.99',
                    'delivery_days': '1-2 business days'
                }
            ]
            
            return self.json_success('Shipping calculated', {
                'shipping_options': shipping_options
            })
            
        except json.JSONDecodeError:
            return self.json_error('Invalid address data format')
        except Exception as e:
            return self.json_error(f'Error calculating shipping: {str(e)}')
    
    def apply_coupon(self, request):
        """Apply coupon code to cart"""
        try:
            coupon_code = request.POST.get('coupon_code', '').strip()
            
            if not coupon_code:
                return self.json_error('Coupon code is required')
            
            cart = self.get_cart()
            
            # TODO: Implement coupon validation and application
            # This would involve:
            # 1. Validating coupon code
            # 2. Checking restrictions (dates, usage limits, etc.)
            # 3. Applying discount to cart
            # 4. Updating cart totals
            
            # Placeholder response
            return self.json_success(f'Coupon {coupon_code} applied successfully', {
                'discount_amount': '5.00',
                'new_total': str(cart.total_amount - Decimal('5.00'))
            })
            
        except Exception as e:
            return self.json_error(f'Error applying coupon: {str(e)}')
    
    def remove_coupon(self, request):
        """Remove coupon from cart"""
        try:
            cart = self.get_cart()
            
            # TODO: Implement coupon removal
            # This would involve:
            # 1. Removing coupon from cart
            # 2. Recalculating totals
            # 3. Updating cart
            
            return self.json_success('Coupon removed successfully')
            
        except Exception as e:
            return self.json_error(f'Error removing coupon: {str(e)}')


class GuestCheckoutView(EcommerceBaseMixin, CartMixin, FormView):
    """Guest checkout for non-authenticated users"""
    
    template_name = 'ecommerce/checkout/guest_checkout.html'
    form_class = CheckoutCustomerForm
    success_url = reverse_lazy('ecommerce:checkout_shipping')
    
    def dispatch(self, request, *args, **kwargs):
        """Ensure user is not authenticated"""
        if request.user.is_authenticated:
            return redirect('ecommerce:checkout_start')
        
        cart = self.get_cart()
        if not cart or cart.items.count() == 0:
            return redirect('ecommerce:cart')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass request and tenant to form"""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['tenant'] = self.tenant
        return kwargs
    
    def form_valid(self, form):
        """Handle guest checkout form submission"""
        try:
            with transaction.atomic():
                # Save guest information to session
                guest_data = form.cleaned_data
                self.request.session['checkout_customer'] = guest_data
                
                # Update cart with guest information
                cart = self.get_cart()
                cart.customer_email = guest_data.get('email')
                cart.customer_phone = guest_data.get('phone')
                cart.save()
                
                messages.success(self.request, "Guest information saved successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error saving guest information: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_cart_context())
        
        # Add checkout steps
        context['checkout_steps'] = [
            {'name': 'Guest Info', 'url': 'ecommerce:guest_checkout', 'active': True, 'completed': False},
            {'name': 'Shipping', 'url': 'ecommerce:checkout_shipping', 'active': False},
            {'name': 'Payment', 'url': 'ecommerce:checkout_payment', 'active': False},
            {'name': 'Review', 'url': 'ecommerce:checkout_review', 'active': False},
        ]
        
        return context
