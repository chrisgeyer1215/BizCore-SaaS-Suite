import json
import logging
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from apps.ecommerce.models import Order, PaymentTransaction
from apps.ecommerce.services import OrderService, PaymentService

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """Handle Stripe webhooks"""
    
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return HttpResponse(status=400)

        # Handle the event
        try:
            self.handle_event(event)
        except Exception as e:
            logger.error(f"Error handling Stripe webhook: {e}")
            return HttpResponse(status=500)

        return HttpResponse(status=200)

    def handle_event(self, event):
        """Route events to appropriate handlers"""
        event_type = event['type']
        
        handlers = {
            'payment_intent.succeeded': self.handle_payment_succeeded,
            'payment_intent.payment_failed': self.handle_payment_failed,
            'payment_intent.requires_action': self.handle_payment_requires_action,
            'charge.succeeded': self.handle_charge_succeeded,
            'charge.failed': self.handle_charge_failed,
            'charge.dispute.created': self.handle_dispute_created,
            'invoice.payment_succeeded': self.handle_subscription_payment,
            'customer.subscription.created': self.handle_subscription_created,
            'customer.subscription.updated': self.handle_subscription_updated,
            'customer.subscription.deleted': self.handle_subscription_cancelled,
        }
        
        handler = handlers.get(event_type)
        if handler:
            handler(event['data']['object'])
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")

    @transaction.atomic
    def handle_payment_succeeded(self, payment_intent):
        """Handle successful payment"""
        try:
            order_id = payment_intent.get('metadata', {}).get('order_id')
            if not order_id:
                logger.error("No order_id in payment_intent metadata")
                return

            order = Order.objects.get(id=order_id)
            
            # Create payment transaction record
            PaymentTransaction.objects.create(
                tenant=order.tenant,
                order=order,
                transaction_type='PAYMENT',
                payment_method='CREDIT_CARD',
                payment_gateway='stripe',
                amount=payment_intent['amount'] / 100,  # Convert from cents
                currency=payment_intent['currency'].upper(),
                status='SUCCESS',
                external_transaction_id=payment_intent['id'],
                gateway_transaction_id=payment_intent['charges']['data'][0]['id'] if payment_intent.get('charges') else None,
                gateway_response=payment_intent
            )
            
            # Update order status
            PaymentService.mark_order_as_paid(order, {
                'payment_method': 'stripe',
                'transaction_id': payment_intent['id'],
                'amount': payment_intent['amount'] / 100
            })
            
            logger.info(f"Payment succeeded for order {order.order_number}")
            
        except Order.DoesNotExist:
            logger.error(f"Order not found for payment_intent {payment_intent['id']}")
        except Exception as e:
            logger.error(f"Error handling payment success: {e}")

    @transaction.atomic
    def handle_payment_failed(self, payment_intent):
        """Handle failed payment"""
        try:
            order_id = payment_intent.get('metadata', {}).get('order_id')
            if not order_id:
                return

            order = Order.objects.get(id=order_id)
            
            # Create failed payment record
            PaymentTransaction.objects.create(
                tenant=order.tenant,
                order=order,
                transaction_type='PAYMENT',
                payment_method='CREDIT_CARD',
                payment_gateway='stripe',
                amount=payment_intent['amount'] / 100,
                currency=payment_intent['currency'].upper(),
                status='FAILED',
                external_transaction_id=payment_intent['id'],
                gateway_response=payment_intent,
                error_message=payment_intent.get('last_payment_error', {}).get('message')
            )
            
            # Update order status
            order.payment_status = 'FAILED'
            order.status = 'CANCELLED'
            order.save()
            
            logger.info(f"Payment failed for order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")

    def handle_charge_succeeded(self, charge):
        """Handle successful charge"""
        try:
            payment_intent_id = charge.get('payment_intent')
            if payment_intent_id:
                # Update existing transaction with charge details
                transaction = PaymentTransaction.objects.filter(
                    external_transaction_id=payment_intent_id
                ).first()
                
                if transaction:
                    transaction.gateway_transaction_id = charge['id']
                    transaction.authorization_code = charge.get('outcome', {}).get('authorization_code')
                    transaction.captured_at = timezone.now()
                    transaction.save()
                    
        except Exception as e:
            logger.error(f"Error handling charge success: {e}")

    def handle_dispute_created(self, dispute):
        """Handle chargeback/dispute"""
        try:
            charge_id = dispute['charge']
            charge = stripe.Charge.retrieve(charge_id)
            
            # Find the related transaction
            transaction = PaymentTransaction.objects.filter(
                gateway_transaction_id=charge_id
            ).first()
            
            if transaction:
                # Create chargeback record
                PaymentTransaction.objects.create(
                    tenant=transaction.tenant,
                    order=transaction.order,
                    transaction_type='CHARGEBACK',
                    payment_method=transaction.payment_method,
                    payment_gateway='stripe',
                    amount=dispute['amount'] / 100,
                    currency=dispute['currency'].upper(),
                    status='SUCCESS',
                    external_transaction_id=dispute['id'],
                    gateway_response=dispute
                )
                
                logger.info(f"Chargeback created for order {transaction.order.order_number}")
                
        except Exception as e:
            logger.error(f"Error handling dispute: {e}")

    def handle_subscription_payment(self, invoice):
        """Handle subscription payment"""
        # Implementation for subscription payments
        pass

    def handle_subscription_created(self, subscription):
        """Handle new subscription"""
        # Implementation for new subscriptions
        pass

    def handle_subscription_updated(self, subscription):
        """Handle subscription updates"""
        # Implementation for subscription updates
        pass

    def handle_subscription_cancelled(self, subscription):
        """Handle subscription cancellation"""
        # Implementation for subscription cancellation
        pass
