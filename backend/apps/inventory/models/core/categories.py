"""
Category and classification models
"""
from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from ..abstract.base import TenantBaseModel, SoftDeleteMixin, ActivatableMixin, OrderableMixin
from ...managers.base import InventoryManager

User = get_user_model()


class Department(TenantBaseModel, SoftDeleteMixin, ActivatableMixin, OrderableMixin):
    """
    Top-level product categorization with enhanced features
    """
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Hierarchy Support
    parent = models.ForeignKey(
        'self', 
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    # Accounting Integration
    revenue_account_code = models.CharField(max_length=20, blank=True)
    cost_account_code = models.CharField(max_length=20, blank=True)
    
    # Business Settings
    default_markup_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    
    # Management
    manager = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )
    
    # Media
    image = models.ImageField(upload_to='departments/', blank=True, null=True)
    icon_class = models.CharField(max_length=50, blank=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_departments'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'code'], 
                name='unique_tenant_department_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'code']),
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['tenant_id', 'parent']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)
    
    @property
    def level(self):
        """Get hierarchy level (0 for root)"""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level
    
    def get_descendants(self):
        """Get all descendant departments"""
        descendants = []
        children = self.children.filter(is_deleted=False)
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_ancestors(self):
        """Get all ancestor departments"""
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return ancestors


class Category(TenantBaseModel, SoftDeleteMixin, ActivatableMixin, OrderableMixin):
    """
    Enhanced category system with attributes and SEO
    """
    
    # Parent Department
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Hierarchy Support
    parent = models.ForeignKey(
        'self', 
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    # Tax & Compliance
    tax_category = models.CharField(max_length=50, blank=True)
    hsn_code = models.CharField(max_length=20, blank=True)  # Harmonized System Nomenclature
    commodity_code = models.CharField(max_length=20, blank=True)
    
    # Product Attributes Configuration
    required_attributes = models.JSONField(default=list, blank=True)
    optional_attributes = models.JSONField(default=list, blank=True)
    
    # SEO & Marketing
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.TextField(blank=True)
    
    # Media
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='categories/banners/', blank=True, null=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_categories'
        ordering = ['department', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'department', 'code'], 
                name='unique_tenant_category_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'department', 'is_active']),
            models.Index(fields=['tenant_id', 'parent']),
            models.Index(fields=['tenant_id', 'tax_category']),
        ]
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return f"{self.department.code}/{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        path.insert(0, self.department.name)
        return " > ".join(path)
    
    def get_all_products(self):
        """Get all products in this category and subcategories"""
        from ..catalog.products import Product
        
        category_ids = [self.id]
        # Add all descendant categories
        descendants = self.get_descendants()
        category_ids.extend([cat.id for cat in descendants])
        
        return Product.objects.filter(category_id__in=category_ids)
    
    def get_descendants(self):
        """Get all descendant categories"""
        descendants = []
        children = self.children.filter(is_deleted=False)
        for child in children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class SubCategory(TenantBaseModel, SoftDeleteMixin, ActivatableMixin, OrderableMixin):
    """
    Detailed subcategory system with specifications
    """
    
    # Parent Category
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    
    # Basic Information
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    # Specifications Template
    specification_template = models.JSONField(default=dict, blank=True)
    
    # Quality Standards
    quality_standards = models.JSONField(default=dict, blank=True)
    
    # Media
    image = models.ImageField(upload_to='subcategories/', blank=True, null=True)
    
    objects = InventoryManager()
    
    class Meta:
        db_table = 'inventory_subcategories'
        ordering = ['category', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id', 'category', 'code'], 
                name='unique_tenant_subcategory_code'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant_id', 'category', 'is_active']),
        ]
        verbose_name_plural = 'Sub Categories'
    
    def __str__(self):
        return f"{self.category.code}/{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        return f"{self.category.department.name} > {self.category.name} > {self.name}"
    
    @property
    def department(self):
        """Get parent department"""
        return self.category.department