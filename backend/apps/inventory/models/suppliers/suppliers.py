"""
Supplier and vendor management models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from ..abstract.base import TenantBaseModel, SoftDeleteMixin, ActivatableMixin
from ...managers.base import InventoryManager


class Supplier(TenantBaseModel, SoftDeleteMixin, ActivatableMixin):
    """
    Comprehensive supplier management with performance tracking
    """
    
    SUPPLIER_TYPES = [
        ('MANUFACTURER', 'Manufacturer'),
        ('WHOLESALER', 'Wholesaler'),
        ('DISTRIBUTOR', 'Distributor'),
        ('RETAILER', 'Retailer'),
        ('DROPSHIPPER', 'Drop Shipper'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('CONSIGNMENT', 'Consignment'),
    ]
    
    PAYMENT_TERMS = [
        ('NET_0', 'Net 0 (Cash)'),
        ('NET_7', 'Net 7'),
        ('NET_15', 'Net 15'),
        ('NET_30', 'Net 30'),
        ('NET_45', 'Net 45'),
        ('NET_60', 'Net 60'),
        ('NET_90', 'Net 90'),
        ('COD', 'Cash on Delivery'),
        ('PREPAID', 'Prepaid'),
        ('CREDIT_CARD', 'Credit Card'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    company_name = models.CharField(max_length=200, blank=True)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPES, default='WHOLESALER')
    
    # Legal Information
    tax_id = models.CharField(max_length=50, blank=True)
    vat_number = models.CharField(max_length=50, blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    
    # Contact Information
    contact_person = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # Billing Address (if different)
    billing_same_as_shipping = models.BooleanField(default=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    
    # Financial Terms
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS, default='NET_30')
    payment_terms_days = models.IntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_used = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Banking Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    # Performance Metrics
    lead_time_days = models.IntegerField(default=7)
    minimum_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_order_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Ratings & Reviews
    quality_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    service_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    overall_rating = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Drop Shipping
    supports_dropshipping = models.BooleanField(default=False)
    dropship_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    dropship_handling_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Integration
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    edi_capability = models.BooleanField(default=False)
    
    # Status & Preferences
    is_preferred = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_minority_owned = models.BooleanField(default=False)
    is_woman_owned = models.BooleanField(default=False)
    
    # Documents & Certifications
    certifications = models.JSONField(default=list, blank=True)
    insurance_certificate = models.FileField(upload_to='supplier_docs/', blank=True, null=True)
    tax_certificate = models.FileField(upload_to='supplier_docs/', blank=True, null=True)
    
    # Additional Information
    return_policy = models.TextField(blank=True)
    warranty_terms = models.TextField(blank=True)
    special_terms = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_suppliers'
        ordering = ['-is_preferred', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'code'], 
                name='unique_tenant_supplier_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'code']),
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['tenant_id', 'supplier_type']),
            models.Index(fields=['tenant_id', 'is_preferred']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def credit_available(self):
        """Available credit limit"""
        return self.credit_limit - self.credit_used
    
    @property
    def credit_utilization_percentage(self):
        """Credit utilization as percentage"""
        if self.credit_limit > 0:
            return (self.credit_used / self.credit_limit * 100).quantize(Decimal('0.01'))
        return Decimal('0')
    
    @property
    def full_address(self):
        """Get formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            f"{self.city}, {self.state} {self.postal_code}",
            self.country
        ]
        return ", ".join(filter(None, address_parts))
    
    def update_overall_rating(self):
        """Calculate and update overall rating"""
        ratings = [self.quality_rating, self.delivery_rating, self.service_rating]
        valid_ratings = [r for r in ratings if r > 0]
        
        if valid_ratings:
            self.overall_rating = sum(valid_ratings) / len(valid_ratings)
            self.save(update_fields=['overall_rating'])


class SupplierContact(TenantBaseModel, ActivatableMixin):
    """
    Additional contacts for suppliers
    """
    
    CONTACT_TYPES = [
        ('PRIMARY', 'Primary Contact'),
        ('SALES', 'Sales Representative'),
        ('SUPPORT', 'Customer Support'),
        ('TECHNICAL', 'Technical Support'),
        ('BILLING', 'Billing/Accounts'),
        ('SHIPPING', 'Shipping/Logistics'),
        ('EMERGENCY', 'Emergency Contact'),
    ]
    
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_supplier_contacts'
        ordering = ['supplier', '-is_primary', 'name']
        indexes = [
            models.Index(fields=['tenant_id', 'supplier', 'is_active']),
            models.Index(fields=['tenant_id', 'contact_type']),
        ]
    
    def __str__(self):
        return f"{self.supplier.name} - {self.name} ({self.contact_type})"