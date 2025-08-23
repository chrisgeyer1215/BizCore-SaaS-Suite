# crm/utils/formatters.py
"""
Data Formatting Utilities for CRM Module

Provides comprehensive formatting functions for displaying data in user-friendly formats:
- Currency formatting with international support
- Date and time formatting with timezone handling
- Phone number display formatting
- Name and address formatting
- Number and percentage formatting
- Text formatting and truncation utilities
"""

import re
from decimal import Decimal
from datetime import datetime, date, time, timezone
from typing import Optional, Dict, Any, List
from django.utils import timezone as django_timezone
from django.conf import settings
from django.utils.formats import date_format, time_format
from django.utils.text import slugify
from django.template.defaultfilters import pluralize
import phonenumbers


def format_currency(amount: Optional[float], 
                   currency_code: str = 'USD',
                   include_symbol: bool = True,
                   decimal_places: int = 2,
                   locale: str = 'en_US') -> str:
    """
    Format currency amount with proper localization.
    
    Args:
        amount: Amount to format
        currency_code: ISO currency code (default: USD)
        include_symbol: Include currency symbol (default: True)
        decimal_places: Number of decimal places (default: 2)
        locale: Locale for formatting (default: en_US)
    
    Returns:
        str: Formatted currency string
    
    Examples:
        >>> format_currency(1234.56, 'USD')
        "$1,234.56"
        >>> format_currency(1234.56, 'EUR', locale='de_DE')
        "€1.234,56"
        >>> format_currency(None)
        "$0.00"
    """
    if amount is None:
        amount = 0
    
    # Convert to Decimal for precision
    try:
        decimal_amount = Decimal(str(amount))
    except:
        decimal_amount = Decimal('0')
    
    # Currency symbols mapping
    currency_symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'CNY': '¥', 'INR': '₹', 'CAD': 'C$', 'AUD': 'A$',
        'CHF': 'Fr', 'SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr',
        'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft', 'RUB': '₽'
    }
    
    # Format based on locale
    if locale == 'en_US':
        # US format: 1,234.56
        formatted_number = f"{decimal_amount:,.{decimal_places}f}"
    elif locale == 'de_DE':
        # German format: 1.234,56
        formatted_number = f"{decimal_amount:,.{decimal_places}f}"
        formatted_number = formatted_number.replace(',', 'X').replace('.', ',').replace('X', '.')
    elif locale == 'fr_FR':
        # French format: 1 234,56
        formatted_number = f"{decimal_amount:,.{decimal_places}f}"
        formatted_number = formatted_number.replace(',', ' ')
    else:
        # Default to US format
        formatted_number = f"{decimal_amount:,.{decimal_places}f}"
    
    if include_symbol:
        symbol = currency_symbols.get(currency_code, currency_code)
        return f"{symbol}{formatted_number}"
    
    return formatted_number


def format_percentage(value: Optional[float], 
                     decimal_places: int = 1,
                     include_symbol: bool = True) -> str:
    """
    Format percentage with proper precision.
    
    Args:
        value: Percentage value to format
        decimal_places: Number of decimal places (default: 1)
        include_symbol: Include % symbol (default: True)
    
    Returns:
        str: Formatted percentage string
    
    Examples:
        >>> format_percentage(75.5)
        "75.5%"
        >>> format_percentage(0.755, decimal_places=2)
        "75.50%"
        >>> format_percentage(None)
        "0.0%"
    """
    if value is None:
        value = 0
    
    try:
        # Convert to proper percentage if value is between 0 and 1
        if 0 <= value <= 1:
            value = value * 100
        
        formatted_value = f"{value:.{decimal_places}f}"
        
        if include_symbol:
            return f"{formatted_value}%"
        return formatted_value
    except:
        return "0.0%" if include_symbol else "0.0"


def format_date_display(dt: Optional[datetime], 
                       format_style: str = 'medium',
                       include_time: bool = False,
                       timezone_name: str = None) -> str:
    """
    Format datetime for display with timezone handling.
    
    Args:
        dt: Datetime to format
        format_style: Style (short, medium, long, full)
        include_time: Include time component
        timezone_name: Target timezone name
    
    Returns:
        str: Formatted date string
    
    Examples:
        >>> format_date_display(datetime(2024, 12, 1, 14, 30))
        "Dec 1, 2024"
        >>> format_date_display(datetime(2024, 12, 1, 14, 30), include_time=True)
        "Dec 1, 2024, 2:30 PM"
    """
    if not dt:
        return ""
    
    # Handle timezone conversion
    if timezone_name:
        import pytz
        tz = pytz.timezone(timezone_name)
        if dt.tzinfo is None:
            dt = django_timezone.make_aware(dt)
        dt = dt.astimezone(tz)
    elif dt.tzinfo is None:
        dt = django_timezone.make_aware(dt)
    
    # Format patterns based on style
    date_formats = {
        'short': 'n/j/Y',      # 12/1/2024
        'medium': 'M j, Y',     # Dec 1, 2024
        'long': 'F j, Y',       # December 1, 2024
        'full': 'l, F j, Y'     # Sunday, December 1, 2024
    }
    
    time_formats = {
        'short': 'g:i A',       # 2:30 PM
        'medium': 'g:i A',      # 2:30 PM
        'long': 'g:i:s A',      # 2:30:45 PM
        'full': 'g:i:s A T'     # 2:30:45 PM EST
    }
    
    date_format_str = date_formats.get(format_style, date_formats['medium'])
    
    if include_time:
        time_format_str = time_formats.get(format_style, time_formats['medium'])
        return date_format(dt, f"{date_format_str}, {time_format_str}")
    
    return date_format(dt, date_format_str)


def format_phone_display(phone: Optional[str], 
                        format_style: str = 'international',
                        country_code: str = 'US') -> str:
    """
    Format phone number for display.
    
    Args:
        phone: Phone number to format
        format_style: Format style (international, national, local)
        country_code: Country code for parsing
    
    Returns:
        str: Formatted phone number
    
    Examples:
        >>> format_phone_display("+15551234567")
        "+1 555-123-4567"
        >>> format_phone_display("5551234567", "national", "US")
        "(555) 123-4567"
    """
    if not phone:
        return ""
    
    try:
        parsed_number = phonenumbers.parse(phone, country_code)
        
        if format_style == 'international':
            return phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
        elif format_style == 'national':
            return phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL
            )
        elif format_style == 'local':
            formatted = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            # Remove country code for local format
            return re.sub(r'^\+?1\s*', '', formatted)
        else:
            return phone
            
    except phonenumbers.NumberParseException:
        return phone


def format_name_display(first_name: str = "", 
                       middle_name: str = "", 
                       last_name: str = "",
                       format_style: str = 'full',
                       include_middle_initial: bool = True) -> str:
    """
    Format person's name for display.
    
    Args:
        first_name: First name
        middle_name: Middle name
        last_name: Last name
        format_style: Format style (full, first_last, last_first, initials)
        include_middle_initial: Include middle initial
    
    Returns:
        str: Formatted name
    
    Examples:
        >>> format_name_display("John", "Michael", "Smith")
        "John Michael Smith"
        >>> format_name_display("John", "Michael", "Smith", "first_last")
        "John Smith"
        >>> format_name_display("John", "Michael", "Smith", "last_first")
        "Smith, John"
        >>> format_name_display("John", "Michael", "Smith", "initials")
        "J.M.S."
    """
    # Clean inputs
    first_name = (first_name or "").strip()
    middle_name = (middle_name or "").strip()
    last_name = (last_name or "").strip()
    
    if format_style == 'full':
        parts = [first_name]
        if middle_name:
            if include_middle_initial and len(middle_name) > 1:
                parts.append(f"{middle_name[0]}.")
            else:
                parts.append(middle_name)
        if last_name:
            parts.append(last_name)
        return " ".join(parts)
    
    elif format_style == 'first_last':
        parts = [first_name, last_name]
        return " ".join(filter(None, parts))
    
    elif format_style == 'last_first':
        if last_name and first_name:
            return f"{last_name}, {first_name}"
        return " ".join(filter(None, [first_name, last_name]))
    
    elif format_style == 'initials':
        initials = []
        if first_name:
            initials.append(f"{first_name[0].upper()}.")
        if middle_name:
            initials.append(f"{middle_name[0].upper()}.")
        if last_name:
            initials.append(f"{last_name[0].upper()}.")
        return "".join(initials)
    
    elif format_style == 'formal':
        # Mr./Ms. Last Name format
        if last_name:
            return f"Mr./Ms. {last_name}"
        return first_name
    
    else:
        return format_name_display(first_name, middle_name, last_name, 'full')


def format_address_display(address_], 
                          format_style: str = 'multiline',
                          country_code: str = 'US') -> str:
    """
    Format address for display.
    
    Args: containing address fields
        format_style: Format style (multiline, single_line, postal)
        country_code: Country code for format rules
    
    Returns:
        str: Formatted address
    
    Examples:
        >>> format_address_display({
        ...     'street1': '123 Main St',
        ...     'city': 'New York',
        ...     'state': 'NY',
        ...     'postal_code': '10001'
        ... })
        "123 Main St\\nNew York, NY 10001"
    """
    street1 = address_data.get('street1', '').strip()
    street2 = address_data.get('street2', '').strip()
    city = address_data.get('city', '').strip()
    state = address_data.get('state', '').strip()
    postal_code = address_data.get('postal_code', '').strip()
    country = address_data.get('country', '').strip()
    
    if format_style == 'multiline':
        lines = []
        if street1:
            lines.append(street1)
        if street2:
            lines.append(street2)
        
        if country_code == 'US':
            if city and state:
                city_state_zip = f"{city}, {state}"
                if postal_code:
                    city_state_zip += f" {postal_code}"
                lines.append(city_state_zip)
        else:
            # International format
            if city:
                lines.append(city)
            if state:
                lines.append(state)
            if postal_code:
                lines.append(postal_code)
        
        if country and country_code != 'US':
            lines.append(country)
        
        return '\n'.join(lines)
    
    elif format_style == 'single_line':
        parts = []
        if street1:
            parts.append(street1)
        if street2:
            parts.append(street2)
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if postal_code:
            parts.append(postal_code)
        if country and country_code != 'US':
            parts.append(country)
        
        return ', '.join(parts)
    
    elif format_style == 'postal':
        # Postal service format
        lines = []
        if street1:
            lines.append(street1.upper())
        if street2:
            lines.append(street2.upper())
        
        city_line = []
        if city:
            city_line.append(city.upper())
        if state:
            city_line.append(state.upper())
        if postal_code:
            city_line.append(postal_code)
        
        if city_line:
            lines.append(' '.join(city_line))
        
        if country and country_code != 'US':
            lines.append(country.upper())
        
        return '\n'.join(lines)
    
    return format_address_display(address_data, 'multiline', country_code)


def truncate_text(text: str, 
                 max_length: int = 100, 
                 suffix: str = "...",
                 preserve_words: bool = True) -> str:
    """
    Truncate text with smart word boundary handling.
    
    Args:
        text: Text to truncate
        max_length: Maximum length (default: 100)
        suffix: Suffix for truncated text (default: "...")
        preserve_words: Preserve word boundaries (default: True)
    
    Returns:
        str: Truncated text
    
    Examples:
        >>> truncate_text("This is a very long text that needs truncating", 20)
        "This is a very long..."
        >>> truncate_text("This is a very long text", 20, preserve_words=False)
        "This is a very lo..."
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    if not preserve_words:
        return text[:max_length - len(suffix)] + suffix
    
    # Find the last space within the limit
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


def format_number(number: Optional[float], 
                 decimal_places: int = 0,
                 include_commas: bool = True,
                 signed: bool = False) -> str:
    """
    Format number with proper thousand separators.
    
    Args:
        number: Number to format
        decimal_places: Number of decimal places
        include_commas: Include thousand separators
        signed: Show + for positive numbers
    
    Returns:
        str: Formatted number
    
    Examples:
        >>> format_number(1234567.89, 2)
        "1,234,567.89"
        >>> format_number(1234, signed=True)
        "+1,234"
    """
    if number is None:
        return "0"
    
    try:
        if include_commas:
            formatted = f"{number:,.{decimal_places}f}"
        else:
            formatted = f"{number:.{decimal_places}f}"
        
        if signed and number > 0:
            formatted = f"+{formatted}"
        
        return formatted
    except:
        return str(number)


def format_duration(seconds: int, 
                   style: str = 'long') -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        style: Format style (long, short, compact)
    
    Returns:
        str: Formatted duration
    
    Examples:
        >>> format_duration(3661)
        "1 hour, 1 minute, 1 second"
        >>> format_duration(3661, 'short')
        "1h 1m 1s"
        >>> format_duration(3661, 'compact')
        "01:01:01"
    """
    if seconds < 0:
        return "0 seconds" if style == 'long' else "0s" if style == 'short' else "00:00:00"
    
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if style == 'compact':
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    elif style == 'short':
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)
    
    else:  # long format
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{pluralize(hours)}")
        if minutes > 0:
            parts.append(f"{minutes} minute{pluralize(minutes)}")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} second{pluralize(seconds)}")
        return ", ".join(parts)


def format_file_size_display(size_bytes: int, 
                           decimal_places: int = 1) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        decimal_places: Number of decimal places
    
    Returns:
        str: Formatted file size
    
    Examples:
        >>> format_file_size_display(1024)
        "1.0 KB"
        >>> format_file_size_display(1536, 2)
        "1.50 KB"
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    if i == 0:  # Bytes - no decimal places
        return f"{int(size)} {size_names[i]}"
    else:
        return f"{size:.{decimal_places}f} {size_names[i]}"


def format_list_display(items: List[str], 
                       conjunction: str = "and",
                       max_items: int = None) -> str:
    """
    Format list of items for display with proper grammar.
    
    Args:
        items: List of items to format
        conjunction: Conjunction word (default: "and")
        max_items: Maximum items to show before truncating
    
    Returns:
        str: Formatted list
    
    Examples:
        >>> format_list_display(["apple", "banana", "orange"])
        "apple, banana, and orange"
        >>> format_list_display(["apple", "banana"], "or")
        "apple or banana"
    """
    if not items:
        return ""
    
    # Remove empty items and duplicates while preserving order
    unique_items = []
    for item in items:
        if item and item not in unique_items:
            unique_items.append(item)
    
    if max_items and len(unique_items) > max_items:
        displayed_items = unique_items[:max_items]
        remaining_count = len(unique_items) - max_items
        displayed_items.append(f"{remaining_count} more")
        unique_items = displayed_items
    
    if len(unique_items) == 0:
        return ""
    elif len(unique_items) == 1:
        return unique_items[0]
    elif len(unique_items) == 2:
        return f"{unique_items[0]} {conjunction} {unique_items[1]}"
    else:
        return f"{', '.join(unique_items[:-1])}, {conjunction} {unique_items[-1]}"


def format_initials(name: str, max_initials: int = 2) -> str:
    """
    Extract and format initials from name.
    
    Args:
        name: Full name
        max_initials: Maximum number of initials
    
    Returns:
        str: Formatted initials
    
    Examples:
        >>> format_initials("John Michael Smith")
        "JS"
        >>> format_initials("John Michael Smith", 3)
        "JMS"
    """
    if not name:
        return ""
    
    # Split name and get initials
    words = name.strip().split()
    initials = []
    
    for word in words[:max_initials]:
        if word and word[0].isalpha():
            initials.append(word[0].upper())
    
    return "".join(initials)


class CRMFormatter:
    """
    CRM-specific formatting utilities.
    """
    
    @staticmethod
    def format_lead_score(score: Optional[int]) -> str:
        """Format lead score with color coding info."""
        if score is None:
            return "N/A"
        
        # Return score with grade
        if score >= 80:
            grade = "Hot"
        elif score >= 60:
            grade = "Warm"
        elif score >= 40:
            grade = "Cold"
        else:
            grade = "Unqualified"
        
        return f"{score} ({grade})"
    
    @staticmethod
    def format_opportunity_stage(stage: str, probability: Optional[int] = None) -> str:
        """Format opportunity stage with probability."""
        if not stage:
            return "Unknown"
        
        formatted_stage = stage.replace('_', ' ').title()
        
        if probability is not None:
            return f"{formatted_stage} ({probability}%)"
        
        return formatted_stage
    
    @staticmethod
    def format_activity_summary(activity_type: str, subject: str, max_length: int = 50) -> str:
        """Format activity summary for display."""
        type_display = activity_type.replace('_', ' ').title()
        
        if subject:
            summary = f"{type_display}: {subject}"
        else:
            summary = type_display
        
        return truncate_text(summary, max_length, preserve_words=True)
    
    @staticmethod
    def format_customer_display(customer_]) -> str:
        """Format customer information for display."""
        if not customer Customer"
        
        # Try different name combinations
        if customer_data.get('company_name'):
            return customer_data['company_name']
        
        name = format_name_display(
            customer_data.get('first_name', ''),
            customer_data.get('middle_name', ''),
            customer_data.get('last_name', ''),
            'first_last'
        )
        
        if name.strip():
            return name
        
        if customer_data.get('email'):
            return customer_data['email']
        
        return f"Customer #{customer_data.get('id', 'Unknown')}"