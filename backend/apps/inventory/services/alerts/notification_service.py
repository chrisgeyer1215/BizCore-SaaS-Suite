from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from typing import List, Dict, Any, Optional
from ..base import BaseService, ServiceResult
from ...models import (
    InventoryAlert, PurchaseOrder, StockTransfer, 
    StockReceipt, PurchaseOrderApproval
)

class NotificationService(BaseService):
    """
    Service for sending various types of notifications
    """
    
    def send_alert_notification(self, alert: InventoryAlert) -> ServiceResult:
        """Send notification for an inventory alert"""
        try:
            rule = alert.alert_rule
            
            # Send email notifications
            if rule.send_email and rule.email_recipients:
                email_result = self._send_alert_email(alert)
                if not email_result.is_success:
                    self.logger.error(f"Failed to send alert email: {email_result.message}")
            
            # Send SMS notifications
            if rule.send_sms:
                sms_result = self._send_alert_sms(alert)
                if not sms_result.is_success:
                    self.logger.error(f"Failed to send alert SMS: {sms_result.message}")
            
            # Send push notifications
            if rule.send_push:
                push_result = self._send_alert_push(alert)
                if not push_result.is_success:
                    self.logger.error(f"Failed to send push notification: {push_result.message}")
            
            # Update notification tracking
            alert.notification_attempts += 1
            alert.email_sent_at = timezone.now() if rule.send_email else None
            alert.sms_sent_at = timezone.now() if rule.send_sms else None
            alert.push_sent_at = timezone.now() if rule.send_push else None
            alert.save(update_fields=[
                'notification_attempts', 'email_sent_at', 
                'sms_sent_at', 'push_sent_at'
            ])
            
            return ServiceResult.success(
                message=f"Notifications sent for alert {alert.reference_number}"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send alert notification: {str(e)}")
    
    def _send_alert_email(self, alert: InventoryAlert) -> ServiceResult:
        """Send email notification for alert"""
        try:
            rule = alert.alert_rule
            
            # Prepare email context
            context = {
                'alert': alert,
                'rule': rule,
                'tenant': self.tenant,
                'product': alert.product,
                'warehouse': alert.warehouse,
                'stock_item': alert.stock_item
            }
            
            # Render email templates
            subject = f"[{alert.priority}] {alert.title}"
            html_message = render_to_string(
                f'inventory/emails/alert_{alert.alert_rule.alert_type.lower()}.html',
                context
            )
            plain_message = render_to_string(
                f'inventory/emails/alert_{alert.alert_rule.alert_type.lower()}.txt',
                context
            )
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=rule.email_recipients,
                fail_silently=False
            )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send alert email: {str(e)}")
    
    def _send_alert_sms(self, alert: InventoryAlert) -> ServiceResult:
        """Send SMS notification for alert"""
        try:
            # Implement SMS sending logic here
            # This would integrate with your SMS provider (Twilio, AWS SNS, etc.)
            
            message = f"ALERT: {alert.title} - {alert.message[:100]}..."
            
            # For now, just log the SMS (implement actual SMS sending)
            self.logger.info(f"SMS Alert: {message}")
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send SMS: {str(e)}")
    
    def _send_alert_push(self, alert: InventoryAlert) -> ServiceResult:
        """Send push notification for alert"""
        try:
            # Implement push notification logic here
            # This would integrate with your push service (Firebase, OneSignal, etc.)
            
            notification_data = {
                'title': alert.title,
                'body': alert.message,
                'data': {
                    'alert_id': alert.id,
                    'type': 'inventory_alert',
                    'priority': alert.priority
                }
            }
            
            # For now, just log the push (implement actual push sending)
            self.logger.info(f"Push Notification: {notification_data}")
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send push notification: {str(e)}")
    
    def send_po_approval_notification(self, approval: PurchaseOrderApproval) -> ServiceResult:
        """Send purchase order approval notification"""
        try:
            po = approval.purchase_order
            
            # Get approvers based on required level
            approvers = self._get_approvers_for_level(approval.required_approval_level)
            
            if not approvers:
                return ServiceResult.error("No approvers found for required level")
            
            context = {
                'approval': approval,
                'purchase_order': po,
                'tenant': self.tenant,
                'approval_url': f"{settings.BASE_URL}/inventory/purchase-orders/{po.id}/approve/"
            }
            
            subject = f"Purchase Order Approval Required - {po.po_number}"
            html_message = render_to_string(
                'inventory/emails/po_approval_request.html',
                context
            )
            plain_message = render_to_string(
                'inventory/emails/po_approval_request.txt',
                context
            )
            
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approver.email for approver in approvers],
                fail_silently=False
            )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send PO approval notification: {str(e)}")
    
    def send_po_approved_notification(self, po: PurchaseOrder) -> ServiceResult:
        """Send purchase order approved notification"""
        try:
            context = {
                'purchase_order': po,
                'tenant': self.tenant,
                'po_url': f"{settings.BASE_URL}/inventory/purchase-orders/{po.id}/"
            }
            
            subject = f"Purchase Order Approved - {po.po_number}"
            html_message = render_to_string(
                'inventory/emails/po_approved.html',
                context
            )
            
            # Send to requester
            if po.created_by and po.created_by.email:
                send_mail(
                    subject=subject,
                    message="",
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[po.created_by.email],
                    fail_silently=False
                )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send PO approved notification: {str(e)}")
    
    def send_po_rejected_notification(self, po: PurchaseOrder) -> ServiceResult:
        """Send purchase order rejected notification"""
        try:
            context = {
                'purchase_order': po,
                'tenant': self.tenant,
                'rejection_reason': po.rejection_reason
            }
            
            subject = f"Purchase Order Rejected - {po.po_number}"
            html_message = render_to_string(
                'inventory/emails/po_rejected.html',
                context
            )
            
            # Send to requester
            if po.created_by and po.created_by.email:
                send_mail(
                    subject=subject,
                    message="",
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[po.created_by.email],
                    fail_silently=False
                )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send PO rejected notification: {str(e)}")
    
    def send_transfer_notification(self, transfer: StockTransfer) -> ServiceResult:
        """Send stock transfer notification"""
        try:
            # Get destination warehouse managers
            dest_managers = self._get_warehouse_managers(transfer.destination_warehouse)
            
            if not dest_managers:
                return ServiceResult.warning("No managers found for destination warehouse")
            
            context = {
                'transfer': transfer,
                'tenant': self.tenant,
                'transfer_url': f"{settings.BASE_URL}/inventory/transfers/{transfer.id}/"
            }
            
            subject = f"Incoming Stock Transfer - {transfer.transfer_number}"
            html_message = render_to_string(
                'inventory/emails/transfer_notification.html',
                context
            )
            
            send_mail(
                subject=subject,
                message="",
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[manager.email for manager in dest_managers],
                fail_silently=False
            )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send transfer notification: {str(e)}")
    
    def send_transfer_approved_notification(self, transfer: StockTransfer) -> ServiceResult:
        """Send transfer approved notification"""
        try:
            context = {
                'transfer': transfer,
                'tenant': self.tenant
            }
            
            subject = f"Stock Transfer Approved - {transfer.transfer_number}"
            html_message = render_to_string(
                'inventory/emails/transfer_approved.html',
                context
            )
            
            # Send to requester
            if transfer.requested_by and transfer.requested_by.email:
                send_mail(
                    subject=subject,
                    message="",
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[transfer.requested_by.email],
                    fail_silently=False
                )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send transfer approved notification: {str(e)}")
    
    def send_transfer_shipped_notification(self, transfer: StockTransfer) -> ServiceResult:
        """Send transfer shipped notification"""
        try:
            # Get destination warehouse managers
            dest_managers = self._get_warehouse_managers(transfer.destination_warehouse)
            
            context = {
                'transfer': transfer,
                'tenant': self.tenant
            }
            
            subject = f"Stock Transfer Shipped - {transfer.transfer_number}"
            html_message = render_to_string(
                'inventory/emails/transfer_shipped.html',
                context
            )
            
            recipients = [manager.email for manager in dest_managers]
            if transfer.requested_by and transfer.requested_by.email:
                recipients.append(transfer.requested_by.email)
            
            send_mail(
                subject=subject,
                message="",
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(set(recipients)),  # Remove duplicates
                fail_silently=False
            )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send transfer shipped notification: {str(e)}")
    
    def send_stock_receipt_notification(self, receipt: StockReceipt) -> ServiceResult:
        """Send stock receipt notification"""
        try:
            # Get warehouse managers and inventory controllers
            recipients = self._get_warehouse_managers(receipt.warehouse)
            
            context = {
                'receipt': receipt,
                'tenant': self.tenant
            }
            
            subject = f"Stock Receipt Processed - {receipt.receipt_number}"
            html_message = render_to_string(
                'inventory/emails/stock_receipt.html',
                context
            )
            
            if recipients:
                send_mail(
                    subject=subject,
                    message="",
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email for recipient in recipients],
                    fail_silently=False
                )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send receipt notification: {str(e)}")
    
    def send_cycle_count_notification(self, cycle_count) -> ServiceResult:
        """Send cycle count notification"""
        try:
            # Get warehouse staff for cycle counting
            staff = self._get_warehouse_staff(cycle_count.warehouse)
            
            context = {
                'cycle_count': cycle_count,
                'tenant': self.tenant
            }
            
            subject = f"Cycle Count Required - {cycle_count.count_number}"
            html_message = render_to_string(
                'inventory/emails/cycle_count_notification.html',
                context
            )
            
            if staff:
                send_mail(
                    subject=subject,
                    message="",
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member.email for member in staff],
                    fail_silently=False
                )
            
            return ServiceResult.success()
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send cycle count notification: {str(e)}")
    
    def _get_approvers_for_level(self, level: str) -> List:
        """Get users who can approve at the specified level"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Map approval levels to user groups/roles
        level_to_groups = {
            'SUPERVISOR': ['supervisor', 'manager', 'director'],
            'MANAGER': ['manager', 'director'],
            'DIRECTOR': ['director'],
            'CEO': ['ceo']
        }
        
        groups = level_to_groups.get(level, [])
        
        return User.objects.filter(
            groups__name__in=groups,
            is_active=True
        ).distinct()
    
    def _get_warehouse_managers(self, warehouse) -> List:
        """Get managers for a specific warehouse"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # This would depend on your user-warehouse relationship model
        # For now, return users with warehouse manager role
        return User.objects.filter(
            groups__name='warehouse_manager',
            is_active=True
        )
    
    def _get_warehouse_staff(self, warehouse) -> List:
        """Get staff members for a specific warehouse"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # This would depend on your user-warehouse relationship model
        return User.objects.filter(
            groups__name__in=['warehouse_staff', 'warehouse_manager'],
            is_active=True
        )
    
    def send_batch_notifications(self, notifications: List[Dict[str, Any]]) -> ServiceResult:
        """Send multiple notifications in batch"""
        try:
            success_count = 0
            error_count = 0
            errors = []
            
            for notification in notifications:
                notification_type = notification.get('type')
                
                try:
                    if notification_type == 'alert':
                        result = self.send_alert_notification(notification['alert'])
                    elif notification_type == 'po_approval':
                        result = self.send_po_approval_notification(notification['approval'])
                    elif notification_type == 'transfer':
                        result = self.send_transfer_notification(notification['transfer'])
                    elif notification_type == 'receipt':
                        result = self.send_stock_receipt_notification(notification['receipt'])
                    else:
                        continue
                    
                    if result.is_success:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(result.message)
                        
                except Exception as e:
                    error_count += 1
                    errors.append(str(e))
            
            return ServiceResult.success(
                data={
                    'success_count': success_count,
                    'error_count': error_count,
                    'errors': errors
                },
                message=f"Batch notifications completed: {success_count} success, {error_count} errors"
            )
            
        except Exception as e:
            return ServiceResult.error(f"Failed to send batch notifications: {str(e)}")