"""
Finance Validators Utilities
Custom validation functions
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class FinancialValidators:
    """Financial data validation utilities"""
    
    @staticmethod
    def validate_account_code(code: str, max_length: int = 20) -> bool:
        """Validate account code format"""
        if not code:
            raise ValidationError(_('Account code is required'))
        
        if len(code) > max_length:
            raise ValidationError(_(f'Account code cannot exceed {max_length} characters'))
        
        return True
    
    @staticmethod
    def validate_journal_entry_balance(debits: list, credits: list, tolerance: Decimal = Decimal('0.01')) -> bool:
        """Validate that journal entry debits equal credits"""
        total_debits = sum(debits) if debits else Decimal('0.00')
        total_credits = sum(credits) if credits else Decimal('0.00')
        
        if abs(total_debits - total_credits) > tolerance:
            raise ValidationError(_('Journal entry must balance'))
        
        return True
    
    @staticmethod
    def validate_tax_rate(rate: Decimal) -> bool:
        """Validate tax rate percentage"""
        if rate < 0 or rate > 100:
            raise ValidationError(_('Tax rate must be between 0 and 100 percent'))
        
        return True


class DocumentValidators:
    """Document validation utilities"""
    
    @staticmethod
    def validate_invoice_number(number: str, prefix: str = 'INV') -> bool:
        """Validate invoice number format"""
        if not number:
            raise ValidationError(_('Invoice number is required'))
        
        if not number.startswith(prefix):
            raise ValidationError(_(f'Invoice number must start with {prefix}'))
        
        return True
