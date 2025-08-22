"""
Cart service for e-commerce functionality
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from typing import Optional, Dict, List, Union, Tuple
import logging

from .base import BaseEcommerceService, ServiceError, ValidationError as ServiceValidationError
from ..models import Cart, CartItem, EcommerceProduct, ProductVariant, Wishlist, WishlistItem


class CartService(BaseEcommerceService):
    """Service for managing shopping cart operations"""
    
    def __init__(self, tenant=None):
        super().__init__(tenant)
        self.logger = logging.getLogger(__name__)
    
    def get_or_create_user_cart(self, user) -> Cart:
        """Get or create cart for authenticated user"""
        try:
            cart, created = Cart.objects.get_or_create(
                tenant=self.tenant,
                user=user,
                defaults={
                    'status': 'active',
                    'created_at': timezone.now(),
                    'updated_at': timezone.now(),
                }
            )
            
            if created:
                self.log_info(f"Created new cart for user {user.username}")
            else:
                # Update cart timestamp
                cart.updated_at = timezone.now()
                cart.save(update_fields=['updated_at'])
            
            return cart
            
        except Exception as e:
            self.log_error(f"Error getting/creating user cart for {user.username}", e)
            raise ServiceError(f"Failed to get user cart: {str(e)}")
    
    def get_or_create_session_cart(self, session_key: str) -> Cart:
        """Get or create cart for anonymous user session"""
        try:
            cart, created = Cart.objects.get_or_create(
                tenant=self.tenant,
                session_key=session_key,
                defaults={
                    'status': 'active',
                    'created_at': timezone.now(),
                    'updated_at': timezone.now(),
                }
            )
            
            if created:
                self.log_info(f"Created new session cart for session {session_key}")
            else:
                # Update cart timestamp
                cart.updated_at = timezone.now()
                cart.save(update_fields=['updated_at'])
            
            return cart
            
        except Exception as e:
            self.log_error(f"Error getting/creating session cart for {session_key}", e)
            raise ServiceError(f"Failed to get session cart: {str(e)}")
    
    def add_to_cart(self, cart: Cart, product_id: int, quantity: int = 1, 
                    variant_id: Optional[int] = None, custom_attributes: Optional[Dict] = None) -> CartItem:
        """Add product to cart"""
        try:
            with transaction.atomic():
                # Validate product
                product = self._get_product(product_id)
                variant = self._get_variant(variant_id) if variant_id else None
                
                # Validate quantity
                self._validate_quantity(quantity, product, variant)
                
                # Check if item already exists
                existing_item = self._get_existing_cart_item(cart, product, variant)
                
                if existing_item:
                    # Update existing item
                    new_quantity = existing_item.quantity + quantity
                    self._validate_quantity(new_quantity, product, variant)
                    
                    existing_item.quantity = new_quantity
                    if custom_attributes:
                        existing_item.custom_attributes = custom_attributes
                    existing_item.updated_at = timezone.now()
                    existing_item.save()
                    
                    self.log_info(f"Updated cart item quantity to {new_quantity}")
                    return existing_item
                else:
                    # Create new cart item
                    cart_item = CartItem.objects.create(
                        cart=cart,
                        product=product,
                        variant=variant,
                        quantity=quantity,
                        custom_attributes=custom_attributes or {},
                        price=variant.price if variant else product.price,
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                    
                    # Update cart totals
                    self._update_cart_totals(cart)
                    
                    self.log_info(f"Added {quantity}x {product.title} to cart")
                    return cart_item
                    
        except Exception as e:
            self.log_error(f"Error adding product {product_id} to cart", e)
            raise ServiceError(f"Failed to add product to cart: {str(e)}")
    
    def update_cart_item(self, cart_item_id: int, quantity: int, 
                        custom_attributes: Optional[Dict] = None) -> CartItem:
        """Update cart item quantity and attributes"""
        try:
            with transaction.atomic():
                cart_item = self._get_cart_item(cart_item_id)
                
                # Validate quantity
                self._validate_quantity(quantity, cart_item.product, cart_item.variant)
                
                # Update item
                cart_item.quantity = quantity
                if custom_attributes is not None:
                    cart_item.custom_attributes = custom_attributes
                cart_item.updated_at = timezone.now()
                cart_item.save()
                
                # Update cart totals
                self._update_cart_totals(cart_item.cart)
                
                self.log_info(f"Updated cart item {cart_item_id} quantity to {quantity}")
                return cart_item
                
        except Exception as e:
            self.log_error(f"Error updating cart item {cart_item_id}", e)
            raise ServiceError(f"Failed to update cart item: {str(e)}")
    
    def remove_from_cart(self, cart_item_id: int) -> bool:
        """Remove item from cart"""
        try:
            with transaction.atomic():
                cart_item = self._get_cart_item(cart_item_id)
                cart = cart_item.cart
                
                # Delete item
                cart_item.delete()
                
                # Update cart totals
                self._update_cart_totals(cart)
                
                self.log_info(f"Removed cart item {cart_item_id}")
                return True
                
        except Exception as e:
            self.log_error(f"Error removing cart item {cart_item_id}", e)
            raise ServiceError(f"Failed to remove cart item: {str(e)}")
    
    def clear_cart(self, cart: Cart) -> bool:
        """Clear all items from cart"""
        try:
            with transaction.atomic():
                # Delete all cart items
                cart.items.all().delete()
                
                # Reset cart totals
                cart.subtotal = Decimal('0.00')
                cart.tax_amount = Decimal('0.00')
                cart.shipping_amount = Decimal('0.00')
                cart.total_amount = Decimal('0.00')
                cart.updated_at = timezone.now()
                cart.save()
                
                self.log_info(f"Cleared cart {cart.id}")
                return True
                
        except Exception as e:
            self.log_error(f"Error clearing cart {cart.id}", e)
            raise ServiceError(f"Failed to clear cart: {str(e)}")
    
    def move_to_wishlist(self, cart_item_id: int, wishlist_id: Optional[int] = None) -> WishlistItem:
        """Move cart item to wishlist"""
        try:
            with transaction.atomic():
                cart_item = self._get_cart_item(cart_item_id)
                
                # Get or create wishlist
                if wishlist_id:
                    wishlist = Wishlist.objects.get(
                        id=wishlist_id,
                        tenant=self.tenant,
                        user=cart_item.cart.user
                    )
                else:
                    wishlist = self._get_or_create_default_wishlist(cart_item.cart.user)
                
                # Check if item already in wishlist
                existing_wishlist_item = WishlistItem.objects.filter(
                    wishlist=wishlist,
                    product=cart_item.product,
                    variant=cart_item.variant
                ).first()
                
                if existing_wishlist_item:
                    # Update quantity
                    existing_wishlist_item.quantity += cart_item.quantity
                    existing_wishlist_item.updated_at = timezone.now()
                    existing_wishlist_item.save()
                else:
                    # Create new wishlist item
                    existing_wishlist_item = WishlistItem.objects.create(
                        wishlist=wishlist,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        quantity=cart_item.quantity,
                        custom_attributes=cart_item.custom_attributes,
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                
                # Remove from cart
                self.remove_from_cart(cart_item_id)
                
                self.log_info(f"Moved cart item {cart_item_id} to wishlist")
                return existing_wishlist_item
                
        except Exception as e:
            self.log_error(f"Error moving cart item {cart_item_id} to wishlist", e)
            raise ServiceError(f"Failed to move item to wishlist: {str(e)}")
    
    def apply_coupon(self, cart: Cart, coupon_code: str) -> Dict:
        """Apply coupon code to cart"""
        try:
            # TODO: Implement coupon logic
            # This would involve:
            # 1. Validating coupon code
            # 2. Checking coupon restrictions
            # 3. Applying discount
            # 4. Updating cart totals
            
            self.log_info(f"Applied coupon {coupon_code} to cart {cart.id}")
            return {
                'success': True,
                'message': f'Coupon {coupon_code} applied successfully',
                'discount_amount': Decimal('0.00')  # Placeholder
            }
            
        except Exception as e:
            self.log_error(f"Error applying coupon {coupon_code} to cart {cart.id}", e)
            raise ServiceError(f"Failed to apply coupon: {str(e)}")
    
    def remove_coupon(self, cart: Cart) -> bool:
        """Remove coupon from cart"""
        try:
            # TODO: Implement coupon removal logic
            cart.coupon_code = None
            cart.updated_at = timezone.now()
            cart.save()
            
            # Recalculate totals
            self._update_cart_totals(cart)
            
            self.log_info(f"Removed coupon from cart {cart.id}")
            return True
            
        except Exception as e:
            self.log_error(f"Error removing coupon from cart {cart.id}", e)
            raise ServiceError(f"Failed to remove coupon: {str(e)}")
    
    def get_cart_summary(self, cart: Cart) -> Dict:
        """Get cart summary information"""
        try:
            items = cart.items.select_related('product', 'variant').all()
            
            summary = {
                'item_count': sum(item.quantity for item in items),
                'unique_items': items.count(),
                'subtotal': cart.subtotal,
                'tax_amount': cart.tax_amount,
                'shipping_amount': cart.shipping_amount,
                'total_amount': cart.total_amount,
                'currency': cart.currency or 'USD',
                'items': []
            }
            
            for item in items:
                summary['items'].append({
                    'id': item.id,
                    'product_id': item.product.id,
                    'product_title': item.product.title,
                    'variant_title': item.variant.title if item.variant else None,
                    'quantity': item.quantity,
                    'price': item.price,
                    'total': item.price * item.quantity,
                    'image': item.product.featured_image.url if item.product.featured_image else None,
                })
            
            return summary
            
        except Exception as e:
            self.log_error(f"Error getting cart summary for cart {cart.id}", e)
            raise ServiceError(f"Failed to get cart summary: {str(e)}")
    
    def merge_carts(self, session_cart: Cart, user_cart: Cart) -> Cart:
        """Merge session cart into user cart"""
        try:
            with transaction.atomic():
                # Move all items from session cart to user cart
                for session_item in session_cart.items.all():
                    # Check if item already exists in user cart
                    existing_item = self._get_existing_cart_item(
                        user_cart, 
                        session_item.product, 
                        session_item.variant
                    )
                    
                    if existing_item:
                        # Update quantity
                        existing_item.quantity += session_item.quantity
                        existing_item.updated_at = timezone.now()
                        existing_item.save()
                    else:
                        # Move item to user cart
                        session_item.cart = user_cart
                        session_item.save()
                
                # Update user cart totals
                self._update_cart_totals(user_cart)
                
                # Delete session cart
                session_cart.delete()
                
                self.log_info(f"Merged session cart into user cart {user_cart.id}")
                return user_cart
                
        except Exception as e:
            self.log_error(f"Error merging carts", e)
            raise ServiceError(f"Failed to merge carts: {str(e)}")
    
    def _get_product(self, product_id: int) -> EcommerceProduct:
        """Get product with validation"""
        try:
            product = EcommerceProduct.objects.get(
                id=product_id,
                tenant=self.tenant,
                is_active=True,
                is_published=True
            )
            return product
        except EcommerceProduct.DoesNotExist:
            raise ServiceValidationError(f"Product {product_id} not found or not available")
    
    def _get_variant(self, variant_id: int) -> Optional[ProductVariant]:
        """Get product variant with validation"""
        if not variant_id:
            return None
        
        try:
            variant = ProductVariant.objects.get(
                id=variant_id,
                product__tenant=self.tenant,
                is_active=True
            )
            return variant
        except ProductVariant.DoesNotExist:
            raise ServiceValidationError(f"Product variant {variant_id} not found or not available")
    
    def _validate_quantity(self, quantity: int, product: EcommerceProduct, variant: Optional[ProductVariant] = None):
        """Validate quantity for product/variant"""
        if quantity <= 0:
            raise ServiceValidationError("Quantity must be greater than 0")
        
        if quantity > 999:
            raise ServiceValidationError("Quantity cannot exceed 999")
        
        # Check inventory if tracking is enabled
        if variant and variant.track_quantity:
            if quantity > variant.stock_quantity:
                raise ServiceValidationError(f"Insufficient stock. Only {variant.stock_quantity} available.")
        elif product.track_quantity:
            if quantity > product.stock_quantity:
                raise ServiceValidationError(f"Insufficient stock. Only {product.stock_quantity} available.")
    
    def _get_existing_cart_item(self, cart: Cart, product: EcommerceProduct, 
                                variant: Optional[ProductVariant] = None) -> Optional[CartItem]:
        """Get existing cart item for product/variant combination"""
        filters = {
            'cart': cart,
            'product': product,
        }
        
        if variant:
            filters['variant'] = variant
        else:
            filters['variant__isnull'] = True
        
        return CartItem.objects.filter(**filters).first()
    
    def _get_cart_item(self, cart_item_id: int) -> CartItem:
        """Get cart item with validation"""
        try:
            cart_item = CartItem.objects.select_related('cart', 'product', 'variant').get(
                id=cart_item_id,
                cart__tenant=self.tenant
            )
            return cart_item
        except CartItem.DoesNotExist:
            raise ServiceValidationError(f"Cart item {cart_item_id} not found")
    
    def _update_cart_totals(self, cart: Cart):
        """Update cart totals based on items"""
        try:
            items = cart.items.all()
            
            # Calculate subtotal
            subtotal = sum(item.price * item.quantity for item in items)
            
            # TODO: Calculate tax based on tax settings
            tax_amount = Decimal('0.00')
            
            # TODO: Calculate shipping based on shipping settings
            shipping_amount = Decimal('0.00')
            
            # Calculate total
            total_amount = subtotal + tax_amount + shipping_amount
            
            # Update cart
            cart.subtotal = subtotal
            cart.tax_amount = tax_amount
            cart.shipping_amount = shipping_amount
            cart.total_amount = total_amount
            cart.updated_at = timezone.now()
            cart.save()
            
        except Exception as e:
            self.log_error(f"Error updating cart totals for cart {cart.id}", e)
            raise ServiceError(f"Failed to update cart totals: {str(e)}")
    
    def _get_or_create_default_wishlist(self, user) -> Wishlist:
        """Get or create default wishlist for user"""
        try:
            wishlist, created = Wishlist.objects.get_or_create(
                tenant=self.tenant,
                user=user,
                is_default=True,
                defaults={
                    'name': 'My Wishlist',
                    'is_active': True,
                    'created_at': timezone.now(),
                    'updated_at': timezone.now(),
                }
            )
            return wishlist
        except Exception as e:
            self.log_error(f"Error getting/creating default wishlist for user {user.username}", e)
            raise ServiceError(f"Failed to get/create wishlist: {str(e)}")
    
    def cleanup_expired_carts(self, days_old: int = 30) -> int:
        """Clean up expired carts"""
        try:
            cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
            
            expired_carts = Cart.objects.filter(
                tenant=self.tenant,
                updated_at__lt=cutoff_date,
                status='active'
            )
            
            count = expired_carts.count()
            expired_carts.delete()
            
            self.log_info(f"Cleaned up {count} expired carts")
            return count
            
        except Exception as e:
            self.log_error("Error cleaning up expired carts", e)
            raise ServiceError(f"Failed to cleanup expired carts: {str(e)}")
