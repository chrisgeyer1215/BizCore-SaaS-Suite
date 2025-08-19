import json
import logging
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from paypalrestsdk import notifications
from apps.ecommerce.models import Order, PaymentTransaction
from apps.ecommerce.services import PaymentService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PayPalWebhookView(View):
    """Handle PayPal webhooks"""
    
    def post(self, request):
        try:
            # Verify webhook signature
            webhook_event = json.loads(request.body.decode('utf-8'))
            
            if not self.verify_webhook_signature(request, webhook_event):
                logger.error("Invalid PayPal webhook signature")
                return HttpResponse(status=400)
            
            # Handle the event
            self.handle_event(webhook_event)
            
        except Exception as e:
            logger.error(f"Error handling PayPal webhook: {e}")
            return HttpResponse(status=500)
            
        return HttpResponse(status=200)

    def verify_webhook_signature(self, request, webhook_event):
        """Verify PayPal webhook signature"""
        try:
            headers = {
                'auth-algo': request.META.get('HTTP_PAYPAL_AUTH_ALGO'),
                'cert-id': request.META.get('HTTP_PAYPAL_CERT_ID'),
                'transmission-id': request.META.get('HTTP_PAYPAL_TRANSMISSION_ID'),
                'transmission-sig': request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG'),
                'transmission-time': request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME'),
            }
            
            # Verify with PayPal SDK
            return notifications.WebhookEvent.verify(
                transmission_id=headers['transmission-id'],
                cert_id=headers['cert-id'],
                auth_algo=headers['auth-algo'],
                transmission_sig=headers['transmission-sig'],
                transmission_time=headers['transmission-time'],
                webhook_id=settings.PAYPAL_WEBHOOK_ID,
                webhook_event=webhook_event
            )
        except Exception as e:
            logger.error(f"Error verifying PayPal webhook: {e}")
            return False

    def handle_event(self, webhook_event):
        """Route events to appropriate handlers"""
        event_type = webhook_event.get('event_type')
        
        handlers = {
            'PAYMENT.CAPTURE.COMPLETED': self.handle_payment_captured,
            'PAYMENT.CAPTURE.DENIED': self.handle_payment_denied,
            'CHECKOUT.ORDER.APPROVED': self.handle_order_approved,
            'CHECKOUT.ORDER.COMPLETED': self.handle_order_completed,
            'PAYMENT.CAPTURE.REFUNDED': self.handle_payment_refunded,
            'CUSTOMER.DISPUTE.CREATED': self.handle_dispute_created,
        }
        
        handler = handlers.get(event_type)
        if handler:
            handler(webhook_event.get('resource', {}))
        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")

    @transaction.atomic
    def handle_payment_captured(self, resource):
        """Handle successful payment capture"""
        try:
            # Extract order information from PayPal resource
            custom_id = resource.get('custom_id')  # Our order ID
            if not custom_id:
                logger.error("No custom_id in PayPal payment capture")
                return

            order = Order.objects.get(id=custom_id)
            
            # Create payment transaction record
            PaymentTransaction.objects.create(
                tenant=order.tenant,
                order=order,
                transaction_type='PAYMENT',
                payment_method='PAYPAL',
                payment_gateway='paypal',
                amount=float(resource.get('amount', {}).get('value', 0)),
                currency=resource.get('amount', {}).get('currency_code', 'USD'),
                status='SUCCESS',
                external_transaction_id=resource.get('id'),
                gateway_response=resource
            )
            
            # Update order status
            PaymentService.mark_order_as_paid(order, {
                'payment_method': 'paypal',
                'transaction_id': resource.get('id'),
                'amount': float(resource.get('amount', {}).get('value', 0))
            })
            
            logger.info(f"PayPal payment captured for order {order.order_number}")
            
        except Order.DoesNotExist:
            logger.error(f"Order not found for PayPal capture {resource.get('id')}")
        except Exception as e:
            logger.error(f"Error handling PayPal payment capture: {e}")

    @transaction.atomic
    def handle_payment_denied(self, resource):
        """Handle denied payment"""
        try:
            custom_id = resource.get('custom_id')
            if not custom_id:
                return

            order = Order.objects.get(id=custom_id)
            
            # Create failed payment record
            PaymentTransaction.objects.create(
                tenant=order.tenant,
                order=order,
                transaction_type='PAYMENT',
                payment_method='PAYPAL',
                payment_gateway='paypal',
                amount=float(resource.get('amount', {}).get('value', 0)),
                currency=resource.get('amount', {}).get('currency_code', 'USD'),
                status='FAILED',
                external_transaction_id=resource.get('id'),
                gateway_response=resource
            )
            
            # Update order status
            order.payment_status = 'FAILED'
            order.status = 'CANCELLED'
            order.save()
            
            logger.info(f"PayPal payment denied for order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Error handling PayPal payment denial: {e}")

    def handle_payment_refunded(self, resource):
        """Handle payment refund"""
        try:
            # Find the original transaction
            original_transaction = PaymentTransaction.objects.filter(
                external_transaction_id=resource.get('id')
            ).first()
            
            if original_transaction:
                # Create refund record
                PaymentTransaction.objects.create(
                    tenant=original_transaction.tenant,
                    order=original_transaction.order,
                    transaction_type='REFUND',
                    payment_method='PAYPAL',
                    payment_gateway='paypal',
                    amount=float(resource.get('amount', {}).get('value', 0)),
                    currency=resource.get('amount', {}).get('currency_code', 'USD'),
                    status='SUCCESS',
                    external_transaction_id=resource.get('id'),
                    gateway_response=resource
                )
                
                logger.info(f"PayPal refund processed for order {original_transaction.order.order_number}")
                
        except Exception as e:
            logger.error(f"Error handling PayPal refund: {e}")

    def handle_dispute_created(self, resource):
        """Handle dispute creation"""
        # Implementation for PayPal disputes
        pass
