from datetime import datetime
from typing import Optional
from .money import Money
from .base import ValueObject


class Price(ValueObject):
    """Price value object with additional pricing metadata"""
    
    def __init__(
        self, 
        amount: Money, 
        list_price: Optional[Money] = None,
        cost_price: Optional[Money] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None
    ):
        if list_price and list_price.currency != amount.currency:
            raise ValueError("List price must have same currency as amount")
        
        if cost_price and cost_price.currency != amount.currency:
            raise ValueError("Cost price must have same currency as amount")
        
        super().__init__(
            amount=amount,
            list_price=list_price or amount,
            cost_price=cost_price,
            valid_from=valid_from or datetime.utcnow(),
            valid_until=valid_until
        )
        object.__setattr__(self, '_initialized', True)
    
    @property
    def amount(self) -> Money:
        return self.__dict__['amount']
    
    @property
    def list_price(self) -> Money:
        return self.__dict__['list_price']
    
    @property
    def cost_price(self) -> Optional[Money]:
        return self.__dict__['cost_price']
    
    @property
    def valid_from(self) -> datetime:
        return self.__dict__['valid_from']
    
    @property
    def valid_until(self) -> Optional[datetime]:
        return self.__dict__['valid_until']
    
    def is_valid_at(self, when: datetime = None) -> bool:
        """Check if price is valid at given time"""
        when = when or datetime.utcnow()
        
        if when < self.valid_from:
            return False
        
        if self.valid_until and when > self.valid_until:
            return False
        
        return True
    
    def has_discount(self) -> bool:
        """Check if price is discounted from list price"""
        return self.amount < self.list_price
    
    def discount_amount(self) -> Money:
        """Get discount amount"""
        if not self.has_discount():
            return Money.zero(self.amount.currency)
        
        return self.list_price - self.amount
    
    def discount_percentage(self) -> float:
        """Get discount percentage"""
        if not self.has_discount() or self.list_price.is_zero():
            return 0.0
        
        discount = self.discount_amount()
        return float((discount.amount / self.list_price.amount) * 100)
    
    def margin(self) -> Optional[Money]:
        """Get profit margin (if cost price is available)"""
        if not self.cost_price:
            return None
        
        return self.amount - self.cost_price
    
    def margin_percentage(self) -> Optional[float]:
        """Get profit margin percentage"""
        margin = self.margin()
        if not margin or self.amount.is_zero():
            return None
        
        return float((margin.amount / self.amount.amount) * 100)
    
    @classmethod
    def create_with_discount(
        cls, 
        list_price: Money, 
        discount_percentage: float,
        **kwargs
    ) -> 'Price':
        """Create price with discount percentage"""
        if not 0 <= discount_percentage <= 100:
            raise ValueError("Discount percentage must be between 0 and 100")
        
        discount_factor = 1 - (discount_percentage / 100)
        discounted_amount = list_price * discount_factor
        
        return cls(amount=discounted_amount, list_price=list_price, **kwargs)