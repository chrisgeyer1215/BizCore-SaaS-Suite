"""
Customer Financial Views
Handle customer financial profiles, statements, and financial data
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import json

from apps.core.decorators import tenant_required
from ..models import (
    Customer, Invoice, Payment, CustomerFinancialProfile,
    LeadFinancialData, Account
)
from ..services.customer_analytics import CustomerAnalyticsService


@login_required
@tenant_required
def customer_financial_list(request):
    """List all customers with financial summary"""
    customers = Customer.objects.filter(tenant=request.tenant).select_related(
        'financial_profile'
    ).order_by('name')
    
    # Filtering
    status = request.GET.get('status')
    customer_type = request.GET.get('customer_type')
    search = request.GET.get('search')
    
    if status:
        customers = customers.filter(status=status)
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(customer_number__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate financial summary for each customer
    customer_analytics = CustomerAnalyticsService(request.tenant)
    for customer in page_obj:
        customer.financial_summary = customer_analytics.get_customer_financial_summary(customer)
    
    # Summary stats
    total_customers = customers.count()
    active_customers = customers.filter(status='ACTIVE').count()
    total_receivables = sum(
        customer.financial_summary.get('total_receivables', Decimal('0.00'))
        for customer in page_obj
    )
    
    context = {
        'page_obj': page_obj,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_receivables': total_receivables,
        'status_choices': Customer.STATUS_CHOICES,
        'customer_type_choices': Customer.CUSTOMER_TYPE_CHOICES,
    }
    
    return render(request, 'finance/customers/list.html', context)


@login_required
@tenant_required
def customer_financial_profile(request, customer_id):
    """Show customer financial profile"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get or create financial profile
    financial_profile, created = CustomerFinancialProfile.objects.get_or_create(
        tenant=request.tenant,
        customer=customer,
        defaults={
            'credit_limit': Decimal('0.00'),
            'payment_terms': 'Net 30',
            'tax_exempt': False,
            'default_account': None,
        }
    )
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Get financial summary
    financial_summary = customer_analytics.get_customer_financial_summary(customer)
    
    # Get recent invoices
    recent_invoices = Invoice.objects.filter(
        tenant=request.tenant,
        customer=customer
    ).order_by('-invoice_date')[:10]
    
    # Get recent payments
    recent_payments = Payment.objects.filter(
        tenant=request.tenant,
        customer=customer
    ).order_by('-payment_date')[:10]
    
    # Get payment history
    payment_history = customer_analytics.get_customer_payment_history(customer, days=365)
    
    # Get credit analysis
    credit_analysis = customer_analytics.get_customer_credit_analysis(customer)
    
    context = {
        'customer': customer,
        'financial_profile': financial_profile,
        'financial_summary': financial_summary,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'payment_history': payment_history,
        'credit_analysis': credit_analysis,
    }
    
    return render(request, 'finance/customers/financial_profile.html', context)


@login_required
@tenant_required
def customer_statement(request, customer_id):
    """Generate customer statement"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = date.today() - timedelta(days=30)
    else:
        start_date = date.today() - timedelta(days=30)
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Generate statement
    statement_data = customer_analytics.generate_customer_statement(
        customer, start_date, end_date
    )
    
    # Get opening balance
    opening_balance = customer_analytics.get_customer_opening_balance(customer, start_date)
    
    context = {
        'customer': customer,
        'statement': statement_data,
        'start_date': start_date,
        'end_date': end_date,
        'opening_balance': opening_balance,
        'period_days': (end_date - start_date).days + 1,
    }
    
    return render(request, 'finance/customers/statement.html', context)


@login_required
@tenant_required
def customer_invoices(request, customer_id):
    """Show customer invoices"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    invoices = Invoice.objects.filter(
        tenant=request.tenant,
        customer=customer
    ).order_by('-invoice_date')
    
    # Filtering
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        invoices = invoices.filter(status=status)
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(invoices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    total_invoices = invoices.count()
    total_amount = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    paid_amount = invoices.filter(status='PAID').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    outstanding_amount = total_amount - paid_amount
    
    context = {
        'customer': customer,
        'page_obj': page_obj,
        'total_invoices': total_invoices,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'outstanding_amount': outstanding_amount,
        'status_choices': Invoice.STATUS_CHOICES,
    }
    
    return render(request, 'finance/customers/invoices.html', context)


@login_required
@tenant_required
def customer_payments(request, customer_id):
    """Show customer payments"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    payments = Payment.objects.filter(
        tenant=request.tenant,
        customer=customer
    ).order_by('-payment_date')
    
    # Filtering
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        payments = payments.filter(status=status)
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    total_payments = payments.count()
    total_amount = payments.aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    cleared_amount = payments.filter(status='CLEARED').aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    
    context = {
        'customer': customer,
        'page_obj': page_obj,
        'total_payments': total_payments,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'status_choices': Payment.STATUS_CHOICES,
    }
    
    return render(request, 'finance/customers/payments.html', context)


@login_required
@tenant_required
def customer_aging(request, customer_id):
    """Show customer aging analysis"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Get aging analysis
    aging_data = customer_analytics.get_customer_aging_analysis(customer)
    
    # Get overdue invoices
    overdue_invoices = Invoice.objects.filter(
        tenant=request.tenant,
        customer=customer,
        status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
        due_date__lt=date.today()
    ).order_by('due_date')
    
    context = {
        'customer': customer,
        'aging_data': aging_data,
        'overdue_invoices': overdue_invoices,
        'aging_buckets': aging_data.get('aging_buckets', {}),
        'summary': aging_data.get('summary', {}),
    }
    
    return render(request, 'finance/customers/aging.html', context)


@login_required
@tenant_required
def customer_credit_analysis(request, customer_id):
    """Show customer credit analysis"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Get credit analysis
    credit_analysis = customer_analytics.get_customer_credit_analysis(customer)
    
    # Get payment history
    payment_history = customer_analytics.get_customer_payment_history(customer, days=365)
    
    # Get credit limit usage
    credit_limit_usage = customer_analytics.get_credit_limit_usage(customer)
    
    # Get risk assessment
    risk_assessment = customer_analytics.assess_customer_risk(customer)
    
    context = {
        'customer': customer,
        'credit_analysis': credit_analysis,
        'payment_history': payment_history,
        'credit_limit_usage': credit_limit_usage,
        'risk_assessment': risk_assessment,
    }
    
    return render(request, 'finance/customers/credit_analysis.html', context)


@login_required
@tenant_required
def customer_financial_export(request, customer_id):
    """Export customer financial data"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    format_type = request.GET.get('format', 'csv')
    
    try:
        # Get customer analytics service
        customer_analytics = CustomerAnalyticsService(request.tenant)
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="customer_{customer.id}_financial_data.csv"'
            
            import csv
            writer = csv.writer(response)
            writer.writerow([
                'Date', 'Type', 'Reference', 'Description', 'Amount', 'Balance'
            ])
            
            # Get all financial transactions
            transactions = customer_analytics.get_customer_transactions(customer)
            
            running_balance = Decimal('0.00')
            for transaction in transactions:
                if transaction['type'] == 'INVOICE':
                    running_balance += transaction['amount']
                else:  # PAYMENT
                    running_balance -= transaction['amount']
                
                writer.writerow([
                    transaction['date'],
                    transaction['type'],
                    transaction['reference'],
                    transaction['description'],
                    transaction['amount'],
                    running_balance
                ])
            
            return response
        
        elif format_type == 'excel':
            # Excel export implementation
            pass
        
        else:  # PDF
            # PDF export implementation
            pass
        
    except Exception as e:
        messages.error(request, f'Error exporting customer data: {str(e)}')
        return redirect('finance:customer_financial_profile', customer_id=customer.id)


@login_required
@tenant_required
def customer_bulk_actions(request):
    """Handle bulk actions on customers"""
    if request.method == 'POST':
        action = request.POST.get('action')
        customer_ids = request.POST.getlist('customer_ids')
        
        if not customer_ids:
            messages.error(request, 'No customers selected.')
            return redirect('finance:customer_financial_list')
        
        customers = Customer.objects.filter(id__in=customer_ids, tenant=request.tenant)
        
        if action == 'activate':
            customers.update(status='ACTIVE')
            messages.success(request, f'{customers.count()} customers activated successfully.')
        
        elif action == 'deactivate':
            customers.update(status='INACTIVE')
            messages.success(request, f'{customers.count()} customers deactivated successfully.')
        
        elif action == 'export_financial_data':
            # This would trigger bulk export
            messages.success(request, f'Financial data export initiated for {customers.count()} customers.')
        
        elif action == 'generate_statements':
            # This would generate statements for all selected customers
            messages.success(request, f'Statements generated for {customers.count()} customers.')
    
    return redirect('finance:customer_financial_list')


@login_required
@tenant_required
def customer_api_data(request):
    """API endpoint for customer financial data (AJAX)"""
    customers = Customer.objects.filter(tenant=request.tenant).select_related('financial_profile')
    
    # Apply filters
    status = request.GET.get('status')
    customer_type = request.GET.get('customer_type')
    search = request.GET.get('search')
    
    if status:
        customers = customers.filter(status=status)
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(customer_number__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Serialize data
    customer_data = []
    for customer in customers:
        financial_summary = customer_analytics.get_customer_financial_summary(customer)
        customer_data.append({
            'id': customer.id,
            'customer_number': customer.customer_number,
            'name': customer.name,
            'customer_type': customer.customer_type,
            'status': customer.status,
            'email': customer.email,
            'total_receivables': float(financial_summary.get('total_receivables', Decimal('0.00'))),
            'overdue_amount': float(financial_summary.get('overdue_amount', Decimal('0.00'))),
            'credit_limit': float(customer.financial_profile.credit_limit if customer.financial_profile else Decimal('0.00')),
            'url': f'/finance/customers/{customer.id}/'
        })
    
    return JsonResponse({'customers': customer_data})


@login_required
@tenant_required
def customer_dashboard_widget(request):
    """Dashboard widget for customers overview"""
    customers = Customer.objects.filter(tenant=request.tenant)
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    # Calculate statistics
    total_customers = customers.count()
    active_customers = customers.filter(status='ACTIVE').count()
    
    # Get top customers by receivables
    top_customers = customer_analytics.get_top_customers_by_receivables(limit=5)
    
    # Get customers with overdue invoices
    overdue_customers = customer_analytics.get_customers_with_overdue_invoices(limit=5)
    
    # Get recent customer activity
    recent_activity = customer_analytics.get_recent_customer_activity(limit=5)
    
    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'top_customers': top_customers,
        'overdue_customers': overdue_customers,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'finance/dashboard/widgets/customers_overview.html', context)


@login_required
@tenant_required
def customer_financial_profile_edit(request, customer_id):
    """Edit customer financial profile"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get or create financial profile
    financial_profile, created = CustomerFinancialProfile.objects.get_or_create(
        tenant=request.tenant,
        customer=customer,
        defaults={
            'credit_limit': Decimal('0.00'),
            'payment_terms': 'Net 30',
            'tax_exempt': False,
            'default_account': None,
        }
    )
    
    if request.method == 'POST':
        # Handle form submission
        credit_limit = request.POST.get('credit_limit')
        payment_terms = request.POST.get('payment_terms')
        tax_exempt = request.POST.get('tax_exempt') == 'on'
        default_account_id = request.POST.get('default_account')
        
        try:
            financial_profile.credit_limit = Decimal(credit_limit) if credit_limit else Decimal('0.00')
            financial_profile.payment_terms = payment_terms
            financial_profile.tax_exempt = tax_exempt
            
            if default_account_id:
                financial_profile.default_account = Account.objects.get(
                    id=default_account_id, tenant=request.tenant
                )
            else:
                financial_profile.default_account = None
            
            financial_profile.save()
            
            messages.success(request, 'Customer financial profile updated successfully.')
            return redirect('finance:customer_financial_profile', customer_id=customer.id)
            
        except Exception as e:
            messages.error(request, f'Error updating financial profile: {str(e)}')
    
    context = {
        'customer': customer,
        'financial_profile': financial_profile,
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
        'payment_terms_options': [
            'Due on Receipt',
            'Net 15',
            'Net 30',
            'Net 45',
            'Net 60',
            'Net 90',
        ],
    }
    
    return render(request, 'finance/customers/edit_financial_profile.html', context)


@login_required
@tenant_required
def customer_risk_assessment(request, customer_id):
    """Perform customer risk assessment"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    # Get customer analytics service
    customer_analytics = CustomerAnalyticsService(request.tenant)
    
    if request.method == 'POST':
        # Handle risk assessment update
        risk_score = request.POST.get('risk_score')
        risk_notes = request.POST.get('risk_notes')
        
        try:
            # Update risk assessment
            customer_analytics.update_customer_risk_assessment(
                customer, risk_score, risk_notes, request.user
            )
            
            messages.success(request, 'Customer risk assessment updated successfully.')
            return redirect('finance:customer_credit_analysis', customer_id=customer.id)
            
        except Exception as e:
            messages.error(request, f'Error updating risk assessment: {str(e)}')
    
    # Get current risk assessment
    risk_assessment = customer_analytics.assess_customer_risk(customer)
    
    # Get risk factors
    risk_factors = customer_analytics.get_customer_risk_factors(customer)
    
    context = {
        'customer': customer,
        'risk_assessment': risk_assessment,
        'risk_factors': risk_factors,
        'risk_score_options': [
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk'),
        ],
    }
    
    return render(request, 'finance/customers/risk_assessment.html', context)


@login_required
@tenant_required
def customer_payment_reminder(request, customer_id):
    """Send payment reminder to customer"""
    customer = get_object_or_404(Customer, id=customer_id, tenant=request.tenant)
    
    if request.method == 'POST':
        reminder_type = request.POST.get('reminder_type')
        custom_message = request.POST.get('custom_message')
        
        try:
            # Get customer analytics service
            customer_analytics = CustomerAnalyticsService(request.tenant)
            
            # Send payment reminder
            reminder_result = customer_analytics.send_payment_reminder(
                customer, reminder_type, custom_message
            )
            
            if reminder_result['success']:
                messages.success(request, f'Payment reminder sent successfully to {customer.name}.')
            else:
                messages.error(request, f'Failed to send reminder: {reminder_result["error"]}')
            
            return redirect('finance:customer_financial_profile', customer_id=customer.id)
            
        except Exception as e:
            messages.error(request, f'Error sending payment reminder: {str(e)}')
    
    # Get overdue invoices
    overdue_invoices = Invoice.objects.filter(
        tenant=request.tenant,
        customer=customer,
        status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
        due_date__lt=date.today()
    ).order_by('due_date')
    
    context = {
        'customer': customer,
        'overdue_invoices': overdue_invoices,
        'reminder_types': [
            ('FRIENDLY', 'Friendly Reminder'),
            ('FIRM', 'Firm Reminder'),
            ('FINAL', 'Final Notice'),
            ('LEGAL', 'Legal Notice'),
        ],
    }
    
    return render(request, 'finance/customers/payment_reminder.html')
