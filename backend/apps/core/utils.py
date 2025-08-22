import uuid
from datetime import datetime


def generate_code(prefix, tenant_id, starting_number=None):
    """
    Generate a unique code with prefix, tenant ID, and optional starting number.
    
    Args:
        prefix (str): The prefix for the code (e.g., 'INV', 'BILL', 'LEAD')
        tenant_id (int): The tenant ID
        starting_number (int, optional): Starting number for sequential codes
        
    Returns:
        str: Generated unique code
    """
    if starting_number is not None:
        # For sequential numbering, use timestamp + tenant_id + starting_number
        timestamp = datetime.now().strftime('%y%m%d')
        code = f"{prefix}-{tenant_id}-{timestamp}-{starting_number:04d}"
    else:
        # For simple codes, use timestamp + tenant_id
        timestamp = datetime.now().strftime('%y%m%d%H%M')
        code = f"{prefix}-{tenant_id}-{timestamp}"
    
    return code