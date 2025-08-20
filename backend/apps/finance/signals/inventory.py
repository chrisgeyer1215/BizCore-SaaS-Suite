# backend/apps/finance/signals/inventory.py

"""
Inventory integration signals
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import BillItem, InvoiceItem
from apps.inventory.models import StockMovement


@receiver(post_save, sender=BillItem)
def bill_item_inventory_update(sender, instance, created, **kwargs):
    """Update inventory when bill items are created"""
    if (created and 
        instance.item_type == 'PRODUCT' and 
        instance.product and 
        instance.bill.status == 'APPROVED'):
        
        # Create stock movement for received inventory
        StockMovement.objects.create(
            tenant=instance.tenant,
            product=instance.product,
            warehouse=instance.warehouse,
            movement_type='IN',
            quantity=instance.quantity,
            reference_type='BILL',
            reference_id=instance.bill.id,
            notes=f'Received from {instance.bill.vendor.company_name}'
        )
        
        # Create cost layer
        from ..services.inventory_costing import InventoryCostingService
        service = InventoryCostingService(instance.tenant)
        service.create_purchase_cost_layer(instance)


@receiver(post_save, sender=InvoiceItem)
def invoice_item_inventory_update(sender, instance, created, **kwargs):
    """Update inventory when invoice items are created"""
    if (created and 
        instance.item_type == 'PRODUCT' and 
        instance.product and 
        instance.invoice.status == 'APPROVED'):
        
        # Create stock movement for sold inventory
        StockMovement.objects.create(
            tenant=instance.tenant,
            product=instance.product,
            warehouse=instance.warehouse,
            movement_type='OUT',
            quantity=instance.quantity,
            reference_type='INVOICE',
            reference_id=instance.invoice.id,
            notes=f'Sold to {instance.invoice.customer.name}'
        )
        
        # Create COGS entry
        from ..services.cogs import COGSService
        service = COGSService(instance.tenant)
        service.create_invoice_item_cogs(instance)