import uuid
import hashlib
from decimal import Decimal
from django.utils.text import slugify
from django.core.files.storage import default_storage
from django.conf import settings
import qrcode
from io import BytesIO


def generate_order_number(prefix='ORD'):
    """Generate unique order number"""
    import time
    timestamp = str(int(time.time()))
    unique_id = str(uuid.uuid4().hex)[:8].upper()
    return f"{prefix}-{timestamp}-{unique_id}"


def generate_sku(product_name, variant_attributes=None):
    """Generate SKU from product name and variant attributes"""
    base_sku = slugify(product_name).replace('-', '').upper()[:8]
    
    if variant_attributes:
        variant_part = ''.join([
            str(v)[:3].upper() for v in variant_attributes.values()
        ])
        return f"{base_sku}-{variant_part}"
    
    return base_sku


def calculate_discount_amount(original_price, discount_type, discount_value):
    """Calculate discount amount based on type and value"""
    if discount_type == 'PERCENTAGE':
        return original_price * (discount_value / 100)
    elif discount_type == 'FIXED_AMOUNT':
        return min(discount_value, original_price)
    return Decimal('0.00')


def format_currency(amount, currency='USD'):
    """Format amount as currency string"""
    currency_symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'CAD': 'C$',
        'AUD': 'A$',
    }
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"


def generate_qr_code(data, size=(200, 200)):
    """Generate QR code for order tracking, etc."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def calculate_weight(items):
    """Calculate total weight of cart/order items"""
    total_weight = Decimal('0.0')
    for item in items:
        product_weight = item.product.weight or Decimal('0.0')
        total_weight += product_weight * item.quantity
    return total_weight


def generate_secure_token():
    """Generate secure token for various purposes"""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()


def slugify_unique(text, model_class, field_name='slug', instance=None):
    """Generate unique slug for model instance"""
    base_slug = slugify(text)
    if not base_slug:
        base_slug = 'item'
    
    slug = base_slug
    counter = 1
    
    while True:
        queryset = model_class.objects.filter(**{field_name: slug})
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        
        if not queryset.exists():
            return slug
        
        slug = f"{base_slug}-{counter}"
        counter += 1


def validate_email_domain(email, allowed_domains=None):
    """Validate email domain against allowed list"""
    if not allowed_domains:
        return True
    
    domain = email.split('@')[1].lower()
    return domain in [d.lower() for d in allowed_domains]


def truncate_text(text, max_length=100):
    """Truncate text to specified length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'


def calculate_tax(amount, tax_rate, tax_included=False):
    """Calculate tax amount"""
    if tax_included:
        # Extract tax from total amount
        return amount - (amount / (1 + tax_rate))
    else:
        # Add tax to amount
        return amount * tax_rate


def generate_barcode(product_id, format='CODE128'):
    """Generate barcode for product"""
    try:
        from barcode import Code128
        from barcode.writer import ImageWriter
        
        code = Code128(str(product_id), writer=ImageWriter())
        buffer = BytesIO()
        code.write(buffer)
        return buffer.getvalue()
    except ImportError:
        return None


def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    import re
    # Remove any non-alphanumeric characters except dots, hyphens, underscores
    safe_filename = re.sub(r'[^a-zA-Z0-9.\-_]', '_', filename)
    return safe_filename[:100]  # Limit length


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def calculate_shipping_dimensions(items):
    """Calculate shipping dimensions for multiple items"""
    # This is a simplified calculation
    # Real implementation would consider packaging efficiency
    total_volume = Decimal('0.0')
    max_length = Decimal('0.0')
    max_width = Decimal('0.0')
    total_height = Decimal('0.0')
    
    for item in items:
        product = item.product
        quantity = item.quantity
        
        if all([product.length, product.width, product.height]):
            item_volume = product.length * product.width * product.height * quantity
            total_volume += item_volume
            
            max_length = max(max_length, product.length)
            max_width = max(max_width, product.width)
            total_height += product.height * quantity
    
    return {
        'volume': total_volume,
        'length': max_length,
        'width': max_width,
        'height': total_height
    }
