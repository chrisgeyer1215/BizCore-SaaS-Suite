import uuid
import hashlib
import random
import string
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.utils.text import slugify
from django.core.cache import cache
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from .constants import DEFAULT_VALUES, BUSINESS_RULES

def generate_reference_number(prefix: str = 'REF', length: int = 8) -> str:
    """Generate a unique reference number"""
    timestamp = timezone.now().strftime('%Y%m%d')
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_part}"

def generate_sku(product_name: str, category_code: str = '', 
                brand_code: str = '', variant: str = '') -> str:
    """Generate SKU from product information"""
    # Clean and prepare components
    name_part = ''.join(c.upper() for c in product_name if c.isalnum())[:6]
    category_part = category_code.upper()[:3] if category_code else ''
    brand_part = brand_code.upper()[:3] if brand_code else ''
    variant_part = variant.upper()[:3] if variant else ''
    
    # Generate timestamp part
    timestamp_part = timezone.now().strftime('%m%d')
    
    # Combine parts
    sku_parts = [p for p in [category_part, brand_part, name_part, variant_part, timestamp_part] if p]
    sku = '-'.join(sku_parts)
    
    # Ensure minimum length
    if len(sku) < 3:
        sku += '-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    
    return sku[:50]  # Ensure max length

def generate_barcode_checksum(barcode: str, barcode_type: str = 'EAN13') -> str:
    """Generate checksum for barcode"""
    if barcode_type == 'EAN13' and len(barcode) == 12:
        # Calculate EAN13 checksum
        odd_sum = sum(int(barcode[i]) for i in range(0, 12, 2))
        even_sum = sum(int(barcode[i]) for i in range(1, 12, 2))
        checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
        return barcode + str(checksum)
    
    elif barcode_type == 'UPC' and len(barcode) == 11:
        # Calculate UPC checksum
        odd_sum = sum(int(barcode[i]) for i in range(0, 11, 2))
        even_sum = sum(int(barcode[i]) for i in range(1, 11, 2))
        checksum = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10
        return barcode + str(checksum)
    
    return barcode

def generate_batch_number(product_code: str = '', production_date: date = None) -> str:
    """Generate batch number"""
    if not production_date:
        production_date = date.today()
    
    date_part = production_date.strftime('%y%m%d')
    product_part = product_code.upper()[:4] if product_code else 'PROD'
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    
    return f"{product_part}-{date_part}-{random_part}"

def generate_serial_number(product_code: str = '', sequence: int = None) -> str:
    """Generate serial number"""
    product_part = product_code.upper()[:4] if product_code else 'PROD'
    year_part = timezone.now().strftime('%y')
    
    if sequence:
        sequence_part = f"{sequence:06d}"
    else:
        sequence_part = ''.join(random.choices(string.digits, k=6))
    
    return f"{product_part}{year_part}{sequence_part}"

def generate_unique_code(length: int = 8, prefix: str = '', suffix: str = '') -> str:
    """Generate unique alphanumeric code"""
    code_chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choices(code_chars, k=length))
    return f"{prefix}{code}{suffix}"

def calculate_weighted_average(values_weights: List[Tuple[Decimal, Decimal]]) -> Decimal:
    """Calculate weighted average from list of (value, weight) tuples"""
    if not values_weights:
        return Decimal('0')
    
    total_weighted_value = sum(value * weight for value, weight in values_weights)
    total_weight = sum(weight for _, weight in values_weights)
    
    if total_weight == 0:
        return Decimal('0')
    
    return total_weighted_value / total_weight

def round_decimal(value: Union[Decimal, float, str], places: int = 2, 
                 rounding_method=ROUND_HALF_UP) -> Decimal:
    """Round decimal to specified places"""
    decimal_value = Decimal(str(value))
    quantizer = Decimal('0.1') ** places
    return decimal_value.quantize(quantizer, rounding=rounding_method)

def format_currency(amount: Union[Decimal, float], currency: str = 'USD', 
                   include_symbol: bool = True) -> str:
    """Format currency amount"""
    from babel.numbers import format_currency as babel_format_currency
    
    try:
        if include_symbol:
            return babel_format_currency(amount, currency)
        else:
            return f"{amount:,.2f}"
    except:
        # Fallback formatting
        symbol = '$' if currency == 'USD' else currency
        return f"{symbol}{amount:,.2f}" if include_symbol else f"{amount:,.2f}"

def format_quantity(quantity: Union[Decimal, float], decimal_places: int = None) -> str:
    """Format quantity with appropriate decimal places"""
    if decimal_places is None:
        # Auto-detect decimal places needed
        decimal_value = Decimal(str(quantity))
        if decimal_value == decimal_value.to_integral_value():
            decimal_places = 0
        else:
            decimal_places = min(abs(decimal_value.as_tuple().exponent), 4)
    
    format_string = f"{{:,.{decimal_places}f}}"
    return format_string.format(quantity)

def format_percentage(value: Union[Decimal, float], decimal_places: int = 1) -> str:
    """Format percentage value"""
    format_string = f"{{:.{decimal_places}f}}%"
    return format_string.format(value)

def format_date_range(start_date: date, end_date: date, 
                     date_format: str = '%Y-%m-%d') -> str:
    """Format date range as string"""
    if start_date == end_date:
        return start_date.strftime(date_format)
    else:
        return f"{start_date.strftime(date_format)} to {end_date.strftime(date_format)}"

def get_financial_period(reference_date: date = None, 
                        period_type: str = 'month') -> Tuple[date, date]:
    """Get financial period dates"""
    if not reference_date:
        reference_date = date.today()
    
    if period_type == 'month':
        start_date = reference_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
    
    elif period_type == 'quarter':
        quarter_start_months = {1: 1, 2: 1, 3: 1, 4: 4, 5: 4, 6: 4,
                               7: 7, 8: 7, 9: 7, 10: 10, 11: 10, 12: 10}
        start_month = quarter_start_months[reference_date.month]
        start_date = reference_date.replace(month=start_month, day=1)
        
        if start_month == 10:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_month + 3) - timedelta(days=1)
    
    elif period_type == 'year':
        start_date = reference_date.replace(month=1, day=1)
        end_date = reference_date.replace(month=12, day=31)
    
    else:
        # Default to month
        start_date = reference_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
    
    return start_date, end_date

def get_age_in_days(from_date: Union[date, datetime], 
                   to_date: Union[date, datetime] = None) -> int:
    """Get age in days between two dates"""
    if not to_date:
        to_date = date.today() if isinstance(from_date, date) else timezone.now()
    
    # Convert to dates if datetime objects
    if isinstance(from_date, datetime):
        from_date = from_date.date()
    if isinstance(to_date, datetime):
        to_date = to_date.date()
    
    return (to_date - from_date).days

def get_business_days(start_date: date, end_date: date, 
                     holidays: List[date] = None) -> int:
    """Calculate number of business days between two dates"""
    if holidays is None:
        holidays = []
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6
        if current_date.weekday() < 5 and current_date not in holidays:
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def create_slug(text: str, max_length: int = 50) -> str:
    """Create URL-friendly slug from text"""
    slug = slugify(text)
    return slug[:max_length] if len(slug) > max_length else slug

def generate, algorithm: str = 'sha256') -> str:
    """Generate hash from data"""
    if algorithm == 'md5':
        return hashlib.md5(data.encode()).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(data.encode()).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

def generate_uuid() -> str:
    """Generate UUID string"""
    return str(uuid.uuid4())

def safe_divide(numerator: Union[Decimal, float], 
               denominator: Union[Decimal, float], 
               default: Union[Decimal, float] = 0) -> Decimal:
    """Safe division that handles zero denominator"""
    try:
        num = Decimal(str(numerator))
        den = Decimal(str(denominator))
        
        if den == 0:
            return Decimal(str(default))
        
        return num / den
    except (ValueError, TypeError):
        return Decimal(str(default))

def safe_percentage(part: Union[Decimal, float], 
                   whole: Union[Decimal, float], 
                   default: Union[Decimal, float] = 0) -> Decimal:
    """Calculate percentage safely"""
    return safe_divide(part, whole, default) * 100

def chunk_list(input_list: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]

def flatten_dict(d: Dict[str, Any], parent_key: str = '', 
                separator: str = '_') -> Dict[str, Any]:
    """Flatten nested dictionary"""
    items = []
    for key, value in d.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, separator).items())
        else:
            items.append((new_key, value))
    
    return dict(items)

def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result

def cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from prefix and arguments"""
    key_parts = [prefix]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    
    key = '_'.join(key_parts)
    return hashlib.md5(key.encode()).hexdigest()[:32]

def get_cached_or_set(cache_key: str, callable_func, timeout: int = 300):
    """Get value from cache or set it using callable"""
    value = cache.get(cache_key)
    if value is None:
        value = callable_func()
        cache.set(cache_key, value, timeout)
    return value

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and periods
    filename = filename.strip(' .')
    
    # Truncate if too long
    if len(filename) > max_length:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = max_length - len(ext) - 1 if ext else max_length
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    return filename or 'unnamed_file'

def convert_size_bytes(size_bytes: int) -> str:
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def extract_numbers(text: str) -> List[str]:
    """Extract all numbers from text"""
    import re
    return re.findall(r'\d+\.?\d*', text)

def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text"""
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)

def normalize_phone(phone: str, country_code: str = '+1') -> str:
    """Normalize phone number"""
    import re
    
    # Remove all non-digits
    digits = re.sub(r'[^\d]', '', phone)
    
    # Add country code if not present
    if not digits.startswith(country_code.replace('+', '')):
        digits = country_code.replace('+', '') + digits
    
    return f"+{digits}"

def is_valid_json(json_string: str) -> bool:
    """Check if string is valid JSON"""
    import json
    try:
        json.loads(json_string)
        return True
    except (ValueError, TypeError):
        return False

def get_client_ip(request) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_agent(request) -> str:
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')

class DataProcessor:
    """Helper class for data processing operations"""
    
    @staticmethod
    def clean_numeric_string(value: str) -> str:
        """Clean numeric string by removing non-numeric characters"""
        import re
        return re.sub(r'[^\d.-]', '', str(value))
    
    @staticmethod
    def parse_decimal(value: Any, default: Decimal = None) -> Optional[Decimal]:
        """Safely parse decimal value"""
        if value is None:
            return default
        
        try:
            if isinstance(value, str):
                value = DataProcessor.clean_numeric_string(value)
            return Decimal(str(value))
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_integer(value: Any, default: int = None) -> Optional[int]:
        """Safely parse integer value"""
        if value is None:
            return default
        
        try:
            if isinstance(value, str):
                value = DataProcessor.clean_numeric_string(value)
            return int(float(value))  # Handle decimal strings
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_boolean(value: Any, default: bool = False) -> bool:
        """Safely parse boolean value"""
        if value is None:
            return default
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
        
        try:
            return bool(int(value))
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_date(value: Any, format_string: str = '%Y-%m-%d') -> Optional[date]:
        """Safely parse date value"""
        if value is None:
            return None
        
        if isinstance(value, date):
            return value
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, str):
            try:
                return datetime.strptime(value, format_string).date()
            except ValueError:
                # Try common formats
                common_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']
                for fmt in common_formats:
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        continue
        
        return None
    
    @staticmethod
    def clean_text(text: str, max_length: int = None, 
                  remove_extra_spaces: bool = True) -> str:
        """Clean and normalize text"""
        if not text:
            return ''
        
        text = str(text).strip()
        
        if remove_extra_spaces:
            import re
            text = re.sub(r'\s+', ' ', text)
        
        if max_length and len(text) > max_length:
            text = text[:max_length].strip()
        
        return text