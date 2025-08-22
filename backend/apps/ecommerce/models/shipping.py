# apps/ecommerce/models/shipping.py

"""
Advanced Shipping Management System with AI-powered predictive analytics, 
intelligent routing, and automated logistics optimization
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import uuid
from datetime import timedelta, date
from enum import TextChoices
import json

from .base import EcommerceBaseModel, CommonChoices, AuditMixin
from .managers import ShippingManager


class ShippingZone(EcommerceBaseModel, AuditMixin):
    """
    Geographic shipping zones with AI-powered delivery optimization
    """
    
    class ZoneType(models.TextChoices):
        DOMESTIC = 'DOMESTIC', 'Domestic'
        INTERNATIONAL = 'INTERNATIONAL', 'International'
        REGIONAL = 'REGIONAL', 'Regional'
        EXPRESS = 'EXPRESS', 'Express Zone'
        RESTRICTED = 'RESTRICTED', 'Restricted'
    
    zone_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=200)
    zone_type = models.CharField(max_length=15, choices=ZoneType.choices, default=ZoneType.DOMESTIC)
    
    # Geographic coverage
    countries = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    states_provinces = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    postal_codes = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    cities = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    
    # Zone configuration
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1, help_text="Lower number = higher priority")
    
    # AI-powered delivery analytics
    average_delivery_days = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    delivery_success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'))
    delivery_cost_efficiency = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Predictive insights
    demand_forecast = models.JSONField(default=dict, blank=True, help_text="Monthly demand predictions")
    seasonal_patterns = models.JSONField(default=dict, blank=True)
    peak_delivery_hours = ArrayField(models.PositiveIntegerField(), default=list, blank=True)
    
    # Risk assessment
    risk_level = models.CharField(max_length=10, default='LOW', choices=[
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk')
    ])
    weather_impact_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    infrastructure_quality = models.PositiveIntegerField(null=True, blank=True, help_text="1-10 scale")
    
    # Performance tracking
    total_shipments = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries = models.PositiveIntegerField(default=0)
    average_delay_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    
    objects = ShippingManager()
    
    class Meta:
        db_table = 'ecommerce_shipping_zones'
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'zone_type', 'is_active']),
            models.Index(fields=['tenant', 'priority']),
            models.Index(fields=['tenant', 'risk_level']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.zone_type})"
    
    def is_address_in_zone(self, address):
        """Check if an address falls within this shipping zone"""
        # Country check
        if self.countries and address.get('country') not in self.countries:
            return False
        
        # State/Province check
        if self.states_provinces and address.get('state_province') not in self.states_provinces:
            return False
        
        # Postal code check (basic implementation)
        if self.postal_codes:
            postal_code = address.get('postal_code', '')
            if not any(postal_code.startswith(pc) for pc in self.postal_codes):
                return False
        
        # City check
        if self.cities and address.get('city') not in self.cities:
            return False
        
        return True
    
    def calculate_delivery_prediction(self, order_weight=None, order_value=None):
        """Calculate AI-powered delivery time prediction"""
        base_days = self.average_delivery_days or Decimal('3.0')
        
        # Adjust based on zone risk level
        risk_adjustments = {
            'LOW': 1.0,
            'MEDIUM': 1.2,
            'HIGH': 1.5,
            'CRITICAL': 2.0
        }
        
        adjusted_days = base_days * Decimal(str(risk_adjustments.get(self.risk_level, 1.0)))
        
        # Weather impact adjustment
        if self.weather_impact_score:
            weather_adjustment = 1 + (self.weather_impact_score / 100)
            adjusted_days *= Decimal(str(weather_adjustment))
        
        # Seasonal adjustment (simple implementation)
        current_month = timezone.now().month
        seasonal_data = self.seasonal_patterns.get(str(current_month), {})
        seasonal_multiplier = seasonal_data.get('delivery_multiplier', 1.0)
        adjusted_days *= Decimal(str(seasonal_multiplier))
        
        return adjusted_days.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    
    def update_performance_metrics(self):
        """Update zone performance metrics from shipment data"""
        # This would be called periodically to update metrics
        shipments = ShipmentTracking.objects.filter(
            shipping_method__shipping_zone=self,
            created_at__gte=timezone.now() - timedelta(days=90)
        )
        
        if shipments.exists():
            self.total_shipments = shipments.count()
            self.successful_deliveries = shipments.filter(status='DELIVERED').count()
            self.failed_deliveries = shipments.filter(status__in=['FAILED', 'LOST', 'DAMAGED']).count()
            
            # Calculate success rate
            if self.total_shipments > 0:
                self.delivery_success_rate = (
                    self.successful_deliveries / self.total_shipments * 100
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Calculate average delivery days
            delivered_shipments = shipments.filter(status='DELIVERED', delivered_at__isnull=False)
            if delivered_shipments.exists():
                delivery_times = []
                for shipment in delivered_shipments:
                    if shipment.shipped_at:
                        delivery_time = (shipment.delivered_at - shipment.shipped_at).days
                        delivery_times.append(delivery_time)
                
                if delivery_times:
                    self.average_delivery_days = Decimal(str(sum(delivery_times) / len(delivery_times)))
            
            self.save(update_fields=[
                'total_shipments', 'successful_deliveries', 'failed_deliveries',
                'delivery_success_rate', 'average_delivery_days'
            ])


class ShippingMethod(EcommerceBaseModel, AuditMixin):
    """
    Shipping methods with AI-powered pricing and delivery optimization
    """
    
    class MethodType(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard Shipping'
        EXPRESS = 'EXPRESS', 'Express Shipping'
        OVERNIGHT = 'OVERNIGHT', 'Overnight Delivery'
        SAME_DAY = 'SAME_DAY', 'Same Day Delivery'
        PICKUP = 'PICKUP', 'Store Pickup'
        DRONE = 'DRONE', 'Drone Delivery'
        FREIGHT = 'FREIGHT', 'Freight Shipping'
    
    class PricingModel(models.TextChoices):
        FLAT_RATE = 'FLAT_RATE', 'Flat Rate'
        WEIGHT_BASED = 'WEIGHT_BASED', 'Weight Based'
        PRICE_BASED = 'PRICE_BASED', 'Price Based'
        ZONE_BASED = 'ZONE_BASED', 'Zone Based'
        AI_DYNAMIC = 'AI_DYNAMIC', 'AI Dynamic Pricing'
    
    method_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=200)
    method_type = models.CharField(max_length=15, choices=MethodType.choices, default=MethodType.STANDARD)
    
    # Method configuration
    shipping_zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='shipping_methods')
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Delivery specifications
    min_delivery_days = models.PositiveIntegerField(default=1)
    max_delivery_days = models.PositiveIntegerField(default=7)
    cutoff_time = models.TimeField(null=True, blank=True, help_text="Order cutoff time for this delivery speed")
    
    # Constraints
    min_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_order_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Pricing configuration
    pricing_model = models.CharField(max_length=15, choices=PricingModel.choices, default=PricingModel.FLAT_RATE)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # AI-powered pricing
    dynamic_pricing_enabled = models.BooleanField(default=False)
    pricing_algorithm = models.CharField(max_length=50, blank=True)
    demand_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    
    # Carrier information
    carrier_name = models.CharField(max_length=100, blank=True)
    carrier_service_code = models.CharField(max_length=50, blank=True)
    tracking_url_template = models.URLField(blank=True)
    
    # Performance metrics
    average_delivery_time = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'))
    customer_satisfaction = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    
    # Predictive analytics
    demand_forecast = models.JSONField(default=dict, blank=True)
    capacity_utilization = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cost_efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Environmental impact
    carbon_footprint_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    eco_friendly_score = models.PositiveIntegerField(null=True, blank=True, help_text="1-10 scale")
    
    objects = ShippingManager()
    
    class Meta:
        db_table = 'ecommerce_shipping_methods'
        ordering = ['shipping_zone', 'min_delivery_days', 'name']
        indexes = [
            models.Index(fields=['tenant', 'shipping_zone', 'is_active']),
            models.Index(fields=['tenant', 'method_type']),
            models.Index(fields=['tenant', 'is_default']),
            models.Index(fields=['tenant', 'carrier_name']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_delivery_days__lte=models.F('max_delivery_days')),
                name='valid_delivery_days_range'
            ),
            models.CheckConstraint(
                check=models.Q(min_weight__lte=models.F('max_weight')) | 
                      models.Q(min_weight__isnull=True) | 
                      models.Q(max_weight__isnull=True),
                name='valid_weight_range'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.shipping_zone.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default method per zone
        if self.is_default:
            ShippingMethod.objects.filter(
                tenant=self.tenant,
                shipping_zone=self.shipping_zone,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    def calculate_shipping_cost(self, order_weight=None, order_value=None, destination_address=None):
        """Calculate AI-powered shipping cost"""
        base_cost = self.base_price
        
        # Apply pricing model
        if self.pricing_model == self.PricingModel.WEIGHT_BASED and order_weight and self.price_per_kg:
            base_cost += order_weight * self.price_per_kg
        
        elif self.pricing_model == self.PricingModel.PRICE_BASED and order_value:
            # Percentage-based pricing (example: 5% of order value)
            percentage = Decimal('0.05')  # This could be configurable
            base_cost = order_value * percentage
        
        elif self.pricing_model == self.PricingModel.AI_DYNAMIC:
            base_cost = self.calculate_dynamic_pricing(order_weight, order_value, destination_address)
        
        # Apply free shipping threshold
        if self.free_shipping_threshold and order_value and order_value >= self.free_shipping_threshold:
            base_cost = Decimal('0.00')
        
        # Apply demand multiplier
        base_cost *= self.demand_multiplier
        
        return base_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def calculate_dynamic_pricing(self, order_weight=None, order_value=None, destination_address=None):
        """AI-powered dynamic pricing calculation"""
        base_cost = self.base_price
        
        # Time-based pricing (higher during peak hours)
        current_hour = timezone.now().hour
        if 9 <= current_hour <= 17:  # Business hours
            base_cost *= Decimal('1.2')
        
        # Demand-based pricing
        if self.capacity_utilization and self.capacity_utilization > 80:
            base_cost *= Decimal('1.3')
        elif self.capacity_utilization and self.capacity_utilization < 50:
            base_cost *= Decimal('0.9')
        
        # Distance-based adjustment (placeholder - would use actual distance calculation)
        if destination_address:
            # This would integrate with mapping services for actual distance
            base_cost *= Decimal('1.1')  # Example adjustment
        
        # Weather impact
        if hasattr(self.shipping_zone, 'weather_impact_score') and self.shipping_zone.weather_impact_score:
            weather_adjustment = 1 + (self.shipping_zone.weather_impact_score / 100)
            base_cost *= Decimal(str(weather_adjustment))
        
        return base_cost
    
    def calculate_delivery_estimate(self, order_placed_at=None):
        """Calculate AI-powered delivery time estimate"""
        if not order_placed_at:
            order_placed_at = timezone.now()
        
        # Start with base delivery time
        base_days = (self.min_delivery_days + self.max_delivery_days) / 2
        
        # Check cutoff time
        cutoff_adjustment = 0
        if self.cutoff_time:
            order_time = order_placed_at.time()
            if order_time > self.cutoff_time:
                cutoff_adjustment = 1  # Add one day if after cutoff
        
        # Weekend adjustment
        order_weekday = order_placed_at.weekday()
        weekend_adjustment = 0
        if order_weekday >= 5:  # Saturday or Sunday
            weekend_adjustment = 2 - order_weekday + 5  # Move to Monday
        
        # Use zone-specific prediction
        zone_prediction = self.shipping_zone.calculate_delivery_prediction()
        
        # Combine factors
        estimated_days = max(
            base_days + cutoff_adjustment + weekend_adjustment,
            float(zone_prediction)
        )
        
        estimated_delivery = order_placed_at + timedelta(days=int(estimated_days))
        
        return estimated_delivery
    
    def is_available_for_order(self, order_weight=None, order_value=None, destination_address=None):
        """Check if this shipping method is available for an order"""
        if not self.is_active:
            return False
        
        # Check weight constraints
        if self.min_weight and order_weight and order_weight < self.min_weight:
            return False
        
        if self.max_weight and order_weight and order_weight > self.max_weight:
            return False
        
        # Check value constraints
        if self.min_order_value and order_value and order_value < self.min_order_value:
            return False
        
        if self.max_order_value and order_value and order_value > self.max_order_value:
            return False
        
        # Check if destination is in shipping zone
        if destination_address and not self.shipping_zone.is_address_in_zone(destination_address):
            return False
        
        return True
    
    def update_performance_metrics(self):
        """Update method performance metrics from shipment data"""
        recent_shipments = ShipmentTracking.objects.filter(
            shipping_method=self,
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        if recent_shipments.exists():
            # Calculate average delivery time
            delivered_shipments = recent_shipments.filter(
                status='DELIVERED',
                delivered_at__isnull=False,
                shipped_at__isnull=False
            )
            
            if delivered_shipments.exists():
                delivery_times = []
                on_time_count = 0
                
                for shipment in delivered_shipments:
                    actual_days = (shipment.delivered_at - shipment.shipped_at).days
                    delivery_times.append(actual_days)
                    
                    # Check if delivered on time (within max delivery days)
                    if actual_days <= self.max_delivery_days:
                        on_time_count += 1
                
                if delivery_times:
                    self.average_delivery_time = Decimal(str(sum(delivery_times) / len(delivery_times)))
                    self.on_time_delivery_rate = (
                        on_time_count / len(delivery_times) * 100
                    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Update capacity utilization (simplified)
            total_orders = recent_shipments.count()
            max_capacity = 1000  # This would be configurable
            self.capacity_utilization = min(
                (total_orders / max_capacity * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                Decimal('100.00')
            )
            
            self.save(update_fields=[
                'average_delivery_time', 'on_time_delivery_rate', 'capacity_utilization'
            ])


class ShipmentTracking(EcommerceBaseModel, AuditMixin):
    """
    Comprehensive shipment tracking with AI-powered insights and predictions
    """
    
    class ShipmentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Shipment'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for Delivery'
        DELIVERED = 'DELIVERED', 'Delivered'
        FAILED = 'FAILED', 'Delivery Failed'
        RETURNED = 'RETURNED', 'Returned to Sender'
        LOST = 'LOST', 'Lost in Transit'
        DAMAGED = 'DAMAGED', 'Damaged'
    
    class DeliveryAttemptResult(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Successful Delivery'
        FAILED_NO_ONE_HOME = 'FAILED_NO_ONE_HOME', 'No One Home'
        FAILED_REFUSED = 'FAILED_REFUSED', 'Delivery Refused'
        FAILED_ADDRESS = 'FAILED_ADDRESS', 'Invalid Address'
        FAILED_DAMAGED = 'FAILED_DAMAGED', 'Package Damaged'
        FAILED_WEATHER = 'FAILED_WEATHER', 'Weather Conditions'
        FAILED_OTHER = 'FAILED_OTHER', 'Other Reason'
    
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tracking_number = models.CharField(max_length=100, unique=True, blank=True)
    
    # Order relationship
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='shipments')
    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.PROTECT, related_name='shipments')
    
    # Shipment details
    status = models.CharField(max_length=20, choices=ShipmentStatus.choices, default=ShipmentStatus.PENDING)
    carrier_name = models.CharField(max_length=100, blank=True)
    carrier_service = models.CharField(max_length=100, blank=True)
    
    # Addresses
    pickup_address = models.JSONField(default=dict, blank=True)
    delivery_address = models.JSONField(default=dict, blank=True)
    
    # Package information
    total_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dimensions = models.JSONField(default=dict, blank=True, help_text="length, width, height in cm")
    package_count = models.PositiveIntegerField(default=1)
    declared_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Timing
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Costs
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    insurance_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    additional_fees = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # AI-powered insights
    delivery_probability = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="AI-predicted successful delivery probability (0-100%)"
    )
    delay_risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Risk score for delivery delays (0-100)"
    )
    damage_risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Risk score for package damage (0-100)"
    )
    
    # Route optimization
    optimized_route = models.JSONField(default=list, blank=True)
    route_efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    carbon_footprint_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Delivery attempts
    delivery_attempts = models.PositiveIntegerField(default=0)
    max_delivery_attempts = models.PositiveIntegerField(default=3)
    last_attempt_result = models.CharField(
        max_length=25, choices=DeliveryAttemptResult.choices, blank=True
    )
    
    # Customer communication
    notifications_sent = models.JSONField(default=list, blank=True)
    customer_signature = models.TextField(blank=True)
    delivery_instructions = models.TextField(blank=True)
    
    # Exception handling
    exceptions = models.JSONField(default=list, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    objects = ShippingManager()
    
    class Meta:
        db_table = 'ecommerce_shipment_tracking'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'tracking_number']),
            models.Index(fields=['tenant', 'order']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'carrier_name']),
            models.Index(fields=['tenant', 'estimated_delivery']),
            models.Index(fields=['tenant', 'shipped_at']),
            models.Index(fields=['tenant', 'delivered_at']),
        ]
    
    def __str__(self):
        return f"Shipment {self.tracking_number} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        
        # Update carrier info from shipping method
        if self.shipping_method and not self.carrier_name:
            self.carrier_name = self.shipping_method.carrier_name
            self.carrier_service = self.shipping_method.carrier_service_code
        
        # Auto-set shipped_at when status changes to SHIPPED
        if self.status == self.ShipmentStatus.SHIPPED and not self.shipped_at:
            self.shipped_at = timezone.now()
        
        # Auto-set delivered_at when status changes to DELIVERED
        if self.status == self.ShipmentStatus.DELIVERED and not self.delivered_at:
            self.delivered_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_tracking_number(self):
        """Generate unique tracking number"""
        import random
        import string
        
        prefix = f"{self.tenant.schema_name.upper()[:3]}"
        timestamp = timezone.now().strftime('%Y%m%d')
        random_suffix = ''.join(random.choices(string.digits, k=6))
        
        return f"{prefix}{timestamp}{random_suffix}"
    
    @property
    def is_delivered(self):
        """Check if shipment is delivered"""
        return self.status == self.ShipmentStatus.DELIVERED
    
    @property
    def is_delayed(self):
        """Check if shipment is delayed"""
        if not self.estimated_delivery:
            return False
        
        return timezone.now() > self.estimated_delivery and not self.is_delivered
    
    @property
    def delivery_time_days(self):
        """Calculate actual delivery time in days"""
        if self.shipped_at and self.delivered_at:
            return (self.delivered_at - self.shipped_at).days
        return None
    
    def calculate_delivery_prediction(self):
        """Calculate AI-powered delivery success probability"""
        base_probability = Decimal('85.00')  # Base 85% success rate
        
        # Adjust based on shipping zone performance
        zone_success_rate = self.shipping_method.shipping_zone.delivery_success_rate
        zone_adjustment = (zone_success_rate - 85) / 10  # Scale adjustment
        base_probability += zone_adjustment
        
        # Adjust based on delivery attempts
        if self.delivery_attempts > 0:
            attempt_penalty = self.delivery_attempts * Decimal('10.00')
            base_probability -= attempt_penalty
        
        # Adjust based on address risk factors
        address_risk = self.assess_address_risk()
        base_probability -= address_risk
        
        # Weather impact (placeholder)
        weather_impact = self.get_weather_impact()
        base_probability -= weather_impact
        
        # Package characteristics
        if self.total_weight and self.total_weight > 10:  # Heavy packages
            base_probability -= Decimal('5.00')
        
        if self.declared_value and self.declared_value > 1000:  # High-value packages
            base_probability -= Decimal('3.00')
        
        self.delivery_probability = max(min(base_probability, Decimal('99.00')), Decimal('1.00'))
        self.save(update_fields=['delivery_probability'])
        
        return self.delivery_probability
    
    def assess_address_risk(self):
        """Assess delivery risk based on address characteristics"""
        risk_score = Decimal('0.00')
        
        delivery_addr = self.delivery_address
        if not delivery_addr:
            return risk_score
        
        # Rural area risk (simplified check)
        if not delivery_addr.get('city') or len(delivery_addr.get('city', '')) < 3:
            risk_score += Decimal('15.00')
        
        # Incomplete address risk
        required_fields = ['address_line_1', 'city', 'postal_code']
        missing_fields = sum(1 for field in required_fields if not delivery_addr.get(field))
        risk_score += missing_fields * Decimal('10.00')
        
        # PO Box delivery (higher risk for some carriers)
        address_line1 = delivery_addr.get('address_line_1', '').upper()
        if 'PO BOX' in address_line1 or 'P.O. BOX' in address_line1:
            risk_score += Decimal('5.00')
        
        return min(risk_score, Decimal('50.00'))  # Cap at 50%
    
    def get_weather_impact(self):
        """Get weather impact on delivery (placeholder for weather API integration)"""
        # This would integrate with weather APIs to assess current conditions
        # For now, return a random factor
        import random
        return Decimal(str(random.uniform(0, 10)))
    
    def calculate_delay_risk(self):
        """Calculate risk of delivery delays"""
        base_risk = Decimal('10.00')  # Base 10% delay risk
        
        # Historical performance of shipping method
        if self.shipping_method.on_time_delivery_rate:
            on_time_rate = self.shipping_method.on_time_delivery_rate
            delay_risk_from_history = 100 - on_time_rate
            base_risk += delay_risk_from_history * Decimal('0.5')
        
        # Capacity utilization impact
        if self.shipping_method.capacity_utilization:
            if self.shipping_method.capacity_utilization > 90:
                base_risk += Decimal('20.00')
            elif self.shipping_method.capacity_utilization > 80:
                base_risk += Decimal('10.00')
        
        # Distance impact (placeholder)
        base_risk += Decimal('5.00')  # Simplified distance factor
        
        # Time of year impact (holiday seasons)
        current_month = timezone.now().month
        if current_month in [11, 12]:  # Holiday season
            base_risk += Decimal('15.00')
        
        self.delay_risk_score = min(base_risk, Decimal('95.00'))
        self.save(update_fields=['delay_risk_score'])
        
        return self.delay_risk_score
    
    def optimize_delivery_route(self):
        """AI-powered delivery route optimization"""
        # This would integrate with routing optimization services
        # For now, create a basic route structure
        
        route_points = []
        
        # Add pickup point
        if self.pickup_address:
            route_points.append({
                'type': 'pickup',
                'address': self.pickup_address,
                'estimated_arrival': timezone.now().isoformat(),
                'priority': 1
            })
        
        # Add delivery point
        if self.delivery_address:
            # Calculate estimated arrival (simplified)
            estimated_arrival = timezone.now() + timedelta(
                days=self.shipping_method.min_delivery_days
            )
            
            route_points.append({
                'type': 'delivery',
                'address': self.delivery_address,
                'estimated_arrival': estimated_arrival.isoformat(),
                'priority': 2
            })
        
        self.optimized_route = route_points
        
        # Calculate efficiency score (simplified)
        self.route_efficiency_score = Decimal('85.00')  # Placeholder
        
        # Estimate carbon footprint
        self.estimate_carbon_footprint()
        
        self.save(update_fields=['optimized_route', 'route_efficiency_score', 'carbon_footprint_kg'])
    
    def estimate_carbon_footprint(self):
        """Estimate carbon footprint of this shipment"""
        # Simplified calculation - in reality this would consider:
        # - Distance traveled
        # - Transportation mode
        # - Package weight
        # - Fuel efficiency
        # - Route optimization
        
        base_footprint = Decimal('2.5')  # kg CO2 base
        
        # Adjust for package weight
        if self.total_weight:
            weight_factor = self.total_weight / 10  # Scale factor
            base_footprint *= (1 + weight_factor * Decimal('0.1'))
        
        # Adjust for shipping method type
        method_factors = {
            'SAME_DAY': Decimal('2.0'),
            'OVERNIGHT': Decimal('1.5'),
            'EXPRESS': Decimal('1.2'),
            'STANDARD': Decimal('1.0'),
            'FREIGHT': Decimal('0.8'),
        }
        
        method_factor = method_factors.get(self.shipping_method.method_type, Decimal('1.0'))
        base_footprint *= method_factor
        
        self.carbon_footprint_kg = base_footprint.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def record_delivery_attempt(self, result, notes=""):
        """Record a delivery attempt"""
        self.delivery_attempts += 1
        self.last_attempt_result = result
        
        attempt_record = {
            'attempt_number': self.delivery_attempts,
            'timestamp': timezone.now().isoformat(),
            'result': result,
            'notes': notes
        }
        
        # Add to notifications history
        if not isinstance(self.notifications_sent, list):
            self.notifications_sent = []
        
        self.notifications_sent.append(attempt_record)
        
        # Update status based on attempt result
        if result == self.DeliveryAttemptResult.SUCCESS:
            self.status = self.ShipmentStatus.DELIVERED
            self.delivered_at = timezone.now()
        elif self.delivery_attempts >= self.max_delivery_attempts:
            self.status = self.ShipmentStatus.RETURNED
        else:
            self.status = self.ShipmentStatus.FAILED
        
        self.save(update_fields=[
            'delivery_attempts', 'last_attempt_result', 'notifications_sent', 
            'status', 'delivered_at'
        ])
    
    def add_exception(self, exception_type, description, severity='MEDIUM'):
        """Add a shipping exception"""
        exception_record = {
            'type': exception_type,
            'description': description,
            'severity': severity,
            'timestamp': timezone.now().isoformat(),
            'resolved': False
        }
        
        if not isinstance(self.exceptions, list):
            self.exceptions = []
        
        self.exceptions.append(exception_record)
        self.save(update_fields=['exceptions'])
    
    def get_tracking_url(self):
        """Get tracking URL from carrier"""
        if self.shipping_method.tracking_url_template and self.tracking_number:
            return self.shipping_method.tracking_url_template.replace(
                '{tracking_number}', self.tracking_number
            )
        return None
    
    def get_shipment_analytics(self):
        """Get comprehensive shipment analytics"""
        analytics = {
            'delivery_prediction': {
                'probability': float(self.delivery_probability or 0),
                'estimated_delivery': self.estimated_delivery.isoformat() if self.estimated_delivery else None,
                'delay_risk': float(self.delay_risk_score or 0)
            },
            'performance': {
                'delivery_attempts': self.delivery_attempts,
                'current_status': self.status,
                'on_time_delivery': self.is_delivered and not self.is_delayed,
                'delivery_time_days': self.delivery_time_days
            },
            'environmental': {
                'carbon_footprint_kg': float(self.carbon_footprint_kg or 0),
                'route_efficiency': float(self.route_efficiency_score or 0)
            },
            'costs': {
                'shipping_cost': float(self.shipping_cost),
                'insurance_cost': float(self.insurance_cost or 0),
                'additional_fees': float(self.additional_fees),
                'total_cost': float(self.shipping_cost + (self.insurance_cost or 0) + self.additional_fees)
            },
            'exceptions': len(self.exceptions) if self.exceptions else 0,
            'customer_satisfaction': {
                'delivery_rating': None,  # Would be populated from customer feedback
                'tracking_engagement': len(self.notifications_sent) if self.notifications_sent else 0
            }
        }
        
        return analytics


class DeliverySlot(EcommerceBaseModel, AuditMixin):
    """
    AI-optimized delivery time slot management
    """
    
    class SlotStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        RESERVED = 'RESERVED', 'Reserved'
        BOOKED = 'BOOKED', 'Booked'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    slot_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    shipping_zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='delivery_slots')
    
    # Time slot details
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=15, choices=SlotStatus.choices, default=SlotStatus.AVAILABLE)
    
    # Capacity management
    max_deliveries = models.PositiveIntegerField(default=10)
    current_bookings = models.PositiveIntegerField(default=0)
    reserved_capacity = models.PositiveIntegerField(default=0)
    
    # AI-powered optimization
    demand_prediction = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    optimal_price_adjustment = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    success_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Route optimization
    delivery_routes = models.JSONField(default=list, blank=True)
    estimated_completion_time = models.TimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ecommerce_delivery_slots'
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['tenant', 'shipping_zone', 'date']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'date', 'start_time']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='valid_time_slot'
            ),
            models.CheckConstraint(
                check=models.Q(current_bookings__lte=models.F('max_deliveries')),
                name='valid_booking_capacity'
            ),
        ]
    
    def __str__(self):
        return f"{self.date} {self.start_time}-{self.end_time} ({self.shipping_zone.name})"
    
    @property
    def is_available(self):
        """Check if slot has available capacity"""
        return (self.status == self.SlotStatus.AVAILABLE and 
                self.current_bookings < self.max_deliveries)
    
    @property
    def utilization_rate(self):
        """Calculate slot utilization rate"""
        if self.max_deliveries == 0:
            return 0
        return (self.current_bookings / self.max_deliveries) * 100
    
    def book_slot(self, shipment):
        """Book this delivery slot for a shipment"""
        if not self.is_available:
            raise ValidationError("Delivery slot is not available")
        
        self.current_bookings += 1
        if self.current_bookings >= self.max_deliveries:
            self.status = self.SlotStatus.BOOKED
        
        self.save(update_fields=['current_bookings', 'status'])
        
        # Update delivery routes
        self.optimize_delivery_routes()
    
    def optimize_delivery_routes(self):
        """Optimize delivery routes for this slot"""
        # This would use AI algorithms to optimize delivery routes
        # For now, create a basic route structure
        
        shipments = ShipmentTracking.objects.filter(
            shipping_method__shipping_zone=self.shipping_zone,
            estimated_delivery__date=self.date,
            estimated_delivery__time__range=(self.start_time, self.end_time)
        )
        
        routes = []
        for i, shipment in enumerate(shipments):
            route_point = {
                'order': i + 1,
                'shipment_id': str(shipment.tracking_id),
                'address': shipment.delivery_address,
                'estimated_duration': 15,  # minutes
                'priority': 'NORMAL'
            }
            routes.append(route_point)
        
        self.delivery_routes = routes
        
        # Calculate estimated completion time
        total_duration = len(routes) * 15  # 15 minutes per delivery
        completion_time = timezone.datetime.combine(
            self.date,
            self.start_time
        ) + timedelta(minutes=total_duration)
        
        self.estimated_completion_time = completion_time.time()
        
        self.save(update_fields=['delivery_routes', 'estimated_completion_time'])
    
    def calculate_demand_prediction(self):
        """Calculate AI-powered demand prediction for this slot"""
        # Analyze historical data for similar slots
        similar_slots = DeliverySlot.objects.filter(
            tenant=self.tenant,
            shipping_zone=self.shipping_zone,
            date__day=self.date.day,
            start_time=self.start_time
        ).exclude(id=self.id)
        
        if similar_slots.exists():
            avg_utilization = similar_slots.aggregate(
                avg_bookings=models.Avg('current_bookings')
            )['avg_bookings'] or 0
            
            self.demand_prediction = Decimal(str(avg_utilization))
        else:
            # Default prediction based on time of day
            hour = self.start_time.hour
            if 9 <= hour <= 17:  # Business hours
                self.demand_prediction = Decimal('8.0')
            elif 17 <= hour <= 20:  # Evening
                self.demand_prediction = Decimal('12.0')
            else:
                self.demand_prediction = Decimal('4.0')
        
        self.save(update_fields=['demand_prediction'])
        
        return self.demand_prediction