"""
Tax Management Models
Tax codes, groups, and multi-jurisdictional tax support
"""

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

from apps.core.models import TenantBaseModel


class TaxCode(TenantBaseModel):
    """Enhanced tax code definitions with multi-jurisdictional support"""
    
    TAX_TYPE_CHOICES = [
        ('SALES_TAX', 'Sales Tax'),
        ('VAT', 'Value Added Tax'),
        ('GST', 'Goods and Services Tax'),
        ('EXCISE', 'Excise Tax'),
        ('WITHHOLDING', 'Withholding Tax'),
        ('IMPORT_DUTY', 'Import Duty'),
        ('OTHER', 'Other Tax'),
    ]
    
    CALCULATION_METHOD_CHOICES = [
        ('PERCENTAGE', 'Percentage of Amount'),
        ('FIXED', 'Fixed Amount'),
        ('COMPOUND', 'Compound Tax'),
        ('TIERED', 'Tiered Rate'),
    ]
    
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES)
    
    # Tax Calculation
    calculation_method = models.CharField(
        max_length=20,
        choices=CALCULATION_METHOD_CHOICES,
        default='PERCENTAGE'
    )
    rate = models.DecimalField(max_digits=8, decimal_places=4)
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Jurisdictional Information
    country = models.CharField(max_length=2, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Tax Accounts
    tax_collected_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        related_name='tax_codes_collected'
    )
    tax_paid_account = models.ForeignKey(
        'finance.Account',
        on_delete=models.PROTECT,
        related_name='tax_codes_paid',
        null=True,
        blank=True
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_compound = models.BooleanField(default=False)
    is_recoverable = models.BooleanField(default=True)
    apply_to_shipping = models.BooleanField(default=False)
    apply_to_discount = models.BooleanField(default=True)
    
    # Effective Dates
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    
    # Reporting
    tax_authority = models.CharField(max_length=200, blank=True)
    reporting_code = models.CharField(max_length=50, blank=True)
    filing_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
            ('SEMI_ANNUALLY', 'Semi-Annually'),
        ],
        blank=True
    )
    
    # Tax Tiers for tiered calculation
    tax_tiers = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['code']
        db_table = 'finance_tax_codes'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_tax_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'tax_type', 'is_active']),
            models.Index(fields=['tenant', 'country', 'state_province']),
        ]
        
    def __str__(self):
        return f'{self.code} - {self.name} ({self.rate}%)'
    
    def clean(self):
        """Validate tax code"""
        if self.rate < 0 or self.rate > 100:
            raise ValidationError('Tax rate must be between 0 and 100')
        
        if self.effective_from and self.effective_to:
            if self.effective_from >= self.effective_to:
                raise ValidationError('Effective from date must be before effective to date')
        
        if self.calculation_method == 'FIXED' and not self.fixed_amount:
            raise ValidationError('Fixed amount is required for fixed calculation method')
        
        if self.calculation_method == 'TIERED' and not self.tax_tiers:
            raise ValidationError('Tax tiers are required for tiered calculation method')
    
    def calculate_tax(self, amount, include_shipping=False, discount_amount=None):
        """Calculate tax amount for given base amount"""
        if not self.is_active or not self.is_effective():
            return Decimal('0.00')
        
        base_amount = amount
        
        # Apply shipping logic
        if not include_shipping and not self.apply_to_shipping:
            # Shipping amount would need to be passed separately
            pass
        
        # Apply discount logic
        if discount_amount and not self.apply_to_discount:
            base_amount += discount_amount
        
        if self.calculation_method == 'PERCENTAGE':
            return base_amount * (self.rate / Decimal('100'))
        elif self.calculation_method == 'FIXED':
            return self.fixed_amount or Decimal('0.00')
        elif self.calculation_method == 'TIERED':
            return self.calculate_tiered_tax(base_amount)
        elif self.calculation_method == 'COMPOUND':
            # Compound tax needs to be calculated with other taxes
            return base_amount * (self.rate / Decimal('100'))
        
        return Decimal('0.00')
    
    def calculate_tiered_tax(self, amount):
        """Calculate tax using tiered rates"""
        if not self.tax_tiers:
            return Decimal('0.00')
        
        total_tax = Decimal('0.00')
        remaining_amount = amount
        
        for tier in self.tax_tiers:
            tier_min = Decimal(str(tier.get('min_amount', 0)))
            tier_max = Decimal(str(tier.get('max_amount', 0)))
            tier_rate = Decimal(str(tier.get('rate', 0)))
            
            if remaining_amount <= 0:
                break
            
            if tier_max > 0:
                taxable_amount = min(remaining_amount, tier_max - tier_min)
            else:
                taxable_amount = remaining_amount
            
            tier_tax = taxable_amount * (tier_rate / Decimal('100'))
            total_tax += tier_tax
            remaining_amount -= taxable_amount
        
        return total_tax
    
    def is_effective(self, check_date=None):
        """Check if tax code is effective on given date"""
        if not check_date:
            check_date = date.today()
        
        if self.effective_from and check_date < self.effective_from:
            return False
        
        if self.effective_to and check_date > self.effective_to:
            return False
        
        return True
    
    def get_jurisdiction_display(self):
        """Get formatted jurisdiction display"""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state_province:
            parts.append(self.state_province)
        if self.country:
            parts.append(self.country)
        
        return ', '.join(parts) if parts else 'Not Specified'


class TaxGroup(TenantBaseModel):
    """Group multiple tax codes for complex tax scenarios"""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    tax_codes = models.ManyToManyField(TaxCode, through='TaxGroupItem')
    is_active = models.BooleanField(default=True)
    
    # Group settings
    calculation_order = models.CharField(
        max_length=20,
        choices=[
            ('SEQUENTIAL', 'Sequential (tax on tax)'),
            ('PARALLEL', 'Parallel (tax on base only)'),
        ],
        default='PARALLEL'
    )
    
    class Meta:
        ordering = ['name']
        db_table = 'finance_tax_groups'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_tax_group'
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def calculate_total_tax(self, amount, include_shipping=False, discount_amount=None):
        """Calculate total tax from all codes in group"""
        total_tax = Decimal('0.00')
        current_base = amount
        
        # Apply discount to base if applicable
        if discount_amount:
            current_base = amount - discount_amount
        
        for item in self.tax_group_items.filter(is_active=True).order_by('sequence'):
            tax_code = item.tax_code
            
            if self.calculation_order == 'SEQUENTIAL':
                # Tax on tax - use accumulated amount
                base_amount = current_base + total_tax
            else:
                # Parallel - always use original base
                base_amount = current_base
            
            tax_amount = tax_code.calculate_tax(
                base_amount,
                include_shipping=include_shipping,
                discount_amount=discount_amount if self.calculation_order == 'PARALLEL' else None
            )
            total_tax += tax_amount
        
        return total_tax
    
    def get_effective_rate(self, amount=Decimal('100.00')):
        """Get effective tax rate for the group"""
        if amount <= 0:
            return Decimal('0.00')
        
        total_tax = self.calculate_total_tax(amount)
        return (total_tax / amount) * Decimal('100')


class TaxGroupItem(TenantBaseModel):
    """Individual tax codes within a tax group"""
    
    APPLY_TO_CHOICES = [
        ('SUBTOTAL', 'Apply to Subtotal Only'),
        ('SUBTOTAL_PLUS_TAX', 'Apply to Subtotal Plus Previous Taxes'),
    ]
    
    tax_group = models.ForeignKey(
        TaxGroup,
        on_delete=models.CASCADE,
        related_name='tax_group_items'
    )
    tax_code = models.ForeignKey(TaxCode, on_delete=models.CASCADE)
    sequence = models.IntegerField(default=1)
    apply_to = models.CharField(
        max_length=20,
        choices=APPLY_TO_CHOICES,
        default='SUBTOTAL'
    )
    is_active = models.BooleanField(default=True)
    
    # Override settings
    override_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Override the tax code rate for this group"
    )
    
    class Meta:
        ordering = ['tax_group', 'sequence']
        db_table = 'finance_tax_group_items'
        constraints = [
            models.UniqueConstraint(
                fields=['tax_group', 'tax_code'],
                name='unique_tax_group_code'
            ),
        ]
        
    def __str__(self):
        return f'{self.tax_group.name} - {self.tax_code.name}'
    
    def get_effective_rate(self):
        """Get the effective rate for this item"""
        if self.override_rate is not None:
            return self.override_rate
        return self.tax_code.rate
    
    def calculate_tax(self, amount):
        """Calculate tax for this specific item"""
        effective_rate = self.get_effective_rate()
        return amount * (effective_rate / Decimal('100'))


class TaxJurisdiction(TenantBaseModel):
    """Tax jurisdictions for location-based tax calculation"""
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    jurisdiction_type = models.CharField(
        max_length=20,
        choices=[
            ('COUNTRY', 'Country'),
            ('STATE', 'State/Province'),
            ('COUNTY', 'County'),
            ('CITY', 'City'),
            ('DISTRICT', 'District'),
        ]
    )
    
    # Geographic Information
    country = models.CharField(max_length=2)
    state_province = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_codes = models.JSONField(default=list, blank=True)
    
    # Parent Jurisdiction
    parent_jurisdiction = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_jurisdictions'
    )
    
    # Default Tax Codes
    default_sales_tax = models.ForeignKey(
        TaxCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_jurisdictions'
    )
    default_purchase_tax = models.ForeignKey(
        TaxCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_jurisdictions'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['jurisdiction_type', 'name']
        db_table = 'finance_tax_jurisdictions'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_tenant_tax_jurisdiction'
            ),
        ]
        
    def __str__(self):
        return f'{self.name} ({self.jurisdiction_type})'
    
    def get_applicable_tax_codes(self, tax_type='SALES_TAX'):
        """Get all applicable tax codes for this jurisdiction"""
        tax_codes = TaxCode.objects.filter(
            tenant=self.tenant,
            is_active=True,
            country=self.country
        )
        
        if self.state_province:
            tax_codes = tax_codes.filter(state_province=self.state_province)
        
        if self.city:
            tax_codes = tax_codes.filter(city=self.city)
        
        return tax_codes.filter(tax_type=tax_type)
    
    def matches_address(self, address):
        """Check if this jurisdiction matches a given address"""
        if not address:
            return False
        
        # Country check
        if address.get('country') != self.country:
            return False
        
        # State/Province check
        if self.state_province and address.get('state') != self.state_province:
            return False
        
        # City check  
        if self.city and address.get('city') != self.city:
            return False
        
        # Postal code check
        if self.postal_codes and address.get('postal_code'):
            return address.get('postal_code') in self.postal_codes
        
        return True