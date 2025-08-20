from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.exceptions import APIException
from typing import Dict, Any, Optional

class InventoryException(Exception):
    """Base exception for inventory operations"""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code or 'INVENTORY_ERROR'
        self.details = details or {}
        super().__init__(self.message)

class InsufficientStockException(InventoryException):
    """Raised when there's insufficient stock for an operation"""
    
    def __init__(self, product_name: str, requested: float, available: float, **kwargs):
        message = f"Insufficient stock for {product_name}. Requested: {requested}, Available: {available}"
        details = {
            'product_name': product_name,
            'requested_quantity': requested,
            'available_quantity': available,
            **kwargs
        }
        super().__init__(message, 'INSUFFICIENT_STOCK', details)

class InvalidMovementException(InventoryException):
    """Raised when an invalid stock movement is attempted"""
    
    def __init__(self, movement_type: str, reason: str, **kwargs):
        message = f"Invalid {movement_type} movement: {reason}"
        details = {
            'movement_type': movement_type,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'INVALID_MOVEMENT', details)

class StockValuationException(InventoryException):
    """Raised when stock valuation calculations fail"""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Stock valuation error: {reason}"
        super().__init__(message, 'VALUATION_ERROR', kwargs)

class ReservationException(InventoryException):
    """Raised when stock reservation operations fail"""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Reservation error: {reason}"
        super().__init__(message, 'RESERVATION_ERROR', kwargs)

class PurchaseOrderException(InventoryException):
    """Raised when purchase order operations fail"""
    
    def __init__(self, po_number: str, reason: str, **kwargs):
        message = f"Purchase order {po_number} error: {reason}"
        details = {
            'po_number': po_number,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'PURCHASE_ORDER_ERROR', details)

class TransferException(InventoryException):
    """Raised when transfer operations fail"""
    
    def __init__(self, transfer_number: str, reason: str, **kwargs):
        message = f"Transfer {transfer_number} error: {reason}"
        details = {
            'transfer_number': transfer_number,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'TRANSFER_ERROR', details)

class AdjustmentException(InventoryException):
    """Raised when adjustment operations fail"""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Adjustment error: {reason}"
        super().__init__(message, 'ADJUSTMENT_ERROR', kwargs)

class CycleCountException(InventoryException):
    """Raised when cycle count operations fail"""
    
    def __init__(self, count_number: str, reason: str, **kwargs):
        message = f"Cycle count {count_number} error: {reason}"
        details = {
            'count_number': count_number,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'CYCLE_COUNT_ERROR', details)

class QualityControlException(InventoryException):
    """Raised when quality control operations fail"""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Quality control error: {reason}"
        super().__init__(message, 'QUALITY_CONTROL_ERROR', kwargs)

class SupplierException(InventoryException):
    """Raised when supplier operations fail"""
    
    def __init__(self, supplier_name: str, reason: str, **kwargs):
        message = f"Supplier {supplier_name} error: {reason}"
        details = {
            'supplier_name': supplier_name,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'SUPPLIER_ERROR', details)

class WarehouseException(InventoryException):
    """Raised when warehouse operations fail"""
    
    def __init__(self, warehouse_name: str, reason: str, **kwargs):
        message = f"Warehouse {warehouse_name} error: {reason}"
        details = {
            'warehouse_name': warehouse_name,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'WAREHOUSE_ERROR', details)

class LocationException(InventoryException):
    """Raised when location operations fail"""
    
    def __init__(self, location_code: str, reason: str, **kwargs):
        message = f"Location {location_code} error: {reason}"
        details = {
            'location_code': location_code,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'LOCATION_ERROR', details)

class BatchException(InventoryException):
    """Raised when batch operations fail"""
    
    def __init__(self, batch_number: str, reason: str, **kwargs):
        message = f"Batch {batch_number} error: {reason}"
        details = {
            'batch_number': batch_number,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'BATCH_ERROR', details)

class SerialNumberException(InventoryException):
    """Raised when serial number operations fail"""
    
    def __init__(self, serial_number: str, reason: str, **kwargs):
        message = f"Serial number {serial_number} error: {reason}"
        details = {
            'serial_number': serial_number,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'SERIAL_NUMBER_ERROR', details)

class IntegrationException(InventoryException):
    """Raised when integration operations fail"""
    
    def __init__(self, platform: str, reason: str, **kwargs):
        message = f"Integration {platform} error: {reason}"
        details = {
            'platform': platform,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'INTEGRATION_ERROR', details)

class ReportException(InventoryException):
    """Raised when report generation fails"""
    
    def __init__(self, report_name: str, reason: str, **kwargs):
        message = f"Report {report_name} error: {reason}"
        details = {
            'report_name': report_name,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'REPORT_ERROR', details)

class AlertException(InventoryException):
    """Raised when alert operations fail"""
    
    def __init__(self, alert_type: str, reason: str, **kwargs):
        message = f"Alert {alert_type} error: {reason}"
        details = {
            'alert_type': alert_type,
            'reason': reason,
            **kwargs
        }
        super().__init__(message, 'ALERT_ERROR', details)

# API Exceptions for REST Framework
class InventoryAPIException(APIException):
    """Base API exception for inventory operations"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An inventory operation error occurred.'
    default_code = 'inventory_error'

class InsufficientStockAPIException(InventoryAPIException):
    """API exception for insufficient stock"""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Insufficient stock for this operation.'
    default_code = 'insufficient_stock'

class InvalidMovementAPIException(InventoryAPIException):
    """API exception for invalid movements"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Invalid stock movement.'
    default_code = 'invalid_movement'

class TenantAccessDeniedAPIException(InventoryAPIException):
    """API exception for tenant access violations"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Access denied to this resource.'
    default_code = 'tenant_access_denied'

class ResourceNotFoundAPIException(InventoryAPIException):
    """API exception for resource not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'resource_not_found'

class BusinessRuleViolationAPIException(InventoryAPIException):
    """API exception for business rule violations"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Business rule violation.'
    default_code = 'business_rule_violation'

class ValidationException(ValidationError):
    """Enhanced validation exception with additional context"""
    
    def __init__(self, message, code=None, params=None, field=None, **kwargs):
        super().__init__(message, code, params)
        self.field = field
        self.additional_context = kwargs

# Exception utilities
def handle_inventory_exception(func):
    """Decorator to handle inventory exceptions and convert to appropriate API exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InsufficientStockException as e:
            raise InsufficientStockAPIException(detail=e.message)
        except InvalidMovementException as e:
            raise InvalidMovementAPIException(detail=e.message)
        except InventoryException as e:
            raise InventoryAPIException(detail=e.message)
        except ValidationError as e:
            raise InventoryAPIException(detail=str(e))
        except Exception as e:
            # Log the original exception
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Unhandled exception in {func.__name__}: {str(e)}")
            raise InventoryAPIException(detail="An unexpected error occurred.")
    
    return wrapper

def create_error_response(exception: InventoryException) -> Dict[str, Any]:
    """Create standardized error response from inventory exception"""
    return {
        'error': {
            'code': exception.code,
            'message': exception.message,
            'details': exception.details,
            'timestamp': timezone.now().isoformat()
        }
    }