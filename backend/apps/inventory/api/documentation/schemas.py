# apps/inventory/api/documentation/schemas.py

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
from typing import Dict, Any

# Common parameters
TENANT_PARAMETER = OpenApiParameter(
    name='tenant',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description='Tenant ID for multi-tenant filtering',
    required=False
)

PAGINATION_PARAMETERS = [
    OpenApiParameter(
        name='page',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description='Page number for pagination',
        required=False
    ),
    OpenApiParameter(
        name='page_size',
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description='Number of results per page (max 100)',
        required=False
    )
]

ORDERING_PARAMETER = OpenApiParameter(
    name='ordering',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description='Field to order results by. Prefix with - for descending order.',
    required=False
)

SEARCH_PARAMETER = OpenApiParameter(
    name='search',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description='Search term for filtering results',
    required=False
)

# Schema decorators for different endpoint types
def inventory_list_schema(summary: str, description: str, serializer_class, 
                         additional_parameters: list = None):
    """Standard schema for list endpoints."""
    parameters = [TENANT_PARAMETER, ORDERING_PARAMETER, SEARCH_PARAMETER] + PAGINATION_PARAMETERS
    if additional_parameters:
        parameters.extend(additional_parameters)
    
    return extend_schema(
        summary=summary,
        description=description,
        parameters=parameters,
        responses={
            200: serializer_class,
            400: 'Bad Request',
            401: 'Unauthorized', 
            403: 'Forbidden',
            500: 'Internal Server Error'
        },
        tags=['Inventory Management']
    )

def inventory_create_schema(summary: str, description: str, serializer_class):
    """Standard schema for create endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        request=serializer_class,
        responses={
            201: serializer_class,
            400: 'Bad Request - Validation errors',
            401: 'Unauthorized',
            403: 'Forbidden',
            409: 'Conflict - Resource already exists',
            500: 'Internal Server Error'
        },
        tags=['Inventory Management']
    )

def inventory_detail_schema(summary: str, description: str, serializer_class):
    """Standard schema for detail endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        responses={
            200: serializer_class,
            401: 'Unauthorized',
            403: 'Forbidden', 
            404: 'Not Found',
            500: 'Internal Server Error'
        },
        tags=['Inventory Management']
    )

def inventory_update_schema(summary: str, description: str, serializer_class):
    """Standard schema for update endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        request=serializer_class,
        responses={
            200: serializer_class,
            400: 'Bad Request - Validation errors',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            409: 'Conflict - Update conflict',
            500: 'Internal Server Error'
        },
        tags=['Inventory Management']
    )

def inventory_delete_schema(summary: str, description: str):
    """Standard schema for delete endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        responses={
            204: 'Successfully deleted',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            409: 'Conflict - Cannot delete due to references',
            500: 'Internal Server Error'
        },
        tags=['Inventory Management']
    )

# ML-specific schemas
def ml_prediction_schema(summary: str, description: str, request_serializer, response_serializer):
    """Schema for ML prediction endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        request=request_serializer,
        responses={
            200: response_serializer,
            400: 'Bad Request - Invalid prediction parameters',
            401: 'Unauthorized',
            403: 'Forbidden',
            422: 'Unprocessable Entity - Insufficient data for prediction',
            429: 'Too Many Requests - Rate limit exceeded',
            500: 'Internal Server Error',
            503: 'Service Unavailable - ML service unavailable'
        },
        tags=['Machine Learning & Analytics']
    )

# Workflow-specific schemas
def workflow_action_schema(summary: str, description: str, request_serializer, response_serializer):
    """Schema for workflow action endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        request=request_serializer,
        responses={
            200: response_serializer,
            400: 'Bad Request - Invalid workflow action',
            401: 'Unauthorized',
            403: 'Forbidden - Insufficient permissions for workflow action',
            404: 'Not Found',
            409: 'Conflict - Workflow state conflict',
            500: 'Internal Server Error'
        },
        tags=['Workflow Management']
    )