from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    InventoryAlert, AlertRule, AlertHistory, StockItem, 
    Product, Warehouse, StockReceipt
)

class AlertService(BaseService):
    """
    Service for generating and managing inventory alerts
    """
    
    ALERT_PRIORITIES = {
        'LOW_STOCK': 'HIGH',
        'OUT_OF_STOCK': 'CRITICAL',
        'OVERSTOCK': 'MEDIUM',
        'EXPIRY': 'HIGH',
        'SLOW_MOVING': 'LOW',
        'DEAD_STOCK': 'MEDIUM',
        'NEGATIVE_STOCK': 'CRITICAL',
        'REORDER_POINT': 'HIGH'
    }
    
    def process_alert_rules(self) -> ServiceResult:
        """
        Process all active alert rules and generate alerts
        """
        try:
            self.validate_tenant()
            
            # Get active alert rules that should be checked
            rules = AlertRule.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
            
            alerts_generated = 0
            rules_processed = 0
            
            for rule in rules:
                if rule.should_check():
                    rule_result = self._process_single_rule(rule)
                    if rule_result.is_success:
                        alerts_generated += rule_result.data.get('alerts_created', 0)
                    
                    rule.mark_checked()
                    rules_processed += 1
            
            self.log_operation('process_alert_rules', {
                'rules_processed': rules_processed,
                'alerts_generated': alerts_generated
            })
            
            return ServiceResult.success(
                data={
                    'rules_processed': rules_processed,
                    'alerts_generated': alerts_generated
                },
                message=f"Processed {rules_processed} rules and generated {alerts_generated} alerts"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to process alert rules: {str(e)}")
    
    def _process_single_rule(self, rule: AlertRule) -> ServiceResult:
        """Process a single alert rule"""
        try:
            alerts_created = 0
            
            if rule.alert_type == 'LOW_STOCK':
                alerts_created = self._check_low_stock_rule(rule)
            elif rule.alert_type == 'OUT_OF_STOCK':
                alerts_created = self._check_out_of_stock_rule(rule)
            elif rule.alert_type == 'OVERSTOCK':
                alerts_created = self._check_overstock_rule(rule)
            elif rule.alert_type == 'EXPIRY':
                alerts_created = self._check_expiry_rule(rule)
            elif rule.alert_type == 'SLOW_MOVING':
                alerts_created = self._check_slow_moving_rule(rule)
            elif rule.alert_type == 'DEAD_STOCK':
                alerts_created = self._check_dead_stock_rule(rule)
            elif rule.alert_type == 'NEGATIVE_STOCK':
                alerts_created = self._check_negative_stock_rule(rule)
            elif rule.alert_type == 'REORDER_POINT':
                alerts_created = self._check_reorder_point_rule(rule)
            
            if alerts_created > 0:
                rule.mark_triggered()
            
            return ServiceResult.success(data={'alerts_created': alerts_created})
            
        except Exception as e:
            return ServiceResult.error(f"Failed to process rule {rule.name}: {str(e)}")
    
    def _check_low_stock_rule(self, rule: AlertRule) -> int:
        """Check low stock rule and create alerts"""
        queryset = self._get_stock_queryset(rule)
        
        # Apply low stock condition
        low_stock_items = queryset.filter(
            quantity_on_hand__lte=models.F('reorder_level'),
            quantity_on_hand__gt=0,
            reorder_level__gt=0
        )
        
        alerts_created = 0
        for stock_item in low_stock_items:
            # Check if alert already exists and not resolved
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_low_stock_alert(rule, stock_item)
                alerts_created += 1
        
        return alerts_created
    
    def _check_out_of_stock_rule(self, rule: AlertRule) -> int:
        """Check out of stock rule and create alerts"""
        queryset = self._get_stock_queryset(rule)
        
        out_of_stock_items = queryset.filter(quantity_on_hand=0)
        
        alerts_created = 0
        for stock_item in out_of_stock_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_out_of_stock_alert(rule, stock_item)
                alerts_created += 1
        
        return alerts_created
    
    def _check_overstock_rule(self, rule: AlertRule) -> int:
        """Check overstock rule and create alerts"""
        queryset = self._get_stock_queryset(rule)
        
        overstock_items = queryset.filter(
            quantity_on_hand__gte=models.F('maximum_stock_level'),
            maximum_stock_level__gt=0
        )
        
        alerts_created = 0
        for stock_item in overstock_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_overstock_alert(rule, stock_item)
                alerts_created += 1
        
        return alerts_created
    
    def _check_expiry_rule(self, rule: AlertRule) -> int:
        """Check expiry rule and create alerts"""
        from django.db.models import Q
        
        days_threshold = int(rule.condition_value or 30)
        cutoff_date = timezone.now().date() + timezone.timedelta(days=days_threshold)
        
        queryset = self._get_stock_queryset(rule)
        
        expiring_items = queryset.filter(
            batch__expiry_date__lte=cutoff_date,
            batch__expiry_date__isnull=False,
            quantity_on_hand__gt=0
        ).distinct()
        
        alerts_created = 0
        for stock_item in expiring_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_expiry_alert(rule, stock_item, cutoff_date)
                alerts_created += 1
        
        return alerts_created
    
    def _check_slow_moving_rule(self, rule: AlertRule) -> int:
        """Check slow moving rule and create alerts"""
        days_threshold = int(rule.condition_value or 90)
        cutoff_date = timezone.now() - timezone.timedelta(days=days_threshold)
        
        queryset = self._get_stock_queryset(rule)
        
        slow_moving_items = queryset.annotate(
            movement_count=Count(
                'stockmovementitem',
                filter=Q(stockmovementitem__movement__created_at__gte=cutoff_date)
            )
        ).filter(
            movement_count__lte=2,  # Configurable threshold
            quantity_on_hand__gt=0
        )
        
        alerts_created = 0
        for stock_item in slow_moving_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_slow_moving_alert(rule, stock_item, days_threshold)
                alerts_created += 1
        
        return alerts_created
    
    def _check_dead_stock_rule(self, rule: AlertRule) -> int:
        """Check dead stock rule and create alerts"""
        days_threshold = int(rule.condition_value or 180)
        cutoff_date = timezone.now() - timezone.timedelta(days=days_threshold)
        
        queryset = self._get_stock_queryset(rule)
        
        dead_stock_items = queryset.filter(
            Q(last_movement_date__lt=cutoff_date) | Q(last_movement_date__isnull=True),
            quantity_on_hand__gt=0
        )
        
        alerts_created = 0
        for stock_item in dead_stock_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_dead_stock_alert(rule, stock_item, days_threshold)
                alerts_created += 1
        
        return alerts_created
    
    def _check_negative_stock_rule(self, rule: AlertRule) -> int:
        """Check negative stock rule and create alerts"""
        queryset = self._get_stock_queryset(rule)
        
        negative_stock_items = queryset.filter(quantity_on_hand__lt=0)
        
        alerts_created = 0
        for stock_item in negative_stock_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert:  # Always create for negative stock
                self._create_negative_stock_alert(rule, stock_item)
                alerts_created += 1
        
        return alerts_created
    
    def _check_reorder_point_rule(self, rule: AlertRule) -> int:
        """Check reorder point rule and create alerts"""
        queryset = self._get_stock_queryset(rule)
        
        reorder_items = queryset.filter(
            quantity_on_hand__lte=models.F('reorder_level'),
            reorder_level__gt=0
        )
        
        alerts_created = 0
        for stock_item in reorder_items:
            existing_alert = InventoryAlert.objects.filter(
                tenant=self.tenant,
                alert_rule=rule,
                stock_item=stock_item,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).first()
            
            if not existing_alert and rule.can_trigger_again():
                self._create_reorder_point_alert(rule, stock_item)
                alerts_created += 1
        
        return alerts_created
    
    def _get_stock_queryset(self, rule: AlertRule):
        """Get stock item queryset based on rule filters"""
        queryset = StockItem.objects.filter(tenant=self.tenant)
        
        # Apply scope filters
        if not rule.apply_to_all_products:
            if rule.product_categories.exists():
                queryset = queryset.filter(product__category__in=rule.product_categories.all())
            
            if rule.specific_products.exists():
                queryset = queryset.filter(product__in=rule.specific_products.all())
        
        if rule.warehouses.exists():
            queryset = queryset.filter(warehouse__in=rule.warehouses.all())
        
        return queryset.select_related('product', 'warehouse')
    
    def _create_low_stock_alert(self, rule: AlertRule, stock_item: StockItem):
        """Create low stock alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Low Stock Alert: {stock_item.product.name}",
            message=f"Stock level ({stock_item.quantity_on_hand}) is below reorder level ({stock_item.reorder_level}) for {stock_item.product.name} in {stock_item.warehouse.name}",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=stock_item.quantity_on_hand,
            threshold_value=stock_item.reorder_level
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_out_of_stock_alert(self, rule: AlertRule, stock_item: StockItem):
        """Create out of stock alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Out of Stock: {stock_item.product.name}",
            message=f"{stock_item.product.name} is out of stock in {stock_item.warehouse.name}",
            priority='CRITICAL',
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=Decimal('0'),
            threshold_value=Decimal('1')
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_overstock_alert(self, rule: AlertRule, stock_item: StockItem):
        """Create overstock alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Overstock Alert: {stock_item.product.name}",
            message=f"Stock level ({stock_item.quantity_on_hand}) exceeds maximum level ({stock_item.maximum_stock_level}) for {stock_item.product.name} in {stock_item.warehouse.name}",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=stock_item.quantity_on_hand,
            threshold_value=stock_item.maximum_stock_level
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_expiry_alert(self, rule: AlertRule, stock_item: StockItem, cutoff_date):
        """Create expiry alert"""
        # Get earliest expiry date for this stock item
        earliest_expiry = stock_item.batch_set.filter(
            expiry_date__isnull=False
        ).aggregate(
            earliest=Min('expiry_date')
        )['earliest']
        
        days_to_expiry = (earliest_expiry - timezone.now().date()).days if earliest_expiry else 0
        
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Expiry Warning: {stock_item.product.name}",
            message=f"{stock_item.product.name} in {stock_item.warehouse.name} will expire in {days_to_expiry} days (Expiry: {earliest_expiry})",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=Decimal(str(days_to_expiry)),
            additional_data={'expiry_date': earliest_expiry.isoformat() if earliest_expiry else None}
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_slow_moving_alert(self, rule: AlertRule, stock_item: StockItem, days_threshold: int):
        """Create slow moving alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Slow Moving Stock: {stock_item.product.name}",
            message=f"{stock_item.product.name} in {stock_item.warehouse.name} has had minimal movement in the last {days_threshold} days",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=Decimal(str(days_threshold)),
            additional_data={'analysis_period_days': days_threshold}
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_dead_stock_alert(self, rule: AlertRule, stock_item: StockItem, days_threshold: int):
        """Create dead stock alert"""
        days_since_movement = (timezone.now().date() - stock_item.last_movement_date).days if stock_item.last_movement_date else 999
        
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Dead Stock Alert: {stock_item.product.name}",
            message=f"{stock_item.product.name} in {stock_item.warehouse.name} has had no movement for {days_since_movement} days",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=Decimal(str(days_since_movement)),
            threshold_value=Decimal(str(days_threshold))
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_negative_stock_alert(self, rule: AlertRule, stock_item: StockItem):
        """Create negative stock alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"CRITICAL: Negative Stock - {stock_item.product.name}",
            message=f"{stock_item.product.name} in {stock_item.warehouse.name} has negative stock: {stock_item.quantity_on_hand}",
            priority='CRITICAL',
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=stock_item.quantity_on_hand,
            threshold_value=Decimal('0')
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _create_reorder_point_alert(self, rule: AlertRule, stock_item: StockItem):
        """Create reorder point alert"""
        alert = InventoryAlert.objects.create(
            tenant=self.tenant,
            alert_rule=rule,
            title=f"Reorder Required: {stock_item.product.name}",
            message=f"{stock_item.product.name} in {stock_item.warehouse.name} has reached reorder point. Current: {stock_item.quantity_on_hand}, Reorder Level: {stock_item.reorder_level}",
            priority=rule.severity,
            product=stock_item.product,
            warehouse=stock_item.warehouse,
            stock_item=stock_item,
            current_value=stock_item.quantity_on_hand,
            threshold_value=stock_item.reorder_level
        )
        
        self._send_alert_notifications(alert)
        return alert
    
    def _send_alert_notifications(self, alert: InventoryAlert):
        """Send notifications for alert"""
        from .notification_service import NotificationService
        
        notification_service = NotificationService(tenant=self.tenant, user=self.user)
        notification_service.send_alert_notification(alert)
    
    @transaction.atomic
    def acknowledge_alert(self, alert_id: int, notes: str = "") -> ServiceResult:
        """Acknowledge an alert"""
        try:
            alert = InventoryAlert.objects.get(id=alert_id, tenant=self.tenant)
            
            if alert.status != 'OPEN':
                return ServiceResult.error("Alert is not open")
            
            alert.acknowledge(self.user, notes)
            
            # Create history entry
            AlertHistory.objects.create(
                tenant=self.tenant,
                alert=alert,
                action='ACKNOWLEDGED',
                old_status='OPEN',
                new_status='ACKNOWLEDGED',
                notes=notes,
                user=self.user
            )
            
            self.log_operation('acknowledge_alert', {
                'alert_id': alert.id,
                'reference_number': alert.reference_number
            })
            
            return ServiceResult.success(
                data=alert,
                message=f"Alert {alert.reference_number} acknowledged successfully"
            )
            
        except InventoryAlert.DoesNotExist:
            return ServiceResult.error("Alert not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to acknowledge alert: {str(e)}")
    
    @transaction.atomic
    def resolve_alert(self, alert_id: int, resolution_notes: str = "") -> ServiceResult:
        """Resolve an alert"""
        try:
            alert = InventoryAlert.objects.get(id=alert_id, tenant=self.tenant)
            
            if alert.status not in ['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS']:
                return ServiceResult.error("Alert cannot be resolved in current status")
            
            old_status = alert.status
            alert.resolve(self.user, resolution_notes)
            
            # Create history entry
            AlertHistory.objects.create(
                tenant=self.tenant,
                alert=alert,
                action='RESOLVED',
                old_status=old_status,
                new_status='RESOLVED',
                notes=resolution_notes,
                user=self.user
            )
            
            self.log_operation('resolve_alert', {
                'alert_id': alert.id,
                'reference_number': alert.reference_number
            })
            
            return ServiceResult.success(
                data=alert,
                message=f"Alert {alert.reference_number} resolved successfully"
            )
            
        except InventoryAlert.DoesNotExist:
            return ServiceResult.error("Alert not found")
        except Exception as e:
            return ServiceResult.error(f"Failed to resolve alert: {str(e)}")
    
    def get_alert_dashboard(self) -> ServiceResult:
        """Get alert dashboard summary"""
        try:
            # Get alert counts by status
            status_counts = InventoryAlert.objects.filter(
                tenant=self.tenant
            ).values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            # Get alert counts by priority
            priority_counts = InventoryAlert.objects.filter(
                tenant=self.tenant,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).values('priority').annotate(
                count=Count('id')
            ).order_by('priority')
            
            # Get recent alerts
            recent_alerts = InventoryAlert.objects.filter(
                tenant=self.tenant
            ).select_related(
                'product', 'warehouse', 'alert_rule'
            ).order_by('-created_at')[:10]
            
            # Get overdue alerts
            overdue_alerts = [
                alert for alert in InventoryAlert.objects.filter(
                    tenant=self.tenant,
                    status__in=['OPEN', 'ACKNOWLEDGED']
                )
                if alert.is_overdue
            ]
            
            return ServiceResult.success(data={
                'status_counts': list(status_counts),
                'priority_counts': list(priority_counts),
                'recent_alerts': [
                    {
                        'id': alert.id,
                        'reference_number': alert.reference_number,
                        'title': alert.title,
                        'priority': alert.priority,
                        'status': alert.status,
                        'created_at': alert.created_at,
                        'age_hours': alert.age_hours
                    } for alert in recent_alerts
                ],
                'overdue_count': len(overdue_alerts),
                'total_open': sum(item['count'] for item in status_counts if item['status'] in ['OPEN', 'ACKNOWLEDGED'])
            })
            
        except Exception as e:
            return ServiceResult.error(f"Failed to get alert dashboard: {str(e)}")
    
    def auto_resolve_alerts(self) -> ServiceResult:
        """Auto-resolve alerts that meet resolution criteria"""
        try:
            # Get alerts that should be auto-resolved
            auto_resolvable_alerts = InventoryAlert.objects.filter(
                tenant=self.tenant,
                is_auto_resolvable=True,
                status__in=['OPEN', 'ACKNOWLEDGED']
            )
            
            resolved_count = 0
            
            for alert in auto_resolvable_alerts:
                if alert.should_auto_resolve():
                    alert.auto_resolve()
                    
                    # Create history entry
                    AlertHistory.objects.create(
                        tenant=self.tenant,
                        alert=alert,
                        action='AUTO_RESOLVED',
                        old_status=alert.status,
                        new_status='AUTO_RESOLVED',
                        notes='Automatically resolved by system'
                    )
                    
                    resolved_count += 1
            
            self.log_operation('auto_resolve_alerts', {
                'resolved_count': resolved_count
            })
            
            return ServiceResult.success(
                data={'resolved_count': resolved_count},
                message=f"Auto-resolved {resolved_count} alerts"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to auto-resolve alerts: {str(e)}")
    
    # Convenience methods for creating specific alerts
    def create_low_stock_alert(self, stock_item: StockItem) -> InventoryAlert:
        """Create low stock alert for a specific stock item"""
        rule = AlertRule.objects.filter(
            tenant=self.tenant,
            alert_type='LOW_STOCK',
            is_active=True
        ).first()
        
        if rule:
            return self._create_low_stock_alert(rule, stock_item)
    
    def create_negative_stock_alert(self, stock_item: StockItem) -> InventoryAlert:
        """Create negative stock alert for a specific stock item"""
        rule = AlertRule.objects.filter(
            tenant=self.tenant,
            alert_type='NEGATIVE_STOCK',
            is_active=True
        ).first()
        
        if rule:
            return self._create_negative_stock_alert(rule, stock_item)
    
    def create_qc_required_alert(self, receipt: StockReceipt) -> InventoryAlert:
        """Create quality control required alert"""
        rule = AlertRule.objects.filter(
            tenant=self.tenant,
            alert_type='QUALITY_CONTROL',
            is_active=True
        ).first()
        
        if rule:
            alert = InventoryAlert.objects.create(
                tenant=self.tenant,
                alert_rule=rule,
                title=f"Quality Control Required: Receipt {receipt.receipt_number}",
                message=f"Quality control inspection required for receipt {receipt.receipt_number} from {receipt.supplier.name if receipt.supplier else 'Unknown'}",
                priority='HIGH',
                warehouse=receipt.warehouse,
                additional_data={
                    'receipt_id': receipt.id,
                    'receipt_number': receipt.receipt_number
                }
            )
            
            self._send_alert_notifications(alert)
            return alert