import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date, datetime, timedelta
from typing import Any, Optional, Union
from .constants import REGEX_PATTERNS, BUSINESS_RULES, DEFAULT_VALUES

def validate_positive_decimal(value: Union[Decimal, float, str]) -> Decimal:
    """Validate that a value is a positive decimal"""
    try:
        decimal_value = Decimal(str(value))
        if decimal_value <= 0:
            raise ValidationError(_('Value must be greater than zero.'))
        return decimal_value
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid decimal value.'))

def validate_non_negative_decimal(value: Union[Decimal, float, str]) -> Decimal:
    """Validate that a value is a non-negative decimal"""
    try:
        decimal_value = Decimal(str(value))
        if decimal_value < 0:
            raise ValidationError(_('Value cannot be negative.'))
        return decimal_value
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid decimal value.'))

def validate_positive_integer(value: Union[int, str]) -> int:
    """Validate that a value is a positive integer"""
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValidationError(_('Value must be greater than zero.'))
        return int_value
    except (ValueError, TypeError):
        raise ValidationError(_('Invalid integer value.'))

def validate_non_negative_integer(value: Union[int, str]) -> int:
    """Validate that a value is a non-negative integer"""
    try:
        int_value = int(value)
        if int_value < 0:
            raise ValidationError(_('Value cannot be negative.'))
        return int_value
    except (ValueError, TypeError):
        raise ValidationError(_('Invalid integer value.'))

def validate_sku_format(value: str) -> str:
    """Validate SKU format"""
    if not value:
        raise ValidationError(_('SKU is required.'))
    
    # Remove whitespace
    sku = value.strip().upper()
    
    # Check pattern
    if not re.match(REGEX_PATTERNS['SKU_PATTERN'], sku):
        raise ValidationError(
            _('SKU must be 3-50 characters long and contain only letters, numbers, hyphens, and underscores.')
        )
    
    return sku

def validate_barcode(value: str, barcode_type: str = 'AUTO') -> str:
    """Validate barcode format"""
    if not value:
        return value  # Barcode is optional
    
    barcode = value.strip()
    
    if barcode_type == 'EAN13' or barcode_type == 'AUTO':
        if re.match(REGEX_PATTERNS['BARCODE_EAN13'], barcode):
            # Validate EAN13 checksum
            if validate_ean13_checksum(barcode):
                return barcode
            elif barcode_type == 'EAN13':
                raise ValidationError(_('Invalid EAN13 barcode checksum.'))
    
    if barcode_type == 'UPC' or barcode_type == 'AUTO':
        if re.match(REGEX_PATTERNS['BARCODE_UPC'], barcode):
            # Validate UPC checksum
            if validate_upc_checksum(barcode):
                return barcode
            elif barcode_type == 'UPC':
                raise ValidationError(_('Invalid UPC barcode checksum.'))
    
    if barcode_type == 'CODE128' or barcode_type == 'AUTO':
        if re.match(REGEX_PATTERNS['BARCODE_CODE128'], barcode):
            return barcode
    
    if barcode_type == 'AUTO':
        # If no specific format matches, accept as generic barcode
        return barcode
    
    raise ValidationError(_('Invalid barcode format.'))

def validate_ean13_checksum(barcode: str) -> bool:
    """Validate EAN13 barcode checksum"""
    if len(barcode) != 13 or not barcode.isdigit():
        return False
    
    # Calculate checksum
    odd_sum = sum(int(barcode[i]) for i in range(0, 12, 2))
    even_sum = sum(int(barcode[i]) for i in range(1, 12, 2))
    checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
    
    return checksum == int(barcode[12])

def validate_upc_checksum(barcode: str) -> bool:
    """Validate UPC barcode checksum"""
    if len(barcode) != 12 or not barcode.isdigit():
        return False
    
    # Calculate checksum
    odd_sum = sum(int(barcode[i]) for i in range(0, 11, 2))
    even_sum = sum(int(barcode[i]) for i in range(1, 11, 2))
    checksum = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10
    
    return checksum == int(barcode[11])

def validate_warehouse_code(value: str) -> str:
    """Validate warehouse code format"""
    if not value:
        raise ValidationError(_('Warehouse code is required.'))
    
    code = value.strip().upper()
    
    if not re.match(REGEX_PATTERNS['WAREHOUSE_CODE'], code):
        raise ValidationError(_('Invalid warehouse code format.'))
    
    return code

def validate_location_code(value: str) -> str:
    """Validate location code format"""
    if not value:
        raise ValidationError(_('Location code is required.'))
    
    code = value.strip().upper()
    
    if not re.match(REGEX_PATTERNS['LOCATION_CODE'], code):
        raise ValidationError(_('Invalid location code format.'))
    
    return code

def validate_batch_number(value: str) -> str:
    """Validate batch number format"""
    if not value:
        return value  # Batch number may be optional
    
    batch = value.strip()
    
    if not re.match(REGEX_PATTERNS['BATCH_NUMBER'], batch):
        raise ValidationError(_('Invalid batch number format.'))
    
    return batch

def validate_serial_number(value: str) -> str:
    """Validate serial number format"""
    if not value:
        return value  # Serial number may be optional
    
    serial = value.strip()
    
    if not re.match(REGEX_PATTERNS['SERIAL_NUMBER'], serial):
        raise ValidationError(_('Invalid serial number format.'))
    
    return serial

def validate_expiry_date(value: Optional[date]) -> Optional[date]:
    """Validate expiry date"""
    if not value:
        return value  # Expiry date may be optional
    
    if not isinstance(value, date):
        raise ValidationError(_('Invalid date format.'))
    
    # Expiry date should not be in the past (allow today)
    if value < date.today():
        raise ValidationError(_('Expiry date cannot be in the past.'))
    
    # Expiry date should not be too far in the future (10 years)
    max_future_date = date.today() + timedelta(days=3650)
    if value > max_future_date:
        raise ValidationError(_('Expiry date is too far in the future.'))
    
    return value

def validate_lead_time_days(value: Union[int, str]) -> int:
    """Validate lead time in days"""
    try:
        days = int(value)
        if days < 0:
            raise ValidationError(_('Lead time cannot be negative.'))
        if days > BUSINESS_RULES['MAX_LEAD_TIME_DAYS']:
            raise ValidationError(_('Lead time exceeds maximum allowed days.'))
        return days
    except (ValueError, TypeError):
        raise ValidationError(_('Invalid lead time value.'))

def validate_reorder_level(value: Union[Decimal, float, str], 
                          maximum_level: Optional[Union[Decimal, float, str]] = None) -> Decimal:
    """Validate reorder level"""
    try:
        reorder_level = Decimal(str(value))
        
        if reorder_level < BUSINESS_RULES['MIN_REORDER_LEVEL']:
            raise ValidationError(_('Reorder level below minimum allowed.'))
        
        if reorder_level > BUSINESS_RULES['MAX_REORDER_LEVEL']:
            raise ValidationError(_('Reorder level exceeds maximum allowed.'))
        
        if maximum_level is not None:
            max_level = Decimal(str(maximum_level))
            if reorder_level >= max_level:
                raise ValidationError(_('Reorder level must be less than maximum stock level.'))
        
        return reorder_level
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid reorder level value.'))

def validate_safety_stock(value: Union[Decimal, float, str]) -> Decimal:
    """Validate safety stock level"""
    try:
        safety_stock = Decimal(str(value))
        
        if safety_stock < BUSINESS_RULES['MIN_SAFETY_STOCK']:
            raise ValidationError(_('Safety stock cannot be negative.'))
        
        return safety_stock
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid safety stock value.'))

def validate_unit_cost(value: Union[Decimal, float, str]) -> Decimal:
    """Validate unit cost"""
    try:
        cost = Decimal(str(value))
        
        if cost < Decimal(str(BUSINESS_RULES['MIN_UNIT_COST'])):
            raise ValidationError(_('Unit cost below minimum allowed.'))
        
        if cost > Decimal(str(BUSINESS_RULES['MAX_UNIT_COST'])):
            raise ValidationError(_('Unit cost exceeds maximum allowed.'))
        
        # Check decimal places
        if cost.as_tuple().exponent < -DEFAULT_VALUES['MAX_DECIMAL_PLACES']:
            raise ValidationError(_('Too many decimal places in unit cost.'))
        
        return cost
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid unit cost value.'))

def validate_quantity(value: Union[Decimal, float, str], allow_negative: bool = False) -> Decimal:
    """Validate quantity"""
    try:
        quantity = Decimal(str(value))
        
        if not allow_negative and quantity < 0:
            raise ValidationError(_('Quantity cannot be negative.'))
        
        if abs(quantity) > BUSINESS_RULES['MAX_QUANTITY']:
            raise ValidationError(_('Quantity exceeds maximum allowed.'))
        
        # Check decimal places (quantities usually have fewer decimal places)
        if quantity.as_tuple().exponent < -DEFAULT_VALUES['MAX_DECIMAL_PLACES']:
            raise ValidationError(_('Too many decimal places in quantity.'))
        
        return quantity
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid quantity value.'))

def validate_percentage(value: Union[Decimal, float, str], 
                       min_value: float = 0, max_value: float = 100) -> Decimal:
    """Validate percentage value"""
    try:
        percentage = Decimal(str(value))
        
        if percentage < min_value:
            raise ValidationError(_('Percentage below minimum allowed ({}%).').format(min_value))
        
        if percentage > max_value:
            raise ValidationError(_('Percentage exceeds maximum allowed ({}%).').format(max_value))
        
        return percentage
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid percentage value.'))

def validate_tax_rate(value: Union[Decimal, float, str]) -> Decimal:
    """Validate tax rate (0-100%)"""
    return validate_percentage(value, 0, 100)

def validate_discount_rate(value: Union[Decimal, float, str]) -> Decimal:
    """Validate discount rate (0-100%)"""
    return validate_percentage(value, 0, 100)

def validate_currency_code(value: str) -> str:
    """Validate ISO 4217 currency code"""
    if not value:
        raise ValidationError(_('Currency code is required.'))
    
    code = value.strip().upper()
    
    if len(code) != 3:
        raise ValidationError(_('Currency code must be 3 characters long.'))
    
    if not code.isalpha():
        raise ValidationError(_('Currency code must contain only letters.'))
    
    return code

def validate_email_list(value: list) -> list:
    """Validate list of email addresses"""
    if not isinstance(value, list):
        raise ValidationError(_('Email list must be a list.'))
    
    from django.core.validators import validate_email
    
    validated_emails = []
    for email in value:
        if not isinstance(email, str):
            raise ValidationError(_('Each email must be a string.'))
        
        try:
            validate_email(email.strip())
            validated_emails.append(email.strip().lower())
        except ValidationError:
            raise ValidationError(_('Invalid email address: {}').format(email))
    
    return validated_emails

def validate_phone_number(value: str) -> str:
    """Validate phone number format"""
    if not value:
        return value  # Phone number may be optional
    
    phone = re.sub(r'[^\d+\-\(\)\s]', '', value.strip())
    
    # Basic phone number validation (can be enhanced for specific regions)
    if len(phone) < 10:
        raise ValidationError(_('Phone number too short.'))
    
    if len(phone) > 20:
        raise ValidationError(_('Phone number too long.'))
    
    return phone

def validate_file_size(file, max_size_mb: int = None) -> None:
    """Validate uploaded file size"""
    if not max_size_mb:
        max_size_mb = DEFAULT_VALUES['MAX_FILE_SIZE_MB']
    
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file.size > max_size_bytes:
        raise ValidationError(
            _('File size exceeds maximum allowed size of {} MB.').format(max_size_mb)
        )

def validate_file_extension(file, allowed_extensions: list) -> None:
    """Validate file extension"""
    import os
    
    if not allowed_extensions:
        return
    
    ext = os.path.splitext(file.name)[1].lower()
    
    if ext not in [f'.{ext.lower()}' for ext in allowed_extensions]:
        raise ValidationError(
            _('File extension not allowed. Allowed extensions: {}').format(
                ', '.join(allowed_extensions)
            )
        )

def validate_json_field(value: Any) -> Any:
    """Validate JSON field data"""
    import json
    
    if value is None:
        return value
    
    if isinstance(value, (dict, list)):
        return value
    
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise ValidationError(_('Invalid JSON format.'))
    
    raise ValidationError(_('JSON field must be dict, list, or valid JSON string.'))

def validate_coordinate(value: Union[Decimal, float, str], 
                       coord_type: str = 'latitude') -> Decimal:
    """Validate GPS coordinates"""
    try:
        coord = Decimal(str(value))
        
        if coord_type.lower() == 'latitude':
            if coord < -90 or coord > 90:
                raise ValidationError(_('Latitude must be between -90 and 90 degrees.'))
        elif coord_type.lower() == 'longitude':
            if coord < -180 or coord > 180:
                raise ValidationError(_('Longitude must be between -180 and 180 degrees.'))
        
        return coord
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid coordinate value.'))

def validate_color_code(value: str) -> str:
    """Validate hex color code"""
    if not value:
        return value  # Color may be optional
    
    color = value.strip()
    
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        raise ValidationError(_('Invalid hex color code format. Use #RRGGBB format.'))
    
    return color.upper()

def validate_url(value: str) -> str:
    """Validate URL format"""
    if not value:
        return value  # URL may be optional
    
    from django.core.validators import URLValidator
    
    url_validator = URLValidator()
    
    try:
        url_validator(value)
        return value
    except ValidationError:
        raise ValidationError(_('Invalid URL format.'))

def validate_date_range(start_date: date, end_date: date) -> tuple:
    """Validate date range"""
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValidationError(_('Invalid date format.'))
    
    if start_date > end_date:
        raise ValidationError(_('Start date cannot be after end date.'))
    
    # Check if range is too large (e.g., more than 10 years)
    max_range = timedelta(days=3650)  # 10 years
    if end_date - start_date > max_range:
        raise ValidationError(_('Date range is too large.'))
    
    return start_date, end_date

def validate_time_range(start_time, end_time) -> tuple:
    """Validate time range"""
    from datetime import time
    
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise ValidationError(_('Invalid time format.'))
    
    # For same-day time ranges
    if start_time > end_time:
        raise ValidationError(_('Start time cannot be after end time.'))
    
    return start_time, end_time

class InventoryValidatorMixin:
    """Mixin class for common inventory validations"""
    
    @staticmethod
    def validate_stock_operation(stock_item, quantity: Decimal, 
                               operation_type: str = 'issue') -> None:
        """Validate stock operation availability"""
        if operation_type in ['issue', 'transfer_out', 'reserve']:
            available = stock_item.quantity_on_hand - stock_item.quantity_reserved
            if quantity > available:
                raise ValidationError(
                    _('Insufficient stock. Available: {}, Requested: {}').format(
                        available, quantity
                    )
                )
    
    @staticmethod
    def validate_product_active(product) -> None:
        """Validate that product is active"""
        if not product.is_active:
            raise ValidationError(_('Product is not active.'))
    
    @staticmethod
    def validate_warehouse_active(warehouse) -> None:
        """Validate that warehouse is active"""
        if not warehouse.is_active:
            raise ValidationError(_('Warehouse is not active.'))
    
    @staticmethod
    def validate_supplier_active(supplier) -> None:
        """Validate that supplier is active"""
        if not supplier.is_active or supplier.status != 'ACTIVE':
            raise ValidationError(_('Supplier is not active.'))
    
    @staticmethod
    def validate_batch_not_expired(batch) -> None:
        """Validate that batch is not expired"""
        if batch.expiry_date and batch.expiry_date < date.today():
            raise ValidationError(_('Batch has expired.'))
    
    @staticmethod
    def validate_location_capacity(location, additional_quantity: Decimal = 0) -> None:
        """Validate location capacity"""
        if location.maximum_capacity:
            current_usage = location.current_capacity or 0
            if current_usage + additional_quantity > location.maximum_capacity:
                raise ValidationError(
                    _('Location capacity exceeded. Available: {}').format(
                        location.maximum_capacity - current_usage
                    )
                )

# Custom regex validators
sku_validator = RegexValidator(
    regex=REGEX_PATTERNS['SKU_PATTERN'],
    message=_('SKU must contain only letters, numbers, hyphens, and underscores.')
)

warehouse_code_validator = RegexValidator(
    regex=REGEX_PATTERNS['WAREHOUSE_CODE'],
    message=_('Invalid warehouse code format.')
)

location_code_validator = RegexValidator(
    regex=REGEX_PATTERNS['LOCATION_CODE'],
    message=_('Invalid location code format.')
)

batch_number_validator = RegexValidator(
    regex=REGEX_PATTERNS['BATCH_NUMBER'],
    message=_('Invalid batch number format.')
)

serial_number_validator = RegexValidator(
    regex=REGEX_PATTERNS['SERIAL_NUMBER'],
    message=_('Invalid serial number format.')
)

reference_number_validator = RegexValidator(
    regex=REGEX_PATTERNS['REFERENCE_NUMBER'],
    message=_('Invalid reference number format.')
)