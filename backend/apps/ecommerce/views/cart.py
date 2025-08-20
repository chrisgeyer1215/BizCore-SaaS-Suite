# apps/ecommerce/views/cart.py

"""
Shopping cart and wishlist views
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from .base import (
    EcommerceTemplateView, EcommerceDetailView, AjaxView,
    StorefrontMixin, EcommerceBaseMixin
)
from ..models import (
    Cart, CartItem, Wishlist, WishlistItem, EcommerceProduct, 
    ProductVariant, Discount, SavedForLater
)
from ..services.cart import CartService
from ..services.discounts import DiscountService


class CartDetailView(EcommerceTemplateView):
    """Shopping cart page"""
    
    template_name = 'ecommerce/cart/cart_detail.html'
    breadcrumb_title = 'Shopping Cart'
    meta_title = 'Shopping Cart'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        cart = self.get_cart()
        context.update({
            'cart': cart,
            'cart_items': cart.items.select_related(
                'product', 'variant'
            ).order_by('added_at') if cart else [],
            'shipping_calculator': self.get_shipping_calculator(),
            'available_coupons': self.get_available_coupons(),
            'recommended_products': self.get_recommended_products(cart),
            'saved_for_later': self.get_saved_for_later(),
        })
        
        return context
    
    def get_shipping_calculator(self):
        """Get shipping calculation data"""
        # This would integrate with shipping service
        return {
            'enabled': True,
            'countries': ['US', 'CA', 'UK', 'AU'],  # Example countries
            'rates': [
                {'name': 'Standard Shipping', 'price': 10.00, 'days': '3-5'},
                {'name': 'Express Shipping', 'price': 25.00, 'days': '1-2'},
                {'name': 'Free Shipping', 'price': 0.00, 'days': '5-7', 'min_order': 50.00},
            ]
        }
    
    def get_available_coupons(self):
        """Get available coupons for display"""
        discount_service = DiscountService(self.tenant)
        return discount_service.get_available_coupons(
            user=self.request.user if self.request.user.is_authenticated else None
        )
    
    def get_recommended_products(self, cart):
        """Get recommended products based on cart contents"""
        if not cart or not cart.items.exists():
            return EcommerceProduct.published.filter(
                tenant=self.tenant,
                is_featured=True
            )[:4]
        
        # Get products from same categories as cart items
        categories = set()
        for item in cart.items.all():
            if item.product.primary_collection:
                categories.add(item.product.primary_collection.id)
        
        if categories:
            return EcommerceProduct.published.filter(
                tenant=self.tenant,
                primary_collection__id__in=categories
            ).exclude(
                id__in=cart.items.values_list('product_id', flat=True)
            )[:4]
        
        return EcommerceProduct.published.filter(
            tenant=self.tenant,
            is_featured=True
        )[:4]
    
    def get_saved_for_later(self):
        """Get saved for later items"""
        if self.request.user.is_authenticated:
            return SavedForLater.objects.filter(
                tenant=self.tenant,
                user=self.request.user
            ).select_related('product', 'variant')[:5]
        else:
            session_key = self.request.session.session_key
            if session_key:
                return SavedForLater.objects.filter(
                    tenant=self.tenant,
                    session_key=session_key
                ).select_related('product', 'variant')[:5]
        return SavedForLater.objects.none()


class AddToCartView(AjaxView):
    """Add product to cart"""
    
    def handle_ajax_post(self):
        product_id = self.request.POST.get('product_id')
        variant_id = self.request.POST.get('variant_id')
        quantity = self.request.POST.get('quantity', 1)
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValidationError('Quantity must be greater than 0')
        except (ValueError, TypeError):
            raise ValidationError('Invalid quantity')
        
        # Get product
        product = get_object_or_404(
            EcommerceProduct.published,
            tenant=self.tenant,
            id=product_id
        )
        
        # Get variant if specified
        variant = None
        if variant_id:
            variant = get_object_or_404(
                ProductVariant,
                tenant=self.tenant,
                id=variant_id,
                ecommerce_product=product,
                is_active=True
            )
        
        # Check stock availability
        if variant:
            available_stock = variant.available_quantity
            item_name = f"{product.title} - {variant.title}"
        else:
            available_stock = product.available_quantity
            item_name = product.title
        
        if product.track_quantity and available_stock < quantity:
            raise ValidationError(
                f'Only {available_stock} items available in stock'
            )
        
        # Get cart service
        cart_service = CartService(self.tenant)
        
        # Get or create cart
        if self.request.user.is_authenticated:
            cart = cart_service.get_or_create_user_cart(self.request.user)
        else:
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
            cart = cart_service.get_or_create_session_cart(session_key)
        
        # Add item to cart
        cart_item = cart_service.add_item(
            cart=cart,
            product=product,
            variant=variant,
            quantity=quantity
        )
        
        return {
            'message': f'{item_name} added to cart',
            'cart_item_count': cart.item_count,
            'cart_total': str(cart.total_amount),
            'item': {
                'id': cart_item.id,
                'name': item_name,
                'quantity': cart_item.quantity,
                'price': str(cart_item.unit_price),
                'total': str(cart_item.line_total)
            }
        }


class UpdateCartView(AjaxView):
    """Update cart item quantity"""
    
    def handle_ajax_post(self):
        cart_item_id = self.request.POST.get('cart_item_id')
        quantity = self.request.POST.get('quantity')
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValidationError('Quantity cannot be negative')
        except (ValueError, TypeError):
            raise ValidationError('Invalid quantity')
        
        # Get cart item
        cart_item = get_object_or_404(
            CartItem,
            tenant=self.tenant,
            id=cart_item_id
        )
        
        # Verify cart ownership
        cart = cart_item.cart
        if not self._verify_cart_access(cart):
            raise ValidationError('Access denied')
        
        cart_service = CartService(self.tenant)
        
        if quantity == 0:
            # Remove item
            cart_service.remove_item(cart, cart_item)
            message = f'{cart_item.item_name} removed from cart'
        else:
            # Update quantity
            cart_service.update_item_quantity(cart_item, quantity)
            message = f'{cart_item.item_name} quantity updated'
        
        # Refresh cart
        cart.refresh_from_db()
        
        return {
            'message': message,
            'cart_item_count': cart.item_count,
            'cart_subtotal': str(cart.subtotal),
            'cart_total': str(cart.total_amount),
            'item_removed': quantity == 0,
            'item': {
                'id': cart_item.id,
                'quantity': cart_item.quantity if quantity > 0 else 0,
                'line_total': str(cart_item.line_total) if quantity > 0 else '0.00'
            }
        }
    
    def _verify_cart_access(self, cart):
        """Verify user has access to cart"""
        if self.request.user.is_authenticated:
            return cart.user == self.request.user
        else:
            return cart.session_key == self.request.session.session_key


class RemoveFromCartView(AjaxView):
    """Remove item from cart"""
    
    def handle_ajax_post(self):
        cart_item_id = self.request.POST.get('cart_item_id')
        
        cart_item = get_object_or_404(
            CartItem,
            tenant=self.tenant,
            id=cart_item_id
        )
        
        # Verify cart ownership
        cart = cart_item.cart
        if not self._verify_cart_access(cart):
            raise ValidationError('Access denied')
        
        item_name = cart_item.item_name
        
        # Remove item
        cart_service = CartService(self.tenant)
        cart_service.remove_item(cart, cart_item)
        
        return {
            'message': f'{item_name} removed from cart',
            'cart_item_count': cart.item_count,
            'cart_subtotal': str(cart.subtotal),
            'cart_total': str(cart.total_amount)
        }
    
    def _verify_cart_access(self, cart):
        """Verify user has access to cart"""
        if self.request.user.is_authenticated:
            return cart.user == self.request.user
        else:
            return cart.session_key == self.request.session.session_key


class ClearCartView(AjaxView):
    """Clear all items from cart"""
    
    def handle_ajax_post(self):
        cart = self.get_cart()
        if not cart:
            raise ValidationError('No active cart found')
        
        cart_service = CartService(self.tenant)
        cart_service.clear_cart(cart)
        
        return {
            'message': 'Cart cleared successfully',
            'cart_item_count': 0,
            'cart_total': '0.00'
        }


class ApplyCouponAjaxView(AjaxView):
    """Apply coupon to cart"""
    
    def handle_ajax_post(self):
        coupon_code = self.request.POST.get('coupon_code', '').strip().upper()
        
        if not coupon_code:
            raise ValidationError('Coupon code is required')
        
        cart = self.get_cart()
        if not cart or cart.is_empty:
            raise ValidationError('Cart is empty')
        
        # Check if coupon already applied
        if coupon_code in cart.applied_coupons:
            raise ValidationError('Coupon already applied')
        
        # Validate and apply coupon
        discount_service = DiscountService(self.tenant)
        try:
            discount = discount_service.validate_coupon(
                code=coupon_code,
                user=self.request.user if self.request.user.is_authenticated else None,
                cart=cart
            )
            
            # Apply coupon
            cart_service = CartService(self.tenant)
            cart_service.apply_coupon(cart, coupon_code, discount)
            
            return {
                'message': f'Coupon "{coupon_code}" applied successfully',
                'discount_amount': str(cart.discount_amount),
                'cart_total': str(cart.total_amount),
                'coupon': {
                    'code': coupon_code,
                    'title': discount.title,
                    'discount_amount': str(discount.calculate_discount(cart.subtotal))
                }
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))


class RemoveCouponAjaxView(AjaxView):
    """Remove coupon from cart"""
    
    def handle_ajax_post(self):
        coupon_code = self.request.POST.get('coupon_code', '').strip().upper()
        
        cart = self.get_cart()
        if not cart:
            raise ValidationError('No active cart found')
        
        if coupon_code not in cart.applied_coupons:
            raise ValidationError('Coupon not applied to cart')
        
        # Remove coupon
        cart_service = CartService(self.tenant)
        cart_service.remove_coupon(cart, coupon_code)
        
        return {
            'message': f'Coupon "{coupon_code}" removed',
            'discount_amount': str(cart.discount_amount),
            'cart_total': str(cart.total_amount)
        }


class SaveForLaterView(AjaxView):
    """Save cart item for later"""
    
    def handle_ajax_post(self):
        cart_item_id = self.request.POST.get('cart_item_id')
        
        cart_item = get_object_or_404(
            CartItem,
            tenant=self.tenant,
            id=cart_item_id
        )
        
        # Verify cart ownership
        cart = cart_item.cart
        if not self._verify_cart_access(cart):
            raise ValidationError('Access denied')
        
        # Create saved for later item
        saved_item_data = {
            'tenant': self.tenant,
            'product': cart_item.product,
            'variant': cart_item.variant,
            'quantity': cart_item.quantity,
            'custom_attributes': cart_item.custom_attributes,
            'saved_price': cart_item.unit_price,
        }
        
        if self.request.user.is_authenticated:
            saved_item_data['user'] = self.request.user
        else:
            saved_item_data['session_key'] = self.request.session.session_key
        
        saved_item = SavedForLater.objects.create(**saved_item_data)
        
        # Remove from cart
        item_name = cart_item.item_name
        cart_item.delete()
        cart.update_totals()
        
        return {
            'message': f'{item_name} saved for later',
            'cart_item_count': cart.item_count,
            'cart_total': str(cart.total_amount),
            'saved_item': {
                'id': saved_item.id,
                'name': item_name
            }
        }
    
    def _verify_cart_access(self, cart):
        """Verify user has access to cart"""
        if self.request.user.is_authenticated:
            return cart.user == self.request.user
        else:
            return cart.session_key == self.request.session.session_key


class MoveToCartView(AjaxView):
    """Move saved item back to cart"""
    
    def handle_ajax_post(self):
        saved_item_id = self.request.POST.get('saved_item_id')
        
        # Get saved item
        saved_item = get_object_or_404(
            SavedForLater,
            tenant=self.tenant,
            id=saved_item_id
        )
        
        # Verify ownership
        if not self._verify_saved_item_access(saved_item):
            raise ValidationError('Access denied')
        
        # Get or create cart
        cart_service = CartService(self.tenant)
        if self.request.user.is_authenticated:
            cart = cart_service.get_or_create_user_cart(self.request.user)
        else:
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
            cart = cart_service.get_or_create_session_cart(session_key)
        
        # Add to cart
        cart_item = cart_service.add_item(
            cart=cart,
            product=saved_item.product,
            variant=saved_item.variant,
            quantity=saved_item.quantity
        )
        
        # Remove from saved items
        item_name = str(saved_item)
        saved_item.delete()
        
        return {
            'message': f'{item_name} moved to cart',
            'cart_item_count': cart.item_count,
            'cart_total': str(cart.total_amount)
        }
    
    def _verify_saved_item_access(self, saved_item):
        """Verify user has access to saved item"""
        if self.request.user.is_authenticated:
            return saved_item.user == self.request.user
        else:
            return saved_item.session_key == self.request.session.session_key


# ============================================================================
# WISHLIST VIEWS
# ============================================================================

class WishlistView(LoginRequiredMixin, EcommerceTemplateView):
    """User's wishlist page"""
    
    template_name = 'ecommerce/wishlist/wishlist.html'
    breadcrumb_title = 'My Wishlist'
    meta_title = 'My Wishlist'
    login_url = '/auth/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get or create default wishlist
        wishlist = self.get_wishlist()
        
        context.update({
            'wishlist': wishlist,
            'wishlist_items': wishlist.get_items() if wishlist else [],
            'user_wishlists': self.get_user_wishlists(),
            'recommended_products': self.get_recommended_products(wishlist),
        })
        
        return context
    
    def get_user_wishlists(self):
        """Get all user wishlists"""
        return Wishlist.objects.filter(
            tenant=self.tenant,
            user=self.request.user
        ).order_by('-is_default', 'name')
    
    def get_recommended_products(self, wishlist):
        """Get recommended products based on wishlist"""
        if not wishlist or not wishlist.items.exists():
            return EcommerceProduct.published.filter(
                tenant=self.tenant,
                is_featured=True
            )[:4]
        
        # Get products from same categories as wishlist items
        categories = set()
        for item in wishlist.items.all():
            if item.product.primary_collection:
                categories.add(item.product.primary_collection.id)
        
        if categories:
            return EcommerceProduct.published.filter(
                tenant=self.tenant,
                primary_collection__id__in=categories
            ).exclude(
                id__in=wishlist.items.values_list('product_id', flat=True)
            )[:4]
        
        return EcommerceProduct.published.filter(
            tenant=self.tenant,
            is_featured=True
        )[:4]


class AddToWishlistView(AjaxView):
    """Add product to wishlist"""
    
    def handle_ajax_post(self):
        if not self.request.user.is_authenticated:
            raise ValidationError('Login required to add to wishlist')
        
        product_id = self.request.POST.get('product_id')
        variant_id = self.request.POST.get('variant_id')
        wishlist_id = self.request.POST.get('wishlist_id')
        
        # Get product
        product = get_object_or_404(
            EcommerceProduct.published,
            tenant=self.tenant,
            id=product_id
        )
        
        # Get variant if specified
        variant = None
        if variant_id:
            variant = get_object_or_404(
                ProductVariant,
                tenant=self.tenant,
                id=variant_id,
                ecommerce_product=product
            )
        
        # Get or create wishlist
        if wishlist_id:
            wishlist = get_object_or_404(
                Wishlist,
                tenant=self.tenant,
                id=wishlist_id,
                user=self.request.user
            )
        else:
            wishlist, created = Wishlist.objects.get_or_create(
                tenant=self.tenant,
                user=self.request.user,
                is_default=True,
                defaults={'name': 'My Wishlist'}
            )
        
        # Check if already in wishlist
        if wishlist.has_product(product, variant):
            return {
                'message': 'Product is already in wishlist',
                'in_wishlist': True,
                'wishlist_count': wishlist.item_count
            }
        
        # Add to wishlist
        wishlist_item, created = wishlist.add_product(product, variant)
        
        item_name = str(wishlist_item)
        
        return {
            'message': f'{item_name} added to wishlist',
            'in_wishlist': True,
            'wishlist_count': wishlist.item_count,
            'item': {
                'id': wishlist_item.id,
                'name': item_name
            }
        }


class RemoveFromWishlistView(AjaxView):
    """Remove product from wishlist"""
    
    def handle_ajax_post(self):
        if not self.request.user.is_authenticated:
            raise ValidationError('Login required')
        
        wishlist_item_id = self.request.POST.get('wishlist_item_id')
        
        wishlist_item = get_object_or_404(
            WishlistItem,
            tenant=self.tenant,
            id=wishlist_item_id,
            wishlist__user=self.request.user
        )
        
        item_name = str(wishlist_item)
        wishlist = wishlist_item.wishlist
        
        # Remove from wishlist
        wishlist_item.delete()
        
        return {
            'message': f'{item_name} removed from wishlist',
            'in_wishlist': False,
            'wishlist_count': wishlist.item_count
        }


class CreateWishlistView(LoginRequiredMixin, AjaxView):
    """Create new wishlist"""
    
    def handle_ajax_post(self):
        name = self.request.POST.get('name', '').strip()
        description = self.request.POST.get('description', '').strip()
        visibility = self.request.POST.get('visibility', 'PRIVATE')
        
        if not name:
            raise ValidationError('Wishlist name is required')
        
        # Check if name already exists
        if Wishlist.objects.filter(
            tenant=self.tenant,
            user=self.request.user,
            name=name
        ).exists():
            raise ValidationError('Wishlist with this name already exists')
        
        # Create wishlist
        wishlist = Wishlist.objects.create(
            tenant=self.tenant,
            user=self.request.user,
            name=name,
            description=description,
            visibility=visibility
        )
        
        return {
            'message': f'Wishlist "{name}" created successfully',
            'wishlist': {
                'id': wishlist.id,
                'name': wishlist.name,
                'item_count': 0
            }
        }


class SharedWishlistView(EcommerceDetailView):
    """View shared wishlist"""
    
    model = Wishlist
    template_name = 'ecommerce/wishlist/shared_wishlist.html'
    context_object_name = 'wishlist'
    slug_field = 'share_token'
    slug_url_kwarg = 'token'
    
    def get_queryset(self):
        return Wishlist.objects.filter(
            tenant=self.tenant,
            visibility__in=['PUBLIC', 'SHARED']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        wishlist = context['wishlist']
        context.update({
            'wishlist_items': wishlist.get_items(),
            'is_owner': (
                self.request.user.is_authenticated and 
                wishlist.user == self.request.user
            ),
            'breadcrumb_title': f'{wishlist.name} (Shared)',
        })
        
        return context


class EstimateShippingView(AjaxView):
    """Estimate shipping costs for cart"""
    
    def handle_ajax_post(self):
        country = self.request.POST.get('country')
        state = self.request.POST.get('state', '')
        zip_code = self.request.POST.get('zip_code', '')
        
        if not country:
            raise ValidationError('Country is required')
        
        cart = self.get_cart()
        if not cart or cart.is_empty:
            raise ValidationError('Cart is empty')
        
        # Calculate shipping rates
        # This would integrate with shipping service
        shipping_rates = [
            {
                'name': 'Standard Shipping',
                'price': '10.00',
                'delivery_time': '3-5 business days',
                'description': 'Standard ground shipping'
            },
            {
                'name': 'Express Shipping',
                'price': '25.00',
                'delivery_time': '1-2 business days',
                'description': 'Fast express delivery'
            }
        ]
        
        # Add free shipping if applicable
        if cart.subtotal >= Decimal('50.00'):
            shipping_rates.insert(0, {
                'name': 'Free Shipping',
                'price': '0.00',
                'delivery_time': '5-7 business days',
                'description': 'Free standard shipping on orders over $50'
            })
        
        return {
            'shipping_rates': shipping_rates,
            'destination': {
                'country': country,
                'state': state,
                'zip_code': zip_code
            }
        }


class CartQuantityUpdateView(AjaxView):
    """Quick quantity update for cart items"""
    
    def handle_ajax_post(self):
        cart_item_id = self.request.POST.get('cart_item_id')
        action = self.request.POST.get('action')  # 'increase' or 'decrease'
        
        cart_item = get_object_or_404(
            CartItem,
            tenant=self.tenant,
            id=cart_item_id
        )
        
        # Verify cart ownership
        cart = cart_item.cart
        if not self._verify_cart_access(cart):
            raise ValidationError('Access denied')
        
        # Calculate new quantity
        if action == 'increase':
            new_quantity = cart_item.quantity + 1
        elif action == 'decrease':
            new_quantity = max(0, cart_item.quantity - 1)
        else:
            raise ValidationError('Invalid action')
        
        cart_service = CartService(self.tenant)
        
        if new_quantity == 0:
            # Remove item
            cart_service.remove_item(cart, cart_item)
            message = f'{cart_item.item_name} removed from cart'
            item_removed = True
        else:
            # Update quantity
            cart_service.update_item_quantity(cart_item, new_quantity)
            message = f'{cart_item.item_name} quantity updated'
            item_removed = False
        
        # Refresh cart
        cart.refresh_from_db()
        
        return {
            'message': message,
            'cart_item_count': cart.item_count,
            'cart_total': str(cart.total_amount),
            'item_removed': item_removed,
            'item': {
                'id': cart_item.id,
                'quantity': new_quantity,
                'line_total': str(cart_item.line_total) if not item_removed else '0.00'
            }
        }
    
    def _verify_cart_access(self, cart):
        """Verify user has access to cart"""
        if self.request.user.is_authenticated:
            return cart.user == self.request.user
        else:
            return cart.session_key == self.request.session.session_key