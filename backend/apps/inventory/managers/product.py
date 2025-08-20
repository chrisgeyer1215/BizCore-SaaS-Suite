from django.db import models
from django.db.models import Q, F, Sum, Count, Avg, Max, Min, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
from .base import TenantAwareManager
from .tenant import TenantQuerySet

class ProductQuerySet(TenantQuerySet):
    """
    Custom queryset for product operations
    """
    
    def with_stock_info(self):
        """Annotate with stock information"""
        from ..models import StockItem
        
        return self.annotate(
            total_stock=Coalesce(
                Sum('stockitem__quantity_on_hand'), 0
            ),
            available_stock=Coalesce(
                Sum(F('stockitem__quantity_on_hand') - F('stockitem__quantity_reserved')), 0
            ),
            reserved_stock=Coalesce(
                Sum('stockitem__quantity_reserved'), 0
            ),
            stock_value=Coalesce(
                Sum(F('stockitem__quantity_on_hand') * F('stockitem__unit_cost')), 0
            )
        )
    
    def with_supplier_info(self):
        """Annotate with primary supplier information"""
        from ..models import ProductSupplier
        
        primary_supplier = ProductSupplier.objects.filter(
            product=OuterRef('pk'),
            is_primary=True
        ).select_related('supplier')
        
        return self.annotate(
            primary_supplier_name=Subquery(primary_supplier.values('supplier__name')[:1]),
            primary_supplier_lead_time=Subquery(primary_supplier.values('lead_time_days')[:1]),
            primary_supplier_cost=Subquery(primary_supplier.values('supplier_cost')[:1])
        )
    
    def active(self):
        """Get active products only"""
        return self.filter(is_active=True)
    
    def sellable(self):
        """Get sellable products"""
        return self.filter(is_active=True, is_sellable=True)
    
    def purchasable(self):
        """Get purchasable products"""
        return self.filter(is_active=True, is_purchasable=True)
    
    def by_category(self, category):
        """Filter by category"""
        return self.filter(category=category)
    
    def by_brand(self, brand):
        """Filter by brand"""
        return self.filter(brand=brand)
    
    def by_product_type(self, product_type):
        """Filter by product type"""
        return self.filter(product_type=product_type)
    
    def search(self, query):
        """Search products by multiple fields"""
        return self.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query) |
            Q(description__icontains=query)
        )
    
    def low_stock(self):
        """Get products with low stock"""
        return self.filter(
            stockitem__quantity_on_hand__lte=F('stockitem__reorder_level')
        ).distinct()
    
    def out_of_stock(self):
        """Get out of stock products"""
        return self.filter(
            stockitem__quantity_on_hand=0
        ).distinct()
    
    def with_variations(self):
        """Include product variations"""
        return self.prefetch_related('variations')
    
    def with_attributes(self):
        """Include product attributes"""
        return self.prefetch_related(
            'productattributevalue_set__attribute',
            'productattributevalue_set__value'
        )

class ProductManager(TenantAwareManager):
    """
    Manager for Product model
    """
    
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db).select_related(
            'category', 'brand', 'department', 'unit_of_measure', 'tenant'
        )
    
    def with_stock_info(self):
        return self.get_queryset().with_stock_info()
    
    def with_supplier_info(self):
        return self.get_queryset().with_supplier_info()
    
    def active(self):
        return self.get_queryset().active()
    
    def sellable(self):
        return self.get_queryset().sellable()
    
    def purchasable(self):
        return self.get_queryset().purchasable()
    
    def by_category(self, category):
        return self.get_queryset().by_category(category)
    
    def by_brand(self, brand):
        return self.get_queryset().by_brand(brand)
    
    def by_product_type(self, product_type):
        return self.get_queryset().by_product_type(product_type)
    
    def search(self, query):
        return self.get_queryset().search(query)
    
    def low_stock(self):
        return self.get_queryset().low_stock()
    
    def out_of_stock(self):
        return self.get_queryset().out_of_stock()
    
    def with_variations(self):
        return self.get_queryset().with_variations()
    
    def with_attributes(self):
        return self.get_queryset().with_attributes()
    
    def get_product_summary(self, tenant):
        """Get comprehensive product summary"""
        return self.for_tenant(tenant).with_stock_info().aggregate(
            total_products=Count('id'),
            active_products=Count('id', filter=Q(is_active=True)),
            sellable_products=Count('id', filter=Q(is_sellable=True, is_active=True)),
            total_stock_value=Sum('stock_value'),
            low_stock_products=Count('id', filter=Q(
                stockitem__quantity_on_hand__lte=F('stockitem__reorder_level')
            )),
            out_of_stock_products=Count('id', filter=Q(
                stockitem__quantity_on_hand=0
            ))
        )
    
    def create_with_stock(self, tenant, warehouse, product_data, initial_stock=0, unit_cost=0):
        """Create product with initial stock"""
        from django.db import transaction
        from ..models import StockItem
        
        with transaction.atomic():
            product = self.create(tenant=tenant, **product_data)
            
            if initial_stock > 0:
                StockItem.objects.create(
                    tenant=tenant,
                    product=product,
                    warehouse=warehouse,
                    quantity_on_hand=initial_stock,
                    unit_cost=unit_cost
                )
            
            return product
    
    def bulk_update_prices(self, tenant, price_updates):
        """Bulk update product prices"""
        from django.db import transaction
        
        with transaction.atomic():
            for product_id, new_price in price_updates.items():
                self.for_tenant(tenant).filter(id=product_id).update(
                    selling_price=new_price,
                    updated_at=timezone.now()
                )
    
    def get_reorder_suggestions(self, tenant, warehouse=None):
        """Get products that need reordering"""
        from ..models import StockItem, ProductSupplier
        
        queryset = (
            self.for_tenant(tenant)
            .filter(is_active=True, is_purchasable=True)
            .with_stock_info()
            .filter(total_stock__lte=F('stockitem__reorder_level'))
        )
        
        if warehouse:
            queryset = queryset.filter(stockitem__warehouse=warehouse)
        
        return queryset.annotate(
            suggested_quantity=F('stockitem__maximum_stock_level') - F('total_stock'),
            primary_supplier_cost=Subquery(
                ProductSupplier.objects.filter(
                    product=OuterRef('pk'),
                    is_primary=True
                ).values('supplier_cost')[:1]
            ),
            estimated_cost=F('suggested_quantity') * F('primary_supplier_cost')
        ).values(
            'id', 'name', 'sku', 'total_stock', 
            'suggested_quantity', 'estimated_cost'
        )