from django.utils.translation import gettext_lazy as _

# Movement Types
MOVEMENT_TYPES = {
    'RECEIPT': _('Stock Receipt'),
    'ISSUE': _('Stock Issue'),
    'TRANSFER_OUT': _('Transfer Out'),
    'TRANSFER_IN': _('Transfer In'),
    'ADJUSTMENT_POSITIVE': _('Positive Adjustment'),
    'ADJUSTMENT_NEGATIVE': _('Negative Adjustment'),
    'PRODUCTION_CONSUMPTION': _('Production Consumption'),
    'PRODUCTION_OUTPUT': _('Production Output'),
    'RETURN_FROM_CUSTOMER': _('Return from Customer'),
    'RETURN_TO_SUPPLIER': _('Return to Supplier'),
    'DAMAGED': _('Damaged Stock'),
    'EXPIRED': _('Expired Stock'),
    'LOST': _('Lost Stock'),
    'FOUND': _('Found Stock'),
    'CYCLE_COUNT': _('Cycle Count'),
    'OPENING_BALANCE': _('Opening Balance'),
    'RESERVATION': _('Stock Reservation'),
    'UNRESERVATION': _('Stock Unreservation'),
    'WRITE_OFF': _('Write Off'),
    'QUALITY_REJECTION': _('Quality Rejection'),
    'OBSOLETE': _('Obsolete Stock'),
    'THEFT': _('Theft/Loss'),
    'PHYSICAL_COUNT': _('Physical Count'),
    'SYSTEM_CORRECTION': _('System Correction'),
}

# Status Choices
STATUS_CHOICES = {
    'DRAFT': _('Draft'),
    'PENDING': _('Pending'),
    'PENDING_APPROVAL': _('Pending Approval'),
    'APPROVED': _('Approved'),
    'REJECTED': _('Rejected'),
    'IN_PROGRESS': _('In Progress'),
    'IN_TRANSIT': _('In Transit'),
    'COMPLETED': _('Completed'),
    'CANCELLED': _('Cancelled'),
    'FAILED': _('Failed'),
    'ON_HOLD': _('On Hold'),
    'PARTIALLY_COMPLETED': _('Partially Completed'),
    'REVERSED': _('Reversed'),
}

# Priority Levels
PRIORITY_LEVELS = {
    'LOW': _('Low'),
    'MEDIUM': _('Medium'),
    'HIGH': _('High'),
    'CRITICAL': _('Critical'),
    'URGENT': _('Urgent'),
}

# Product Types
PRODUCT_TYPES = {
    'FINISHED_GOOD': _('Finished Good'),
    'RAW_MATERIAL': _('Raw Material'),
    'COMPONENT': _('Component'),
    'SUBASSEMBLY': _('Subassembly'),
    'PACKAGING': _('Packaging Material'),
    'SERVICE': _('Service Item'),
    'CONSUMABLE': _('Consumable'),
    'TOOL': _('Tool/Equipment'),
    'SPARE_PART': _('Spare Part'),
    'DIGITAL': _('Digital Product'),
}

# Costing Methods
COSTING_METHODS = {
    'FIFO': _('First In, First Out'),
    'LIFO': _('Last In, First Out'),
    'WEIGHTED_AVERAGE': _('Weighted Average'),
    'STANDARD': _('Standard Cost'),
    'SPECIFIC': _('Specific Identification'),
}

# ABC Classifications
ABC_CLASSIFICATIONS = {
    'A': _('Class A - High Value'),
    'B': _('Class B - Medium Value'), 
    'C': _('Class C - Low Value'),
    'N': _('Not Classified'),
}

# UOM Categories
UOM_CATEGORIES = {
    'WEIGHT': _('Weight'),
    'VOLUME': _('Volume'),
    'LENGTH': _('Length'),
    'AREA': _('Area'),
    'PIECE': _('Piece/Unit'),
    'TIME': _('Time'),
    'TEMPERATURE': _('Temperature'),
}

# Alert Types
ALERT_TYPES = {
    'LOW_STOCK': _('Low Stock'),
    'OUT_OF_STOCK': _('Out of Stock'),
    'OVERSTOCK': _('Overstock'),
    'EXPIRY': _('Expiry Warning'),
    'SLOW_MOVING': _('Slow Moving'),
    'DEAD_STOCK': _('Dead Stock'),
    'REORDER_POINT': _('Reorder Point'),
    'NEGATIVE_STOCK': _('Negative Stock'),
    'COST_VARIANCE': _('Cost Variance'),
    'ABC_CHANGE': _('ABC Classification Change'),
    'QUALITY_CONTROL': _('Quality Control Required'),
    'SUPPLIER_DELAY': _('Supplier Delay'),
    'FORECAST_VARIANCE': _('Forecast Variance'),
}

# Reservation Types
RESERVATION_TYPES = {
    'SALES_ORDER': _('Sales Order'),
    'PRODUCTION_ORDER': _('Production Order'),
    'TRANSFER_ORDER': _('Transfer Order'),
    'CUSTOMER_HOLD': _('Customer Hold'),
    'QUALITY_HOLD': _('Quality Hold'),
    'DAMAGE_HOLD': _('Damage Hold'),
    'INSPECTION_HOLD': _('Inspection Hold'),
    'ECOMMERCE_ORDER': _('E-commerce Order'),
    'BACKORDER': _('Backorder'),
    'CONSIGNMENT': _('Consignment'),
}

# Report Types
REPORT_TYPES = {
    'STOCK_SUMMARY': _('Stock Summary'),
    'STOCK_VALUATION': _('Stock Valuation'),
    'MOVEMENT_HISTORY': _('Movement History'),
    'ABC_ANALYSIS': _('ABC Analysis'),
    'AGING_ANALYSIS': _('Aging Analysis'),
    'REORDER_REPORT': _('Reorder Report'),
    'DEAD_STOCK': _('Dead Stock Report'),
    'FAST_SLOW_MOVING': _('Fast/Slow Moving'),
    'SUPPLIER_PERFORMANCE': _('Supplier Performance'),
    'PURCHASE_ANALYSIS': _('Purchase Analysis'),
    'TRANSFER_REPORT': _('Transfer Report'),
    'ADJUSTMENT_REPORT': _('Adjustment Report'),
    'CYCLE_COUNT': _('Cycle Count Report'),
    'RESERVATION_REPORT': _('Reservation Report'),
    'ALERT_SUMMARY': _('Alert Summary'),
    'FORECAST_ACCURACY': _('Forecast Accuracy'),
    'INVENTORY_KPI': _('Inventory KPI Dashboard'),
    'CUSTOM': _('Custom Report'),
}

# File Formats
FILE_FORMATS = {
    'PDF': _('PDF Document'),
    'EXCEL': _('Excel Spreadsheet'),
    'CSV': _('CSV File'),
    'JSON': _('JSON Data'),
    'XML': _('XML Data'),
    'HTML': _('HTML Page'),
}

# Integration Platforms
INTEGRATION_PLATFORMS = {
    'SHOPIFY': _('Shopify'),
    'WOOCOMMERCE': _('WooCommerce'),
    'MAGENTO': _('Magento'),
    'AMAZON': _('Amazon'),
    'EBAY': _('eBay'),
    'BIGCOMMERCE': _('BigCommerce'),
    'PRESTASHOP': _('PrestaShop'),
    'OPENCART': _('OpenCart'),
}

# Quality Control Status
QC_STATUS_CHOICES = {
    'PENDING': _('Pending QC'),
    'IN_PROGRESS': _('QC In Progress'),
    'PASSED': _('QC Passed'),
    'FAILED': _('QC Failed'),
    'CONDITIONAL': _('Conditional Pass'),
    'WAIVED': _('QC Waived'),
    'NOT_REQUIRED': _('QC Not Required'),
}

# Supplier Status
SUPPLIER_STATUS = {
    'PROSPECT': _('Prospect'),
    'ACTIVE': _('Active'),
    'INACTIVE': _('Inactive'),
    'APPROVED': _('Approved'),
    'SUSPENDED': _('Suspended'),
    'BLACKLISTED': _('Blacklisted'),
    'PREFERRED': _('Preferred'),
}

# Performance Ratings
PERFORMANCE_RATINGS = {
    'EXCELLENT': _('Excellent (90-100%)'),
    'GOOD': _('Good (80-89%)'),
    'SATISFACTORY': _('Satisfactory (70-79%)'),
    'NEEDS_IMPROVEMENT': _('Needs Improvement (60-69%)'),
    'POOR': _('Poor (Below 60%)'),
}

# Currency Codes (ISO 4217)
CURRENCY_CODES = {
    'USD': _('US Dollar'),
    'EUR': _('Euro'),
    'GBP': _('British Pound'),
    'JPY': _('Japanese Yen'),
    'CAD': _('Canadian Dollar'),
    'AUD': _('Australian Dollar'),
    'CHF': _('Swiss Franc'),
    'CNY': _('Chinese Yuan'),
    'INR': _('Indian Rupee'),
    'BRL': _('Brazilian Real'),
}

# Default Values
DEFAULT_VALUES = {
    'DEFAULT_CURRENCY': 'USD',
    'DEFAULT_COSTING_METHOD': 'FIFO',
    'DEFAULT_UOM': 'EACH',
    'DEFAULT_LEAD_TIME_DAYS': 14,
    'DEFAULT_SAFETY_STOCK_DAYS': 7,
    'DEFAULT_REORDER_QUANTITY': 100,
    'DEFAULT_ABC_CLASS': 'N',
    'DEFAULT_TAX_RATE': 0.0,
    'DEFAULT_DISCOUNT_RATE': 0.0,
    'MAX_DECIMAL_PLACES': 4,
    'MAX_FILE_SIZE_MB': 100,
    'INVENTORY_TURNOVER_PERIODS': 12,  # months
    'ABC_CLASS_A_PERCENTAGE': 80,
    'ABC_CLASS_B_PERCENTAGE': 95,
    'SEASONAL_ANALYSIS_YEARS': 2,
    'FORECAST_HORIZON_MONTHS': 12,
}

# Business Rules
BUSINESS_RULES = {
    'MIN_REORDER_LEVEL': 1,
    'MAX_REORDER_LEVEL': 999999,
    'MIN_SAFETY_STOCK': 0,
    'MAX_LEAD_TIME_DAYS': 365,
    'MIN_UNIT_COST': 0.0001,
    'MAX_UNIT_COST': 999999.9999,
    'MAX_QUANTITY': 999999999,
    'AUTO_APPROVE_THRESHOLD': 1000.00,
    'BULK_OPERATION_LIMIT': 10000,
    'REPORT_RETENTION_DAYS': 90,
    'ALERT_RETENTION_DAYS': 365,
    'MOVEMENT_HISTORY_YEARS': 7,
    'MAX_RESERVATION_DAYS': 30,
    'CYCLE_COUNT_VARIANCE_THRESHOLD': 5.0,  # percentage
}

# System Configuration
SYSTEM_CONFIG = {
    'ENABLE_MULTI_CURRENCY': True,
    'ENABLE_MULTI_UOM': True,
    'ENABLE_BATCH_TRACKING': True,
    'ENABLE_SERIAL_TRACKING': True,
    'ENABLE_EXPIRY_TRACKING': True,
    'ENABLE_LOCATION_TRACKING': True,
    'ENABLE_QUALITY_CONTROL': True,
    'ENABLE_LANDED_COSTS': True,
    'ENABLE_CONSIGNMENT': True,
    'ENABLE_KITTING': True,
    'ENABLE_FORECASTING': True,
    'ENABLE_ANALYTICS': True,
    'ENABLE_MOBILE_ACCESS': True,
    'ENABLE_API_ACCESS': True,
    'ENABLE_WEBHOOK_NOTIFICATIONS': True,
}

# Error Messages
ERROR_MESSAGES = {
    'INSUFFICIENT_STOCK': _('Insufficient stock available for this operation.'),
    'INVALID_QUANTITY': _('Quantity must be greater than zero.'),
    'INVALID_COST': _('Unit cost must be a positive number.'),
    'DUPLICATE_SKU': _('A product with this SKU already exists.'),
    'INVALID_BARCODE': _('Invalid barcode format.'),
    'WAREHOUSE_REQUIRED': _('Warehouse is required for this operation.'),
    'SUPPLIER_INACTIVE': _('Cannot process order for inactive supplier.'),
    'PRODUCT_DISCONTINUED': _('This product has been discontinued.'),
    'LOCATION_FULL': _('Storage location is at maximum capacity.'),
    'BATCH_EXPIRED': _('Cannot use expired batch for this operation.'),
    'SERIAL_NUMBER_DUPLICATE': _('This serial number already exists.'),
    'RESERVATION_EXPIRED': _('Stock reservation has expired.'),
    'ADJUSTMENT_LIMIT_EXCEEDED': _('Adjustment amount exceeds authorized limit.'),
    'CYCLE_COUNT_IN_PROGRESS': _('Cycle count already in progress for this location.'),
    'TRANSFER_SAME_WAREHOUSE': _('Cannot transfer to the same warehouse.'),
    'PO_ALREADY_RECEIVED': _('Purchase order has already been fully received.'),
    'INVALID_MOVEMENT_TYPE': _('Invalid movement type for this operation.'),
    'PERMISSION_DENIED': _('You do not have permission to perform this action.'),
    'TENANT_MISMATCH': _('Resource does not belong to your organization.'),
    'VALIDATION_FAILED': _('Data validation failed. Please check your input.'),
}

# Success Messages
SUCCESS_MESSAGES = {
    'STOCK_MOVEMENT_CREATED': _('Stock movement created successfully.'),
    'PURCHASE_ORDER_APPROVED': _('Purchase order approved successfully.'),
    'TRANSFER_COMPLETED': _('Stock transfer completed successfully.'),
    'ADJUSTMENT_APPLIED': _('Stock adjustment applied successfully.'),
    'RESERVATION_CREATED': _('Stock reservation created successfully.'),
    'ALERT_RESOLVED': _('Alert resolved successfully.'),
    'REPORT_GENERATED': _('Report generated successfully.'),
    'CYCLE_COUNT_COMPLETED': _('Cycle count completed successfully.'),
    'BATCH_OPERATION_COMPLETED': _('Batch operation completed successfully.'),
    'INTEGRATION_SYNCED': _('Data synchronized successfully.'),
    'SETTINGS_UPDATED': _('Settings updated successfully.'),
    'BACKUP_CREATED': _('Data backup created successfully.'),
}

# API Configuration
API_CONFIG = {
    'DEFAULT_PAGE_SIZE': 25,
    'MAX_PAGE_SIZE': 1000,
    'API_VERSION': 'v1',
    'RATE_LIMIT_PER_MINUTE': 1000,
    'RATE_LIMIT_PER_HOUR': 10000,
    'RATE_LIMIT_PER_DAY': 100000,
    'MAX_BULK_OPERATIONS': 1000,
    'WEBHOOK_TIMEOUT_SECONDS': 30,
    'WEBHOOK_RETRY_ATTEMPTS': 3,
    'CACHE_TIMEOUT_SECONDS': 300,
}

# Regular Expressions
REGEX_PATTERNS = {
    'SKU_PATTERN': r'^[A-Z0-9\-_]{3,50}$',
    'BARCODE_EAN13': r'^\d{13}$',
    'BARCODE_UPC': r'^\d{12}$',
    'BARCODE_CODE128': r'^[A-Za-z0-9\-\.\s\$\/\+\%]{1,48}$',
    'REFERENCE_NUMBER': r'^[A-Z]{2,4}-\d{8}-[A-Z0-9]{4}$',
    'WAREHOUSE_CODE': r'^[A-Z]{2,4}\d{2,4}$',
    'LOCATION_CODE': r'^[A-Z0-9\-]{3,20}$',
    'BATCH_NUMBER': r'^[A-Za-z0-9\-_]{3,30}$',
    'SERIAL_NUMBER': r'^[A-Za-z0-9\-_]{5,50}$',
    'PO_NUMBER': r'^PO-\d{8}-[A-Z0-9]{4}$',
    'INVOICE_NUMBER': r'^INV-\d{8}-[A-Z0-9]{4}$',
}