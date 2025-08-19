from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.core.models import Tenant
from apps.crm.models import Customer
from apps.inventory.models import Product, Warehouse
from .models import (
    EcommerceSettings, Collection, EcommerceProduct, ProductVariant,
    Cart, CartItem, Order, OrderItem, Coupon, ProductReview,
    ShippingZone, ShippingMethod, PaymentTransaction
)
from .services import ProductService, CartService, OrderService, PaymentService

User = get_user_model()


class EcommerceTestCase(TestCase):
    """Base test case for e-commerce tests"""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test-tenant')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            name='Test Customer',
            email='test@example.com'
        )
        
        # Create warehouse
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant,
            name='Test Warehouse',
            is_sellable=True
        )
        
        # Create inventory product
        self.inventory_product = Product.objects.create(
            tenant=self.tenant,
            name='Test Product',
            sku='TEST-001',
            unit_price=Decimal('10.00')
        )
        
        # Create e-commerce product
        self.product = EcommerceProduct.objects.create(
            tenant=self.tenant,
            inventory_product=self.inventory_product,
            title='Test Product',
            slug='test-product',
            url_handle='test-product',
            regular_price=Decimal('15.00'),
            status='ACTIVE',
            is_published=True,
            stock_quantity=100
        )
        
        # Create collection
        self.collection = Collection.objects.create(
            tenant=self.tenant,
            title='Test Collection',
            slug='test-collection'
        )


class ProductModelTests(EcommerceTestCase):
    """Test product model functionality"""
    
    def test_current_price_regular(self):
        """Test current price returns regular price when no sale"""
        self.assertEqual(self.product.current_price, Decimal('15.00'))
    
    def test_current_price_on_sale(self):
        """Test current price returns sale price when on sale"""
        self.product.sale_price = Decimal('12.00')
        self.product.sale_price_start = timezone.now() - timezone.timedelta(days=1)
        self.product.sale_price_end = timezone.now() + timezone.timedelta(days=1)
        self.product.save()
        
        self.assertEqual(self.product.current_price, Decimal('12.00'))
    
    def test_is_on_sale_true(self):
        """Test is_on_sale returns True when product is on sale"""
        self.product.sale_price = Decimal('12.00')
        self.product.sale_price_start = timezone.now() - timezone.timedelta(days=1)
        self.product.sale_price_end = timezone.now() + timezone.timedelta(days=1)
        self.product.save()
        
        self.assertTrue(self.product.is_on_sale)
    
    def test_is_on_sale_false(self):
        """Test is_on_sale returns False when not on sale"""
        self.assertFalse(self.product.is_on_sale)
    
    def test_discount_percentage(self):
        """Test discount percentage calculation"""
        self.product.sale_price = Decimal('12.00')
        self.product.sale_price_start = timezone.now() - timezone.timedelta(days=1)
        self.product.sale_price_end = timezone.now() + timezone.timedelta(days=1)
        self.product.save()
        
        expected_discount = round(((15.00 - 12.00) / 15.00) * 100, 2)
        self.assertEqual(self.product.discount_percentage, expected_discount)
    
    def test_is_in_stock_with_tracking(self):
        """Test stock status with quantity tracking"""
        self.product.track_quantity = True
        self.product.stock_quantity = 10
        self.product.save()
        
        self.assertTrue(self.product.is_in_stock)
    
    def test_is_in_stock_without_tracking(self):
        """Test stock status without quantity tracking"""
        self.product.track_quantity = False
        self.product.stock_quantity = 0
        self.product.save()
        
        self.assertTrue(self.product.is_in_stock)
    
    def test_is_in_stock_with_backorders(self):
        """Test stock status with backorders allowed"""
        self.product.track_quantity = True
        self.product.stock_quantity = 0
        self.product.continue_selling_when_out_of_stock = True
        self.product.save()
        
        self.assertTrue(self.product.is_in_stock)


class CartModelTests(EcommerceTestCase):
    """Test cart model functionality"""
    
    def setUp(self):
        super().setUp()
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            currency='USD'
        )
    
    def test_item_count(self):
        """Test cart item count calculation"""
        CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=2,
            price=self.product.current_price
        )
        
        CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=3,
            price=self.product.current_price
        )
        
        self.assertEqual(self.cart.item_count, 5)
    
    def test_unique_item_count(self):
        """Test cart unique item count"""
        CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=2,
            price=self.product.current_price
        )
        
        self.assertEqual(self.cart.unique_item_count, 1)


class CartItemModelTests(EcommerceTestCase):
    """Test cart item model functionality"""
    
    def setUp(self):
        super().setUp()
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer
        )
        self.cart_item = CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=3,
            price=Decimal('15.00')
        )
    
    def test_line_total(self):
        """Test cart item line total calculation"""
        expected_total = Decimal('45.00')  # 3 * 15.00
        self.assertEqual(self.cart_item.line_total, expected_total)
    
    def test_item_name_without_variant(self):
        """Test item name without variant"""
        self.assertEqual(self.cart_item.item_name, self.product.title)
    
    def test_item_name_with_variant(self):
        """Test item name with variant"""
        variant = ProductVariant.objects.create(
            tenant=self.tenant,
            ecommerce_product=self.product,
            title='Large',
            sku='TEST-001-L'
        )
        self.cart_item.variant = variant
        self.cart_item.save()
        
        expected_name = f"{self.product.title} - Large"
        self.assertEqual(self.cart_item.item_name, expected_name)


class CouponModelTests(EcommerceTestCase):
    """Test coupon model functionality"""
    
    def setUp(self):
        super().setUp()
        self.coupon = Coupon.objects.create(
            tenant=self.tenant,
            code='TEST10',
            name='Test Coupon',
            coupon_type='PERCENTAGE',
            discount_value=Decimal('10'),
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            subtotal=Decimal('100.00')
        )
    
    def test_is_valid_active_coupon(self):
        """Test valid active coupon"""
        is_valid, message = self.coupon.is_valid()
        self.assertTrue(is_valid)
        self.assertEqual(message, "Valid")
    
    def test_is_valid_inactive_coupon(self):
        """Test inactive coupon"""
        self.coupon.is_active = False
        self.coupon.save()
        
        is_valid, message = self.coupon.is_valid()
        self.assertFalse(is_valid)
        self.assertEqual(message, "Coupon is inactive")
    
    def test_is_valid_expired_coupon(self):
        """Test expired coupon"""
        self.coupon.valid_until = timezone.now() - timezone.timedelta(days=1)
        self.coupon.save()
        
        is_valid, message = self.coupon.is_valid()
        self.assertFalse(is_valid)
        self.assertEqual(message, "Coupon has expired")
    
    def test_can_apply_to_cart_valid(self):
        """Test coupon can be applied to valid cart"""
        can_apply, message = self.coupon.can_apply_to_cart(self.cart)
        self.assertTrue(can_apply)
    
    def test_can_apply_to_cart_minimum_amount(self):
        """Test coupon with minimum amount requirement"""
        self.coupon.minimum_order_amount = Decimal('150.00')
        self.coupon.save()
        
        can_apply, message = self.coupon.can_apply_to_cart(self.cart)
        self.assertFalse(can_apply)
        self.assertIn('Minimum purchase amount', message)
    
    def test_calculate_discount_amount_percentage(self):
        """Test percentage discount calculation"""
        discount = self.coupon.calculate_discount_amount(self.cart)
        expected_discount = Decimal('10.00')  # 10% of 100
        self.assertEqual(discount, expected_discount)
    
    def test_calculate_discount_amount_fixed(self):
        """Test fixed amount discount calculation"""
        self.coupon.coupon_type = 'FIXED_AMOUNT'
        self.coupon.discount_value = Decimal('15.00')
        self.coupon.save()
        
        discount = self.coupon.calculate_discount_amount(self.cart)
        expected_discount = Decimal('15.00')
        self.assertEqual(discount, expected_discount)


class ProductServiceTests(EcommerceTestCase):
    """Test product service functionality"""
    
    def test_check_stock_availability_in_stock(self):
        """Test stock availability check for in-stock item"""
        self.product.track_quantity = True
        self.product.stock_quantity = 10
        self.product.save()
        
        is_available, message = ProductService.check_stock_availability(
            self.product, 5
        )
        
        self.assertTrue(is_available)
        self.assertEqual(message, "In stock")
    
    def test_check_stock_availability_out_of_stock(self):
        """Test stock availability check for out-of-stock item"""
        self.product.track_quantity = True
        self.product.stock_quantity = 5
        self.product.continue_selling_when_out_of_stock = False
        self.product.save()
        
        is_available, message = ProductService.check_stock_availability(
            self.product, 10
        )
        
        self.assertFalse(is_available)
        self.assertIn("Only 5 items available", message)
    
    def test_check_stock_availability_backorder(self):
        """Test stock availability with backorders allowed"""
        self.product.track_quantity = True
        self.product.stock_quantity = 0
        self.product.continue_selling_when_out_of_stock = True
        self.product.save()
        
        is_available, message = ProductService.check_stock_availability(
            self.product, 5
        )
        
        self.assertTrue(is_available)
        self.assertEqual(message, "Backorder allowed")


class CartServiceTests(EcommerceTestCase):
    """Test cart service functionality"""
    
    def setUp(self):
        super().setUp()
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer
        )
    
    def test_add_to_cart_new_item(self):
        """Test adding new item to cart"""
        cart_item, created = CartService.add_to_cart(
            self.cart, self.product, quantity=2
        )
        
        self.assertTrue(created)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.price, self.product.current_price)
    
    def test_add_to_cart_existing_item(self):
        """Test adding to existing cart item"""
        # Add item first time
        CartService.add_to_cart(self.cart, self.product, quantity=2)
        
        # Add same item again
        cart_item, created = CartService.add_to_cart(
            self.cart, self.product, quantity=3
        )
        
        self.assertFalse(created)
        self.assertEqual(cart_item.quantity, 5)  # 2 + 3
    
    def test_remove_from_cart(self):
        """Test removing item from cart"""
        cart_item = CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=2,
            price=self.product.current_price
        )
        
        success = CartService.remove_from_cart(self.cart, cart_item.id)
        
        self.assertTrue(success)
        self.assertFalse(
            CartItem.objects.filter(id=cart_item.id).exists()
        )
    
    def test_apply_coupon_success(self):
        """Test successful coupon application"""
        coupon = Coupon.objects.create(
            tenant=self.tenant,
            code='TEST10',
            name='Test Coupon',
            coupon_type='PERCENTAGE',
            discount_value=Decimal('10'),
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )
        
        success, message = CartService.apply_coupon(self.cart, 'TEST10')
        
        self.assertTrue(success)
        self.assertIn('TEST10', self.cart.discount_codes)
    
    def test_apply_coupon_invalid_code(self):
        """Test applying invalid coupon code"""
        success, message = CartService.apply_coupon(self.cart, 'INVALID')
        
        self.assertFalse(success)
        self.assertEqual(message, "Invalid coupon code")


class OrderServiceTests(EcommerceTestCase):
    """Test order service functionality"""
    
    def setUp(self):
        super().setUp()
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            subtotal=Decimal('30.00'),
            total=Decimal('30.00')
        )
        
        CartItem.objects.create(
            tenant=self.tenant,
            cart=self.cart,
            product=self.product,
            quantity=2,
            price=Decimal('15.00')
        )
        
        self.customer_info = {
            'email': 'test@example.com',
            'phone': '1234567890',
            'first_name': 'John',
            'last_name': 'Doe',
            'address1': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postal_code': '12345',
            'country': 'US'
        }
        
        self.shipping_info = self.customer_info.copy()
        self.payment_info = {
            'method': 'CREDIT_CARD',
            'gateway': 'stripe'
        }
    
    def test_create_order_from_cart(self):
        """Test creating order from cart"""
        order = OrderService.create_order_from_cart(
            self.cart, self.customer_info, self.shipping_info, self.payment_info
        )
        
        self.assertIsInstance(order, Order)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.total_amount, self.cart.total)
        self.assertEqual(order.items.count(), 1)
        
        # Check cart status
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, 'completed')
    
    def test_update_order_status(self):
        """Test updating order status"""
        order = Order.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            customer_email='test@example.com',
            status='PENDING',
            subtotal=Decimal('30.00'),
            total_amount=Decimal('30.00'),
            billing_address=self.customer_info,
            shipping_address=self.shipping_info,
            payment_method='CREDIT_CARD'
        )
        
        OrderService.update_order_status(order, 'CONFIRMED')
        
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')
        self.assertIsNotNone(order.confirmed_at)


class PaymentServiceTests(EcommerceTestCase):
    """Test payment service functionality"""
    
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            customer_email='test@example.com',
            status='PENDING',
            payment_status='PENDING',
            subtotal=Decimal('30.00'),
            total_amount=Decimal('30.00'),
            billing_address={},
            shipping_address={},
            payment_method='CREDIT_CARD'
        )
    
    def test_mark_order_as_paid(self):
        """Test marking order as paid"""
        payment_data = {
            'payment_method': 'stripe',
            'transaction_id': 'test_transaction_123',
            'amount': Decimal('30.00')
        }
        
        PaymentService.mark_order_as_paid(self.order, payment_data)
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'PAID')
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertIsNotNone(self.order.payment_date)
    
    def test_process_refund(self):
        """Test processing refund"""
        # Mark order as paid first
        self.order.payment_status = 'PAID'
        self.order.save()
        
        refund_transaction = PaymentService.process_refund(
            self.order, Decimal('15.00'), 'Customer request'
        )
        
        self.assertIsInstance(refund_transaction, PaymentTransaction)
        self.assertEqual(refund_transaction.transaction_type, 'REFUND')
        self.assertEqual(refund_transaction.amount, Decimal('15.00'))
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'PARTIAL')


class ShippingTests(EcommerceTestCase):
    """Test shipping functionality"""
    
    def setUp(self):
        super().setUp()
        self.shipping_zone = ShippingZone.objects.create(
            tenant=self.tenant,
            name='US Zone',
            countries=['US'],
            is_active=True
        )
        
        self.shipping_method = ShippingMethod.objects.create(
            tenant=self.tenant,
            name='Standard Shipping',
            shipping_zone=self.shipping_zone,
            rate_type='FLAT_RATE',
            base_rate=Decimal('9.99')
        )
        
        self.cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            subtotal=Decimal('50.00')
        )
    
    def test_calculate_shipping_rate_flat_rate(self):
        """Test flat rate shipping calculation"""
        rate = self.shipping_method.calculate_rate(
            order_total=Decimal('50.00'),
            weight=Decimal('2.0')
        )
        
        self.assertEqual(rate, Decimal('9.99'))
    
    def test_calculate_shipping_rate_minimum_order(self):
        """Test shipping rate with minimum order requirement"""
        self.shipping_method.minimum_order_amount = Decimal('100.00')
        self.shipping_method.save()
        
        rate = self.shipping_method.calculate_rate(
            order_total=Decimal('50.00'),
            weight=Decimal('2.0')
        )
        
        self.assertIsNone(rate)  # Below minimum
    
    def test_calculate_shipping_rates_service(self):
        """Test shipping rates calculation service"""
        shipping_address = {
            'country': 'US',
            'state': 'CA'
        }
        
        rates = OrderService.calculate_shipping_rates(self.cart, shipping_address)
        
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]['method_id'], self.shipping_method.id)
        self.assertEqual(rates[0]['rate'], Decimal('9.99'))


class IntegrationTests(TransactionTestCase):
    """Integration tests for e-commerce functionality"""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test-tenant')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            name='Test Customer',
            email='test@example.com'
        )
        
        # Create inventory product
        self.inventory_product = Product.objects.create(
            tenant=self.tenant,
            name='Test Product',
            sku='TEST-001',
            unit_price=Decimal('10.00')
        )
        
        # Create e-commerce product
        self.product = EcommerceProduct.objects.create(
            tenant=self.tenant,
            inventory_product=self.inventory_product,
            title='Test Product',
            slug='test-product',
            url_handle='test-product',
            regular_price=Decimal('15.00'),
            status='ACTIVE',
            is_published=True,
            stock_quantity=100
        )
    
    def test_complete_purchase_flow(self):
        """Test complete purchase flow from cart to order"""
        # Create cart and add items
        cart = Cart.objects.create(
            tenant=self.tenant,
            customer=self.customer
        )
        
        cart_item, created = CartService.add_to_cart(
            cart, self.product, quantity=2
        )
        
        self.assertTrue(created)
        
        # Apply coupon
        coupon = Coupon.objects.create(
            tenant=self.tenant,
            code='TEST10',
            name='Test Coupon',
            coupon_type='PERCENTAGE',
            discount_value=Decimal('10'),
            valid_from=timezone.now(),
            is_active=True
        )
        
        success, message = CartService.apply_coupon(cart, 'TEST10')
        self.assertTrue(success)
        
        # Calculate totals
        CartService.calculate_totals(cart)
        
        # Create order
        customer_info = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'address1': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postal_code': '12345',
            'country': 'US'
        }
        
        order = OrderService.create_order_from_cart(
            cart, customer_info, customer_info, {'method': 'CREDIT_CARD'}
        )
        
        # Verify order creation
        self.assertIsInstance(order, Order)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.customer, self.customer)
        
        # Verify cart status
        cart.refresh_from_db()
        self.assertEqual(cart.status, 'completed')
        
        # Mark as paid
        PaymentService.mark_order_as_paid(order, {
            'payment_method': 'stripe',
            'transaction_id': 'test_123',
            'amount': order.total_amount
        })
        
        # Verify payment status
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'PAID')
        self.assertEqual(order.status, 'CONFIRMED')
