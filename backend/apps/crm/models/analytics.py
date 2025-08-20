class Report(TenantBaseModel, SoftDeleteMixin):
    """Enhanced reporting system with custom parameters"""
    
    REPORT_TYPES = [
        ('SALES', 'Sales Report'),
        ('MARKETING', 'Marketing Report'),
        ('ACTIVITY', 'Activity Report'),
        ('CUSTOMER', 'Customer Report'),
        ('PIPELINE', 'Pipeline Report'),
        ('PERFORMANCE', 'Performance Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    REPORT_FORMATS = [
        ('TABLE', 'Table'),
        ('CHART', 'Chart'),
        ('GRAPH', 'Graph'),
        ('DASHBOARD', 'Dashboard'),
    ]
    
    # Report Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    format = models.CharField(max_length=15, choices=REPORT_FORMATS, default='TABLE')
    
    # Query Configuration
    data_source = models.CharField(max_length=100)  # Model or view name
    filters = models.JSONField(default=dict)
    grouping = models.JSONField(default=list)
    sorting = models.JSONField(default=list)
    aggregations = models.JSONField(default=dict)
    
    # Display Configuration
    columns = models.JSONField(default=list)
    chart_config = models.JSONField(default=dict)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_reports'
    )
    shared_with = models.ManyToManyField(
        User,
        through='ReportShare',
        related_name='shared_reports',
        blank=True
    )
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
        ],
        blank=True
    )
    schedule_time = models.TimeField(null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Performance
    execution_time_seconds = models.FloatField(null=True, blank=True)
    row_count = models.IntegerField(null=True, blank=True)
    
    # Usage Tracking
    run_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'report_type', 'owner']),
            models.Index(fields=['tenant', 'is_scheduled']),
        ]
        
    def __str__(self):
        return self.name
    
    def execute(self, user=None, parameters=None):
        """Execute the report and return results"""
        from .services import ReportingService
        
        service = ReportingService(self.tenant)
        results = service.execute_report(self, user, parameters)
        
        # Update usage statistics
        self.run_count += 1
        self.last_accessed = timezone.now()
        self.last_run = timezone.now()
        self.save(update_fields=['run_count', 'last_accessed', 'last_run'])
        
        return results


class ReportShare(TenantBaseModel):
    """Report sharing permissions"""
    
    PERMISSION_LEVELS = [
        ('VIEW', 'View Only'),
        ('EDIT', 'Edit'),
        ('ADMIN', 'Admin'),
    ]
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='shares'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='report_shares'
    )
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='VIEW')
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['report', 'user'],
                name='unique_report_share'
            ),
        ]
        
    def __str__(self):
        return f'{self.report.name} - {self.user.get_full_name()} ({self.permission_level})'


class Dashboard(TenantBaseModel, SoftDeleteMixin):
    """Enhanced dashboard management with widgets"""
    
    DASHBOARD_TYPES = [
        ('PERSONAL', 'Personal Dashboard'),
        ('TEAM', 'Team Dashboard'),
        ('EXECUTIVE', 'Executive Dashboard'),
        ('SALES', 'Sales Dashboard'),
        ('MARKETING', 'Marketing Dashboard'),
        ('SUPPORT', 'Support Dashboard'),
    ]
    
    # Dashboard Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES)
    
    # Layout Configuration
    layout = models.JSONField(default=dict)  # Grid layout configuration
    widgets = models.JSONField(default=list)  # Widget configurations
    
    # Access Control
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_dashboards'
    )
    shared_with = models.ManyToManyField(
        User,
        through='DashboardShare',
        related_name='shared_dashboards',
        blank=True
    )
    
    # Refresh Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval_seconds = models.IntegerField(default=300)  # 5 minutes
    last_refresh = models.DateTimeField(null=True, blank=True)
    
    # Usage Tracking
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'dashboard_type', 'owner']),
            models.Index(fields=['tenant', 'is_default']),
        ]
        
    def __str__(self):
        return self.name
    
    def add_widget(self, widget_config):
        """Add a widget to the dashboard"""
        if not self.widgets:
            self.widgets = []
        self.widgets.append(widget_config)
        self.save(update_fields=['widgets'])
    
    def remove_widget(self, widget_id):
        """Remove a widget from the dashboard"""
        if self.widgets:
            self.widgets = [w for w in self.widgets if w.get('id') != widget_id]
            self.save(update_fields=['widgets'])


class DashboardShare(TenantBaseModel):
    """Dashboard sharing permissions"""
    
    PERMISSION_LEVELS = [
        ('VIEW', 'View Only'),
        ('EDIT', 'Edit'),
        ('ADMIN', 'Admin'),
    ]
    
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='shares'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_shares'
    )
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='VIEW')
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dashboard', 'user'],
                name='unique_dashboard_share'
            ),
        ]
        
    def __str__(self):
        return f'{self.dashboard.name} - {self.user.get_full_name()} ({self.permission_level})'


class Forecast(TenantBaseModel, SoftDeleteMixin):
    """Enhanced sales forecasting with AI/ML integration"""
    
    FORECAST_TYPES = [
        ('REVENUE', 'Revenue Forecast'),
        ('UNITS', 'Units Forecast'),
        ('PIPELINE', 'Pipeline Forecast'),
        ('QUOTA', 'Quota Forecast'),
    ]
    
    FORECAST_PERIODS = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
    ]
    
    # Forecast Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPES)
    period_type = models.CharField(max_length=15, choices=FORECAST_PERIODS)
    
    # Time Period
    start_date = models.DateField()
    end_date = models.DateField()
    forecast_date = models.DateField()  # When forecast was created
    
    # Forecasted Values
    forecasted_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    best_case_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    worst_case_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Actual Results (for accuracy tracking)
    actual_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Methodology
    methodology = models.CharField(
        max_length=20,
        choices=[
            ('MANUAL', 'Manual'),
            ('PIPELINE', 'Pipeline Based'),
            ('HISTORICAL', 'Historical Trending'),
            ('ML', 'Machine Learning'),
            ('HYBRID', 'Hybrid Approach'),
        ],
        default='MANUAL'
    )
    
    # Confidence & Accuracy
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=Decimal('50.00')
    )
    accuracy_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Ownership & Territory
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_forecasts'
    )
    territory = models.ForeignKey(
        'Territory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forecasts'
    )
    team = models.ForeignKey(
        'Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forecasts'
    )
    
    # Breakdown Data
    breakdown_data = models.JSONField(default=dict)  # Detailed breakdown by product, rep, etc.
    assumptions = models.TextField(blank=True)
    risk_factors = models.TextField(blank=True)
    
    # Approval Workflow
    is_submitted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    submitted_date = models.DateTimeField(null=True, blank=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_forecasts'
    )
    
    class Meta:
        ordering = ['-forecast_date']
        indexes = [
            models.Index(fields=['tenant', 'forecast_type', 'period_type']),
            models.Index(fields=['tenant', 'owner', 'start_date']),
            models.Index(fields=['tenant', 'territory']),
        ]
        
    def __str__(self):
        return f'{self.name} - {self.start_date} to {self.end_date}'
    
    def calculate_accuracy(self):
        """Calculate forecast accuracy when actual results are available"""
        if self.actual_amount is not None and self.forecasted_amount > 0:
            variance = abs(self.actual_amount - self.forecasted_amount)
            self.accuracy_percentage = max(0, 100 - ((variance / self.forecasted_amount) * 100))
            self.save(update_fields=['accuracy_percentage'])
    
    @property
    def variance_amount(self):
        """Calculate variance between forecast and actual"""
        if self.actual_amount is not None:
            return self.actual_amount - self.forecasted_amount
        return None
    
    @property
    def variance_percentage(self):
        """Calculate variance percentage"""
        if self.actual_amount is not None and self.forecasted_amount > 0:
            return ((self.actual_amount - self.forecasted_amount) / self.forecasted_amount) * 100
        return None


class PerformanceMetric(TenantBaseModel):
    """Enhanced performance metrics tracking"""
    
    METRIC_TYPES = [
        ('REVENUE', 'Revenue'),
        ('LEADS', 'Leads'),
        ('CONVERSION', 'Conversion Rate'),
        ('ACTIVITY', 'Activity Count'),
        ('SATISFACTION', 'Customer Satisfaction'),
        ('RESPONSE_TIME', 'Response Time'),
        ('RESOLUTION_TIME', 'Resolution Time'),
        ('QUOTA_ATTAINMENT', 'Quota Attainment'),
    ]
    
    AGGREGATION_TYPES = [
        ('SUM', 'Sum'),
        ('AVERAGE', 'Average'),
        ('COUNT', 'Count'),
        ('MAX', 'Maximum'),
        ('MIN', 'Minimum'),
        ('PERCENTAGE', 'Percentage'),
    ]
    
    # Metric Definition
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    aggregation_type = models.CharField(max_length=15, choices=AGGREGATION_TYPES)
    
    # Time Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Metric Values
    target_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    actual_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    previous_period_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Entity Association
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='performance_metrics'
    )
    team = models.ForeignKey(
        'Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performance_metrics'
    )
    territory = models.ForeignKey(
        'Territory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performance_metrics'
    )
    
    # Calculation Details
    calculation_method = models.TextField(blank=True)
    data_sources = models.JSONField(default=list)
    filters_applied = models.JSONField(default=dict)
    
    # Status
    is_current = models.BooleanField(default=True)
    last_calculated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-period_end', 'name']
        indexes = [
            models.Index(fields=['tenant', 'metric_type', 'period_end']),
            models.Index(fields=['tenant', 'user', 'period_end']),
            models.Index(fields=['tenant', 'team', 'period_end']),
        ]
        
    def __str__(self):
        entity = self.user or self.team or self.territory or 'Company'
        return f'{self.name} - {entity} ({self.period_start} to {self.period_end})'
    
    @property
    def achievement_percentage(self):
        """Calculate achievement percentage against target"""
        if self.target_value and self.target_value > 0:
            return (self.actual_value / self.target_value) * 100
        return 0
    
    @property
    def variance_from_target(self):
        """Calculate variance from target"""
        if self.target_value is not None:
            return self.actual_value - self.target_value
        return None
    
    @property
    def period_over_period_change(self):
        """Calculate change from previous period"""
        if self.previous_period_value is not None:
            return self.actual_value - self.previous_period_value
        return None
    
    @property
    def period_over_period_percentage(self):
        """Calculate percentage change from previous period"""
        if self.previous_period_value and self.previous_period_value > 0:
            return ((self.actual_value - self.previous_period_value) / self.previous_period_value) * 100
        return None