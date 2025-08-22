"""
Batch and serial number tracking models
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from apps.core.models import TenantBaseModel
from ..abstract.base import ActivatableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class Batch(TenantBaseModel):
    """
    Enhanced batch/lot tracking for products with quality management
    """
    
    BATCH_STATUS = [
        ('ACTIVE', 'Active'),
        ('QUARANTINED', 'Quarantined'),
        ('EXPIRED', 'Expired'),
        ('RECALLED', 'Recalled'),
        ('CONSUMED', 'Fully Consumed'),
        ('REJECTED', 'Rejected'),
    ]
    
    QUALITY_GRADES = [
        ('A', 'Grade A - Premium'),
        ('B', 'Grade B - Standard'),
        ('C', 'Grade C - Lower Grade'),
        ('D', 'Grade D - Substandard'),
    ]
    
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='batches'
    )
    batch_number = models.CharField(max_length=50)
    lot_number = models.CharField(max_length=50, blank=True)
    
    # Manufacturing Information
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    best_before_date = models.DateField(null=True, blank=True)
    
    # Quality Information
    quality_grade = models.CharField(max_length=1, choices=QUALITY_GRADES, default='A')
    quality_notes = models.TextField(blank=True)
    quality_test_results = models.JSONField(default=dict, blank=True)
    
    # Quantities
    initial_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reserved_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    allocated_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    # Costing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    landed_cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Source Information
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='batches'
    )
    purchase_order_number = models.CharField(max_length=50, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    
    # Status & Tracking
    status = models.CharField(max_length=20, choices=BATCH_STATUS, default='ACTIVE')
    received_date = models.DateTimeField(default=timezone.now)
    quarantine_reason = models.TextField(blank=True)
    recall_reason = models.TextField(blank=True)
    
    # Certifications & Compliance
    certifications = models.JSONField(default=list, blank=True)
    compliance_data = models.JSONField(default=dict, blank=True)
    
    # Storage & Handling
    storage_conditions = models.TextField(blank=True)
    handling_instructions = models.TextField(blank=True)
    temperature_requirements = models.JSONField(default=dict, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_batches'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'batch_number'], 
                name='unique_tenant_product_batch'
            ),
        ]
        ordering = ['expiry_date', 'received_date']
        indexes = [
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'expiry_date']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'batch_number']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - Batch: {self.batch_number}"
    
    @property
    def available_quantity(self):
        """Available quantity (current - reserved - allocated)"""
        return self.current_quantity - self.reserved_quantity - self.allocated_quantity
    
    @property
    def is_expired(self):
        """Check if batch is expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False
    
    @property
    def days_until_expiry(self):
        """Days until expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def is_near_expiry(self, days_threshold=30):
        """Check if batch is nearing expiry"""
        days_to_expiry = self.days_until_expiry
        return days_to_expiry is not None and 0 <= days_to_expiry <= days_threshold
    
    def reserve_quantity(self, quantity):
        """Reserve quantity from batch"""
        quantity = Decimal(str(quantity))
        if self.available_quantity >= quantity:
            self.reserved_quantity += quantity
            self.save(update_fields=['reserved_quantity'])
            return True
        return False
    
    def allocate_quantity(self, quantity):
        """Allocate reserved quantity"""
        quantity = Decimal(str(quantity))
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
            self.allocated_quantity += quantity
            self.save(update_fields=['reserved_quantity', 'allocated_quantity'])
            return True
        return False
    
    def consume_quantity(self, quantity):
        """Consume allocated quantity"""
        quantity = Decimal(str(quantity))
        if self.allocated_quantity >= quantity:
            self.allocated_quantity -= quantity
            self.current_quantity -= quantity
            if self.current_quantity <= 0:
                self.status = 'CONSUMED'
            self.save(update_fields=['allocated_quantity', 'current_quantity', 'status'])
            return True
        return False
    
    def release_reservation(self, quantity):
        """Release reserved quantity"""
        quantity = Decimal(str(quantity))
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
            self.save(update_fields=['reserved_quantity'])
            return True
        return False


class SerialNumber(TenantBaseModel):
    """
    Serial number tracking for individual items with lifecycle management
    """
    
    SERIAL_STATUS = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('ALLOCATED', 'Allocated'),
        ('SOLD', 'Sold'),
        ('RETURNED', 'Returned'),
        ('DEFECTIVE', 'Defective'),
        ('RECALLED', 'Recalled'),
        ('SCRAPPED', 'Scrapped'),
        ('IN_SERVICE', 'In Service'),
        ('WARRANTY_CLAIM', 'Warranty Claim'),
    ]
    
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='serial_numbers'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='serial_numbers'
    )
    serial_number = models.CharField(max_length=100)
    
    # Manufacturing Details
    manufacture_date = models.DateField(null=True, blank=True)
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    warranty_period_months = models.IntegerField(null=True, blank=True)
    
    # Status & Location
    status = models.CharField(max_length=20, choices=SERIAL_STATUS, default='AVAILABLE')
    current_location = models.ForeignKey(
        'warehouse.StockLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='serial_numbers'
    )
    
    # Cost & Value
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Customer Information (if sold)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    sale_date = models.DateTimeField(null=True, blank=True)
    sale_order_number = models.CharField(max_length=50, blank=True)
    
    # Service & Maintenance History
    service_history = models.JSONField(default=list, blank=True)
    last_service_date = models.DateField(null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    maintenance_schedule = models.JSONField(default=dict, blank=True)
    
    # Quality & Defect Tracking
    defect_reports = models.JSONField(default=list, blank=True)
    quality_incidents = models.JSONField(default=list, blank=True)
    
    # Additional Information
    notes = models.TextField(blank=True)
    custom_attributes = models.JSONField(default=dict, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_serial_numbers'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'product', 'serial_number'], 
                name='unique_tenant_product_serial'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'product', 'status']),
            models.Index(fields=['tenant_id', 'serial_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'customer_email']),
        ]
    
    def __str__(self):
        return f"{self.product.sku} - SN: {self.serial_number}"
    
    @property
    def warranty_active(self):
        """Check if warranty is still active"""
        if self.warranty_end_date:
            return self.warranty_end_date >= timezone.now().date()
        return False
    
    @property
    def warranty_days_remaining(self):
        """Days remaining in warranty"""
        if self.warranty_end_date:
            delta = self.warranty_end_date - timezone.now().date()
            return max(0, delta.days)
        return 0
    
    @property
    def age_in_days(self):
        """Age of the item since manufacture"""
        if self.manufacture_date:
            delta = timezone.now().date() - self.manufacture_date
            return delta.days
        return None
    
    def add_service_record(self, service_date, service_type, description, technician=None):
        """Add service record to history"""
        service_record = {
            'date': service_date.isoformat() if service_date else None,
            'type': service_type,
            'description': description,
            'technician': technician,
            'timestamp': timezone.now().isoformat()
        }
        
        if not isinstance(self.service_history, list):
            self.service_history = []
        
        self.service_history.append(service_record)
        self.last_service_date = service_date
        self.save(update_fields=['service_history', 'last_service_date'])
    
    def add_defect_report(self, defect_type, description, severity='MEDIUM', reported_by=None):
        """Add defect report"""
        defect_record = {
            'date': timezone.now().date().isoformat(),
            'type': defect_type,
            'description': description,
            'severity': severity,
            'reported_by': reported_by,
            'timestamp': timezone.now().isoformat()
        }
        
        if not isinstance(self.defect_reports, list):
            self.defect_reports = []
        
        self.defect_reports.append(defect_record)
        
        # Update status if severe defect
        if severity in ['HIGH', 'CRITICAL']:
            self.status = 'DEFECTIVE'
        
        self.save(update_fields=['defect_reports', 'status'])