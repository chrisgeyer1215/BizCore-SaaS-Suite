# backend/apps/finance/viewsets/reports.py

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from datetime import date, datetime
from ..services.reporting import FinancialReportingService
from ..serializers import (
    BalanceSheetSerializer, IncomeStatementSerializer, CashFlowSerializer,
    ARAgingSerializer, APAgingSerializer, TrialBalanceSerializer
)
from apps.core.permissions import TenantPermission

class FinancialReportsViewSet(viewsets.GenericViewSet):
    """ViewSet for Financial Reports"""
    
    permission_classes = [permissions.IsAuthenticated, TenantPermission]
    
    @action(detail=False, methods=['get'])
    def balance_sheet(self, request):
        """Generate Balance Sheet"""
        as_of_date = request.query_params.get('as_of_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_balance_sheet_pdf(as_of_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="balance_sheet_{as_of_date}.pdf"'
            return response
        
        balance_sheet_data = service.generate_balance_sheet(as_of_date)
        serializer = BalanceSheetSerializer(balance_sheet_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def income_statement(self, request):
        """Generate Income Statement"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_income_statement_pdf(start_date, end_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="income_statement_{start_date}_to_{end_date}.pdf"'
            return response
        
        income_statement_data = service.generate_income_statement(start_date, end_date)
        serializer = IncomeStatementSerializer(income_statement_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def cash_flow(self, request):
        """Generate Cash Flow Statement"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_cash_flow_pdf(start_date, end_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="cash_flow_{start_date}_to_{end_date}.pdf"'
            return response
        
        cash_flow_data = service.generate_cash_flow_statement(start_date, end_date)
        serializer = CashFlowSerializer(cash_flow_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """Generate Trial Balance"""
        as_of_date = request.query_params.get('as_of_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_trial_balance_pdf(as_of_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="trial_balance_{as_of_date}.pdf"'
            return response
        
        trial_balance_data = service.generate_trial_balance(as_of_date)
        serializer = TrialBalanceSerializer(trial_balance_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def ar_aging(self, request):
        """Generate Accounts Receivable Aging"""
        as_of_date = request.query_params.get('as_of_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_ar_aging_pdf(as_of_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ar_aging_{as_of_date}.pdf"'
            return response
        
        ar_aging_data = service.generate_ar_aging_report(as_of_date)
        serializer = ARAgingSerializer(ar_aging_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def ap_aging(self, request):
        """Generate Accounts Payable Aging"""
        as_of_date = request.query_params.get('as_of_date', date.today())
        format_type = request.query_params.get('format', 'json')
        
        service = FinancialReportingService(request.tenant)
        
        if format_type == 'pdf':
            pdf_content = service.generate_ap_aging_pdf(as_of_date)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ap_aging_{as_of_date}.pdf"'
            return response
        
        ap_aging_data = service.generate_ap_aging_report(as_of_date)
        serializer = APAgingSerializer(ap_aging_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def custom_report(self, request):
        """Generate custom financial report"""
        report_type = request.query_params.get('type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        accounts = request.query_params.getlist('accounts')
        
        service = FinancialReportingService(request.tenant)
        
        try:
            report_data = service.generate_custom_report(
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                account_ids=accounts
            )
            return Response(report_data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )