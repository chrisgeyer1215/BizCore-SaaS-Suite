# apps/inventory/api/v1/serializers/alerts.py

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.inventory.models.alerts.alerts import InventoryAlert
from .base import AuditableSerializer, DynamicFieldsSerializer

class InventoryAlertSerializer(AuditableSerializer, DynamicFieldsSerializer):
    """Main inventory alert serializer."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True, allow_null=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True, allow_null=True)
    
    # Calculated fields
    alert_age_hours = serializers.SerializerMethodField()
    response_time_hours = serializers.SerializerMethodField()
    resolution_time_hours = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    severity_score = serializers.SerializerMethodField()
    
    # Context data
    current_stock_level = serializers.SerializerMethodField()
    threshold_value = serializers.SerializerMethodField()
    recommended_action = serializers.SerializerMethodField()
    
    class Meta:
        model = InventoryAlert
        fields = [
            'id', 'alert_type', 'priority', 'status', 'title', 'message',
            'product', 'product_name', 'product_sku',
            'warehouse', 'warehouse_name', 'threshold_value',
            'current_value', 'current_stock_level', 'context_data',
            'acknowledged_at', 'acknowledged_by', 'acknowledged_by_name', 'acknowledgment_notes',
            'resolved_at', 'resolved_by', 'resolved_by_name', 'resolution_notes',
            'dismissed_at', 'dismissal_reason', 'auto_resolved',
            'alert_age_hours', 'response_time_hours', 'resolution_time_hours',
            'is_overdue', 'severity_score', 'recommended_action',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'alert_age_hours', 'response_time_hours', 'resolution_time_hours',
            'is_overdue', 'severity_score', 'current_stock_level', 'recommended_action'
        ]
    
    def get_alert_age_hours(self, obj):
        """Calculate hours since alert was created."""
        return (timezone.now() - obj.created_at).total_seconds() / 3600
    
    def get_response_time_hours(self, obj):
        """Calculate response time (creation to acknowledgment)."""
        if not obj.acknowledged_at:
            return None
        return (obj.acknowledged_at - obj.created_at).total_seconds() / 3600
    
    def get_resolution_time_hours(self, obj):
        """Calculate resolution time (creation to resolution)."""
        if not obj.resolved_at:
            return None
        return (obj.resolved_at - obj.created_at).total_seconds() / 3600
    
    def get_is_overdue(self, obj):
        """Check if alert is overdue based on priority SLA."""
        sla_hours = {
            'CRITICAL': 2,
            'HIGH': 8,
            'MEDIUM': 24,
            'LOW': 72
        }
        
        max_hours = sla_hours.get(obj.priority, 24)
        age_hours = self.get_alert_age_hours(obj)
        
        return obj.status == 'ACTIVE' and age_hours > max_hours
    
    def get_severity_score(self, obj):
        """Calculate severity score based on multiple factors."""
        score = 0
        
        # Base priority score
        priority_scores = {'CRITICAL': 100, 'HIGH': 75, 'MEDIUM': 50, 'LOW': 25}
        score += priority_scores.get(obj.priority, 25)
        
        # Age factor (older = more severe)
        age_hours = self.get_alert_age_hours(obj)
        if age_hours > 48:
            score += 25
        elif age_hours > 24:
            score += 15
        elif age_hours > 8:
            score += 10
        
        # Stock level factor (for stock-related alerts)
        if obj.alert_type in ['LOW_STOCK', 'OUT_OF_STOCK', 'OVERSTOCK']:
            current_level = self.get_current_stock_level(obj)
            if obj.alert_type == 'OUT_OF_STOCK':
                score += 30
            elif current_level and current_level <= 5:  # Very low stock
                score += 20
        
        return min(score, 150)  # Cap at 150
    
    def get_current_stock_level(self, obj):
        """Get current stock level for the product/warehouse."""
        if not obj.product or not obj.warehouse:
            return None
        
        try:
            from apps.inventory.models.stock.items import StockItem
            stock_item = StockItem.objects.get(
                product=obj.product,
                warehouse=obj.warehouse,
                tenant=obj.tenant
            )
            return stock_item.quantity_on_hand
        except StockItem.DoesNotExist:
            return 0
    
    def get_threshold_value(self, obj):
        """Get the threshold value that triggered the alert."""
        if obj.alert_type == 'LOW_STOCK' and obj.product:
            return obj.product.reorder_level
        elif obj.alert_type == 'OVERSTOCK' and obj.product:
            return obj.product.max_stock_level
        return obj.context_data.get('threshold') if obj.context_data else None
    
    def get_recommended_action(self, obj):
        """Generate recommended action based on alert type."""
        actions = {
            'LOW_STOCK': 'Create purchase order or transfer stock from other locations',
            'OUT_OF_STOCK': 'Immediate restocking required - check supplier lead times',
            'OVERSTOCK': 'Consider promotional activities or transfers to other locations',
            'EXPIRING_STOCK': 'Prioritize usage or consider markdowns',
            'SLOW_MOVING': 'Review pricing strategy or marketing campaigns',
            'DEAD_STOCK': 'Consider liquidation or write-off procedures',
            'NEGATIVE_STOCK': 'Investigate and correct inventory discrepancies',
            'CYCLE_COUNT_VARIANCE': 'Review and approve cycle count adjustments',
            'SUPPLIER_DELAY': 'Contact supplier and update expected delivery dates',
            'QUALITY_ISSUE': 'Quarantine affected stock and investigate quality problems'
        }
        
        base_action = actions.get(obj.alert_type, 'Review alert details and take appropriate action')
        
        # Add context-specific recommendations
        if obj.product and obj.alert_type == 'LOW_STOCK':
            current_level = self.get_current_stock_level(obj)
            if current_level and obj.product.lead_time_days:
                days_of_stock = current_level / (obj.product.average_daily_usage or 1)
                if days_of_stock < obj.product.lead_time_days:
                    base_action += f" (Stock will last {days_of_stock:.1f} days, lead time is {obj.product.lead_time_days} days)"
        
        return base_action

class InventoryAlertDetailSerializer(InventoryAlertSerializer):
    """Detailed alert serializer with additional information."""
    
    related_alerts = serializers.SerializerMethodField()
    action_history = serializers.SerializerMethodField()
    impact_analysis = serializers.SerializerMethodField()
    escalation_path = serializers.SerializerMethodField()
    
    class Meta(InventoryAlertSerializer.Meta):
        fields = InventoryAlertSerializer.Meta.fields + [
            'related_alerts', 'action_history', 'impact_analysis', 'escalation_path'
        ]
    
    def get_related_alerts(self, obj):
        """Get related alerts for same product/warehouse."""
        related = InventoryAlert.objects.filter(
            product=obj.product,
            warehouse=obj.warehouse,
            tenant=obj.tenant,
            status='ACTIVE'
        ).exclude(id=obj.id)[:5]
        
        return [
            {
                'id': alert.id,
                'alert_type': alert.alert_type,
                'priority': alert.priority,
                'created_at': alert.created_at,
                'message': alert.message
            }
            for alert in related
        ]
    
    def get_action_history(self, obj):
        """Get history of actions taken on this alert."""
        history = []
        
        # Acknowledgment
        if obj.acknowledged_at:
            history.append({
                'action': 'ACKNOWLEDGED',
                'timestamp': obj.acknowledged_at,
                'user': obj.acknowledged_by.get_full_name() if obj.acknowledged_by else None,
                'notes': obj.acknowledgment_notes
            })
        
        # Resolution
        if obj.resolved_at:
            history.append({
                'action': 'RESOLVED',
                'timestamp': obj.resolved_at,
                'user': obj.resolved_by.get_full_name() if obj.resolved_by else None,
                'notes': obj.resolution_notes,
                'auto_resolved': obj.auto_resolved
            })
        
        # Dismissal
        if obj.dismissed_at:
            history.append({
                'action': 'DISMISSED',
                'timestamp': obj.dismissed_at,
                'user': None,  # Would need to track dismissing user
                'reason': obj.dismissal_reason
            })
        
        return sorted(history, key=lambda x: x['timestamp'])
    
    def get_impact_analysis(self, obj):
        """Analyze potential impact of the alert condition."""
        impact = {
            'financial_impact': 'LOW',
            'operational_impact': 'LOW',
            'customer_impact': 'LOW',
            'estimated_cost': None,
            'affected_orders': 0,
            'revenue_at_risk': Decimal('0')
        }
        
        if obj.alert_type == 'OUT_OF_STOCK':
            impact['operational_impact'] = 'HIGH'
            impact['customer_impact'] = 'HIGH'
            # Calculate potential lost sales
            if obj.product:
                daily_sales = obj.product.average_daily_sales or 0
                impact['revenue_at_risk'] = daily_sales * (obj.product.selling_price or 0) * 7  # 1 week estimate
        
        elif obj.alert_type == 'OVERSTOCK':
            impact['financial_impact'] = 'MEDIUM'
            # Calculate carrying cost
            if obj.product:
                current_level = self.get_current_stock_level(obj)
                excess_stock = max(0, current_level - (obj.product.max_stock_level or 0))
                impact['estimated_cost'] = excess_stock * (obj.product.cost_price or 0) * Decimal('0.02')  # 2% monthly carrying cost
        
        elif obj.alert_type == 'EXPIRING_STOCK':
            impact['financial_impact'] = 'HIGH'
            # Calculate potential loss from expired stock
            expiring_quantity = obj.context_data.get('expiring_quantity', 0)
            if obj.product and expiring_quantity:
                impact['estimated_cost'] = expiring_quantity * (obj.product.cost_price or 0)
        
        return impact
    
    def get_escalation_path(self, obj):
        """Define escalation path based on alert priority and age."""
        escalation = {
            'current_level': 1,
            'next_escalation_at': None,
            'escalation_levels': []
        }
        
        age_hours = self.get_alert_age_hours(obj)
        
        # Define escalation levels based on priority
        if obj.priority == 'CRITICAL':
            levels = [
                {'level': 1, 'role': 'Inventory Manager', 'hours': 0},
                {'level': 2, 'role': 'Operations Manager', 'hours': 2},
                {'level': 3, 'role': 'General Manager', 'hours': 4}
            ]
        elif obj.priority == 'HIGH':
            levels = [
                {'level': 1, 'role': 'Inventory Clerk', 'hours': 0},
                {'level': 2, 'role': 'Inventory Manager', 'hours': 8},
                {'level': 3, 'role': 'Operations Manager', 'hours': 24}
            ]
        else:
            levels = [
                {'level': 1, 'role': 'Inventory Clerk', 'hours': 0},
                {'level': 2, 'role': 'Inventory Manager', 'hours': 24}
            ]
        
        escalation['escalation_levels'] = levels
        
        # Determine current escalation level
        for level in levels:
            if age_hours >= level['hours']:
                escalation['current_level'] = level['level']
        
        # Calculate next escalation time
        current_level = escalation['current_level']
        if current_level < len(levels):
            next_level = levels[current_level]
            time_to_next = next_level['hours'] - age_hours
            if time_to_next > 0:
                escalation['next_escalation_at'] = timezone.now() + timezone.timedelta(hours=time_to_next)
        
        return escalation

class AlertRuleSerializer(serializers.Serializer):
    """Serializer for alert rule configuration."""
    
    rule_name = serializers.CharField(max_length=100)
    alert_type = serializers.ChoiceField(choices=[
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('EXPIRING_STOCK', 'Expiring Stock'),
        ('SLOW_MOVING', 'Slow Moving'),
        ('DEAD_STOCK', 'Dead Stock'),
        ('NEGATIVE_STOCK', 'Negative Stock'),
        ('CYCLE_COUNT_VARIANCE', 'Cycle Count Variance'),
        ('SUPPLIER_DELAY', 'Supplier Delay'),
        ('QUALITY_ISSUE', 'Quality Issue')
    ])
    priority = serializers.ChoiceField(choices=[
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low')
    ])
    is_active = serializers.BooleanField(default=True)
    
    # Rule conditions
    conditions = serializers.JSONField(help_text="Rule conditions in JSON format")
    
    # Notification settings
    notify_immediately = serializers.BooleanField(default=True)
    notification_channels = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('EMAIL', 'Email'),
            ('SMS', 'SMS'),
            ('PUSH', 'Push Notification'),
            ('WEBHOOK', 'Webhook')
        ]),
        default=['EMAIL']
    )
    
    # Recipients
    recipient_roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of role names to notify"
    )
    recipient_users = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of user IDs to notify"
    )
    
    # Escalation settings
    enable_escalation = serializers.BooleanField(default=False)
    escalation_hours = serializers.IntegerField(required=False, min_value=1)
    escalation_recipients = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate_conditions(self, value):
        """Validate rule conditions structure."""
        required_keys = ['threshold_type', 'threshold_value']
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Conditions must be a JSON object")
        
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"Missing required condition: {key}")
        
        return value
    
    def validate(self, data):
        """Cross-field validation for alert rules."""
        if data.get('enable_escalation') and not data.get('escalation_hours'):
            raise serializers.ValidationError(
                "escalation_hours is required when escalation is enabled"
            )
        
        return data

class AlertConfigurationSerializer(serializers.Serializer):
    """Serializer for overall alert system configuration."""
    
    global_settings = serializers.JSONField()
    alert_rules = AlertRuleSerializer(many=True)
    notification_settings = serializers.JSONField()
    escalation_matrix = serializers.JSONField()
    
    def validate_global_settings(self, value):
        """Validate global alert settings."""
        required_settings = [
            'enable_alerts',
            'default_priority',
            'auto_resolve_enabled',
            'batch_processing_enabled'
        ]
        
        for setting in required_settings:
            if setting not in value:
                raise serializers.ValidationError(f"Missing global setting: {setting}")
        
        return value

class BulkAlertActionSerializer(serializers.Serializer):
    """Serializer for bulk alert operations."""
    
    alert_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of alert IDs to process"
    )
    action = serializers.ChoiceField(choices=[
        ('acknowledge', 'Acknowledge'),
        ('resolve', 'Resolve'),
        ('dismiss', 'Dismiss'),
        ('change_priority', 'Change Priority'),
        ('reassign', 'Reassign')
    ])
    
    # Action-specific fields
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    new_priority = serializers.ChoiceField(
        choices=[('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')],
        required=False
    )
    assigned_to = serializers.IntegerField(required=False)
    
    def validate_alert_ids(self, value):
        """Validate alert IDs list."""
        if not value:
            raise serializers.ValidationError("Alert IDs list cannot be empty")
        
        if len(value) > 100:  # Reasonable limit
            raise serializers.ValidationError("Cannot process more than 100 alerts at once")
        
        return value
    
    def validate(self, data):
        """Cross-field validation based on action type."""
        action = data.get('action')
        
        if action in ['resolve', 'dismiss'] and not data.get('reason'):
            raise serializers.ValidationError(f"Reason is required for {action} action")
        
        if action == 'change_priority' and not data.get('new_priority'):
            raise serializers.ValidationError("new_priority is required for change_priority action")
        
        if action == 'reassign' and not data.get('assigned_to'):
            raise serializers.ValidationError("assigned_to is required for reassign action")
        
        return data