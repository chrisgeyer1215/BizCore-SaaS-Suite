"""
Comprehensive DRF views for the Inventory Management System
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter, DateFilter
from django.db.models import Q, Sum, F, Count, Avg, Min, Max, Case, When, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from apps.core.views import TenantViewSetMixin
from apps.core.permissions import TenantPermission
from .models import (
    InventorySettings, UnitOfMeasure, Department, Category, SubCategory,
    Brand, Supplier, SupplierContact, Warehouse, StockLocation,
    ProductAttribute, AttributeValue, Product, ProductAttributeValue,
    ProductVariation, ProductSupplier, Batch, SerialNumber, StockItem,
    StockMovement, PurchaseOrder, PurchaseOrderItem, StockReceipt,
    StockReceiptItem, StockTransfer, StockTransferItem, CycleCount,
    CycleCountItem, StockAdjustment, StockAdjustmentItem, StockReservation,
    StockReservationItem, InventoryAlert, InventoryReport
)
from .serializers import (
    InventorySettingsSerializer, UnitOfMeasureSerializer, DepartmentSerializer,
    CategorySerializer, SubCategorySerializer, BrandSerializer, SupplierSerializer,
    SupplierContactSerializer, WarehouseSerializer, StockLocationSerializer,
    ProductAttributeSerializer, AttributeValueSerializer, ProductSerializer,
    ProductAttributeValueSerializer, ProductVariationSerializer, ProductSupplierSerializer,
    BatchSerializer, SerialNumberSerializer, StockItemSerializer, StockMovementSerializer,
    PurchaseOrderSerializer, PurchaseOrderItemSerializer, StockReceiptSerializer,
    StockReceiptItemSerializer, StockTransferSerializer, StockTransferItemSerializer,
    CycleCountSerializer, CycleCountItemSerializer, StockAdjustmentSerializer,
    StockAdjustmentItemSerializer, StockReservationSerializer, StockReservationItemSerializer,
    InventoryAlertSerializer, InventoryReportSerializer, InventoryDashboardSerializer,
    StockSummarySerializer
)


# ============================================================================
# FILTER CLASSES
# ============================================================================

class ProductFilter(FilterSet):
    """Advanced product filtering"""
    
    search = CharFilter(method='filter_search')
    department = CharFilter(field_name='department__code', lookup_expr='iexact')
    category = CharFilter(field_name='category__code', lookup_expr='iexact')
    brand = CharFilter(field_name='brand__code', lookup_expr='iexact')
    supplier = CharFilter(field_name='preferred_supplier__code', lookup_expr='iexact')
    price_min = NumberFilter(field_name='selling_price', lookup_expr='gte')
    price_max = NumberFilter(field_name='selling_price', lookup_expr='lte')
    cost_min = NumberFilter(field_name='cost_price', lookup_expr='gte')
    cost_max = NumberFilter(field_name='cost_price', lookup_expr='lte')
    stock_status = CharFilter(method='filter_stock_status')
    abc_class = CharFilter(field_name='abc_classification')
    is_low_stock = CharFilter(method='filter_low_stock')
    
    class Meta:
        model = Product
        fields = ['status', 'product_type', 'is_saleable', 'is_purchasable', 'track_inventory']
    
    def filter_search(self, queryset, name, value):
        """Multi-field search"""
        return queryset.filter(
            Q(name__icontains=value) |
            Q(sku__icontains=value) |
            Q(barcode__icontains=value) |
            Q(description__icontains=value) |
            Q(brand__name__icontains=value)
        )
    
    def filter_stock_status(self, queryset, name, value):
        """Filter by stock status"""
        if value == 'IN_STOCK':
            return queryset.filter(stock_items__quantity_available__gt=0)
        elif value == 'LOW_STOCK':
            return queryset.filter(
                stock_items__quantity_available__lte=F('reorder_point'),
                stock_items__quantity_available__gt=0
            )
        elif value == 'OUT_OF_STOCK':
            return queryset.filter(stock_items__quantity_available__lte=0)
        return queryset
    
    def filter_low_stock(self, queryset, name, value):
        """Filter products with low stock"""
        if value.lower() == 'true':
            return queryset.filter(stock_items__quantity_available__lte=F('reorder_point'))
        return queryset


class StockItemFilter(FilterSet):
    """Stock item filtering"""
    
    warehouse = CharFilter(field_name='warehouse__code', lookup_expr='iexact')
    location = CharFilter(field_name='location__code', lookup_expr='iexact')
    product = CharFilter(field_name='product__sku', lookup_expr='iexact')
    batch = CharFilter(field_name='batch__batch_number', lookup_expr='iexact')
    stock_min = NumberFilter(field_name='quantity_available', lookup_expr='gte')
    stock_max = NumberFilter(field_name='quantity_available', lookup_expr='lte')
    value_min = NumberFilter(field_name='total_value', lookup_expr='gte')
    value_max = NumberFilter(field_name='total_value', lookup_expr='lte')
    last_movement = DateFilter(field_name='last_movement_date', lookup_expr='gte')
    
    class Meta:
        model = StockItem
        fields = ['is_active', 'is_quarantined', 'abc_classification']


class PurchaseOrderFilter(FilterSet):
    """Purchase order filtering"""
    
    supplier = CharFilter(field_name='supplier__code', lookup_expr='iexact')
    warehouse = CharFilter(field_name='delivery_warehouse__code', lookup_expr='iexact')
    buyer = CharFilter(field_name='buyer__username', lookup_expr='iexact')
    date_from = DateFilter(field_name='order_date', lookup_expr='gte')
    date_to = DateFilter(field_name='order_date', lookup_expr='lte')
    amount_min = NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_max = NumberFilter(field_name='total_amount', lookup_expr='lte')
    
    class Meta:
        model = PurchaseOrder
        fields = ['status', 'priority', 'po_type']


# ============================================================================
# CORE SETTINGS VIEWS
# ============================================================================

class InventorySettingsViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Inventory settings management"""
    
    queryset = InventorySettings.objects.all()
    serializer_class = InventorySettingsSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    
    def get_queryset(self):
        """Get or create settings for tenant"""
        settings, created = InventorySettings.objects.get_or_create(
            tenant=self.request.tenant,
            defaults={}
        )
        return InventorySettings.objects.filter(tenant=self.request.tenant)


class UnitOfMeasureViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Unit of measure management"""
    
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'abbreviation', 'symbol']
    ordering_fields = ['name', 'unit_type', 'created_at']
    ordering = ['unit_type', 'name']
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get units grouped by type"""
        units = self.get_queryset().filter(is_active=True)
        grouped = {}
        for unit in units:
            unit_type = unit.get_unit_type_display()
            if unit_type not in grouped:
                grouped[unit_type] = []
            grouped[unit_type].append(self.get_serializer(unit).data)
        return Response(grouped)


# ============================================================================
# CATEGORIZATION VIEWS
# ============================================================================

class DepartmentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Department management with hierarchy"""
    
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    @action(detail=False, methods=['get'])
    def hierarchy(self, request):
        """Get department hierarchy tree"""
        departments = self.get_queryset().filter(parent=None, is_active=True)
        serializer = self.get_serializer(departments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reorder(self, request, pk=None):
        """Reorder department children"""
        department = self.get_object()
        order_data = request.data.get('order', [])
        
        for item in order_data:
            child_id = item.get('id')
            sort_order = item.get('sort_order', 0)
            try:
                child = department.children.get(id=child_id)
                child.sort_order = sort_order
                child.save(update_fields=['sort_order'])
            except Department.DoesNotExist:
                continue
        
        return Response({'status': 'success'})


class CategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Category management"""
    
    queryset = Category.objects.select_related('department', 'parent').all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department', 'parent', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'sort_order', 'created_at']
    ordering = ['department__name', 'sort_order', 'name']
    
    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Get categories grouped by department"""
        department_id = request.query_params.get('department')
        if department_id:
            categories = self.get_queryset().filter(
                department_id=department_id,
                is_active=True
            )
        else:
            categories = self.get_queryset().filter(is_active=True)
        
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class SubCategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Sub-category management"""
    
    queryset = SubCategory.objects.select_related('category__department').all()
    serializer_class = SubCategorySerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'sort_order', 'created_at']
    ordering = ['category__name', 'sort_order', 'name']


# ============================================================================
# BRAND & SUPPLIER VIEWS
# ============================================================================

class BrandViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Brand management"""
    
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_preferred', 'manufacturer']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'quality_rating', 'created_at']
    ordering = ['-is_preferred', 'name']
    
    @action(detail=False, methods=['get'])
    def top_brands(self, request):
        """Get top brands by product count"""
        brands = self.get_queryset().annotate(
            product_count=Count('products')
        ).filter(
            is_active=True,
            product_count__gt=0
        ).order_by('-product_count')[:10]
        
        serializer = self.get_serializer(brands, many=True)
        return Response(serializer.data)


class SupplierContactViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Supplier contact management"""
    
    queryset = SupplierContact.objects.select_related('supplier').all()
    serializer_class = SupplierContactSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'contact_type', 'is_active']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'contact_type', 'created_at']
    ordering = ['supplier__name', '-is_primary', 'name']


class SupplierViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Comprehensive supplier management"""
    
    queryset = Supplier.objects.prefetch_related('contacts').all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier_type', 'is_active', 'is_preferred', 'is_verified', 'currency']
    search_fields = ['name', 'code', 'company_name', 'email', 'phone']
    ordering_fields = ['name', 'code', 'overall_rating', 'created_at']
    ordering = ['-is_preferred', 'name']
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get supplier performance metrics"""
        supplier = self.get_object()
        
        # Calculate performance metrics
        total_pos = supplier.purchase_orders.count()
        on_time_deliveries = supplier.purchase_orders.filter(
            status='COMPLETED',
            delivery_date__lte=F('required_date')
        ).count()
        
        on_time_percentage = (on_time_deliveries / total_pos * 100) if total_pos > 0 else 0
        
        # Recent purchase orders
        recent_pos = supplier.purchase_orders.order_by('-order_date')[:10]
        po_data = PurchaseOrderSerializer(recent_pos, many=True, context={'request': request}).data
        
        return Response({
            'total_purchase_orders': total_pos,
            'on_time_deliveries': on_time_deliveries,
            'on_time_percentage': round(on_time_percentage, 2),
            'quality_rating': float(supplier.quality_rating),
            'delivery_rating': float(supplier.delivery_rating),
            'service_rating': float(supplier.service_rating),
            'overall_rating': float(supplier.overall_rating),
            'recent_purchase_orders': po_data
        })
    
    @action(detail=False, methods=['get'])
    def top_performers(self, request):
        """Get top performing suppliers"""
        suppliers = self.get_queryset().filter(
            is_active=True,
            overall_rating__gt=0
        ).order_by('-overall_rating', '-is_preferred')[:10]
        
        serializer = self.get_serializer(suppliers, many=True)
        return Response(serializer.data)


# ============================================================================
# WAREHOUSE & LOCATION VIEWS
# ============================================================================

class WarehouseViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Comprehensive warehouse management"""
    
    queryset = Warehouse.objects.prefetch_related('locations').all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['warehouse_type', 'is_active', 'is_default', 'temperature_zone']
    search_fields = ['name', 'code', 'city', 'state', 'country']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['-is_default', 'name']
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get warehouse summary with stock information"""
        warehouse = self.get_object()
        
        # Stock summary
        stock_summary = warehouse.stock_items.filter(is_active=True).aggregate(
            total_items=Count('id'),
            total_value=Coalesce(Sum('total_value'), 0),
            low_stock_items=Count(Case(
                When(quantity_available__lte=F('product__reorder_point'), then=1)
            )),
            out_of_stock_items=Count(Case(
                When(quantity_available__lte=0, then=1)
            ))
        )
        
        # Recent movements
        recent_movements = StockMovement.objects.filter(
            stock_item__warehouse=warehouse
        ).select_related(
            'stock_item__product', 'performed_by'
        ).order_by('-movement_date')[:10]
        
        movement_data = StockMovementSerializer(
            recent_movements, many=True, context={'request': request}
        ).data
        
        return Response({
            'warehouse': self.get_serializer(warehouse).data,
            'stock_summary': stock_summary,
            'recent_movements': movement_data
        })
    
    @action(detail=False, methods=['get'])
    def utilization(self, request):
        """Get warehouse utilization report"""
        warehouses = self.get_queryset().filter(is_active=True)
        
        utilization_data = []
        for warehouse in warehouses:
            stock_value = warehouse.stock_items.filter(is_active=True).aggregate(
                total=Coalesce(Sum('total_value'), 0)
            )['total']
            
            utilization_data.append({
                'warehouse_id': warehouse.id,
                'warehouse_name': warehouse.name,
                'warehouse_code': warehouse.code,
                'total_stock_value': float(stock_value),
                'current_occupancy_percentage': float(warehouse.current_occupancy_percentage),
                'total_area': float(warehouse.total_area or 0),
                'storage_area': float(warehouse.storage_area or 0),
            })
        
        return Response(utilization_data)


class StockLocationViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Stock location management"""
    
    queryset = StockLocation.objects.select_related('warehouse').all()
    serializer_class = StockLocationSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['warehouse', 'location_type', 'is_active', 'is_pickable', 'is_receivable']
    search_fields = ['name', 'code', 'zone', 'aisle', 'rack', 'shelf']
    ordering_fields = ['name', 'code', 'pick_sequence', 'created_at']
    ordering = ['warehouse__name', 'zone', 'aisle', 'rack', 'shelf']


# ============================================================================
# PRODUCT ATTRIBUTE VIEWS
# ============================================================================

class ProductAttributeViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Product attribute management"""
    
    queryset = ProductAttribute.objects.prefetch_related('values').all()
    serializer_class = ProductAttributeSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['attribute_type', 'is_active', 'is_required', 'is_variant_attribute']
    search_fields = ['name', 'display_name', 'attribute_group']
    ordering_fields = ['name', 'attribute_type', 'sort_order', 'created_at']
    ordering = ['attribute_group', 'sort_order', 'name']


class AttributeValueViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Attribute value management"""
    
    queryset = AttributeValue.objects.select_related('attribute').all()
    serializer_class = AttributeValueSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['attribute', 'is_active', 'is_default']
    search_fields = ['value', 'display_name']
    ordering_fields = ['value', 'display_name', 'sort_order', 'created_at']
    ordering = ['attribute__name', 'sort_order', 'display_name']


# ============================================================================
# PRODUCT VIEWS
# ============================================================================

class ProductViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Comprehensive product management"""
    
    queryset = Product.objects.select_related(
        'department', 'category', 'subcategory', 'brand', 'unit', 'preferred_supplier'
    ).prefetch_related(
        'variations', 'attribute_values', 'supplier_items', 'stock_items'
    ).all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku', 'barcode', 'description']
    ordering_fields = ['name', 'sku', 'cost_price', 'selling_price', 'created_at']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get product stock summary across all warehouses"""
        product = self.get_object()
        
        # Get stock items grouped by warehouse
        stock_items = product.stock_items.filter(is_active=True).select_related(
            'warehouse', 'location', 'batch'
        ).order_by('warehouse__name')
        
        warehouse_stock = {}
        for item in stock_items:
            warehouse_key = item.warehouse.code
            if warehouse_key not in warehouse_stock:
                warehouse_stock[warehouse_key] = {
                    'warehouse_name': item.warehouse.name,
                    'warehouse_code': item.warehouse.code,
                    'total_stock': 0,
                    'available_stock': 0,
                    'reserved_stock': 0,
                    'allocated_stock': 0,
                    'total_value': 0,
                    'locations': []
                }
            
            warehouse_data = warehouse_stock[warehouse_key]
            warehouse_data['total_stock'] += float(item.quantity_on_hand)
            warehouse_data['available_stock'] += float(item.quantity_available)
            warehouse_data['reserved_stock'] += float(item.quantity_reserved)
            warehouse_data['allocated_stock'] += float(item.quantity_allocated)
            warehouse_data['total_value'] += float(item.total_value)
            
            warehouse_data['locations'].append({
                'location_name': item.location.name if item.location else 'Default',
                'location_code': item.location.code if item.location else '',
                'batch_number': item.batch.batch_number if item.batch else '',
                'quantity_on_hand': float(item.quantity_on_hand),
                'quantity_available': float(item.quantity_available),
                'average_cost': float(item.average_cost),
                'total_value': float(item.total_value)
            })
        
        # Recent movements
        recent_movements = StockMovement.objects.filter(
            stock_item__product=product
        ).select_related(
            'stock_item__warehouse', 'performed_by'
        ).order_by('-movement_date')[:20]
        
        movement_data = StockMovementSerializer(
            recent_movements, many=True, context={'request': request}
        ).data
        
        return Response({
            'product': self.get_serializer(product).data,
            'warehouse_stock': list(warehouse_stock.values()),
            'recent_movements': movement_data,
            'totals': {
                'total_stock': float(product.total_stock),
                'available_stock': float(product.available_stock),
                'reserved_stock': float(product.reserved_stock),
                'reorder_needed': product.available_stock <= product.reorder_point
            }
        })
    
    @action(detail=True, methods=['get'])
    def suppliers(self, request, pk=None):
        """Get product suppliers with pricing"""
        product = self.get_object()
        supplier_items = product.supplier_items.filter(is_active=True).select_related('supplier')
        serializer = ProductSupplierSerializer(supplier_items, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """Quick stock adjustment for a product"""
        product = self.get_object()
        warehouse_id = request.data.get('warehouse_id')
        adjustment_type = request.data.get('adjustment_type', 'ADJUSTMENT')
        quantity = Decimal(str(request.data.get('quantity', 0)))
        reason = request.data.get('reason', '')
        
        if not warehouse_id:
            return Response({'error': 'Warehouse ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id, tenant=request.tenant)
            
            # Get or create stock item
            stock_item, created = StockItem.objects.get_or_create(
                tenant=request.tenant,
                product=product,
                warehouse=warehouse,
                defaults={
                    'average_cost': product.cost_price,
                    'unit_cost': product.cost_price,
                    'last_cost': product.cost_price
                }
            )
            
            # Perform adjustment
            old_quantity = stock_item.quantity_on_hand
            if adjustment_type == 'SET':
                new_quantity = quantity
            elif adjustment_type == 'INCREASE':
                new_quantity = old_quantity + quantity
            elif adjustment_type == 'DECREASE':
                new_quantity = max(0, old_quantity - quantity)
            else:
                return Response({'error': 'Invalid adjustment type'}, status=status.HTTP_400_BAD_REQUEST)
            
            adjustment = stock_item.adjust_stock(
                new_quantity=new_quantity,
                reason=reason,
                user=request.user
            )
            
            return Response({
                'success': True,
                'old_quantity': float(old_quantity),
                'new_quantity': float(new_quantity),
                'adjustment': float(adjustment),
                'stock_item': StockItemSerializer(stock_item, context={'request': request}).data
            })
            
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with low stock"""
        products = self.get_queryset().annotate(
            total_available=Coalesce(Sum('stock_items__quantity_available'), 0)
        ).filter(
            total_available__lte=F('reorder_point'),
            status='ACTIVE',
            track_inventory=True
        ).order_by('total_available')
        
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Get out of stock products"""
        products = self.get_queryset().annotate(
            total_available=Coalesce(Sum('stock_items__quantity_available'), 0)
        ).filter(
            total_available__lte=0,
            status='ACTIVE',
            track_inventory=True
        )
        
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def top_selling(self, request):
        """Get top selling products"""
        # This would typically connect to sales data
        # For now, we'll use stock movement data as a proxy
        products = self.get_queryset().annotate(
            sales_volume=Coalesce(Sum(
                Case(
                    When(stock_items__movements__movement_type='SALE', 
                         then='stock_items__movements__quantity'),
                    default=0
                )
            ), 0)
        ).filter(
            sales_volume__gt=0
        ).order_by('-sales_volume')[:20]
        
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)


class ProductVariationViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Product variation management"""
    
    queryset = ProductVariation.objects.select_related('product').all()
    serializer_class = ProductVariationSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'is_active']
    search_fields = ['name', 'sku', 'barcode', 'variation_code']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['product__name', 'sort_order', 'name']


class BatchViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Batch tracking management"""
    
    queryset = Batch.objects.select_related('product', 'supplier').all()
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'supplier', 'status', 'quality_grade']
    search_fields = ['batch_number', 'lot_number']
    ordering_fields = ['batch_number', 'manufacture_date', 'expiry_date', 'received_date']
    ordering = ['expiry_date', 'received_date']
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get batches expiring within specified days"""
        days = int(request.query_params.get('days', 30))
        expiry_date = timezone.now().date() + timedelta(days=days)
        
        batches = self.get_queryset().filter(
            expiry_date__lte=expiry_date,
            expiry_date__gt=timezone.now().date(),
            status='ACTIVE',
            current_quantity__gt=0
        ).order_by('expiry_date')
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get expired batches"""
        batches = self.get_queryset().filter(
            expiry_date__lt=timezone.now().date(),
            status='ACTIVE',
            current_quantity__gt=0
        ).order_by('expiry_date')
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)


# ============================================================================
# STOCK MANAGEMENT VIEWS
# ============================================================================

class StockItemViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Comprehensive stock item management"""
    
    queryset = StockItem.objects.select_related(
        'product', 'variation', 'warehouse', 'location', 'batch'
    ).all()
    serializer_class = StockItemSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StockItemFilter
    search_fields = ['product__name', 'product__sku', 'warehouse__name', 'batch__batch_number']
    ordering_fields = ['product__name', 'warehouse__name', 'quantity_available', 'total_value']
    ordering = ['product__name', 'warehouse__name']
    
    @action(detail=True, methods=['post'])
    def reserve(self, request, pk=None):
        """Reserve stock"""
        stock_item = self.get_object()
        quantity = Decimal(str(request.data.get('quantity', 0)))
        reason = request.data.get('reason', '')
        
        if quantity <= 0:
            return Response({'error': 'Quantity must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        
        success = stock_item.reserve_stock(quantity, reason)
        if success:
            return Response({
                'success': True,
                'reserved_quantity': float(quantity),
                'remaining_available': float(stock_item.quantity_available),
                'total_reserved': float(stock_item.quantity_reserved)
            })
        else:
            return Response({
                'error': 'Insufficient stock available',
                'available': float(stock_item.quantity_available)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def release_reservation(self, request, pk=None):
        """Release reserved stock"""
        stock_item = self.get_object()
        quantity = Decimal(str(request.data.get('quantity', 0)))
        reason = request.data.get('reason', '')
        
        if quantity <= 0:
            return Response({'error': 'Quantity must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        
        success = stock_item.release_reservation(quantity, reason)
        if success:
            return Response({
                'success': True,
                'released_quantity': float(quantity),
                'available_quantity': float(stock_item.quantity_available),
                'reserved_quantity': float(stock_item.quantity_reserved)
            })
        else:
            return Response({
                'error': 'Insufficient reserved stock',
                'reserved': float(stock_item.quantity_reserved)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def valuation_report(self, request):
        """Get stock valuation report"""
        warehouse_id = request.query_params.get('warehouse')
        category_id = request.query_params.get('category')
        
        queryset = self.get_queryset().filter(is_active=True)
        
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        
        # Calculate totals by category
        valuation_data = queryset.values(
            'product__category__name',
            'product__category__code'
        ).annotate(
            total_quantity=Sum('quantity_on_hand'),
            total_value=Sum('total_value'),
            average_cost=Avg('average_cost'),
            item_count=Count('id')
        ).order_by('product__category__name')
        
        # Grand totals
        grand_totals = queryset.aggregate(
            total_quantity=Sum('quantity_on_hand'),
            total_value=Sum('total_value'),
            total_items=Count('id')
        )
        
        return Response({
            'valuation_by_category': list(valuation_data),
            'grand_totals': grand_totals,
            'generated_at': timezone.now(),
            'filters': {
                'warehouse_id': warehouse_id,
                'category_id': category_id
            }
        })


class StockMovementViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Stock movement tracking"""
    
    queryset = StockMovement.objects.select_related(
        'stock_item__product', 'stock_item__warehouse', 'performed_by', 'authorized_by'
    ).all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['movement_type', 'movement_reason', 'stock_item__warehouse', 'performed_by']
    search_fields = ['stock_item__product__name', 'stock_item__product__sku', 'reason', 'reference_number']
    ordering_fields = ['movement_date', 'quantity', 'total_cost']
    ordering = ['-movement_date']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get movement summary by type and date range"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        warehouse_id = request.query_params.get('warehouse')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(movement_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(movement_date__lte=end_date)
        if warehouse_id:
            queryset = queryset.filter(stock_item__warehouse_id=warehouse_id)
        
        # Summary by movement type
        type_summary = queryset.values('movement_type').annotate(
            total_movements=Count('id'),
            total_quantity=Sum('quantity'),
            total_value=Sum('total_cost')
        ).order_by('movement_type')
        
        # Daily movement trend
        daily_trend = queryset.extra(
            select={'day': 'date(movement_date)'}
        ).values('day').annotate(
            total_movements=Count('id'),
            inbound_quantity=Sum(
                Case(When(movement_type__in=['RECEIVE', 'PURCHASE', 'ADJUST_IN'], then='quantity'), default=0)
            ),
            outbound_quantity=Sum(
                Case(When(movement_type__in=['SALE', 'SHIP', 'ADJUST_OUT'], then='quantity'), default=0)
            )
        ).order_by('day')
        
        return Response({
            'summary_by_type': list(type_summary),
            'daily_trend': list(daily_trend),
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'warehouse_id': warehouse_id
            }
        })


# ============================================================================
# PURCHASE ORDER VIEWS
# ============================================================================

class PurchaseOrderViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Comprehensive purchase order management"""
    
    queryset = PurchaseOrder.objects.select_related(
        'supplier', 'delivery_warehouse', 'buyer', 'approved_by'
    ).prefetch_related('items__product').all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PurchaseOrderFilter
    search_fields = ['po_number', 'supplier__name', 'supplier_po_number']
    ordering_fields = ['po_number', 'order_date', 'total_amount', 'required_date']
    ordering = ['-order_date']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve purchase order"""
        purchase_order = self.get_object()
        
        if purchase_order.status != 'PENDING_APPROVAL':
            return Response(
                {'error': 'Purchase order is not pending approval'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = purchase_order.approve(request.user)
        if success:
            return Response({
                'success': True,
                'message': 'Purchase order approved',
                'status': purchase_order.status
            })
        
        return Response({'error': 'Failed to approve purchase order'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_to_supplier(self, request, pk=None):
        """Send purchase order to supplier"""
        purchase_order = self.get_object()
        
        success = purchase_order.send_to_supplier(request.user)
        if success:
            return Response({
                'success': True,
                'message': 'Purchase order sent to supplier',
                'status': purchase_order.status
            })
        
        return Response({'error': 'Cannot send purchase order to supplier'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel purchase order"""
        purchase_order = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response({'error': 'Cancellation reason is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        success = purchase_order.cancel(reason, request.user)
        if success:
            return Response({
                'success': True,
                'message': 'Purchase order cancelled',
                'status': purchase_order.status
            })
        
        return Response({'error': 'Cannot cancel purchase order'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def receipt_history(self, request, pk=None):
        """Get receipt history for purchase order"""
        purchase_order = self.get_object()
        receipts = purchase_order.receipts.all().order_by('-receipt_date')
        serializer = StockReceiptSerializer(receipts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_receipts(self, request):
        """Get purchase orders pending receipt"""
        pos = self.get_queryset().filter(
            status__in=['CONFIRMED', 'PARTIAL_RECEIVED'],
            required_date__lte=timezone.now().date() + timedelta(days=7)
        ).order_by('required_date')
        
        serializer = self.get_serializer(pos, many=True)
        return Response(serializer.data)


class PurchaseOrderItemViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Purchase order item management"""
    
    queryset = PurchaseOrderItem.objects.select_related(
        'purchase_order', 'product', 'variation', 'unit'
    ).all()
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['purchase_order', 'product', 'status']
    search_fields = ['product__name', 'product__sku', 'supplier_sku']
    ordering_fields = ['line_number', 'product__name', 'quantity_ordered']
    ordering = ['purchase_order', 'line_number']
    
    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """Receive quantity for purchase order item"""
        po_item = self.get_object()
        
        quantity = Decimal(str(request.data.get('quantity', 0)))
        batch_number = request.data.get('batch_number', '')
        expiry_date = request.data.get('expiry_date')
        location_id = request.data.get('location_id')
        
        if expiry_date:
            try:
                expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            except ValueError:
                expiry_date = None
        
        location = None
        if location_id:
            try:
                location = StockLocation.objects.get(id=location_id, tenant=request.tenant)
            except StockLocation.DoesNotExist:
                pass
        
        success, message = po_item.receive_quantity(
            quantity=quantity,
            batch_number=batch_number,
            expiry_date=expiry_date,
            location=location,
            user=request.user
        )
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'quantity_received': float(po_item.quantity_received),
                'pending_quantity': float(po_item.pending_quantity),
                'status': po_item.status
            })
        
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# DASHBOARD & ANALYTICS VIEWS
# ============================================================================

class InventoryDashboardViewSet(TenantViewSetMixin, viewsets.ViewSet):
    """Inventory dashboard and analytics"""
    
    permission_classes = [IsAuthenticated, TenantPermission]
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get inventory dashboard summary"""
        # Product counts
        total_products = Product.objects.filter(tenant=request.tenant).count()
        active_products = Product.objects.filter(tenant=request.tenant, status='ACTIVE').count()
        
        # Stock summary
        stock_summary = StockItem.objects.filter(
            tenant=request.tenant, is_active=True
        ).aggregate(
            total_value=Coalesce(Sum('total_value'), 0),
            low_stock_items=Count(Case(
                When(quantity_available__lte=F('product__reorder_point'), then=1)
            )),
            out_of_stock_items=Count(Case(
                When(quantity_available__lte=0, then=1)
            ))
        )
        
        # Expiring batches
        expiry_date = timezone.now().date() + timedelta(days=30)
        expiring_batches = Batch.objects.filter(
            tenant=request.tenant,
            expiry_date__lte=expiry_date,
            expiry_date__gt=timezone.now().date(),
            status='ACTIVE',
            current_quantity__gt=0
        ).count()
        
        # Purchase orders
        pending_pos = PurchaseOrder.objects.filter(
            tenant=request.tenant,
            status__in=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'SENT_TO_SUPPLIER']
        ).count()
        
        # Receipts
        pending_receipts = StockReceipt.objects.filter(
            tenant=request.tenant,
            status__in=['DRAFT', 'PENDING']
        ).count()
        
        # Alerts
        active_alerts = InventoryAlert.objects.filter(
            tenant=request.tenant,
            status='ACTIVE'
        ).count()
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_movements = StockMovement.objects.filter(
            tenant=request.tenant,
            movement_date__gte=week_ago
        ).values('movement_date__date').annotate(
            inbound=Sum(Case(
                When(movement_type__in=['RECEIVE', 'PURCHASE', 'ADJUST_IN'], then='quantity'),
                default=0
            )),
            outbound=Sum(Case(
                When(movement_type__in=['SALE', 'SHIP', 'ADJUST_OUT'], then='quantity'),
                default=0
            ))
        ).order_by('movement_date__date')
        
        # Top products by value
        top_products = StockItem.objects.filter(
            tenant=request.tenant,
            is_active=True,
            total_value__gt=0
        ).select_related('product').order_by('-total_value')[:10].values(
            'product__name',
            'product__sku',
            'total_value'
        )
        
        return Response({
            'total_products': total_products,
            'active_products': active_products,
            'total_stock_value': float(stock_summary['total_value']),
            'low_stock_items': stock_summary['low_stock_items'],
            'out_of_stock_items': stock_summary['out_of_stock_items'],
            'expiring_batches': expiring_batches,
            'pending_purchase_orders': pending_pos,
            'pending_receipts': pending_receipts,
            'active_alerts': active_alerts,
            'stock_movement_trend': list(recent_movements),
            'top_products_by_value': list(top_products),
            'generated_at': timezone.now()
        })
    
    @action(detail=False, methods=['get'])
    def abc_analysis(self, request):
        """Get ABC analysis of products"""
        # Get products with stock value
        products_with_value = StockItem.objects.filter(
            tenant=request.tenant,
            is_active=True
        ).values(
            'product_id',
            'product__name',
            'product__sku'
        ).annotate(
            total_value=Sum('total_value')
        ).order_by('-total_value')
        
        total_value = sum(item['total_value'] for item in products_with_value)
        
        if total_value == 0:
            return Response({
                'class_a': [],
                'class_b': [],
                'class_c': [],
                'summary': {
                    'class_a_count': 0,
                    'class_b_count': 0,
                    'class_c_count': 0,
                    'total_value': 0
                }
            })
        
        # Calculate cumulative percentages
        cumulative_value = 0
        class_a, class_b, class_c = [], [], []
        
        for item in products_with_value:
            cumulative_value += item['total_value']
            cumulative_percentage = (cumulative_value / total_value) * 100
            
            item['value_percentage'] = (item['total_value'] / total_value) * 100
            item['cumulative_percentage'] = cumulative_percentage
            
            if cumulative_percentage <= 80:
                item['abc_class'] = 'A'
                class_a.append(item)
            elif cumulative_percentage <= 95:
                item['abc_class'] = 'B'
                class_b.append(item)
            else:
                item['abc_class'] = 'C'
                class_c.append(item)
        
        return Response({
            'class_a': class_a,
            'class_b': class_b,
            'class_c': class_c,
            'summary': {
                'class_a_count': len(class_a),
                'class_b_count': len(class_b),
                'class_c_count': len(class_c),
                'total_value': float(total_value),
                'class_a_value_percentage': sum(item['value_percentage'] for item in class_a),
                'class_b_value_percentage': sum(item['value_percentage'] for item in class_b),
                'class_c_value_percentage': sum(item['value_percentage'] for item in class_c)
            }
        })


# ============================================================================
# ALERT MANAGEMENT VIEWS
# ============================================================================

class InventoryAlertViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Inventory alert management"""
    
    queryset = InventoryAlert.objects.select_related(
        'product', 'warehouse', 'acknowledged_by', 'resolved_by', 'assigned_to'
    ).all()
    serializer_class = InventoryAlertSerializer
    permission_classes = [IsAuthenticated, TenantPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'status', 'product', 'warehouse']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'severity', 'alert_type']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge alert"""
        alert = self.get_object()
        success = alert.acknowledge(request.user)
        
        if success:
            return Response({
                'success': True,
                'message': 'Alert acknowledged',
                'status': alert.status
            })
        
        return Response({'error': 'Alert cannot be acknowledged'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve alert"""
        alert = self.get_object()
        notes = request.data.get('notes', '')
        
        success = alert.resolve(request.user, notes)
        
        if success:
            return Response({
                'success': True,
                'message': 'Alert resolved',
                'status': alert.status
            })
        
        return Response({'error': 'Alert cannot be resolved'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def snooze(self, request, pk=None):
        """Snooze alert"""
        alert = self.get_object()
        hours = int(request.data.get('hours', 24))
        
        until_datetime = timezone.now() + timedelta(hours=hours)
        alert.snooze(until_datetime)
        
        return Response({
            'success': True,
            'message': f'Alert snoozed for {hours} hours',
            'snoozed_until': until_datetime
        })
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get alert dashboard summary"""
        alerts = self.get_queryset()
        
        summary = {
            'total_alerts': alerts.count(),
            'active_alerts': alerts.filter(status='ACTIVE').count(),
            'critical_alerts': alerts.filter(status='ACTIVE', severity='CRITICAL').count(),
            'high_alerts': alerts.filter(status='ACTIVE', severity='HIGH').count(),
            'by_type': list(alerts.filter(status='ACTIVE').values('alert_type').annotate(
                count=Count('id')
            )),
            'recent_alerts': AlertSerializer(
                alerts.filter(status='ACTIVE').order_by('-created_at')[:10],
                many=True,
                context={'request': request}
            ).data
        }
        
        return Response(summary)
