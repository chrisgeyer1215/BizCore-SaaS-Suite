from decimal import Decimal, ROUND_HALF_UP
from typing import Union
from .base import ValueObject


class Money(ValueObject):
    """Money value object with currency"""
    
    SUPPORTED_CURRENCIES = {'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'}
    
    def __init__(self, amount: Union[int, float, str, Decimal], currency: str = 'USD'):
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}")
        
        # Convert to Decimal for precision
        if isinstance(amount, (int, float, str)):
            amount = Decimal(str(amount))
        elif not isinstance(amount, Decimal):
            raise ValueError(f"Invalid amount type: {type(amount)}")
        
        # Round to 2 decimal places
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        
        super().__init__(amount=amount, currency=currency)
        object.__setattr__(self, '_initialized', True)
    
    @property
    def amount(self) -> Decimal:
        return self.__dict__['amount']
    
    @property
    def currency(self) -> str:
        return self.__dict__['currency']
    
    def __str__(self):
        return f"{self.amount} {self.currency}"
    
    def __add__(self, other: 'Money') -> 'Money':
        if not isinstance(other, Money):
            raise TypeError("Can only add Money to Money")
        if self.currency != other.currency:
            raise ValueError(f"Cannot add different currencies: {self.currency} and {other.currency}")
        
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        if not isinstance(other, Money):
            raise TypeError("Can only subtract Money from Money")
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract different currencies: {self.currency} and {other.currency}")
        
        return Money(self.amount - other.amount, self.currency)
    
    def __mul__(self, factor: Union[int, float, Decimal]) -> 'Money':
        if not isinstance(factor, (int, float, Decimal)):
            raise TypeError("Can only multiply Money by number")
        
        return Money(self.amount * Decimal(str(factor)), self.currency)
    
    def __truediv__(self, divisor: Union[int, float, Decimal]) -> 'Money':
        if not isinstance(divisor, (int, float, Decimal)):
            raise TypeError("Can only divide Money by number")
        if divisor == 0:
            raise ValueError("Cannot divide by zero")
        
        return Money(self.amount / Decimal(str(divisor)), self.currency)
    
    def is_zero(self) -> bool:
        return self.amount == 0
    
    def is_positive(self) -> bool:
        return self.amount > 0
    
    @classmethod
    def zero(cls, currency: str = 'USD') -> 'Money':
        """Create zero money"""
        return cls(0, currency)
    
    def to_cents(self) -> int:
        """Convert to cents (for payment processing)"""
        return int(self.amount * 100)
    
    @classmethod
    def from_cents(cls, cents: int, currency: str = 'USD') -> 'Money':
        """Create from cents"""
        return cls(Decimal(cents) / 100, currency)