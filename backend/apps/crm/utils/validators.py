# crm/utils/validators.py
"""
Custom Validators for CRM Module

Provides comprehensive validation functions for CRM data including:
- Email validation
- Phone number validation
- Financial data validation
- Date and time validation
- Business rule validation
- Custom field validation
"""

import re
import phonenumbers
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, time
from typing import Any, List, Dict, Optional, Union
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.utils.translation import gettext_lazy as _
import pycountry


def validate_email_format(email: str) -> bool:
    """
    Validate email format with enhanced checks.
    
    Args:
        email: Email address to validate
    
    Returns:
        bool: True if valid email format
    
    Raises:
        ValidationError: If email format is invalid
    """
    if not email:
        raise ValidationError(_("Email address is required."))
    
    # Basic Django email validation
    try:
        django_validate_email(email)
    except ValidationError:
        raise ValidationError(_("Invalid email format."))
    
    # Additional custom checks
    email = email.lower().strip()
    
    # Check for common typos in domains
    common_domains = {
        'gmail.com': ['gmai.com', 'gmial.com', 'gmail.co'],
        'yahoo.com': ['yaho.com', 'yahoo.co'],
        'hotmail.com': ['hotmai.com', 'hotmial.com'],
        'outlook.com': ['outlok.com', 'outook.com']
    }
    
    domain = email.split('@')[1]
    for correct_domain, typos in common_domains.items():
        if domain in typos:
            raise ValidationError(
                _("Did you mean {}?").format(email.replace(domain, correct_domain))
            )
    
    # Check for disposable email domains (basic list)
    disposable_domains = [
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'temp-mail.org'
    ]
    
    if domain in disposable_domains:
        raise ValidationError(_("Disposable email addresses are not allowed."))
    
    return True


def validate_phone_number(phone: str, country_code: str = None) -> bool:
    """
    Validate phone number format using international standards.
    
    Args:
        phone: Phone number to validate
        country_code: Country code for validation (optional)
    
    Returns:
        bool: True if valid phone number
    
    Raises:
        ValidationError: If phone number is invalid
    """
    if not phone:
        raise ValidationError(_("Phone number is required."))
    
    try:
        # Parse the phone number
        parsed_number = phonenumbers.parse(phone, country_code)
        
        # Check if the number is valid
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValidationError(_("Invalid phone number format."))
        
        # Check if it's a possible number
        if not phonenumbers.is_possible_number(parsed_number):
            raise ValidationError(_("Phone number is not possible for the given region."))
        
        return True
        
    except phonenumbers.NumberParseException as e:
        error_messages = {
            phonenumbers.NumberParseException.INVALID_COUNTRY_CODE: _("Invalid country code."),
            phonenumbers.NumberParseException.NOT_A_NUMBER: _("The phone number is not a valid number."),
            phonenumbers.NumberParseException.TOO_SHORT_NSN: _("Phone number is too short."),
            phonenumbers.NumberParseException.TOO_LONG: _("Phone number is too long."),
        }
        
        message = error_messages.get(e.error_type, _("Invalid phone number."))
        raise ValidationError(message)


def validate_currency_amount(amount: Union[str, int, float, Decimal], 
                           min_value: Decimal = None, 
                           max_value: Decimal = None) -> Decimal:
    """
    Validate currency amount with precision and range checks.
    
    Args:
        amount: Amount to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
    
    Returns:
        Decimal: Validated amount
    
    Raises:
        ValidationError: If amount is invalid
    """
    if amount is None:
        raise ValidationError(_("Amount is required."))
    
    try:
        # Convert to Decimal for precise calculations
        decimal_amount = Decimal(str(amount))
        
        # Check for negative values (unless min_value allows it)
        if min_value is None and decimal_amount < 0:
            raise ValidationError(_("Amount cannot be negative."))
        
        # Check minimum value
        if min_value is not None and decimal_amount < min_value:
            raise ValidationError(_("Amount cannot be less than {}.").format(min_value))
        
        # Check maximum value
        if max_value is not None and decimal_amount > max_value:
            raise ValidationError(_("Amount cannot be greater than {}.").format(max_value))
        
        # Check decimal places (max 2 for currency)
        if decimal_amount.as_tuple().exponent < -2:
            raise ValidationError(_("Amount can have at most 2 decimal places."))
        
        return decimal_amount
        
    except (InvalidOperation, ValueError):
        raise ValidationError(_("Invalid amount format."))


def validate_percentage(percentage: Union[str, int, float], 
                       min_value: float = 0.0, 
                       max_value: float = 100.0) -> float:
    """
    Validate percentage value within specified range.
    
    Args:
        percentage: Percentage to validate
        min_value: Minimum allowed percentage (default: 0.0)
        max_value: Maximum allowed percentage (default: 100.0)
    
    Returns:
        float: Validated percentage
    
    Raises:
        ValidationError: If percentage is invalid
    """
    if percentage is None:
        raise ValidationError(_("Percentage is required."))
    
    try:
        float_percentage = float(percentage)
        
        if float_percentage < min_value:
            raise ValidationError(_("Percentage cannot be less than {}%.").format(min_value))
        
        if float_percentage > max_value:
            raise ValidationError(_("Percentage cannot be greater than {}%.").format(max_value))
        
        return float_percentage
        
    except (ValueError, TypeError):
        raise ValidationError(_("Invalid percentage format."))


def validate_date_range(start_date: date, end_date: date, 
                       max_duration_days: int = None) -> bool:
    """
    Validate date range with optional duration limit.
    
    Args:
        start_date: Start date
        end_date: End date
        max_duration_days: Maximum allowed duration in days (optional)
    
    Returns:
        bool: True if valid date range
    
    Raises:
        ValidationError: If date range is invalid
    """
    if not start_date:
        raise ValidationError(_("Start date is required."))
    
    if not end_date:
        raise ValidationError(_("End date is required."))
    
    if end_date < start_date:
        raise ValidationError(_("End date cannot be before start date."))
    
    if max_duration_days:
        duration = (end_date - start_date).days
        if duration > max_duration_days:
            raise ValidationError(
                _("Date range cannot exceed {} days.").format(max_duration_days)
            )
    
    return True


def validate_business_hours(start_time: time, end_time: time) -> bool:
    """
    Validate business hours format.
    
    Args:
        start_time: Start time
        end_time: End time
    
    Returns:
        bool: True if valid business hours
    
    Raises:
        ValidationError: If business hours are invalid
    """
    if not start_time:
        raise ValidationError(_("Start time is required."))
    
    if not end_time:
        raise ValidationError(_("End time is required."))
    
    if end_time <= start_time:
        raise ValidationError(_("End time must be after start time."))
    
    return True


def validate_priority_level(priority: Union[str, int]) -> int:
    """
    Validate priority level (1-5 scale).
    
    Args:
        priority: Priority level to validate
    
    Returns:
        int: Validated priority level
    
    Raises:
        ValidationError: If priority is invalid
    """
    try:
        priority_int = int(priority)
        if priority_int < 1 or priority_int > 5:
            raise ValidationError(_("Priority must be between 1 and 5."))
        return priority_int
    except (ValueError, TypeError):
        raise ValidationError(_("Invalid priority format."))


def validate_probability(probability: Union[str, int, float]) -> int:
    """
    Validate probability percentage (0-100).
    
    Args:
        probability: Probability to validate
    
    Returns:
        int: Validated probability
    
    Raises:
        ValidationError: If probability is invalid
    """
    try:
        prob_int = int(float(probability))
        if prob_int < 0 or prob_int > 100:
            raise ValidationError(_("Probability must be between 0 and 100."))
        return prob_int
    except (ValueError, TypeError):
        raise ValidationError(_("Invalid probability format."))


def validate_country_code(country_code: str) -> str:
    """
    Validate ISO country code.
    
    Args:
        country_code: Country code to validate
    
    Returns:
        str: Validated country code
    
    Raises:
        ValidationError: If country code is invalid
    """
    if not country_code:
        raise ValidationError(_("Country code is required."))
    
    country_code = country_code.upper().strip()
    
    try:
        # Validate using pycountry
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            raise ValidationError(_("Invalid country code."))
        return country_code
    except:
        raise ValidationError(_("Invalid country code."))


def validate_currency_code(currency_code: str) -> str:
    """
    Validate ISO currency code.
    
    Args:
        currency_code: Currency code to validate
    
    Returns:
        str: Validated currency code
    
    Raises:
        ValidationError: If currency code is invalid
    """
    if not currency_code:
        raise ValidationError(_("Currency code is required."))
    
    currency_code = currency_code.upper().strip()
    
    try:
        # Validate using pycountry
        currency = pycountry.currencies.get(alpha_3=currency_code)
        if not currency:
            raise ValidationError(_("Invalid currency code."))
        return currency_code
    except:
        raise ValidationError(_("Invalid currency code."))


def validate_sku(sku: str, pattern: str = None) -> str:
    """
    Validate SKU format with optional custom pattern.
    
    Args:
        sku: SKU to validate
        pattern: Regex pattern for validation (optional)
    
    Returns:
        str: Validated SKU
    
    Raises:
        ValidationError: If SKU is invalid
    """
    if not sku:
        raise ValidationError(_("SKU is required."))
    
    sku = sku.strip().upper()
    
    # Default pattern: alphanumeric with hyphens and underscores
    if pattern is None:
        pattern = r'^[A-Z0-9\-_]{3,20}$'
    
    if not re.match(pattern, sku):
        raise ValidationError(_("Invalid SKU format."))
    
    return sku


def validate_url(url: str, require_https: bool = False) -> str:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        require_https: Whether to require HTTPS (default: False)
    
    Returns:
        str: Validated URL
    
    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError(_("URL is required."))
    
    url = url.strip()
    
    # Basic URL pattern
    url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    
    if not re.match(url_pattern, url):
        raise ValidationError(_("Invalid URL format."))
    
    if require_https and not url.startswith('https://'):
        raise ValidationError(_("URL must use HTTPS."))
    
    return url


def validate_social_security_number(ssn: str) -> str:
    """
    Validate US Social Security Number format.
    
    Args:
        ssn: SSN to validate
    
    Returns:
        str: Validated SSN
    
    Raises:
        ValidationError: If SSN is invalid
    """
    if not ssn:
        raise ValidationError(_("SSN is required."))
    
    # Remove any non-digit characters
    ssn_digits = re.sub(r'\D', '', ssn)
    
    if len(ssn_digits) != 9:
        raise ValidationError(_("SSN must be 9 digits."))
    
    # Check for invalid patterns
    invalid_patterns = [
        '000000000', '111111111', '222222222', '333333333',
        '444444444', '555555555', '666666666', '777777777',
        '888888888', '999999999', '123456789'
    ]
    
    if ssn_digits in invalid_patterns:
        raise ValidationError(_("Invalid SSN pattern."))
    
    # Format as XXX-XX-XXXX
    formatted_ssn = f"{ssn_digits[:3]}-{ssn_digits[3:5]}-{ssn_digits[5:]}"
    return formatted_ssn


def validate_tax_id(tax_id: str, country_code: str = 'US') -> str:
    """
    Validate tax ID based on country.
    
    Args:
        tax_id: Tax ID to validate
        country_code: Country code for validation
    
    Returns:
        str: Validated tax ID
    
    Raises:
        ValidationError: If tax ID is invalid
    """
    if not tax_id:
        raise ValidationError(_("Tax ID is required."))
    
    tax_id = tax_id.strip().upper()
    
    if country_code == 'US':
        # US EIN format: XX-XXXXXXX
        ein_pattern = r'^\d{2}-\d{7}$'
        if not re.match(ein_pattern, tax_id):
            # Try to format if it's just digits
            digits = re.sub(r'\D', '', tax_id)
            if len(digits) == 9:
                tax_id = f"{digits[:2]}-{digits[2:]}"
            else:
                raise ValidationError(_("Invalid US Tax ID format. Expected XX-XXXXXXX."))
    
    return tax_id


class CRMFieldValidator:
    """
    Custom validator for CRM-specific field combinations.
    """
    
    @staticmethod
    def validate_lea Dict[str, Any]:
        """Validate lead data integrity."""
        errors = {}
        
        # Validate required fields based on lead source
        if data.get('source') == 'WEBSITE' and not data.get('email'):
            errors['email'] = _("Email is required for website leads.")
        
        if data.get('source') == 'PHONE' and not data.get('phone'):
            errors['phone'] = _("Phone is required for phone leads.")
        
        # Validate score range
        if data.get('score') is not None:
            try:
                score = int(data['score'])
                if score < 0 or score > 100:
                    errors['score'] = _("Score must be between 0 and 100.")
            except (ValueError, TypeError):
                errors['score'] = _("Invalid score format.")
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    @staticmethod
    def validate_opportunity, Any]) -> Dict[str, Any]:
        """Validate opportunity data integrity."""
        errors = {}
        
        # Validate value and probability
        if data.get('value') and data.get('probability'):
            try:
                value = Decimal(str(data['value']))
                probability = int(data['probability'])
                
                if value > 0 and probability == 0:
                    errors['probability'] = _("Probability should be greater than 0 for valued opportunities.")
                
                if value == 0 and probability > 0:
                    errors['value'] = _("Value should be greater than 0 for probable opportunities.")
                    
            except (ValueError, TypeError, InvalidOperation):
                pass  # Individual field validation will catch these
        
        # Validate close date
        if data.get('expected_close_date'):
            close_date = data['expected_close_date']
            if isinstance(close_date, str):
                try:
                    close_date = datetime.strptime(close_date, '%Y-%m-%d').date()
                except ValueError:
                    errors['expected_close_date'] = _("Invalid date format.")
            
            if close_date and close_date < date.today():
                errors['expected_close_date'] = _("Expected close date cannot be in the past.")
        
        if errors:
            raise ValidationError(errors)
        
        return data