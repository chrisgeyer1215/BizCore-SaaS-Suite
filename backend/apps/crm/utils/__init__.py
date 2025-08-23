# crm/utils/__init__.py
"""
CRM Utils Package

This package provides utility functions, validators, formatters, and helper classes
for the CRM module. It includes specialized utilities for:

- Data validation and formatting
- Email processing and templates
- Import/export operations
- Lead scoring and analytics
- Pipeline management
- Multi-tenant operations
- Custom field handling

Usage:
    from crm.utils.helpers import generate_reference_number
    from crm.utils.validators import validate_email_format
    from crm.utils.scoring_utils import calculate_lead_score
"""

# Import commonly used utilities for easy access
from .helpers import (
    generate_reference_number,
    format_phone_number,
    parse_name_components,
    calculate_time_difference,
    get_tenant_setting,
    sanitize_input,
    generate_secure_token
)

from .validators import (
    validate_email_format,
    validate_phone_number,
    validate_currency_amount,
    validate_percentage,
    validate_date_range,
    validate_business_hours
)

from .formatters import (
    format_currency,
    format_percentage,
    format_date_display,
    format_phone_display,
    format_name_display,
    truncate_text
)

from .email_utils import (
    send_crm_email,
    render_email_template,
    validate_email_template,
    track_email_open,
    parse_email_content
)

from .scoring_utils import (
    calculate_lead_score,
    get_scoring_factors,
    update_lead_scores,
    analyze_conversion_probability
)

from .pipeline_utils import (
    get_next_stage,
    calculate_stage_duration,
    check_stage_requirements,
    auto_advance_opportunities
)

from .tenant_utils import (
    get_tenant_from_request,
    check_tenant_limits,
    get_tenant_settings,
    tenant_context
)

__all__ = [
    # Helpers
    'generate_reference_number',
    'format_phone_number',
    'parse_name_components',
    'calculate_time_difference',
    'get_tenant_setting',
    'sanitize_input',
    'generate_secure_token',
    
    # Validators
    'validate_email_format',
    'validate_phone_number',
    'validate_currency_amount',
    'validate_percentage',
    'validate_date_range',
    'validate_business_hours',
    
    # Formatters
    'format_currency',
    'format_percentage',
    'format_date_display',
    'format_phone_display',
    'format_name_display',
    'truncate_text',
    
    # Email Utils
    'send_crm_email',
    'render_email_template',
    'validate_email_template',
    'track_email_open',
    'parse_email_content',
    
    # Scoring Utils
    'calculate_lead_score',
    'get_scoring_factors',
    'update_lead_scores',
    'analyze_conversion_probability',
    
    # Pipeline Utils
    'get_next_stage',
    'calculate_stage_duration',
    'check_stage_requirements',
    'auto_advance_opportunities',
    
    # Tenant Utils
    'get_tenant_from_request',
    'check_tenant_limits',
    'get_tenant_settings',
    'tenant_context',
]