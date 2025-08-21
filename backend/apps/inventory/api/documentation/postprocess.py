# apps/inventory/api/documentation/postprocess.py

def postprocess_schema(result, generator, request, public):
    """Post-process the generated schema."""
    
    # Add custom tags
    result['tags'] = [
        {
            'name': 'Authentication',
            'description': 'User authentication and authorization endpoints'
        },
        {
            'name': 'Inventory Management', 
            'description': 'Core inventory operations - products, stock, movements'
        },
        {
            'name': 'Warehouse Operations',
            'description': 'Warehouse and location management'
        },
        {
            'name': 'Purchase Management',
            'description': 'Purchase orders, receipts, and supplier management'
        },
        {
            'name': 'Transfer Operations', 
            'description': 'Inter-warehouse stock transfers'
        },
        {
            'name': 'Stock Adjustments',
            'description': 'Stock adjustments and cycle counting'
        },
        {
            'name': 'Reservations',
            'description': 'Stock reservations and allocations'
        },
        {
            'name': 'Machine Learning & Analytics',
            'description': 'AI-powered forecasting and advanced analytics'
        },
        {
            'name': 'Workflow Management',
            'description': 'Approval workflows and process automation'  
        },
        {
            'name': 'Alerts & Notifications',
            'description': 'Inventory alerts and notification system'
        },
        {
            'name': 'Reporting',
            'description': 'Report generation and business intelligence'
        },
        {
            'name': 'System Administration',
            'description': 'System configuration and maintenance'
        }
    ]
    
    # Add servers information
    result['servers'] = [
        {
            'url': 'https://api.inventory-system.com',
            'description': 'Production server'
        },
        {
            'url': 'https://staging-api.inventory-system.com', 
            'description': 'Staging server'
        },
        {
            'url': 'http://localhost:8000',
            'description': 'Development server'
        }
    ]
    
    # Add security schemes
    result['components']['securitySchemes'] = {
        'TokenAuth': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Token-based authentication. Format: `Token <your-token>`'
        },
        'SessionAuth': {
            'type': 'apiKey', 
            'in': 'cookie',
            'name': 'sessionid',
            'description': 'Session-based authentication for web clients'
        }
    }
    
    # Add global security requirement
    result['security'] = [
        {'TokenAuth': []},
        {'SessionAuth': []}
    ]
    
    return result