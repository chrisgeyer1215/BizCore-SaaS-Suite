from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class EcommerceAutoSchema(AutoSchema):
    """Custom schema generator for e-commerce APIs"""
    
    def get_tags(self):
        """Get tags for API endpoints"""
        if hasattr(self.view, 'queryset') and hasattr(self.view.queryset, 'model'):
            model_name = self.view.queryset.model._meta.verbose_name_plural
            return [model_name.title()]
        return ['E-commerce']
    
    def get_operation_id(self):
        """Generate operation ID for API endpoints"""
        if hasattr(self.view, 'action'):
            action = self.view.action
            model = getattr(self.view, 'queryset', None)
            if model and hasattr(model, 'model'):
                model_name = model.model._meta.object_name.lower()
                return f"{action}_{model_name}"
        
        return super().get_operation_id()


# Custom field documentation
@extend_schema_field(serializers.CharField)
class CurrencyField(serializers.DecimalField):
    """Currency amount field with proper formatting"""
    pass


@extend_schema_field(serializers.CharField)
class SlugField(serializers.SlugField):
    """URL-safe slug field"""
    pass


# API Examples
PRODUCT_EXAMPLES = {
    'product_list_response': {
        'summary': 'Product List Response',
        'description': 'Example response for product listing',
        'value': {
            'count': 150,
            'next': 'http://api.example.com/products/?page=2',
            'previous': None,
            'results': [
                {
                    'id': 1,
                    'title': 'Wireless Headphones',
                    'slug': 'wireless-headphones',
                    'regular_price': '99.99',
                    'sale_price': '79.99',
                    'is_on_sale': True,
                    'featured_image': 'https://example.com/headphones.jpg',
                    'average_rating': 4.5,
                    'review_count': 23,
                    'is_in_stock': True
                }
            ]
        }
    },
    'product_detail_response': {
        'summary': 'Product Detail Response',
        'description': 'Example response for product detail',
        'value': {
            'id': 1,
            'title': 'Wireless Headphones',
            'description': 'High-quality wireless headphones with noise cancellation',
            'regular_price': '99.99',
            'sale_price': '79.99',
            'variants': [
                {
                    'id': 1,
                    'title': 'Black',
                    'price': '79.99',
                    'inventory_quantity': 50
                }
            ],
            'collections': [
                {
                    'id': 1,
                    'title': 'Electronics',
                    'slug': 'electronics'
                }
            ]
        }
    }
}

CART_EXAMPLES = {
    'cart_response': {
        'summary': 'Cart Response',
        'description': 'Example cart with items',
        'value': {
            'cart_id': 'uuid-string',
            'items': [
                {
                    'id': 1,
                    'product_title': 'Wireless Headphones',
                    'quantity': 2,
                    'price': '79.99',
                    'line_total': '159.98'
                }
            ],
            'subtotal': '159.98',
            'tax_amount': '16.00',
            'total': '175.98',
            'item_count': 2
        }
    },
    'add_to_cart_request': {
        'summary': 'Add to Cart Request',
        'description': 'Example request to add item to cart',
        'value': {
            'product': 1,
            'variant': 1,
            'quantity': 2,
            'custom_attributes': {
                'gift_wrap': True,
                'message': 'Happy Birthday!'
            }
        }
    }
}

ORDER_EXAMPLES = {
    'checkout_request': {
        'summary': 'Checkout Request',
        'description': 'Example checkout request',
        'value': {
            'billing_address': {
                'first_name': 'John',
                'last_name': 'Doe',
                'address1': '123 Main St',
                'city': 'New York',
                'state': 'NY',
                'postal_code': '10001',
                'country': 'US'
            },
            'shipping_address': {
                'first_name': 'John',
                'last_name': 'Doe',
                'address1': '123 Main St',
                'city': 'New York',
                'state': 'NY',
                'postal_code': '10001',
                'country': 'US'
            },
            'shipping_method_id': 1,
            'payment_method': 'CREDIT_CARD',
            'customer_notes': 'Please handle with care'
        }
    },
    'order_response': {
        'summary': 'Order Response',
        'description': 'Example order response',
        'value': {
            'order_number': 'ORD-2024-001234',
            'status': 'CONFIRMED',
            'total_amount': '175.98',
            'items': [
                {
                    'title': 'Wireless Headphones',
                    'quantity': 2,
                    'price': '79.99'
                }
            ]
        }
    }
}

# OpenAPI Schema Customizations
OPENAPI_TAGS = [
    {
        'name': 'Products',
        'description': 'Product catalog management'
    },
    {
        'name': 'Collections',
        'description': 'Product collections and categories'
    },
    {
        'name': 'Cart',
        'description': 'Shopping cart operations'
    },
    {
        'name': 'Orders',
        'description': 'Order management and processing'
    },
    {
        'name': 'Coupons',
        'description': 'Discount coupons and promotions'
    },
    {
        'name': 'Reviews',
        'description': 'Product reviews and ratings'
    },
    {
        'name': 'Shipping',
        'description': 'Shipping zones and methods'
    }
]
