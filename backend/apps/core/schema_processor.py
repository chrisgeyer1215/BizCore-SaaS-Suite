# backend/apps/core/schema_processors.py
def custom_preprocessing_hook(endpoints):
    """Custom preprocessing hook for API schema."""
    # Filter out internal endpoints
    filtered = []
    for (path, path_regex, method, callback) in endpoints:
        # Skip admin and debug endpoints
        if path.startswith('/admin/') or path.startswith('/_debug_/'):
            continue
        # Skip internal health checks in production docs
        if 'health' in path and method == 'GET':
            continue
        filtered.append((path, path_regex, method, callback))
    return filtered

def custom_postprocessing_hook(result, generator, request, public):
    """Custom postprocessing hook for API schema."""
    # Add custom headers to all endpoints
    for path_item in result.get('paths', {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and 'parameters' in operation:
                # Add tenant header requirement
                operation['parameters'].append({
                    'name': 'X-Tenant-Domain',
                    'in': 'header',
                    'required': True,
                    'description': 'Tenant domain for multi-tenant access',
                    'schema': {'type': 'string', 'example': 'acme-corp'}
                })
    
    # Add response examples
    _add_response_examples(result)
    
    return result

def _add_response_examples(schema):
    """Add response examples to schema."""
    examples = {
        'Account': {
            'id': 1,
            'name': 'Acme Corporation',
            'email': 'contact@acme.com',
            'phone': '+1-555-0123',
            'industry': 'Technology',
            'annual_revenue': 5000000,
            'employees': 150,
            'status': 'active',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-20T14:45:00Z'
        },
        'Lead': {
            'id': 1,
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'john.smith@example.com',
            'phone': '+1-555-0124',
            'company': 'Example Inc',
            'title': 'CTO',
            'status': 'qualified',
            'score': 85,
            'source': 'website',
            'created_at': '2024-01-18T09:15:00Z',
            'updated_at': '2024-01-19T16:20:00Z'
        },
        'Opportunity': {
            'id': 1,
            'name': 'Q1 Enterprise Deal',
            'account': 1,
            'stage': 'proposal',
            'amount': 250000,
            'probability': 75,
            'expected_close_date': '2024-03-31',
            'next_step': 'Schedule final presentation',
            'created_at': '2024-01-10T11:00:00Z',
            'updated_at': '2024-01-22T13:30:00Z'
        }
    }
    
    # Add examples to schema components
    if 'components' not in schema:
        schema['components'] = {}
    if 'examples' not in schema['components']:
        schema['components']['examples'] = examples