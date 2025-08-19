from rest_framework import status
from rest_framework.exceptions import APIException


class EcommerceBaseException(APIException):
    """Base exception for e-commerce module"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An error occurred in the e-commerce system'
    default_code = 'ecommerce_error'


class ProductNotAvailableException(EcommerceBaseException):
    """Exception raised when product is not available"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Product is not available for purchase'
    default_code = 'product_not_available'


class InsufficientStockException(EcommerceBaseException):
    """Exception raised when there's insufficient stock"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Insufficient stock available'
    default_code = 'insufficient_stock'
    
    def __init__(self, available_stock=0, requested_quantity=0):
        self.available_stock = available_stock
        self.requested_quantity = requested_quantity
        detail = f'Only {available_stock} items available, requested {requested_quantity}'
        super().__init__(detail)


class InvalidCouponException(EcommerceBaseException):
    """Exception raised when coupon is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid or expired coupon code'
    default_code = 'invalid_coupon'


class PaymentProcessingException(EcommerceBaseException):
    """Exception raised during payment processing"""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment processing failed'
    default_code = 'payment_failed'


class CartNotFoundException(EcommerceBaseException):
    """Exception raised when cart is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Shopping cart not found'
    default_code = 'cart_not_found'


class OrderNotFoundException(EcommerceBaseException):
    """Exception raised when order is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Order not found'
    default_code = 'order_not_found'


class InvalidShippingAddressException(EcommerceBaseException):
    """Exception raised for invalid shipping address"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid shipping address provided'
    default_code = 'invalid_shipping_address'


class CheckoutValidationException(EcommerceBaseException):
    """Exception raised during checkout validation"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Checkout validation failed'
    default_code = 'checkout_validation_failed'


class PriceChangedException(EcommerceBaseException):
    """Exception raised when product price has changed"""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Product price has changed since adding to cart'
    default_code = 'price_changed'


class ShippingNotAvailableException(EcommerceBaseException):
    """Exception raised when shipping is not available"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Shipping not available for this location'
    default_code = 'shipping_not_available'


class ReturnWindowExpiredException(EcommerceBaseException):
    """Exception raised when return window has expired"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Return window has expired for this order'
    default_code = 'return_window_expired'


class RefundProcessingException(EcommerceBaseException):
    """Exception raised during refund processing"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Refund processing failed'
    default_code = 'refund_failed'
