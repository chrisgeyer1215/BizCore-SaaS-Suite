class ProductCategory(TenantBaseModel, SoftDeleteMixin):
    """Enhanced product categorization for CRM"""
    
    # Category Information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent_category = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    level = models.PositiveSmallIntegerField(default=0)
    
    # Business Information
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    default_margin = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Performance Metrics
    total_products = models.IntegerField(default=0)
    total_sales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Product Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_tenant_product_category'
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-calculate level based on parent
        if self.parent_category:
            self.level = self.parent_category.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)


class Product(TenantBaseModel, SoftDeleteMixin):
    """Enhanced CRM product catalog with inventory integration"""
    
    PRODUCT_TYPES = [
        ('PHYSICAL', 'Physical Product'),
        ('SERVICE', 'Service'),
        ('SOFTWARE', 'Software'),
        ('SUBSCRIPTION', 'Subscription'),
        ('BUNDLE', 'Product Bundle'),
        ('DIGITAL', 'Digital Product'),
    ]
    
    # Product Identification
    product_code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    product_type = models.CharField(max_length=15, choices=PRODUCT_TYPES, default='PHYSICAL')
    
    # Categorization
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    
    # Inventory Integration
    inventory_product_id = models.IntegerField(null=True, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    
    # Pricing
    list_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    minimum_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Commission & Margins
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    margin_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Product Details
    manufacturer = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    
    # Service/Subscription Details
    is_recurring = models.BooleanField(default=False)
    billing_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
            ('ONE_TIME', 'One Time'),
        ],
        default='ONE_TIME'
    )
    
    # Sales Information
    sales_start_date = models.DateField(null=True, blank=True)
    sales_end_date = models.DateField(null=True, blank=True)
    
    # Performance Metrics
    total_opportunities = models.IntegerField(default=0)
    total_sales_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_quantity_sold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Additional Information
    features = models.JSONField(default=list)
    specifications = models.JSONField(default=dict)
    attachments = models.JSONField(default=list)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_taxable = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'product_type', 'is_active']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'sku']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'product_code'],
                name='unique_tenant_product_code',
                condition=models.Q(product_code__isnull=False)
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.product_code:
            self.product_code = self.generate_product_code()
        
        # Calculate margin percentage
        if self.list_price and self.cost_price:
            self.margin_percentage = ((self.list_price - self.cost_price) / self.list_price) * 100
        
        super().save(*args, **kwargs)
    
    def generate_product_code(self):
        """Generate unique product code"""
        return generate_code('PROD', self.tenant_id)
    
    @property
    def gross_margin(self):
        """Calculate gross margin amount"""
        if self.list_price and self.cost_price:
            return self.list_price - self.cost_price
        return Decimal('0.00')
    
    @property
    def is_profitable(self):
        """Check if product is profitable"""
        return self.gross_margin > 0
    
    def update_sales_metrics(self):
        """Update sales performance metrics"""
        # This would be called by signals when opportunities are won
        won_products = OpportunityProduct.objects.filter(
            opportunity__is_won=True,
            product_id=self.inventory_product_id
        ).aggregate(
            total_amount=models.Sum('total_price'),
            total_quantity=models.Sum('quantity'),
            total_count=models.Count('id')
        )
        
        self.total_sales_amount = won_products['total_amount'] or Decimal('0.00')
        self.total_quantity_sold = won_products['total_quantity'] or Decimal('0.00')
        self.total_opportunities = won_products['total_count'] or 0
        
        self.save(update_fields=[
            'total_sales_amount',
            'total_quantity_sold',
            'total_opportunities'
        ])


class PricingModel(TenantBaseModel, SoftDeleteMixin):
    """Enhanced pricing models for different customer segments"""
    
    PRICING_TYPES = [
        ('STANDARD', 'Standard Pricing'),
        ('VOLUME', 'Volume Pricing'),
        ('TIERED', 'Tiered Pricing'),
        ('CUSTOMER_SPECIFIC', 'Customer Specific'),
        ('PROMOTIONAL', 'Promotional Pricing'),
        ('CONTRACT', 'Contract Pricing'),
    ]
    
    # Pricing Model Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPES)
    
    # Product Association
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='pricing_models'
    )
    
    # Customer Targeting
    customer_segment = models.CharField(max_length=100, blank=True)
    specific_customers = models.ManyToManyField(
        Account,
        blank=True,
        related_name='pricing_models'
    )
    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pricing_models'
    )
    
    # Pricing Structure
    base_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Volume/Tiered Pricing
    pricing_tiers = models.JSONField(default=list)
    
    # Discount Information
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Validity
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    
    # Approval
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_pricing_models'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_apply = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['product', 'effective_from']
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['tenant', 'effective_from', 'effective_to']),
        ]
        
    def __str__(self):
        return f'{self.name} - {self.product.name}'
    
    def get_price_for_quantity(self, quantity):
        """Calculate price based on quantity and pricing tiers"""
        if self.pricing_type == 'VOLUME' and self.pricing_tiers:
            for tier in sorted(self.pricing_tiers, key=lambda x: x.get('min_quantity', 0), reverse=True):
                if quantity >= tier.get('min_quantity', 0):
                    return Decimal(str(tier.get('price', self.base_price)))
        
        elif self.pricing_type == 'TIERED' and self.pricing_tiers:
            total_price = Decimal('0.00')
            remaining_quantity = quantity
            
            for tier in sorted(self.pricing_tiers, key=lambda x: x.get('min_quantity', 0)):
                tier_min = tier.get('min_quantity', 0)
                tier_max = tier.get('max_quantity', float('inf'))
                tier_price = Decimal(str(tier.get('price', self.base_price)))
                
                if remaining_quantity <= 0:
                    break
                
                tier_quantity = min(remaining_quantity, tier_max - tier_min + 1)
                total_price += tier_quantity * tier_price
                remaining_quantity -= tier_quantity
            
            return total_price / quantity if quantity > 0 else self.base_price
        
        return self.base_price
    
    def is_valid_for_date(self, check_date=None):
        """Check if pricing model is valid for given date"""
        if not check_date:
            check_date = date.today()
        
        if check_date < self.effective_from:
            return False
        
        if self.effective_to and check_date > self.effective_to:
            return False
        
        return self.is_active


class ProductBundle(TenantBaseModel, SoftDeleteMixin):
    """Enhanced product bundles with dynamic pricing"""
    
    BUNDLE_TYPES = [
        ('FIXED', 'Fixed Bundle'),
        ('CONFIGURABLE', 'Configurable Bundle'),
        ('PROMOTIONAL', 'Promotional Bundle'),
    ]
    
    # Bundle Information
    bundle_code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPES, default='FIXED')
    
    # Pricing
    bundle_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    individual_price_sum = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    savings_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Validity
    available_from = models.DateField()
    available_to = models.DateField(null=True, blank=True)
    
    # Performance Tracking
    total_sales = models.IntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'bundle_code'],
                name='unique_tenant_bundle_code',
                condition=models.Q(bundle_code__isnull=False)
            ),
        ]
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.bundle_code:
            self.bundle_code = self.generate_bundle_code()
        
        # Calculate savings
        self.calculate_savings()
        
        super().save(*args, **kwargs)
    
    def generate_bundle_code(self):
        """Generate unique bundle code"""
        return generate_code('BUNDLE', self.tenant_id)
    
    def calculate_savings(self):
        """Calculate bundle savings"""
        individual_sum = self.bundle_items.aggregate(
            total=models.Sum(
                models.F('quantity') * models.F('product__list_price'),
                output_field=models.DecimalField()
            )
        )['total'] or Decimal('0.00')
        
        self.individual_price_sum = individual_sum
        self.savings_amount = individual_sum - self.bundle_price
    
    @property
    def savings_percentage(self):
        """Calculate savings percentage"""
        if self.individual_price_sum > 0:
            return (self.savings_amount / self.individual_price_sum) * 100
        return Decimal('0.00')


class ProductBundleItem(TenantBaseModel):
    """Enhanced bundle item configuration"""
    
    bundle = models.ForeignKey(
        ProductBundle,
        on_delete=models.CASCADE,
        related_name='bundle_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='bundle_memberships'
    )
    
    # Quantity & Configuration
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(0.01)]
    )
    
    # Optional/Required
    is_required = models.BooleanField(default=True)
    is_default_selected = models.BooleanField(default=True)
    
    # Pricing Override
    override_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Display
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['bundle', 'display_order']
        constraints = [
            models.UniqueConstraint(
                fields=['bundle', 'product'],
                name='unique_product_per_bundle'
            ),
        ]
        
    def __str__(self):
        return f'{self.bundle.name} - {self.product.name} (x{self.quantity})'
    
    @property
    def effective_price(self):
        """Get effective price for this bundle item"""
        return self.override_price or self.product.list_price
    
    @property
    def total_price(self):
        """Calculate total price for this bundle item"""
        return self.effective_price * self.quantity