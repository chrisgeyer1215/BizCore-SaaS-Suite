from django.db import models
from django.utils.translation import gettext_lazy as _
from .constants import *

class ProductTypeChoices(models.TextChoices):
    """Product type choices"""
    FINISHED_GOOD = 'FINISHED_GOOD', _('Finished Good')
    RAW_MATERIAL = 'RAW_MATERIAL', _('Raw Material')
    COMPONENT = 'COMPONENT', _('Component')
    SUBASSEMBLY = 'SUBASSEMBLY', _('Subassembly')
    PACKAGING = 'PACKAGING', _('Packaging Material')
    SERVICE = 'SERVICE', _('Service Item')
    CONSUMABLE = 'CONSUMABLE', _('Consumable')
    TOOL = 'TOOL', _('Tool/Equipment')
    SPARE_PART = 'SPARE_PART', _('Spare Part')
    DIGITAL = 'DIGITAL', _('Digital Product')

class MovementTypeChoices(models.TextChoices):
    """Stock movement type choices"""
    RECEIPT = 'RECEIPT', _('Stock Receipt')
    ISSUE = 'ISSUE', _('Stock Issue')
    TRANSFER_OUT = 'TRANSFER_OUT', _('Transfer Out')
    TRANSFER_IN = 'TRANSFER_IN', _('Transfer In')
    ADJUSTMENT_POSITIVE = 'ADJUSTMENT_POSITIVE', _('Positive Adjustment')
    ADJUSTMENT_NEGATIVE = 'ADJUSTMENT_NEGATIVE', _('Negative Adjustment')
    PRODUCTION_CONSUMPTION = 'PRODUCTION_CONSUMPTION', _('Production Consumption')
    PRODUCTION_OUTPUT = 'PRODUCTION_OUTPUT', _('Production Output')
    RETURN_FROM_CUSTOMER = 'RETURN_FROM_CUSTOMER', _('Return from Customer')
    RETURN_TO_SUPPLIER = 'RETURN_TO_SUPPLIER', _('Return to Supplier')
    DAMAGED = 'DAMAGED', _('Damaged Stock')
    EXPIRED = 'EXPIRED', _('Expired Stock')
    LOST = 'LOST', _('Lost Stock')
    FOUND = 'FOUND', _('Found Stock')
    CYCLE_COUNT = 'CYCLE_COUNT', _('Cycle Count')
    OPENING_BALANCE = 'OPENING_BALANCE', _('Opening Balance')
    RESERVATION = 'RESERVATION', _('Stock Reservation')
    UNRESERVATION = 'UNRESERVATION', _('Stock Unreservation')

class StatusChoices(models.TextChoices):
    """General status choices"""
    DRAFT = 'DRAFT', _('Draft')
    PENDING = 'PENDING', _('Pending')
    PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Approval')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')
    FAILED = 'FAILED', _('Failed')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED', _('Partially Completed')
    REVERSED = 'REVERSED', _('Reversed')

class PriorityChoices(models.TextChoices):
    """Priority level choices"""
    LOW = 'LOW', _('Low')
    MEDIUM = 'MEDIUM', _('Medium')
    HIGH = 'HIGH', _('High')
    CRITICAL = 'CRITICAL', _('Critical')
    URGENT = 'URGENT', _('Urgent')

class CostingMethodChoices(models.TextChoices):
    """Inventory costing method choices"""
    FIFO = 'FIFO', _('First In, First Out')
    LIFO = 'LIFO', _('Last In, First Out')
    WEIGHTED_AVERAGE = 'WEIGHTED_AVERAGE', _('Weighted Average')
    STANDARD = 'STANDARD', _('Standard Cost')
    SPECIFIC = 'SPECIFIC', _('Specific Identification')

class ABCClassificationChoices(models.TextChoices):
    """ABC classification choices"""
    A = 'A', _('Class A - High Value')
    B = 'B', _('Class B - Medium Value')
    C = 'C', _('Class C - Low Value')
    N = 'N', _('Not Classified')

class UOMCategoryChoices(models.TextChoices):
    """Unit of measure category choices"""
    WEIGHT = 'WEIGHT', _('Weight')
    VOLUME = 'VOLUME', _('Volume')
    LENGTH = 'LENGTH', _('Length')
    AREA = 'AREA', _('Area')
    PIECE = 'PIECE', _('Piece/Unit')
    TIME = 'TIME', _('Time')
    TEMPERATURE = 'TEMPERATURE', _('Temperature')

class AlertTypeChoices(models.TextChoices):
    """Alert type choices"""
    LOW_STOCK = 'LOW_STOCK', _('Low Stock')
    OUT_OF_STOCK = 'OUT_OF_STOCK', _('Out of Stock')
    OVERSTOCK = 'OVERSTOCK', _('Overstock')
    EXPIRY = 'EXPIRY', _('Expiry Warning')
    SLOW_MOVING = 'SLOW_MOVING', _('Slow Moving')
    DEAD_STOCK = 'DEAD_STOCK', _('Dead Stock')
    REORDER_POINT = 'REORDER_POINT', _('Reorder Point')
    NEGATIVE_STOCK = 'NEGATIVE_STOCK', _('Negative Stock')
    COST_VARIANCE = 'COST_VARIANCE', _('Cost Variance')
    ABC_CHANGE = 'ABC_CHANGE', _('ABC Classification Change')
    QUALITY_CONTROL = 'QUALITY_CONTROL', _('Quality Control Required')

class ReservationTypeChoices(models.TextChoices):
    """Stock reservation type choices"""
    SALES_ORDER = 'SALES_ORDER', _('Sales Order')
    PRODUCTION_ORDER = 'PRODUCTION_ORDER', _('Production Order')
    TRANSFER_ORDER = 'TRANSFER_ORDER', _('Transfer Order')
    CUSTOMER_HOLD = 'CUSTOMER_HOLD', _('Customer Hold')
    QUALITY_HOLD = 'QUALITY_HOLD', _('Quality Hold')
    DAMAGE_HOLD = 'DAMAGE_HOLD', _('Damage Hold')
    INSPECTION_HOLD = 'INSPECTION_HOLD', _('Inspection Hold')
    ECOMMERCE_ORDER = 'ECOMMERCE_ORDER', _('E-commerce Order')
    BACKORDER = 'BACKORDER', _('Backorder')
    CONSIGNMENT = 'CONSIGNMENT', _('Consignment')

class ReportTypeChoices(models.TextChoices):
    """Report type choices"""
    STOCK_SUMMARY = 'STOCK_SUMMARY', _('Stock Summary')
    STOCK_VALUATION = 'STOCK_VALUATION', _('Stock Valuation')
    MOVEMENT_HISTORY = 'MOVEMENT_HISTORY', _('Movement History')
    ABC_ANALYSIS = 'ABC_ANALYSIS', _('ABC Analysis')
    AGING_ANALYSIS = 'AGING_ANALYSIS', _('Aging Analysis')
    REORDER_REPORT = 'REORDER_REPORT', _('Reorder Report')
    DEAD_STOCK = 'DEAD_STOCK', _('Dead Stock Report')
    FAST_SLOW_MOVING = 'FAST_SLOW_MOVING', _('Fast/Slow Moving')
    SUPPLIER_PERFORMANCE = 'SUPPLIER_PERFORMANCE', _('Supplier Performance')
    PURCHASE_ANALYSIS = 'PURCHASE_ANALYSIS', _('Purchase Analysis')
    CUSTOM = 'CUSTOM', _('Custom Report')

class FileFormatChoices(models.TextChoices):
    """File format choices"""
    PDF = 'PDF', _('PDF Document')
    EXCEL = 'EXCEL', _('Excel Spreadsheet')
    CSV = 'CSV', _('CSV File')
    JSON = 'JSON', _('JSON Data')
    XML = 'XML', _('XML Data')
    HTML = 'HTML', _('HTML Page')

class QCStatusChoices(models.TextChoices):
    """Quality control status choices"""
    PENDING = 'PENDING', _('Pending QC')
    IN_PROGRESS = 'IN_PROGRESS', _('QC In Progress')
    PASSED = 'PASSED', _('QC Passed')
    FAILED = 'FAILED', _('QC Failed')
    CONDITIONAL = 'CONDITIONAL', _('Conditional Pass')
    WAIVED = 'WAIVED', _('QC Waived')
    NOT_REQUIRED = 'NOT_REQUIRED', _('QC Not Required')

class SupplierStatusChoices(models.TextChoices):
    """Supplier status choices"""
    PROSPECT = 'PROSPECT', _('Prospect')
    ACTIVE = 'ACTIVE', _('Active')
    INACTIVE = 'INACTIVE', _('Inactive')
    APPROVED = 'APPROVED', _('Approved')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    BLACKLISTED = 'BLACKLISTED', _('Blacklisted')
    PREFERRED = 'PREFERRED', _('Preferred')

class PerformanceRatingChoices(models.TextChoices):
    """Performance rating choices"""
    EXCELLENT = 'EXCELLENT', _('Excellent (90-100%)')
    GOOD = 'GOOD', _('Good (80-89%)')
    SATISFACTORY = 'SATISFACTORY', _('Satisfactory (70-79%)')
    NEEDS_IMPROVEMENT = 'NEEDS_IMPROVEMENT', _('Needs Improvement (60-69%)')
    POOR = 'POOR', _('Poor (Below 60%)')

class IntegrationPlatformChoices(models.TextChoices):
    """Integration platform choices"""
    SHOPIFY = 'SHOPIFY', _('Shopify')
    WOOCOMMERCE = 'WOOCOMMERCE', _('WooCommerce')
    MAGENTO = 'MAGENTO', _('Magento')
    AMAZON = 'AMAZON', _('Amazon')
    EBAY = 'EBAY', _('eBay')
    BIGCOMMERCE = 'BIGCOMMERCE', _('BigCommerce')
    PRESTASHOP = 'PRESTASHOP', _('PrestaShop')
    OPENCART = 'OPENCART', _('OpenCart')

class CurrencyChoices(models.TextChoices):
    """Currency choices (ISO 4217)"""
    USD = 'USD', _('US Dollar')
    EUR = 'EUR', _('Euro')
    GBP = 'GBP', _('British Pound')
    JPY = 'JPY', _('Japanese Yen')
    CAD = 'CAD', _('Canadian Dollar')
    AUD = 'AUD', _('Australian Dollar')
    CHF = 'CHF', _('Swiss Franc')
    CNY = 'CNY', _('Chinese Yuan')
    INR = 'INR', _('Indian Rupee')
    BRL = 'BRL', _('Brazilian Real')

class AlertSeverityChoices(models.TextChoices):
    """Alert severity choices"""
    LOW = 'LOW', _('Low')
    MEDIUM = 'MEDIUM', _('Medium')
    HIGH = 'HIGH', _('High')
    CRITICAL = 'CRITICAL', _('Critical')

class FulfillmentStrategyChoices(models.TextChoices):
    """Fulfillment strategy choices"""
    FIFO = 'FIFO', _('First In First Out')
    LIFO = 'LIFO', _('Last In Last Out')
    PRIORITY = 'PRIORITY', _('Priority Based')
    PARTIAL_ALLOWED = 'PARTIAL_ALLOWED', _('Allow Partial Fulfillment')
    ALL_OR_NOTHING = 'ALL_OR_NOTHING', _('All or Nothing')

class AdjustmentTypeChoices(models.TextChoices):
    """Stock adjustment type choices"""
    PHYSICAL_COUNT = 'PHYSICAL_COUNT', _('Physical Count Adjustment')
    DAMAGE = 'DAMAGE', _('Damage Adjustment')
    THEFT = 'THEFT', _('Theft/Loss Adjustment')
    EXPIRY = 'EXPIRY', _('Expiry Adjustment')
    QUALITY_REJECTION = 'QUALITY_REJECTION', _('Quality Rejection')
    SYSTEM_CORRECTION = 'SYSTEM_CORRECTION', _('System Correction')
    TRANSFER_DAMAGE = 'TRANSFER_DAMAGE', _('Transfer Damage')
    OBSOLETE = 'OBSOLETE', _('Obsolete Stock')
    OTHER = 'OTHER', _('Other Adjustment')

class CountFrequencyChoices(models.TextChoices):
    """Cycle count frequency choices"""
    DAILY = 'DAILY', _('Daily')
    WEEKLY = 'WEEKLY', _('Weekly')
    MONTHLY = 'MONTHLY', _('Monthly')
    QUARTERLY = 'QUARTERLY', _('Quarterly')
    SEMI_ANNUALLY = 'SEMI_ANNUALLY', _('Semi-Annually')
    ANNUALLY = 'ANNUALLY', _('Annually')
    AD_HOC = 'AD_HOC', _('Ad-hoc')

class LocationTypeChoices(models.TextChoices):
    """Storage location type choices"""
    RECEIVING = 'RECEIVING', _('Receiving Area')
    BULK_STORAGE = 'BULK_STORAGE', _('Bulk Storage')
    PICK_FACE = 'PICK_FACE', _('Pick Face')
    RESERVE = 'RESERVE', _('Reserve Storage')
    SHIPPING = 'SHIPPING', _('Shipping Area')
    QUALITY_CONTROL = 'QUALITY_CONTROL', _('Quality Control')
    QUARANTINE = 'QUARANTINE', _('Quarantine')
    DAMAGED = 'DAMAGED', _('Damaged Goods')
    RETURNS = 'RETURNS', _('Returns Processing')
    CROSS_DOCK = 'CROSS_DOCK', _('Cross-dock')

class WarehouseTypeChoices(models.TextChoices):
    """Warehouse type choices"""
    DISTRIBUTION_CENTER = 'DISTRIBUTION_CENTER', _('Distribution Center')
    RETAIL_STORE = 'RETAIL_STORE', _('Retail Store')
    MANUFACTURING = 'MANUFACTURING', _('Manufacturing Facility')
    THIRD_PARTY = 'THIRD_PARTY', _('Third Party Logistics')
    CROSS_DOCK = 'CROSS_DOCK', _('Cross-dock Facility')
    COLD_STORAGE = 'COLD_STORAGE', _('Cold Storage')
    HAZMAT = 'HAZMAT', _('Hazardous Materials')
    BONDED = 'BONDED', _('Bonded Warehouse')
    CONSIGNMENT = 'CONSIGNMENT', _('Consignment')
    VIRTUAL = 'VIRTUAL', _('Virtual/Dropship')