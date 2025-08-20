"""
Celery tasks for inventory management
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.tenants.models import Tenant
from .services import InventoryService, AlertService, AnalyticsService, PurchaseOrderService
from .models import InventoryAlert, StockItem, Batch, Product

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_inventory_alerts(self, tenant_id=None):
    """
    Check inventory conditions and create alerts
    Runs every hour
    """
    try:
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id, is_active=True)
        else:
            tenants = Tenant.objects.filter(is_active=True)
        
        total_alerts_created = 0
        
        for tenant in tenants:
            logger.info(f"Checking alerts for tenant: {tenant.name}")
            
            alert_service = AlertService(tenant)
            
            # Check expiry alerts
            alert_service.check_expiry_alerts()
            
            # Check cycle count alerts
            alert_service.check_cycle_count_alerts()
            
            # Count new active alerts
            new_alerts = InventoryAlert.objects.filter(
                tenant=tenant,
                status='ACTIVE',
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            total_alerts_created += new_alerts
            
            logger.info(f"Created {new_alerts} new alerts for tenant: {tenant.name}")
        
        return f"Alert check completed. Created {total_alerts_created} new alerts."
        
    except Exception as exc:
        logger.error(f"Error in check_inventory_alerts: {str(exc)}")
        raise self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=2)
def calculate_abc_analysis(self, tenant_id=None):
    """
    Calculate ABC analysis for products
    Runs daily
    """
    try:
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id, is_active=True)
        else:
            tenants = Tenant.objects.filter(is_active=True)
        
        total_products_updated = 0
        
        for tenant in tenants:
            logger.info(f"Calculating ABC analysis for tenant: {tenant.name}")
            
            analytics_service = AnalyticsService(tenant)
            analytics_service.calculate_abc_analysis()
            analytics_service.calculate_turnover_rates()
            
            # Count updated products
            products_count = Product.objects.filter(
                tenant=tenant,
                abc_classification__isnull=False
            ).count()
            
            total_products_updated += products_count
            
            logger.info(f"Updated ABC classification for {products_count} products in tenant: {tenant.name}")
        
        return f"ABC analysis completed. Updated {total_products_updated} products."
        
    except Exception as exc:
        logger.error(f"Error in calculate_abc_analysis: {str(exc)}")
        raise self.retry(countdown=300, exc=exc)


@shared_task(bind=True, max_retries=3)
def auto_generate_purchase_orders(self, tenant_id):
    """
    Auto-generate purchase orders for products below reorder point
    Runs daily for tenants with auto-reorder enabled
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
        
        logger.info(f"Auto-generating purchase orders for tenant: {tenant.name}")
        
        po_service = PurchaseOrderService(tenant)
        success, result = po_service.auto_generate_purchase_orders()
        
        if success:
            pos_created = len(result)
            logger.info(f"Created {pos_created} purchase orders for tenant: {tenant.name}")
            return f"Auto-generated {pos_created} purchase orders"
        else:
            logger.error(f"Failed to auto-generate purchase orders for tenant: {tenant.name} - {result}")
            return f"Failed: {result}"
            
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with ID {tenant_id} not found")
        return f"Tenant {tenant_id} not found"
    except Exception as exc:
        logger.error(f"Error in auto_generate_purchase_orders: {str(exc)}")
        raise self.retry(countdown=300, exc=exc)


@shared_task(bind=True)
def cleanup_old_inventory_data(self, tenant_id=None, days_to_keep=365):
    """
    Cleanup old inventory data based on retention policies
    Runs weekly
    """
    try:
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id, is_active=True)
        else:
            tenants = Tenant.objects.filter(is_active=True)
        
        total_deleted = 0
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        for tenant in tenants:
            logger.info(f"Cleaning up old data for tenant: {tenant.name}")
            
            alert_service = AlertService(tenant)
            deleted_count = alert_service.cleanup_resolved_alerts()
            
            total_deleted += deleted_count
            
            logger.info(f"Deleted {deleted_count} old records for tenant: {tenant.name}")
        
        return f"Cleanup completed. Deleted {total_deleted} old records."
        
    except Exception as exc:
        loggerstr(exc)}")
        return f"Cleanup failed: {str(exc)}"


@shared_task(bind=True, max_retries=3)
def update_stock_levels(self, tenant_id, stock_updates):
    """
    Bulk update stock levels
    Used for batch operations
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
        inventory_service = InventoryService(tenant)
        
        updated_count = 0
        failed_updates = []
        
        for update in stock_updates:
            try:
                product_id = update['product_id']
                warehouse_id = update['warehouse_id']
                new_quantity = update['quantity']
                reason = update.get('reason', 'Bulk update')
                
                from .models import Product, Warehouse
                product = Product.objects.get(id=product_id, tenant=tenant)
                warehouse = Warehouse.objects.get(id=warehouse_id, tenant=tenant)
                
                # Get or create stock item
                stock_item, created = StockItem.objects.get_or_create(
                    tenant=tenant,
                    product=product,
                    warehouse=warehouse,
                    defaults={
                        'average_cost': product.cost_price,
                        'unit_cost': product.cost_price,
                        'last_cost': product.cost_price
                    }
                )
                
                # Adjust stock
                stock_item.adjust_stock(new_quantity, reason)
                updated_count += 1
                
            except Exception as e:
                failed_updates.append({
                    'update': update,
                    'error': str(e)
                })
                logger.error(f"Failed to update stock: {update} - {str(e)}")
        
        result = {
            'updated_count': updated_count,
            'failed_count': len(failed_updates),
            'failed_updates': failed_updates
        }
        
        logger.info(f"Bulk stock update completed for tenant {tenant.name}: {updated_count} updated, {len(failed_updates)} failed")
        return result
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with ID {tenant_id} not found")
        return {'error': f'Tenant {tenant_id} not found'}
    except Exception as exc:
        logger.error(f"Error in update_stock_levels: {str(exc)}")
        raise self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=2)
def generate_inventory_report(self, tenant_id, report_type, parameters=None):
    """
    Generate inventory report asynchronously
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id, is_active=True)
        
        logger.info(f"Generating {report_type} report for tenant: {tenant.name}")
        
        from .models import InventoryReport
        
        # Create report record
        report = InventoryReport.objects.create(
            tenant=tenant,
            report_name=f"{report_type} Report",
            report_type=report_type,
            parameters=parameters or {},
            status='GENERATING'
        )
        
        # Generate report data based on type
        if report_type == 'STOCK_SUMMARY':
            data = generate_stock_summary_report(tenant, parameters)
        elif report_type == 'ABC_ANALYSIS':
            data = generate_abc_analysis_report(tenant, parameters)
        elif report_type == 'MOVEMENT_REPORT':
            data = generate_movement_report(tenant, parameters)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Update report with data
        report.data = data
        report.status = 'COMPLETED'
        report.generated_at = timezone.now()
        report.save()
        
        logger.info(f"Report {report.id} generated successfully for tenant: {tenant.name}")
        return f"Report {report.id} generated successfully"
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with ID {tenant_id} not found")
        return {'error': f'Tenant {tenant_id} not found'}
    except Exception as exc:
        logger.error(f"Error generating report: {str(exc)}")
        if hasattr(locals(), 'report'):
            report.status = 'FAILED'
            report.save()
        raise self.retry(countdown=300, exc=exc)


def generate_stock_summary_report(tenant, parameters):
    """Generate stock summary report data"""
    from django.db.models import Sum, Count
    
    stock_items = StockItem.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('product', 'warehouse')
    
    # Apply filters if provided
    if parameters:
        if 'warehouse_ids' in parameters:
            stock_items = stock_items.filter(warehouse_id__in=parameters['warehouse_ids'])
        if 'category_ids' in parameters:
            stock_items = stock_items.filter(product__category_id__in=parameters['category_ids'])
    
    # Generate summary data
    summary = stock_items.aggregate(
        total_items=Count('id'),
        total_quantity=Sum('quantity_on_hand'),
        total_value=Sum('total_value')
    )
    
    # Group by category
    by_category = stock_items.values(
        'product__category__name'
    ).annotate(
        total_quantity=Sum('quantity_on_hand'),
        total_value=Sum('total_value'),
        item_count=Count('id')
    ).order_by('-total_value')
    
    # Group by warehouse
    by_warehouse = stock_items.values(
        'warehouse__name'
    ).annotate(
        total_quantity=Sum('quantity_on_hand'),
        total_value=Sum('total_value'),
        item_count=Count('id')
    ).order_by('-total_value')
    
    return {
        'summary': summary,
        'by_category': list(by_category),
        'by_warehouse': list(by_warehouse),
        'generated_at': timezone.now().isoformat()
    }


def generate_abc_analysis_report(tenant, parameters):
    """Generate ABC analysis report data"""
    from django.db.models import Sum
    
    products = Product.objects.filter(
        tenant=tenant,
        status='ACTIVE'
    ).annotate(
        total_value=Sum('stock_items__total_value')
    ).filter(
        total_value__gt=0
    ).order_by('-total_value')
    
    # Calculate ABC classification
    total_value = sum(p.total_value for p in products)
    
    if total_value == 0:
        return {'error': 'No products with stock value found'}
    
    cumulative_value = 0
    class_a = []
    class_b = []
    class_c = []
    
    for product in products:
        cumulative_value += product.total_value
        cumulative_percentage = (cumulative_value / total_value) * 100
        
        product_data = {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'total_value': float(product.total_value),
            'value_percentage': float((product.total_value / total_value) * 100),
            'cumulative_percentage': float(cumulative_percentage)
        }
        
        if cumulative_percentage <= 80:
            product_data['abc_class'] = 'A'
            class_a.append(product_data)
        elif cumulative_percentage <= 95:
            product_data['abc_class'] = 'B'
            class_b.append(product_data)
        else:
            product_data['abc_class'] = 'C'
            class_c.append(product_data)
    
    return {
        'class_a': class_a,
        'class_b': class_b,
        'class_c': class_c,
        'summary': {
            'total_products': len(products),
            'total_value': float(total_value),
            'class_a_count': len(class_a),
            'class_b_count': len(class_b),
            'class_c_count': len(class_c)
        },
        'generated_at': timezone.now().isoformat()
    }


def generate_movement_report(tenant, parameters):
    """Generate stock movement report data"""
    from django.db.models import Sum, Count
    from .models import StockMovement
    
    movements = StockMovement.objects.filter(
        tenant=tenant
    ).select_related('stock_item__product', 'stock_item__warehouse', 'performed_by')
    
    # Apply date filters
    if parameters:
        if 'start_date' in parameters:
            movements = movements.filter(movement_date__gte=parameters['start_date'])
        if 'end_date' in parameters:
            movements = movements.filter(movement_date__lte=parameters['end_date'])
        if 'warehouse_ids' in parameters:
            movements = movements.filter(stock_item__warehouse_id__in=parameters['warehouse_ids'])
    
    # Summary by movement type
    by_type = movements.values('movement_type').annotate(
        total_movements=Count('id'),
        total_quantity=Sum('quantity'),
        total_value=Sum('total_cost')
    ).order_by('movement_type')
    
    # Daily trend
    daily_trend = movements.extra(
        select={'day': 'date(movement_date)'}
    ).values('day').annotate(
        total_movements=Count('id'),
        inbound_quantity=Sum('quantity', filter=models.Q(movement_type__in=['RECEIVE', 'PURCHASE', 'ADJUST_IN'])),
        outbound_quantity=Sum('quantity', filter=models.Q(movement_type__in=['SALE', 'SHIP', 'ADJUST_OUT']))
    ).order_by('day')
    
    return {
        'by_type': list(by_type),
        'daily_trend': list(daily_trend),
        'total_movements': movements.count(),
        'generated_at': timezone.now().isoformat()
    }


# Periodic tasks setup (for celery beat)
from celery.schedules import crontab

# Add to your celery.py beat schedule:
"""
CELERY_BEAT_SCHEDULE = {
    'check-inventory-alerts': {
        'task': 'apps.inventory.tasks.check_inventory_alerts',
        'schedule': crontab(minute=0),  # Every hour
    },
    'calculate-abc-analysis': {
        'task': 'apps.inventory.tasks.calculate_abc_analysis',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-data': {
        'task': 'apps.inventory.tasks.cleanup_old_inventory_data',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly on Sunday at 3 AM
    },
}
"""
