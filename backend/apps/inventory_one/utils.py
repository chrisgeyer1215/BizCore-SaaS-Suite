"""
Enhanced utility functions for inventory management
"""

import csv
import io
import json
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from django.http import HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import Product, StockItem, StockMovement, Batch

logger = logging.getLogger(__name__)


# ============================================================================
# BARCODE & QR CODE GENERATION
# ============================================================================

def generate_product_barcode(product, format='EAN13'):
    """Generate barcode for product"""
    try:
        # Use product ID padded with zeros for barcode
        barcode_data = str(product.id).zfill(12)
        
        # Generate barcode
        if format.upper() == 'EAN13':
            from barcode import EAN13
            ean = EAN13(barcode_data, writer=ImageWriter())
        elif format.upper() == 'CODE128':
            from barcode import Code128
            ean = Code128(barcode_data, writer=ImageWriter())
        else:
            raise ValueError(f"Unsupported barcode format: {format}")
        
        # Save to BytesIO
        buffer = BytesIO()
        ean.write(buffer)
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating barcode for product {product.id}: {str(e)}")
        return None


def generate_product_qr_code(product):
    """Generate QR code for product"""
    try:
        # Create QR code data
        qr_data = {
            'sku': product.sku,
            'name': product.name,
            'price': str(product.selling_price),
            'category': product.category.name if product.category else '',
            'brand': product.brand.name if product.brand else ''
        }
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating QR code for product {product.id}: {str(e)}")
        return None


def generate_batch_qr_code(batch):
    """Generate QR code for batch"""
    try:
        qr_data = {
            'batch_number': batch.batch_number,
            'product_sku': batch.product.sku,
            'product_name': batch.product.name,
            'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else '',
            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else '',
            'quantity': str(batch.current_quantity)
        }
        
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating QR code for batch {batch.id}: {str(e)}")
        return None


# ============================================================================
# DATA EXPORT FUNCTIONS
# ============================================================================

def export_products_to_csv(queryset, fields=None):
    """Export products to CSV"""
    if fields is None:
        fields = [
            'sku', 'name', 'description', 'department__name', 'category__name',
            'brand__name', 'cost_price', 'selling_price', 'status', 'is_saleable'
        ]
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    header = []
    for field in fields:
        if '__' in field:
            header.append(field.replace('__', ' ').replace('_', ' ').title())
        else:
            header.append(field.replace('_', ' ').title())
    writer.writerow(header)
    
    # Write data
    for product in queryset:
        row = []
        for field in fields:
            if '__' in field:
                # Handle related fields
                value = product
                for part in field.split('__'):
                    value = getattr(value, part, '') if value else ''
            else:
                value = getattr(product, field, '')
            
            row.append(str(value) if value is not None else '')
        writer.writerow(row)
    
    return response


def export_stock_to_csv(queryset):
    """Export stock items to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'SKU', 'Product Name', 'Warehouse', 'Location', 'On Hand', 
        'Available', 'Reserved', 'Average Cost', 'Total Value', 'ABC Class'
    ])
    
    # Write data
    for stock in queryset.select_related('product', 'warehouse', 'location'):
        writer.writerow([
            stock.product.sku,
            stock.product.name,
            stock.warehouse.name,
            stock.location.name if stock.location else '',
            str(stock.quantity_on_hand),
            str(stock.quantity_available),
            str(stock.quantity_reserved),
            str(stock.average_cost),
            str(stock.total_value),
            stock.abc_classification or ''
        ])
    
    return response


def export_movements_to_csv(queryset, start_date=None, end_date=None):
    """Export stock movements to CSV"""
    filename = 'stock_movements_export.csv'
    if start_date and end_date:
        filename = f'movements_{start_date}_{end_date}.csv'
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Date', 'SKU', 'Product Name', 'Warehouse', 'Movement Type', 
        'Quantity', 'Unit Cost', 'Total Cost', 'Performed By', 'Reason'
    ])
    
    # Write data
    for movement in queryset.select_related('stock_item__product', 'stock_item__warehouse', 'performed_by'):
        writer.writerow([
            movement.movement_date.strftime('%Y-%m-%d %H:%M'),
            movement.stock_item.product.sku,
            movement.stock_item.product.name,
            movement.stock_item.warehouse.name,
            movement.get_movement_type_display(),
            str(movement.quantity),
            str(movement.unit_cost),
            str(movement.total_cost),
            movement.performed_by.get_full_name() if movement.performed_by else '',
            movement.reason
        ])
    
    return response


def export_to_json(data, filename='export.json'):
    """Export data to JSON"""
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    json.dump(data, response, cls=DjangoJSONEncoder, indent=2)
    return response


# ============================================================================
# STOCK VALUATION HELPERS
# ============================================================================

def calculate_fifo_cost(stock_item, quantity):
    """Calculate cost using FIFO method"""
    from .models import StockValuationLayer
    
    layers = StockValuationLayer.objects.filter(
        stock_item=stock_item,
        is_active=True,
        quantity_remaining__gt=0
    ).order_by('receipt_date')
    
    total_cost = Decimal('0')
    remaining_qty = Decimal(str(quantity))
    
    for layer in layers:
        if remaining_qty <= 0:
            break
        
        layer_qty = min(layer.quantity_remaining, remaining_qty)
        layer_cost = layer_qty * layer.unit_cost
        
        total_cost += layer_cost
        remaining_qty -= layer_qty
        
        # Update layer
        layer.quantity_consumed += layer_qty
        layer.quantity_remaining -= layer_qty
        if layer.quantity_remaining <= 0:
            layer.is_fully_consumed = True
        layer.save()
    
    return total_cost


def calculate_lifo_cost(stock_item, quantity):
    """Calculate cost using LIFO method"""
    from .models import StockValuationLayer
    
    layers = StockValuationLayer.objects.filter(
        stock_item=stock_item,
        is_active=True,
        quantity_remaining__gt=0
    ).order_by('-receipt_date')  # Reverse order for LIFO
    
    total_cost = Decimal('0')
    remaining_qty = Decimal(str(quantity))
    
    for layer in layers:
        if remaining_qty <= 0:
            break
        
        layer_qty = min(layer.quantity_remaining, remaining_qty)
        layer_cost = layer_qty * layer.unit_cost
        
        total_cost += layer_cost
        remaining_qty -= layer_qty
        
        # Update layer
        layer.quantity_consumed += layer_qty
        layer.quantity_remaining -= layer_qty
        if layer.quantity_remaining <= 0:
            layer.is_fully_consumed = True
        layer.save()
    
    return total_cost


def calculate_weighted_average_cost(stock_item):
    """Calculate weighted average cost"""
    from .models import StockValuationLayer
    
    layers = StockValuationLayer.objects.filter(
        stock_item=stock_item,
        is_active=True,
        quantity_remaining__gt=0
    )
    
    total_cost = sum(layer.quantity_remaining * layer.unit_cost for layer in layers)
    total_quantity = sum(layer.quantity_remaining for layer in layers)
    
    if total_quantity > 0:
        return total_cost / total_quantity
    return Decimal('0')


# ============================================================================
# REPORTING HELPERS
# ============================================================================

def generate_stock_valuation_report(tenant, warehouse_ids=None, category_ids=None):
    """Generate comprehensive stock valuation report"""
    stock_items = StockItem.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity_on_hand__gt=0
    ).select_related('product', 'warehouse', 'product__category')
    
    if warehouse_ids:
        stock_items = stock_items.filter(warehouse_id__in=warehouse_ids)
    if category_ids:
        stock_items = stock_items.filter(product__category_id__in=category_ids)
    
    # Calculate totals by category
    category_totals = {}
    warehouse_totals = {}
    grand_total = {'quantity': Decimal('0'), 'value': Decimal('0')}
    
    for stock in stock_items:
        category = stock.product.category.name if stock.product.category else 'Uncategorized'
        warehouse = stock.warehouse.name
        
        # Category totals
        if category not in category_totals:
            category_totals[category] = {'quantity': Decimal('0'), 'value': Decimal('0'), 'items': 0}
        category_totals[category]['quantity'] += stock.quantity_on_hand
        category_totals[category]['value'] += stock.total_value
        category_totals[category]['items'] += 1
        
        # Warehouse totals
        if warehouse not in warehouse_totals:
            warehouse_totals[warehouse] = {'quantity': Decimal('0'), 'value': Decimal('0'), 'items': 0}
        warehouse_totals[warehouse]['quantity'] += stock.quantity_on_hand
        warehouse_totals[warehouse]['value'] += stock.total_value
        warehouse_totals[warehouse]['items'] += 1
        
        # Grand totals
        grand_total['quantity'] += stock.quantity_on_hand
        grand_total['value'] += stock.total_value
    
    return {
        'by_category': category_totals,
        'by_warehouse': warehouse_totals,
        'grand_total': grand_total,
        'total_items': stock_items.count(),
        'generated_at': timezone.now()
    }


def generate_aging_report(tenant, as_of_date=None):
    """Generate inventory aging report"""
    if not as_of_date:
        as_of_date = timezone.now().date()
    
    # Get batches with their ages
    batches = Batch.objects.filter(
        tenant=tenant,
        status='ACTIVE',
        current_quantity__gt=0
    ).select_related('product')
    
    age_brackets = {
        '0-30 days': {'batches': [], 'total_quantity': Decimal('0'), 'total_value': Decimal('0')},
        '31-60 days': {'batches': [], 'total_quantity': Decimal('0'), 'total_value': Decimal('0')},
        '61-90 days': {'batches': [], 'total_quantity': Decimal('0'), 'total_value': Decimal('0')},
        '91-180 days': {'batches': [], 'total_quantity': Decimal('0'), 'total_value': Decimal('0')},
        '180+ days': {'batches': [], 'total_quantity': Decimal('0'), 'total_value': Decimal('0')}
    }
    
    for batch in batches:
        if batch.manufacture_date:
            age_days = (as_of_date - batch.manufacture_date).days
        else:
            age_days = (as_of_date - batch.received_date.date()).days
        
        batch_value = batch.current_quantity * batch.unit_cost
        batch_data = {
            'batch_number': batch.batch_number,
            'product_name': batch.product.name,
            'product_sku': batch.product.sku,
            'quantity': batch.current_quantity,
            'unit_cost': batch.unit_cost,
            'total_value': batch_value,
            'age_days': age_days
        }
        
        if age_days <= 30:
            bracket = '0-30 days'
        elif age_days <= 60:
            bracket = '31-60 days'
        elif age_days <= 90:
            bracket = '61-90 days'
        elif age_days <= 180:
            bracket = '91-180 days'
        else:
            bracket = '180+ days'
        
        age_brackets[bracket]['batches'].append(batch_data)
        age_brackets[bracket]['total_quantity'] += batch.current_quantity
        age_brackets[bracket]['total_value'] += batch_value
    
    return {
        'age_brackets': age_brackets,
        'as_of_date': as_of_date,
        'generated_at': timezone.now()
    }


def calculate_inventory_turnover(tenant, product_ids=None, days=365):
    """Calculate inventory turnover ratios"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    products = Product.objects.filter(tenant=tenant, status='ACTIVE')
    if product_ids:
        products = products.filter(id__in=product_ids)
    
    turnover_data = []
    
    for product in products:
        # Calculate average inventory
        stock_items = product.stock_items.filter(is_active=True)
        current_stock = sum(item.quantity_on_hand for item in stock_items)
        avg_inventory_value = sum(item.total_value for item in stock_items)
        
        # Calculate cost of goods sold (approximation from outbound movements)
        outbound_movements = StockMovement.objects.filter(
            stock_item__product=product,
            movement_date__range=[start_date, end_date],
            movement_type__in=['SALE', 'SHIP', 'OUT']
        )
        
        cogs = sum(movement.total_cost for movement in outbound_movements)
        total_quantity_sold = sum(movement.quantity for movement in outbound_movements)
        
        # Calculate turnover ratios
        if avg_inventory_value > 0:
            turnover_ratio = cogs / avg_inventory_value
            days_in_inventory = days / turnover_ratio if turnover_ratio > 0 else 0
        else:
            turnover_ratio = 0
            days_in_inventory = 0
        
        turnover_data.append({
            'product_id': product.id,
            'product_name': product.name,
            'product_sku': product.sku,
            'current_stock': current_stock,
            'inventory_value': avg_inventory_value,
            'quantity_sold': total_quantity_sold,
            'cogs': cogs,
            'turnover_ratio': float(turnover_ratio),
            'days_in_inventory': float(days_in_inventory),
            'classification': classify_turnover_speed(days_in_inventory)
        })
    
    return sorted(turnover_data, key=lambda x: x['turnover_ratio'], reverse=True)


def classify_turnover_speed(days_in_inventory):
    """Classify inventory turnover speed"""
    if days_in_inventory == 0:
        return 'NO_MOVEMENT'
    elif days_in_inventory <= 30:
        return 'FAST_MOVING'
    elif days_in_inventory <= 90:
        return 'MEDIUM_MOVING'
    elif days_in_inventory <= 180:
        return 'SLOW_MOVING'
    else:
        return 'DEAD_STOCK'


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

def bulk_update_stock_levels(tenant, updates, user=None):
    """Bulk update stock levels"""
    results = {'success': 0, 'failed': 0, 'errors': []}
    
    for update in updates:
        try:
            product_id = update['product_id']
            warehouse_id = update['warehouse_id']
            new_quantity = Decimal(str(update['quantity']))
            reason = update.get('reason', 'Bulk update')
            
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
            stock_item.adjust_stock(new_quantity, reason, user)
            results['success'] += 1
            
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'update': update,
                'error': str(e)
            })
            logger.error(f"Failed bulk stock update: {update} - {str(e)}")
    
    return results


def bulk_import_products(tenant, csv_data, user=None):
    """Bulk import products from CSV"""
    results = {'success': 0, 'failed': 0, 'errors': []}
    
    try:
        # Parse CSV
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            try:
                # Basic validation
                required_fields = ['sku', 'name', 'cost_price', 'selling_price']
                for field in required_fields:
                    if not row.get(field):
                        raise ValueError(f"Missing required field: {field}")
                
                # Create or update product
                product, created = Product.objects.get_or_create(
                    tenant=tenant,
                    sku=row['sku'],
                    defaults={
                        'name': row['name'],
                        'description': row.get('description', ''),
                        'cost_price': Decimal(row['cost_price']),
                        'selling_price': Decimal(row['selling_price']),
                        'status': 'ACTIVE',
                        'is_saleable': True,
                        'is_purchasable': True
                    }
                )
                
                if not created:
                    # Update existing product
                    product.name = row['name']
                    product.description = row.get('description', product.description)
                    product.cost_price = Decimal(row['cost_price'])
                    product.selling_price = Decimal(row['selling_price'])
                    product.save()
                
                results['success'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': row,
                    'error': str(e)
                })
                logger.error(f"Failed to import product: {row} - {str(e)}")
    
    except Exception as e:
        results['errors'].append({'error': f"CSV parsing error: {str(e)}"})
    
    return results


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_stock_adjustment(stock_item, new_quantity, allow_negative=None):
    """Validate stock adjustment"""
    errors = []
    
    if new_quantity < 0:
        if allow_negative is None:
            allow_negative = stock_item.warehouse.allow_negative_stock
        
        if not allow_negative:
            errors.append("Negative stock not allowed for this warehouse")
    
    # Check for reserved stock
    if new_quantity < stock_item.quantity_reserved:
        errors.append(f"Cannot reduce stock below reserved quantity ({stock_item.quantity_reserved})")
    
    # Check for allocated stock
    if new_quantity < (stock_item.quantity_reserved + stock_item.quantity_allocated):
        errors.append("Cannot reduce stock below reserved + allocated quantities")
    
    return errors


def validate_batch_expiry(batch):
    """Validate batch expiry and return warnings"""
    warnings = []
    
    if batch.expiry_date:
        days_until_expiry = (batch.expiry_date - timezone.now().date()).days
        
        if days_until_expiry < 0:
            warnings.append(f"Batch {batch.batch_number} has expired")
        elif days_until_expiry <= 7:
            warnings.append(f"Batch {batch.batch_number} expires in {days_until_expiry} days")
        elif days_until_expiry <= 30:
            warnings.append(f"Batch {batch.batch_number} expires in {days_until_expiry} days")
    
    return warnings


# ============================================================================
# FORMATTING HELPERS
# ============================================================================

def format_currency(amount, currency='USD'):
    """Format currency amount"""
    if currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    elif currency == 'GBP':
        return f"£{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_quantity(quantity, unit=None):
    """Format quantity with unit"""
    if unit:
        return f"{quantity:,.3f} {unit}"
    else:
        return f"{quantity:,.3f}"


def format_percentage(value):
    """Format percentage value"""
    return f"{value:.1f}%"


# ============================================================================
# SEARCH HELPERS
# ============================================================================

def search_products(tenant, query, filters=None):
    """Advanced product search"""
    products = Product.objects.filter(tenant=tenant, status='ACTIVE')
    
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    if filters:
        if 'category' in filters:
            products = products.filter(category_id__in=filters['category'])
        if 'brand' in filters:
            products = products.filter(brand_id__in=filters['brand'])
        if 'price_range' in filters:
            min_price, max_price = filters['price_range']
            products = products.filter(selling_price__gte=min_price, selling_price__lte=max_price)
        if 'stock_status' in filters:
            if filters['stock_status'] == 'in_stock':
                products = products.filter(stock_items__quantity_available__gt=0)
            elif filters['stock_status'] == 'low_stock':
                products = products.filter(stock_items__quantity_available__lte=F('reorder_point'))
            elif filters['stock_status'] == 'out_of_stock':
                products = products.filter(stock_items__quantity_available__lte=0)
    
    return products.distinct()


class InventoryCalculator:
    """Helper class for inventory calculations"""
    
    @staticmethod
    def calculate_reorder_point(avg_daily_usage, lead_time_days, safety_stock=0):
        """Calculate reorder point"""
        return (avg_daily_usage * lead_time_days) + safety_stock
    
    @staticmethod
    def calculate_economic_order_quantity(annual_demand, ordering_cost, holding_cost):
        """Calculate EOQ"""
        import math
        return math.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
    
    @staticmethod
    def calculate_safety_stock(avg_daily_usage, max_lead_time, avg_lead_time):
        """Calculate safety stock"""
        return avg_daily_usage * (max_lead_time - avg_lead_time)
    
    @staticmethod
    def calculate_carrying_cost(inventory_value, carrying_cost_percentage):
        """Calculate carrying cost"""
        return inventory_value * (carrying_cost_percentage / 100)
