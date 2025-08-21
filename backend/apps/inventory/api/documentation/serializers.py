# apps/inventory/api/documentation/serializers.py

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Product Creation Example',
            summary='Create a new product',
            description='Example of creating a new product with all required fields',
            value={
                "name": "iPhone 14 Pro",
                "sku": "IPHONE14PRO256",
                "barcode": "1234567890123",
                "description": "iPhone 14 Pro 256GB Space Black",
                "category": 1,
                "brand": 2,
                "supplier": 3,
                "uom": 1,
                "cost_price": "899.00",
                "selling_price": "1099.00",
                "weight": "0.206",
                "dimensions": "147.5 x 71.5 x 7.85 mm",
                "reorder_level": "10.0000",
                "max_stock_level": "100.0000",
                "lead_time_days": 7,
                "shelf_life_days": null,
                "is_serialized": True,
                "track_batches": False,
                "storage_requirements": "Store in cool, dry place",
                "is_active": True
            },
            request_only=True,
        ),
        OpenApiExample(
            'Product Response Example',
            summary='Product response with analytics',
            description='Complete product information including stock levels and analytics',
            value={
                "id": 1,
                "name": "iPhone 14 Pro",
                "sku": "IPHONE14PRO256", 
                "barcode": "1234567890123",
                "description": "iPhone 14 Pro 256GB Space Black",
                "category": {
                    "id": 1,
                    "name": "Smartphones",
                    "department": "Electronics"
                },
                "brand": {
                    "id": 2,
                    "name": "Apple"
                },
                "supplier": {
                    "id": 3,
                    "name": "Tech Distributor Inc",
                    "supplier_code": "TD001"
                },
                "uom": {
                    "id": 1,
                    "name": "Each",
                    "abbreviation": "EA"
                },
                "cost_price": "899.00",
                "selling_price": "1099.00",
                "profit_margin": "22.2%",
                "weight": "0.206",
                "abc_classification": "A",
                "total_stock": "45.0000",
                "stock_value": "$40,455.00",
                "last_movement_date": "2024-01-15",
                "turnover_ratio": 8.5,
                "reorder_level": "10.0000",
                "max_stock_level": "100.0000", 
                "is_active": True,
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-15T14:30:00Z"
            },
            response_only=True,
        ),
    ]
)
class DocumentedProductSerializer(serializers.Serializer):
    """
    Product serializer with comprehensive documentation and examples.
    
    Products are the core entities in the inventory system. Each product
    can have multiple stock items across different warehouses and locations.
    """
    
    id = serializers.IntegerField(
        read_only=True,
        help_text="Unique identifier for the product"
    )
    
    name = serializers.CharField(
        max_length=200,
        help_text="Product name (e.g., 'iPhone 14 Pro 256GB')"
    )
    
    sku = serializers.CharField(
        max_length=100,
        help_text="Stock Keeping Unit - unique product identifier"
    )
    
    barcode = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        help_text="Product barcode (UPC, EAN, etc.)"
    )
    
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Detailed product description"
    )
    
    category = serializers.IntegerField(
        help_text="Product category ID"
    )
    
    brand = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Brand ID (optional)"
    )
    
    supplier = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Primary supplier ID (optional)"
    )
    
    cost_price = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Product cost price from supplier"
    )
    
    selling_price = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Product selling price to customers"
    )
    
    abc_classification = serializers.ChoiceField(
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        read_only=True,
        help_text="ABC classification based on value/movement analysis"
    )
    
    total_stock = serializers.DecimalField(
        max_digits=15,
        decimal_places=4,
        read_only=True,
        help_text="Total stock across all warehouses"
    )
    
    reorder_level = serializers.DecimalField(
        max_digits=15,
        decimal_places=4,
        help_text="Minimum stock level before reordering"
    )
    
    is_active = serializers.BooleanField(
        default=True,
        help_text="Whether the product is active in the system"
    )

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Demand Forecast Request',
            summary='AI demand forecasting request',
            description='Request AI-powered demand forecasting for specific products',
            value={
                "tenant_id": 1,
                "products": [1, 2, 3, 15, 22],
                "warehouses": [1, 2], 
                "forecast_horizon": 30,
                "confidence_level": 0.95,
                "model_preference": "ensemble",
                "include_seasonality": True,
                "include_promotions": True
            },
            request_only=True,
        ),
        OpenApiExample(
            'Demand Forecast Response',
            summary='AI demand forecasting results',
            description='Comprehensive demand forecast with confidence intervals and business insights',
            value={
                "status": "success",
                "predictions": {
                    "1": {
                        "status": "success",
                        "forecast": [
                            {
                                "date": "2024-01-16",
                                "predicted_demand": 12.5,
                                "confidence_lower": 8.2,
                                "confidence_upper": 16.8
                            },
                            {
                                "date": "2024-01-17", 
                                "predicted_demand": 11.3,
                                "confidence_lower": 7.8,
                                "confidence_upper": 14.9
                            }
                        ],
                        "summary": {
                            "total_forecasted_demand": 342.7,
                            "average_daily_demand": 11.4,
                            "peak_demand": 18.2,
                            "peak_demand_date": "2024-01-25"
                        },
                        "model_info": {
                            "model_id": "ensemble_v1_a8b9c7d2",
                            "algorithm": "Ensemble",
                            "version": "1.0.0",
                            "training_date": "2024-01-10T09:15:00Z",
                            "performance_mae": 2.14
                        }
                    }
                },
                "metadata": {
                    "forecast_horizon_days": 30,
                    "confidence_level": 0.95,
                    "latency_ms": 245.6,
                    "timestamp": "2024-01-15T16:30:00Z"
                }
            },
            response_only=True,
        ),
    ]
)
class MLForecastRequestSerializer(serializers.Serializer):
    """
    AI-powered demand forecasting request serializer.
    
    This endpoint uses machine learning models to predict future demand
    for specified products with configurable confidence intervals.
    """
    
    tenant_id = serializers.IntegerField(
        help_text="Tenant ID for multi-tenant isolation"
    )
    
    products = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100,
        help_text="List of product IDs to forecast (max 100 products per request)"
    )
    
    warehouses = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Optional list of warehouse IDs to filter by"
    )
    
    forecast_horizon = serializers.IntegerField(
        min_value=1,
        max_value=365,
        default=30,
        help_text="Number of days to forecast (1-365 days)"
    )
    
    confidence_level = serializers.FloatField(
        min_value=0.5,
        max_value=0.99,
        default=0.95,
        help_text="Confidence level for prediction intervals (0.5-0.99)"
    )
    
    model_preference = serializers.ChoiceField(
        choices=[
            ('best', 'Best performing model'),
            ('ensemble', 'Ensemble model'),
            ('random_forest', 'Random Forest'),
            ('xgboost', 'XGBoost'),
            ('lstm', 'LSTM Neural Network'),
            ('prophet', 'Facebook Prophet')
        ],
        default='best',
        help_text="Preferred ML model for forecasting"
    )
    
    include_seasonality = serializers.BooleanField(
        default=True,
        help_text="Include seasonal patterns in forecast"
    )
    
    include_promotions = serializers.BooleanField(
        default=True,
        help_text="Include promotional effects in forecast"
    )

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'ABC Analysis Request',
            summary='Trigger ABC analysis',
            description='Start ABC classification analysis for inventory optimization',
            value={
                "analysis_name": "Q1 2024 ABC Analysis",
                "analysis_period_start": "2023-04-01",
                "analysis_period_end": "2024-03-31", 
                "analysis_method": "SALES_VALUE",
                "class_a_threshold": 80.0,
                "class_b_threshold": 95.0,
                "warehouse_filter": [1, 2],
                "category_filter": [1, 3, 5],
                "auto_apply_results": True
            },
            request_only=True,
        ),
    ]
)
class ABCAnalysisRequestSerializer(serializers.Serializer):
    """
    ABC Analysis request for inventory classification and optimization.
    
    ABC Analysis classifies inventory items into three categories:
    - Class A: High-value items (typically 80% of value, 20% of items)  
    - Class B: Medium-value items (typically 15% of value, 30% of items)
    - Class C: Low-value items (typically 5% of value, 50% of items)
    """
    
    analysis_name = serializers.CharField(
        max_length=200,
        help_text="Name for this ABC analysis run"
    )
    
    analysis_period_start = serializers.DateField(
        help_text="Start date for analysis period (YYYY-MM-DD)"
    )
    
    analysis_period_end = serializers.DateField(
        help_text="End date for analysis period (YYYY-MM-DD)"
    )
    
    analysis_method = serializers.ChoiceField(
        choices=[
            ('SALES_VALUE', 'Sales Value'),
            ('USAGE_QUANTITY', 'Usage Quantity'), 
            ('PROFIT_MARGIN', 'Profit Margin'),
            ('INVENTORY_VALUE', 'Inventory Value'),
            ('MOVEMENT_FREQUENCY', 'Movement Frequency')
        ],
        default='SALES_VALUE',
        help_text="Method for ABC classification"
    )
    
    class_a_threshold = serializers.FloatField(
        min_value=50.0,
        max_value=95.0,
        default=80.0,
        help_text="Cumulative percentage threshold for Class A items"
    )
    
    class_b_threshold = serializers.FloatField(
        min_value=80.0,
        max_value=99.0, 
        default=95.0,
        help_text="Cumulative percentage threshold for Class B items"
    )
    
    auto_apply_results = serializers.BooleanField(
        default=False,
        help_text="Automatically apply ABC classifications to products"
    )