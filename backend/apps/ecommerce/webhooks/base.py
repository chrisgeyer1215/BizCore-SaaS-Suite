import json
import hmac
import hashlib
import logging
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class BaseWebhookView(View):
    """Base webhook view for payment gateways"""
    
    webhook_secret = None
    signature_header = None
    
    def post(self, request, *args, **kwargs):
        """Handle webhook POST request"""
        try:
            # Verify webhook signature
            if not self.verify_signature(request):
                logger.warning(f"Invalid webhook signature from {self.__class__.__name__}")
                return HttpResponse(status=400)
            
            # Parse webhook payload
            payload = self.parse_payload(request)
            
            # Process webhook event
            result = self.process_webhook(payload)
            
            if result:
                return HttpResponse(status=200)
            else:
                return HttpResponse(status=400)
                
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return HttpResponse(status=500)
    
    def verify_signature(self, request):
        """Verify webhook signature - to be implemented by subclasses"""
        return True
    
    def parse_payload(self, request):
        """Parse webhook payload"""
        try:
            return json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return None
    
    def process_webhook(self, payload):
        """Process webhook event - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement process_webhook")
    
    def create_signature(self, payload, secret):
        """Create HMAC signature for payload"""
        return hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
    
    def verify_hmac_signature(self, payload, signature, secret):
        """Verify HMAC signature"""
        expected_signature = self.create_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)
