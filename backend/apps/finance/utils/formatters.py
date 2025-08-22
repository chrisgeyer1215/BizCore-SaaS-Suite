"""
Finance Formatters Utilities
Number and currency formatting utilities
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional

class CurrencyFormatter:
    """Currency formatting utilities"""
    
    CURRENCY_FORMATS = {
        'USD': {'symbol': '$', 'position': 'before', 'decimal_places': 2},
        'EUR': {'symbol': '€', 'position': 'before', 'decimal_places': 2},
        'GBP': {'symbol': '£', 'position': 'before', 'decimal_places': 2},
    }
    
    @classmethod
    def format_currency(cls, amount: Union[Decimal, float, int], 
                       currency_code: str = 'USD',
                       show_symbol: bool = True) -> str:
        """Format amount as currency"""
        if amount is None:
            return ''
        
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        currency_format = cls.CURRENCY_FORMATS.get(currency_code.upper(), {
            'symbol': currency_code,
            'position': 'before',
            'decimal_places': 2
        })
        
        places = currency_format['decimal_places']
        rounded_amount = amount.quantize(
            Decimal('0.' + '0' * places), 
            rounding=ROUND_HALF_UP
        )
        
        if places == 0:
            formatted_number = f"{int(rounded_amount):,}"
        else:
            formatted_number = f"{float(rounded_amount):,.{places}f}"
        
        if show_symbol and currency_format['symbol']:
            if currency_format['position'] == 'before':
                return f"{currency_format['symbol']}{formatted_number}"
            else:
                return f"{formatted_number}{currency_format['symbol']}"
        
        return formatted_number


class NumberFormatter:
    """Number formatting utilities"""
    
    @staticmethod
    def format_number(number: Union[Decimal, float, int], 
                     decimal_places: int = 2,
                     use_commas: bool = True) -> str:
        """Format number with specified options"""
        if number is None:
            return ''
        
        if not isinstance(number, Decimal):
            number = Decimal(str(number))
        
        rounded_number = number.quantize(
            Decimal('0.' + '0' * decimal_places), 
            rounding=ROUND_HALF_UP
        )
        
        if decimal_places == 0:
            formatted = f"{int(rounded_number)}"
        else:
            formatted = f"{float(rounded_number):.{decimal_places}f}"
        
        if use_commas:
            parts = formatted.split('.')
            parts[0] = f"{int(parts[0]):,}"
            formatted = '.'.join(parts)
        
        return formatted
    
    @staticmethod
    def format_percentage(value: Union[Decimal, float, int],
                         decimal_places: int = 2) -> str:
        """Format value as percentage"""
        if value is None:
            return ''
        
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        percentage = value.quantize(
            Decimal('0.' + '0' * decimal_places), 
            rounding=ROUND_HALF_UP
        )
        
        return f"{percentage}%"


class DateFormatter:
    """Date formatting utilities"""
    
    @staticmethod
    def format_date(date_obj, format_type: str = 'short') -> str:
        """Format date in various formats"""
        if not date_obj:
            return ''
        
        if format_type == 'short':
            return date_obj.strftime('%m/%d/%Y')
        elif format_type == 'long':
            return date_obj.strftime('%B %d, %Y')
        elif format_type == 'iso':
            return date_obj.strftime('%Y-%m-%d')
        else:
            return date_obj.strftime('%m/%d/%Y')
