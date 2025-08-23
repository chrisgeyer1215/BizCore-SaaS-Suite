# backend/apps/crm/viewsets/account.py
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
    OpenApiTypes
)
from drf_spectacular.openapi import AutoSchema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Account
from ..serializers import AccountSerializer, AccountCreateSerializer
from .base import BaseViewSet

@extend_schema_view(
    list=extend_schema(
        summary="List Accounts",
        description="""
        Retrieve a list of customer accounts for the authenticated tenant.
        
        **Features:**
        - Pagination support (page size: 20)
        - Advanced filtering by industry, status, revenue range
        - Search across name, email, phone fields  
        - Sorting by name, created_at, annual_revenue
        - Includes contact count and recent activity summary
        
        **Permissions:** Requires 'view_account' permission
        """,
        parameters=[
            OpenApiParameter(
                name='search',
                description='Search accounts by name, email, or phone',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                examples=[
                    OpenApiExample('Search by name', value='acme'),
                    OpenApiExample('Search by email', value='@gmail.com'),
                ]
            ),
            OpenApiParameter(
                name='industry',
                description='Filter by industry',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['technology', 'healthcare', 'finance', 'manufacturing', 'retail']
            ),
            OpenApiParameter(
                name='status',
                description='Filter by account status',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['active', 'inactive', 'prospect', 'customer']
            ),
            OpenApiParameter(
                name='min_revenue',
                description='Minimum annual revenue',
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='max_revenue',
                description='Maximum annual revenue',
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='ordering',
                description='Sort results by field',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['name', '-name', 'created_at', '-created_at', 'annual_revenue', '-annual_revenue']
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AccountSerializer(many=True),
                description="List of accounts",
                examples=[
                    OpenApiExample(
                        'Successful Response',
                        value={
                            'count': 150,
                            'next': 'https://api.saas-aice.com/api/v1/crm/accounts/?page=2',
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Acme Corporation',
                                    'email': 'contact@acme.com',
                                    'phone': '+1-555-0123',
                                    'industry': 'Technology',
                                    'annual_revenue': 5000000,
                                    'employees': 150,
                                    'status': 'active',
                                    'contact_count': 12,
                                    'opportunity_count': 3,
                                    'last_activity': '2024-01-20T14:45:00Z',
                                    'created_at': '2024-01-15T10:30:00Z',
                                    'updated_at': '2024-01-20T14:45:00Z'
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        tags=['Accounts']
    ),
    create=extend_schema(
        summary="Create Account",
        description="""
        Create a new customer account in the authenticated tenant.
        
        **Business Rules:**
        - Account name must be unique within tenant
        - Email validation with domain verification
        - Automatic lead scoring calculation
        - Territory assignment based on location
        - Webhook notifications for integrations
        
        **Permissions:** Requires 'add_account' permission
        """,
        request=AccountCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=AccountSerializer,
                description="Account created successfully",
                examples=[
                    OpenApiExample(
                        'Created Account',
                        value={
                            'id': 1,
                            'name': 'New Customer Corp',
                            'email': 'info@newcustomer.com',
                            'phone': '+1-555-0199',
                            'industry': 'Technology',
                            'annual_revenue': 2500000,
                            'employees': 50,
                            'status': 'prospect',
                            'territory': 'North America',
                            'assigned_to': 'sales@company.com',
                            'created_at': '2024-01-22T15:30:00Z',
                            'updated_at': '2024-01-22T15:30:00Z'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation errors",
                examples=[
                    OpenApiExample(
                        'Validation Error',
                        value={
                            'name': ['This field is required.'],
                            'email': ['Enter a valid email address.'],
                            'annual_revenue': ['Ensure this value is greater than or equal to 0.']
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        tags=['Accounts']
    ),
    retrieve=extend_schema(
        summary="Get Account Details",
        description="""
        Retrieve detailed information about a specific account.
        
        **Includes:**
        - Complete account profile
        - Contact list with roles
        - Open opportunities summary
        - Recent activity timeline
        - Performance metrics
        - Related documents count
        
        **Permissions:** Requires 'view_account' permission
        """,
        responses={
            200: OpenApiResponse(
                response=AccountSerializer,
                description="Account details",
            ),
            404: OpenApiResponse(description="Account not found"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        tags=['Accounts']
    ),
    update=extend_schema(
        summary="Update Account",
        description="""
        Update an existing account's information.
        
        **Business Rules:**
        - Partial updates supported (PATCH)
        - Full updates require all fields (PUT)
        - Status changes trigger workflow automation
        - Revenue changes recalculate territory assignments
        - Audit trail maintained for all changes
        
        **Permissions:** Requires 'change_account' permission
        """,
        tags=['Accounts']
    ),
    destroy=extend_schema(
        summary="Delete Account",
        description="""
        Delete an account (soft delete by default).
        
        **Cascade Rules:**
        - Associated contacts are archived
        - Open opportunities are marked as lost
        - Activities remain for historical purposes
        - Documents are moved to archived state
        
        **Permissions:** Requires 'delete_account' permission
        """,
        responses={
            204: OpenApiResponse(description="Account deleted successfully"),
            404: OpenApiResponse(description="Account not found"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        tags=['Accounts']
    )
)
class AccountViewSet(BaseViewSet):
    """
    Account management endpoints for customer relationship management.
    
    Accounts represent companies or organizations that are customers or prospects.
    Each account can have multiple contacts, opportunities, and activities associated with it.
    """
    
    serializer_class = AccountSerializer
    filterset_fields = ['industry', 'status', 'employees', 'annual_revenue']
    search_fields = ['name', 'email', 'phone', 'website']
    ordering_fields = ['name', 'created_at', 'annual_revenue', 'employees']
    ordering = ['-created_at']

    def get_queryset(self):
        return Account.objects.select_related('territory', 'assigned_to').prefetch_related(
            'contacts', 'opportunities', 'activities'
        ).filter(tenant=self.request.tenant)

    @extend_schema(
        summary="Get Account Analytics",
        description="""
        Retrieve comprehensive analytics for a specific account.
        
        **Metrics Include:**
        - Revenue pipeline and conversion rates
        - Activity timeline and engagement scores
        - Opportunity win/loss analysis
        - Contact interaction patterns
        - Performance vs. industry benchmarks
        
        **Time Ranges:** 30d, 90d, 1y, all-time
        """,
        parameters=[
            OpenApiParameter(
                name='time_range',
                description='Time range for analytics',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['30d', '90d', '1y', 'all'],
                default='90d'
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Account analytics data",
                examples=[
                    OpenApiExample(
                        'Analytics Response',
                        value={
                            'account_id': 1,
                            'time_range': '90d',
                            'revenue_metrics': {
                                'total_opportunities': 5,
                                'won_opportunities': 2,
                                'lost_opportunities': 1,
                                'pending_opportunities': 2,
                                'win_rate': 40.0,
                                'average_deal_size': 125000,
                                'total_revenue': 250000
                            },
                            'activity_metrics': {
                                'total_activities': 45,
                                'calls': 15,
                                'emails': 25,
                                'meetings': 5,
                                'engagement_score': 85
                            },
                            'contact_metrics': {
                                'total_contacts': 8,
                                'active_contacts': 6,
                                'decision_makers': 3
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(description="Account not found"),
            401: OpenApiResponse(description="Authentication required"),
        },
        tags=['Accounts', 'Analytics']
    )
    @action(detail=True, methods=['get'], url_path='analytics')
    def analytics(self, request, pk=None):
        """Get detailed analytics for an account."""
        account = self.get_object()
        time_range = request.query_params.get('time_range', '90d')
        
        analytics_data = self.get_account_analytics(account, time_range)
        return Response(analytics_data)

    @extend_schema(
        summary="Bulk Import Accounts",
        description="""
        Import multiple accounts from CSV or Excel file.
        
        **Supported Formats:** CSV, XLSX
        **Max File Size:** 10MB
        **Max Records:** 1000 per import
        
        **Required Fields:** name, email
        **Optional Fields:** phone, industry, annual_revenue, employees, status
        
        **Features:**
        - Duplicate detection and handling
        - Validation with detailed error reporting  
        - Background processing for large files
        - Import progress tracking
        - Rollback support on validation failures
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'CSV or Excel file containing account data'
                    },
                    'skip_duplicates': {
                        'type': 'boolean',
                        'description': 'Skip duplicate records instead of failing',
                        'default': True
                    },
                    'update_existing': {
                        'type': 'boolean', 
                        'description': 'Update existing records with new data',
                        'default': False
                    }
                }
            }
        },
        responses={
            202: OpenApiResponse(
                description="Import started successfully",
                examples=[
                    OpenApiExample(
                        'Import Started',
                        value={
                            'import_id': 'imp_abc123',
                            'status': 'processing',
                            'total_records': 150,
                            'processed_records': 0,
                            'message': 'Import started successfully. Check status using import_id.'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="File validation errors",
                examples=[
                    OpenApiExample(
                        'File Error',
                        value={
                            'error': 'invalid_file_format',
                            'message': 'Only CSV and Excel files are supported.',
                            'supported_formats': ['csv', 'xlsx']
                        }
                    )
                ]
            )
        },
        tags=['Accounts', 'Bulk Operations']
    )
    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """Bulk import accounts from file."""
        # Implementation would go here
        pass

    @extend_schema(
        summary="Bulk Export Accounts", 
        description="""
        Export accounts to CSV or Excel format.
        
        **Export Options:**
        - All accounts or filtered subset
        - Customizable field selection
        - Multiple output formats (CSV, Excel, PDF)
        - Scheduled exports with email delivery
        
        **Features:**
        - Large dataset support (up to 100K records)
        - Background processing for big exports
        - Compressed download for large files
        - Export history and re-download capability
        """,
        parameters=[
            OpenApiParameter(
                name='format',
                description='Export format',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['csv', 'xlsx', 'pdf'],
                default='csv'
            ),
            OpenApiParameter(
                name='fields',
                description='Comma-separated list of fields to include',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                example='name,email,phone,industry,annual_revenue'
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Export file",
                headers={
                    'Content-Disposition': {
                        'description': 'File attachment header',
                        'schema': {'type': 'string', 'example': 'attachment; filename="accounts_export.csv"'}
                    },
                    'Content-Type': {
                        'description': 'File content type',
                        'schema': {'type': 'string', 'example': 'text/csv'}
                    }
                }
            ),
            202: OpenApiResponse(
                description="Export started (for large datasets)",
                examples=[
                    OpenApiExample(
                        'Export Started',
                        value={
                            'export_id': 'exp_xyz789',
                            'status': 'processing', 
                            'estimated_completion': '2024-01-22T16:00:00Z',
                            'download_url': None,
                            'message': 'Export started. You will receive an email when ready.'
                        }
                    )
                ]
            )
        },
        tags=['Accounts', 'Bulk Operations']
    )
    @action(detail=False, methods=['get'], url_path='bulk-export')
    def bulk_export(self, request):
        """Bulk export accounts to file."""
        # Implementation would go here
        pass

    def get_account_analytics(self, account, time_range):
        """Calculate analytics for account."""
        # Implementation would go here
        pass