# apps/inventory/api/v1/views/reports.py

import io
import csv
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Sum, Count, Avg, Max, Min, Case, When
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta, datetime
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.inventory.api.v1.views.base import BaseInventoryViewSet
from apps.inventory.api.v1.serializers.reports import (
    InventoryReportSerializer, ReportConfigSerializer,
    ReportScheduleSerializer, CustomReportSerializer
)
from apps.inventory.models.reports.reports import InventoryReport
from apps.inventory.services.reports.report_service import ReportService
from apps.inventory.services.reports.analytics_service import AnalyticsService
from apps.inventory.utils.exceptions import InventoryError
from apps.inventory.utils.permissions import InventoryPermissionMixin
from apps.inventory.utils.constants import REPORT_TYPES, REPORT_FORMATS, REPORT_STATUSES


class InventoryReportViewSet(BaseInventoryViewSet, InventoryPermissionMixin):
    """
    ViewSet for managing inventory reports and analytics.
    
    Supports:
    - Pre-defined report types (stock summary, valuation, movements, etc.)
    - Custom report generation
    - Scheduled reports
    - Multiple output formats (PDF, Excel, CSV, JSON)
    - Real-time analytics dashboards
    """
    serializer_class = InventoryReportSerializer
    queryset = InventoryReport.objects.none()
    
    def get_queryset(self):
        """Get tenant-specific reports with optimizations."""
        return InventoryReport.objects.select_related(
            'created_by'
        ).order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def available_reports(self, request):
        """Get list of available report types and their configurations."""
        try:
            report_service = ReportService(request.user.tenant)
            
            available_reports = report_service.get_available_reports()
            
            return Response({
                'success': True,
                'data': {
                    'reports': available_reports,
                    'total_types': len(available_reports)
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve available reports')
    
    @action(detail=False, methods=['post'])
    def generate_stock_summary(self, request):
        """Generate stock summary report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            # Get report parameters
            filters = {
                'warehouse_id': request.data.get('warehouse_id'),
                'category_id': request.data.get('category_id'),
                'brand_id': request.data.get('brand_id'),
                'include_zero_stock': request.data.get('include_zero_stock', False),
                'abc_classification': request.data.get('abc_classification'),
                'valuation_method': request.data.get('valuation_method', 'FIFO')
            }
            
            output_format = request.data.get('format', 'JSON')
            
            # Generate report
            report = report_service.generate_stock_summary_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id,
                    'generated_at': report.created_at
                })
            else:
                # Return file download response
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate stock summary report')
    
    @action(detail=False, methods=['post'])
    def generate_valuation_report(self, request):
        """Generate inventory valuation report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            filters = {
                'warehouse_id': request.data.get('warehouse_id'),
                'category_id': request.data.get('category_id'),
                'valuation_date': request.data.get('valuation_date', timezone.now().date()),
                'valuation_method': request.data.get('valuation_method', 'FIFO'),
                'include_adjustments': request.data.get('include_adjustments', True)
            }
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_valuation_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id,
                    'total_valuation': report.data.get('summary', {}).get('total_valuation', 0)
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate valuation report')
    
    @action(detail=False, methods=['post'])
    def generate_movement_report(self, request):
        """Generate stock movement report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            filters = {
                'start_date': request.data.get('start_date'),
                'end_date': request.data.get('end_date'),
                'warehouse_id': request.data.get('warehouse_id'),
                'product_id': request.data.get('product_id'),
                'movement_types': request.data.get('movement_types', []),
                'include_adjustments': request.data.get('include_adjustments', True)
            }
            
            # Validate date range
            if not filters['start_date'] or not filters['end_date']:
                return Response({
                    'success': False,
                    'errors': ['start_date and end_date are required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_movement_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate movement report')
    
    @action(detail=False, methods=['post'])
    def generate_abc_analysis(self, request):
        """Generate ABC analysis report."""
        try:
            analytics_service = AnalyticsService(request.user.tenant)
            
            filters = {
                'warehouse_id': request.data.get('warehouse_id'),
                'category_id': request.data.get('category_id'),
                'analysis_period_days': request.data.get('analysis_period_days', 365),
                'classification_criteria': request.data.get('classification_criteria', 'REVENUE')
            }
            
            abc_analysis = analytics_service.generate_abc_analysis(filters)
            
            return Response({
                'success': True,
                'data': abc_analysis,
                'generated_at': timezone.now()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to generate ABC analysis')
    
    @action(detail=False, methods=['post'])
    def generate_aging_report(self, request):
        """Generate inventory aging report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            filters = {
                'warehouse_id': request.data.get('warehouse_id'),
                'category_id': request.data.get('category_id'),
                'aging_periods': request.data.get('aging_periods', [30, 60, 90, 180]),
                'include_zero_stock': request.data.get('include_zero_stock', False)
            }
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_aging_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate aging report')
    
    @action(detail=False, methods=['post'])
    def generate_reorder_report(self, request):
        """Generate reorder recommendations report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            filters = {
                'warehouse_id': request.data.get('warehouse_id'),
                'category_id': request.data.get('category_id'),
                'supplier_id': request.data.get('supplier_id'),
                'include_safety_stock': request.data.get('include_safety_stock', True),
                'lead_time_buffer_days': request.data.get('lead_time_buffer_days', 7)
            }
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_reorder_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id,
                    'items_to_reorder': len(report.data.get('items', []))
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate reorder report')
    
    @action(detail=False, methods=['post'])
    def generate_supplier_performance(self, request):
        """Generate supplier performance report."""
        try:
            report_service = ReportService(request.user.tenant)
            
            filters = {
                'supplier_id': request.data.get('supplier_id'),
                'start_date': request.data.get('start_date'),
                'end_date': request.data.get('end_date'),
                'include_quality_metrics': request.data.get('include_quality_metrics', True),
                'include_delivery_metrics': request.data.get('include_delivery_metrics', True),
                'include_pricing_trends': request.data.get('include_pricing_trends', True)
            }
            
            # Default to last 90 days if no dates provided
            if not filters['start_date']:
                filters['start_date'] = timezone.now().date() - timedelta(days=90)
            if not filters['end_date']:
                filters['end_date'] = timezone.now().date()
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_supplier_performance_report(
                filters=filters,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate supplier performance report')
    
    @action(detail=False, methods=['post'])
    def generate_custom_report(self, request):
        """Generate custom report based on user-defined criteria."""
        try:
            report_service = ReportService(request.user.tenant)
            
            report_config = {
                'title': request.data.get('title', 'Custom Inventory Report'),
                'description': request.data.get('description', ''),
                'data_sources': request.data.get('data_sources', []),
                'filters': request.data.get('filters', {}),
                'grouping': request.data.get('grouping', []),
                'sorting': request.data.get('sorting', []),
                'calculations': request.data.get('calculations', []),
                'chart_config': request.data.get('chart_config', {})
            }
            
            output_format = request.data.get('format', 'JSON')
            
            report = report_service.generate_custom_report(
                config=report_config,
                format=output_format,
                user=request.user
            )
            
            if output_format == 'JSON':
                return Response({
                    'success': True,
                    'data': report.data,
                    'report_id': report.id,
                    'config': report_config
                })
            else:
                return self._create_file_response(report, output_format)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to generate custom report')
    
    @action(detail=False, methods=['get'])
    def dashboard_kpis(self, request):
        """Get key performance indicators for inventory dashboard."""
        try:
            analytics_service = AnalyticsService(request.user.tenant)
            
            # Get time period from query params
            period_days = int(request.query_params.get('period_days', 30))
            warehouse_id = request.query_params.get('warehouse_id')
            
            kpis = analytics_service.get_dashboard_kpis(
                period_days=period_days,
                warehouse_id=warehouse_id
            )
            
            return Response({
                'success': True,
                'data': kpis,
                'period_days': period_days,
                'generated_at': timezone.now()
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve dashboard KPIs')
    
    @action(detail=False, methods=['get'])
    def inventory_trends(self, request):
        """Get inventory trends and analytics."""
        try:
            analytics_service = AnalyticsService(request.user.tenant)
            
            # Get parameters
            period_days = int(request.query_params.get('period_days', 90))
            trend_type = request.query_params.get('trend_type', 'STOCK_LEVELS')
            warehouse_id = request.query_params.get('warehouse_id')
            category_id = request.query_params.get('category_id')
            
            trends = analytics_service.get_inventory_trends(
                period_days=period_days,
                trend_type=trend_type,
                warehouse_id=warehouse_id,
                category_id=category_id
            )
            
            return Response({
                'success': True,
                'data': trends,
                'trend_type': trend_type,
                'period_days': period_days
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to retrieve inventory trends')
    
    @action(detail=False, methods=['post'])
    def schedule_report(self, request):
        """Schedule a report for automatic generation."""
        try:
            report_service = ReportService(request.user.tenant)
            
            schedule_config = {
                'report_type': request.data.get('report_type'),
                'report_filters': request.data.get('report_filters', {}),
                'schedule_frequency': request.data.get('schedule_frequency', 'WEEKLY'),
                'output_format': request.data.get('output_format', 'PDF'),
                'recipients': request.data.get('recipients', []),
                'next_run_date': request.data.get('next_run_date'),
                'is_active': request.data.get('is_active', True)
            }
            
            # Validate required fields
            if not schedule_config['report_type']:
                return Response({
                    'success': False,
                    'errors': ['report_type is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            scheduled_report = report_service.schedule_report(
                config=schedule_config,
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Report scheduled successfully',
                'data': {
                    'schedule_id': scheduled_report.id,
                    'next_run_date': scheduled_report.next_run_date,
                    'frequency': scheduled_report.frequency
                }
            })
        except Exception as e:
            return self.handle_error(e, 'Failed to schedule report')
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a generated report file."""
        try:
            report = self.get_object()
            
            if not report.file_path:
                return Response({
                    'success': False,
                    'errors': ['Report file not available']
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create file response based on format
            return self._create_file_response(report, report.format)
            
        except Exception as e:
            return self.handle_error(e, 'Failed to download report')
    
    @action(detail=False, methods=['get'])
    def export_data(self, request):
        """Export raw inventory data in various formats."""
        try:
            # Get export parameters
            data_type = request.query_params.get('data_type', 'PRODUCTS')  # PRODUCTS, STOCK_ITEMS, MOVEMENTS
            format_type = request.query_params.get('format', 'CSV')
            filters = {}
            
            # Parse filters from query params
            for key, value in request.query_params.items():
                if key.startswith('filter_'):
                    filter_name = key.replace('filter_', '')
                    filters[filter_name] = value
            
            report_service = ReportService(request.user.tenant)
            
            # Generate export based on data type
            if data_type == 'PRODUCTS':
                export_data = report_service.export_products_data(filters, format_type)
            elif data_type == 'STOCK_ITEMS':
                export_data = report_service.export_stock_items_data(filters, format_type)
            elif data_type == 'MOVEMENTS':
                export_data = report_service.export_movements_data(filters, format_type)
            else:
                return Response({
                    'success': False,
                    'errors': ['Invalid data_type. Must be PRODUCTS, STOCK_ITEMS, or MOVEMENTS']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create appropriate response
            if format_type == 'JSON':
                return Response({
                    'success': True,
                    'data': export_data,
                    'exported_at': timezone.now()
                })
            else:
                # Create file response
                return self._create_export_response(export_data, format_type, data_type)
                
        except Exception as e:
            return self.handle_error(e, 'Failed to export data')
    
    def _create_file_response(self, report, format_type):
        """Create HTTP response for file download."""
        try:
            if format_type.upper() == 'CSV':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{report.title}.csv"'
                
                # Write CSV data
                writer = csv.writer(response)
                if hasattr(report.data, 'items')
                    writer.writerow(report.data['headers'])
                    writer.writerows(report.data.get('rows', []))
                
                return response
                
            elif format_type.upper() == 'EXCEL':
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{report.title}.xlsx"'
                
                # For Excel format, you would use openpyxl or similar library
                # This is a placeholder for the actual implementation
                response.write(b"Excel file placeholder")
                return response
                
            elif format_type.upper() == 'PDF':
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{report.title}.pdf"'
                
                # For PDF format, you would use reportlab or similar library
                # This is a placeholder for the actual implementation
                response.write(b"PDF file placeholder")
                return response
                
            else:
                raise InventoryError(f"Unsupported format: {format_type}")
                
        except Exception as e:
            raise InventoryError(f"Failed to create file response: {str(e)}")
    
    def _create_export_response(self, data, format_type, data_type):
        """Create HTTP response for data export."""
        try:
            filename = f"{data_type.lower()}_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format_type.upper() == 'CSV':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
                
                ifdata[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                
                return response
                
            elif format_type.upper() == 'EXCEL':
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
                
                # Excel implementation placeholder
                response.write(b"Excel export placeholder")
                return response
                
            else:
                raise InventoryError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            raise InventoryError(f"Failed to create export response: {str(e)}")