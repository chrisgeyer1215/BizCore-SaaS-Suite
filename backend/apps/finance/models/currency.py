"""
Currency and Exchange Rate Models
Multi-currency support for the finance module
"""

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel


class Currency(TenantBaseModel):
    """Currency definitions with exchange rates"""
    
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    decimal_places = models.IntegerField(default=2)
    is_active = models.BooleanField(default=True)
    is_base_currency = models.BooleanField(default=False)
    
    # Display settings
    symbol_position = models.CharField(
        max_length=10,
        choices=[
            ('BEFORE', 'Before Amount ($100)'),
            ('AFTER', 'After Amount (100$)'),
            ('BEFORE_SPACE', 'Before with Space ($ 100)'),
            ('AFTER_SPACE', 'After with Space (100 $)'),
        ],
        default='BEFORE'
    )
    
    # Rounding settings
    rounding_method = models.CharField(
        max_length=20,
        choices=[
            ('ROUND_HALF_UP', 'Round Half Up'),
            ('ROUND_HALF_DOWN', 'Round Half Down'),
            ('ROUND_UP', 'Round Up'),
            ('ROUND_DOWN', 'Round Down'),
        ],
        default='ROUND_HALF_UP'
    )
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Currencies'
        db_table = 'finance_currencies'
        
    def __str__(self):
        return f'{self.code} - {self.name}'
    
    def clean(self):
        """Validate currency"""
        if self.decimal_places < 0 or self.decimal_places > 6:
            raise ValidationError('Decimal places must be between 0 and 6')
        
        if len(self.code) != 3:
            raise ValidationError('Currency code must be exactly 3 characters')
        
        if self.code != self.code.upper():
            self.code = self.code.upper()
    
    def format_amount(self, amount):
        """Format amount with currency symbol and proper decimal places"""
        if amount is None:
            amount = Decimal('0.00')
        
        # Round amount to currency decimal places
        decimal_places = self.decimal_places
        rounded_amount = amount.quantize(Decimal('0.1') ** decimal_places)
        
        # Format with proper decimal places
        if decimal_places == 0:
            formatted = f"{rounded_amount:,.0f}"
        else:
            formatted = f"{rounded_amount:,.{decimal_places}f}"
        
        # Add currency symbol based on position
        if self.symbol_position == 'BEFORE':
            return f"{self.symbol}{formatted}"
        elif self.symbol_position == 'AFTER':
            return f"{formatted}{self.symbol}"
        elif self.symbol_position == 'BEFORE_SPACE':
            return f"{self.symbol} {formatted}"
        elif self.symbol_position == 'AFTER_SPACE':
            return f"{formatted} {self.symbol}"
        else:
            return f"{self.symbol}{formatted}"


class ExchangeRate(TenantBaseModel):
    """Exchange rates for multi-currency support"""
    
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_from'
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_to'
    )
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    effective_date = models.DateField()
    created_date = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, blank=True)  # API source like 'xe.com', 'manual'
    
    # Rate metadata
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Historical tracking
    high_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    low_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    volatility = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    class Meta:
        ordering = ['-effective_date']
        db_table = 'finance_exchange_rates'
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'effective_date']),
            models.Index(fields=['effective_date', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'from_currency', 'to_currency', 'effective_date'],
                name='unique_tenant_exchange_rate'
            ),
        ]
        
    def __str__(self):
        return f'{self.from_currency.code} to {self.to_currency.code}: {self.rate} ({self.effective_date})'
    
    def clean(self):
        """Validate exchange rate"""
        if self.rate <= 0:
            raise ValidationError('Exchange rate must be positive')
        
        if self.from_currency == self.to_currency:
            raise ValidationError('From and to currencies cannot be the same')
        
        if self.high_rate and self.high_rate < self.rate:
            raise ValidationError('High rate cannot be less than current rate')
        
        if self.low_rate and self.low_rate > self.rate:
            raise ValidationError('Low rate cannot be greater than current rate')
    
    @classmethod
    def get_rate(cls, tenant, from_currency, to_currency, as_of_date=None):
        """Get exchange rate for currency conversion"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Same currency conversion
        if from_currency == to_currency:
            return Decimal('1.000000')
        
        # Direct rate lookup
        rate = cls.objects.filter(
            tenant=tenant,
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date__lte=as_of_date,
            is_active=True
        ).order_by('-effective_date').first()
        
        if rate:
            return rate.rate
        
        # Try inverse rate
        inverse_rate = cls.objects.filter(
            tenant=tenant,
            from_currency=to_currency,
            to_currency=from_currency,
            effective_date__lte=as_of_date,
            is_active=True
        ).order_by('-effective_date').first()
        
        if inverse_rate:
            return Decimal('1.000000') / inverse_rate.rate
        
        # Try conversion through base currency
        base_currency = cls.get_base_currency(tenant)
        if base_currency and base_currency not in [from_currency, to_currency]:
            from_base_rate = cls.get_rate(tenant, from_currency, base_currency, as_of_date)
            to_base_rate = cls.get_rate(tenant, base_currency, to_currency, as_of_date)
            
            if from_base_rate and to_base_rate:
                return from_base_rate * to_base_rate
        
        return Decimal('1.000000')  # Default to 1:1 if no rate found
    
    @classmethod
    def get_base_currency(cls, tenant):
        """Get the base currency for a tenant"""
        try:
            return Currency.objects.get(tenant=tenant, is_base_currency=True)
        except Currency.DoesNotExist:
            return None
    
    @classmethod
    def convert_amount(cls, tenant, amount, from_currency, to_currency, as_of_date=None):
        """Convert amount from one currency to another"""
        if not amount:
            return Decimal('0.00')
        
        rate = cls.get_rate(tenant, from_currency, to_currency, as_of_date)
        return amount * rate
    
    def calculate_inverse_rate(self):
        """Calculate the inverse exchange rate"""
        if self.rate > 0:
            return Decimal('1.000000') / self.rate
        return Decimal('1.000000')
    
    def update_volatility(self):
        """Update volatility based on recent rates"""
        recent_rates = ExchangeRate.objects.filter(
            tenant=self.tenant,
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            effective_date__gte=self.effective_date - timedelta(days=30),
            is_active=True
        ).values_list('rate', flat=True)
        
        if len(recent_rates) > 1:
            rates_list = list(recent_rates)
            mean_rate = sum(rates_list) / len(rates_list)
            variance = sum((r - mean_rate) ** 2 for r in rates_list) / len(rates_list)
            self.volatility = (variance ** 0.5) / mean_rate
            self.save(update_fields=['volatility'])