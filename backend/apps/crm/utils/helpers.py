# crm/utils/helpers.py
"""
General Helper Functions for CRM Module

Provides common utility functions used throughout the CRM system including:
- Reference number generation
- Data sanitization and validation
- Date/time calculations
- Name parsing and formatting
- Security utilities
- Tenant-specific operations
"""

import re
import uuid
import secrets
import hashlib
import phonenumbers
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from django.utils import timezone as django_timezone
from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.template.defaultfilters import truncatewords
import bleach


def generate_reference_number(prefix: str = "CRM", length: int = 8) -> str:
    """
    Generate a unique reference number with prefix.
    
    Args:
        prefix: String prefix for the reference number
        length: Length of the random part (default: 8)
    
    Returns:
        String: Formatted reference number (e.g., "CRM-20241201-A1B2C3D4")
    
    Examples:
        >>> generate_reference_number("LEAD")
        "LEAD-20241201-A1B2C3D4"
        >>> generate_reference_number("OPP", 6)
        "OPP-20241201-X1Y2Z3"
    """
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(length // 2).upper()
    return f"{prefix}-{timestamp}-{random_part}"


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Token length (default: 32)
    
    Returns:
        String: Secure random token
    """
    return secrets.token_urlsafe(length)


def format_phone_number(phone: str, country_code: str = 'US') -> Optional[str]:
    """
    Format phone number using international standards.
    
    Args:
        phone: Raw phone number string
        country_code: Country code for parsing (default: 'US')
    
    Returns:
        Optional[str]: Formatted phone number or None if invalid
    
    Examples:
        >>> format_phone_number("(555) 123-4567")
        "+1 555-123-4567"
        >>> format_phone_number("5551234567", "US")
        "+1 555-123-4567"
    """
    try:
        if not phone:
            return None
            
        # Parse the phone number
        parsed_number = phonenumbers.parse(phone, country_code)
        
        # Validate the number
        if phonenumbers.is_valid_number(parsed_number):
            # Format in international format
            return phonenumbers.format_number(
                parsed_number, 
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
        return None
    except phonenumbers.NumberParseException:
        return None


def parse_name_components(full_name: str) -> Dict[str, str]:
    """
    Parse full name into components (first, middle, last).
    
    Args:
        full_name: Full name string
    
    Returns:
        Dict: Dictionary with name components
    
    Examples:
        >>> parse_name_components("John Michael Smith")
        {"first_name": "John", "middle_name": "Michael", "last_name": "Smith"}
        >>> parse_name_components("Jane Doe")
        {"first_name": "Jane", "middle_name": "", "last_name": "Doe"}
    """
    if not full_name:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    
    # Clean and split the name
    name_parts = [part.strip().title() for part in full_name.strip().split() if part.strip()]
    
    if len(name_parts) == 0:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    elif len(name_parts) == 1:
        return {"first_name": name_parts[0], "middle_name": "", "last_name": ""}
    elif len(name_parts) == 2:
        return {"first_name": name_parts[0], "middle_name": "", "last_name": name_parts[1]}
    else:
        # More than 2 parts - first is first name, last is last name, middle is everything else
        return {
            "first_name": name_parts[0],
            "middle_name": " ".join(name_parts[1:-1]),
            "last_name": name_parts[-1]
        }


def calculate_time_difference(start_time: datetime, end_time: datetime = None) -> Dict[str, Any]:
    """
    Calculate time difference with detailed breakdown.
    
    Args:
        start_time: Start datetime
        end_time: End datetime (default: now)
    
    Returns:
        Dict: Time difference breakdown
    
    Examples:
        >>> calculate_time_difference(datetime(2024, 1, 1), datetime(2024, 1, 2))
        {"days": 1, "hours": 0, "minutes": 0, "total_seconds": 86400, "human_readable": "1 day"}
    """
    if end_time is None:
        end_time = django_timezone.now()
    
    # Ensure both times are timezone-aware
    if start_time.tzinfo is None:
        start_time = django_timezone.make_aware(start_time)
    if end_time.tzinfo is None:
        end_time = django_timezone.make_aware(end_time)
    
    diff = end_time - start_time
    total_seconds = int(diff.total_seconds())
    
    days = diff.days
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Generate human-readable format
    if days > 0:
        human_readable = f"{days} day{'s' if days != 1 else ''}"
        if hours > 0:
            human_readable += f", {hours} hour{'s' if hours != 1 else ''}"
    elif hours > 0:
        human_readable = f"{hours} hour{'s' if hours != 1 else ''}"
        if minutes > 0:
            human_readable += f", {minutes} minute{'s' if minutes != 1 else ''}"
    elif minutes > 0:
        human_readable = f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        human_readable = f"{seconds} second{'s' if seconds != 1 else ''}"
    
    return {
        "days": days,
        "hours": hours % 24,
        "minutes": minutes,
        "seconds": seconds,
        "total_seconds": total_seconds,
        "human_readable": human_readable
    }


def sanitize_input(input_text: str, allowed_tags: List[str] = None) -> str:
    """
    Sanitize user input to prevent XSS attacks.
    
    Args:
        input_text: Input text to sanitize
        allowed_tags: List of allowed HTML tags (default: None)
    
    Returns:
        String: Sanitized text
    """
    if not input_text:
        return ""
    
    if allowed_tags is None:
        allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
    
    # Use bleach to clean the input
    clean_text = bleach.clean(
        input_text,
        tags=allowed_tags,
        attributes={'*': ['class']},
        strip=True
    )
    
    return clean_text


def get_tenant_setting(tenant, setting_name: str, default_value: Any = None) -> Any:
    """
    Get tenant-specific setting value.
    
    Args:
        tenant: Tenant instance
        setting_name: Setting name to retrieve
        default_value: Default value if setting not found
    
    Returns:
        Any: Setting value or default
    """
    cache_key = f"tenant_setting_{tenant.id}_{setting_name}"
    cached_value = cache.get(cache_key)
    
    if cached_value is not None:
        return cached_value
    
    try:
        from crm.models.system import TenantSetting
        setting = TenantSetting.objects.get(
            tenant=tenant,
            setting_name=setting_name
        )
        value = setting.setting_value
        
        # Cache for 1 hour
        cache.set(cache_key, value, 3600)
        return value
    except:
        return default_value


def create_slug(text: str, max_length: int = 50) -> str:
    """
    Create URL-friendly slug from text.
    
    Args:
        text: Text to convert to slug
        max_length: Maximum slug length
    
    Returns:
        String: URL-friendly slug
    """
    if not text:
        return ""
    
    slug = slugify(text)
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')
    
    return slug
, algorithm: str = 'sha256') -> str:
    """
    Hash data using specified algorithm.
     Data to hash
        algorithm: Hash algorithm (default: 'sha256')
    
    Returns:
        String: Hashed data
    """
    if algorithm == 'md5':
        return hashlib.md5(data.encode()).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(data.encode()).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def extract_domain_from_email(email: str) -> Optional[str]:
    """
    Extract domain from email address.
    
    Args:
        email: Email address
    
    Returns:
        Optional[str]: Domain name or None
    """
    if not email or '@' not in email:
        return None
    
    try:
        domain = email.split('@')[1].lower()
        return domain
    except (IndexError, AttributeError):
        return None


def generate_avatar_url(email: str, size: int = 200) -> str:
    """
    Generate Gravatar URL for email.
    
    Args:
        email: Email address
        size: Avatar size in pixels
    
    Returns:
        String: Gravatar URL
    """
    if not email:
        return f"https://www.gravatar.com/avatar/default?s={size}&d=identicon"
    
    email_hash = hashlib.md5(email.lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"


def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
    """
    Calculate number of business days between two dates.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        int: Number of business days
    """
    if start_date > end_date:
        return 0
    
    business_days = 0
    current_date = start_date.date() if isinstance(start_date, datetime) else start_date
    end = end_date.date() if isinstance(end_date, datetime) else end_date
    
    while current_date <= end:
        # Monday is 0, Sunday is 6
        if current_date.weekday() < 5:  # Monday to Friday
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.
    
    Args:
        size_bytes: File size in bytes
    
    Returns:
        String: Formatted file size
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask sensitive data like phone numbers, emails, etc.
     Data to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to keep visible at the end
    
    Returns:
        String: Masked data
    """
    if not data or len(data) <= visible_chars:
        return data
    
    masked_length = len(data) - visible_chars
    return mask_char * masked_length + data[-visible_chars:]


class CRMCache:
    """
    CRM-specific caching utilities.
    """
    
    @staticmethod
    def get_cache_key(tenant_id: int, object_type: str, object_id: int = None) -> str:
        """Generate standardized cache key."""
        if object_id:
            return f"crm_tenant_{tenant_id}_{object_type}_{object_id}"
        return f"crm_tenant_{tenant_id}_{object_type}"
    
    @staticmethod
    def set_tenant_cache(tenant_id: int, key: str, value: Any, timeout: int = 3600) -> None:
        """Set tenant-specific cache."""
        cache_key = CRMCache.get_cache_key(tenant_id, key)
        cache.set(cache_key, value, timeout)
    
    @staticmethod
    def get_tenant_cache(tenant_id: int, key: str, default: Any = None) -> Any:
        """Get tenant-specific cache."""
        cache_key = CRMCache.get_cache_key(tenant_id, key)
        return cache.get(cache_key, default)
    
    @staticmethod
    def delete_tenant_cache(tenant_id: int, key: str) -> None:
        """Delete tenant-specific cache."""
        cache_key = CRMCache.get_cache_key(tenant_id, key)
        cache.delete(cache_key)


def get_ip_address(request) -> str:
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
    
    Returns:
        String: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def is_business_hours(dt: datetime = None, timezone_name: str = 'UTC') -> bool:
    """
    Check if given datetime falls within business hours.
    
    Args:
        dt: Datetime to check (default: now)
        timezone_name: Timezone name
    
    Returns:
        bool: True if within business hours
    """
    if dt is None:
        dt = django_timezone.now()
    
    # Convert to specified timezone
    import pytz
    tz = pytz.timezone(timezone_name)
    local_dt = dt.astimezone(tz)
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if local_dt.weekday() > 4:  # Saturday or Sunday
        return False
    
    # Check if it's within business hours (9 AM - 6 PM)
    hour = local_dt.hour
    return 9 <= hour < 18