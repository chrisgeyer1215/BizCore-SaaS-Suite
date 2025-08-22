"""
Payment Management Views
Handle customer payments, vendor payments, and payment applications
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
import json

from apps.core.decorators import tenant_required
from apps.core.utils import generate_code
from ..models import Payment, PaymentApplication, Invoice, Bill, Customer, Vendor, Account
from ..forms.payments import PaymentForm, PaymentApplicationFormSet
from ..services.payment import PaymentService


@login_required
@tenant_required
def payment_list(request):
    """List all payments with filtering and pagination"""
    payments = Payment.objects.filter(tenant=request.tenant).select_related(
        'customer', 'vendor', 'payment_method', 'bank_account'
    ).order_by('-payment_date')
    
    # Filtering
    payment_type = request.GET.get('payment_type')
    status = request.GET.get('status')
    customer_id = request.GET.get('customer')
    vendor_id = request.GET.get('vendor')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    if status:
        payments = payments.filter(status=status)
    if customer_id:
        payments = payments.filter(customer_id=customer_id)
    if vendor_id:
        payments = payments.filter(vendor_id=vendor_id)
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
    pending_amount = payments.filter(status='PENDING').aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    
    context = {
        'page_obj': page_obj,
        'total_payments': total_payments,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'pending_amount': pending_amount,
        'customers': Customer.objects.filter(tenant=request.tenant, is_active=True),
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'payment_type_choices': Payment.PAYMENT_TYPE_CHOICES,
        'status_choices': Payment.STATUS_CHOICES,
    }
    
    return render(request, 'finance/payments/list.html', context)


@login_required
@tenant_required
def payment_detail(request, payment_id):
    """Show payment details"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    # Get payment applications
    applications = payment.applications.all().select_related('invoice', 'bill')
    
    # Get journal entries
    from ..models import JournalEntry
    journal_entries = JournalEntry.objects.filter(
        tenant=request.tenant,
        reference_type='PAYMENT',
        reference_id=payment.id
    ).order_by('-entry_date')
    
    context = {
        'payment': payment,
        'applications': applications,
        'journal_entries': journal_entries,
    }
    
    return render(request, 'finance/payments/detail.html', context)


@login_required
@tenant_required
def payment_create(request):
    """Create new payment"""
    if request.method == 'POST':
        form = PaymentForm(request.POST, tenant=request.tenant)
        formset = PaymentApplicationFormSet(request.POST, instance=Payment(tenant=request.tenant))
        
        if form.is_valid() and formset.is_valid():
            payment = form.save(commit=False)
            payment.tenant = request.tenant
            payment.payment_number = generate_code('PAY', request.tenant)
            payment.save()
            
            formset.instance = payment
            formset.save()
            
            # Create journal entry
            payment_service = PaymentService(request.tenant)
            payment_service.create_payment_journal_entry(payment)
            
            messages.success(request, f'Payment {payment.payment_number} created successfully.')
            return redirect('finance:payment_detail', payment_id=payment.id)
    else:
        form = PaymentForm(tenant=request.tenant)
        formset = PaymentApplicationFormSet(instance=Payment(tenant=request.tenant))
    
    context = {
        'form': form,
        'formset': formset,
        'customers': Customer.objects.filter(tenant=request.tenant, is_active=True),
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/payments/form.html', context)


@login_required
@tenant_required
def payment_edit(request, payment_id):
    """Edit existing payment"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if payment.status in ['CLEARED', 'CANCELLED']:
        messages.error(request, 'Cannot edit cleared or cancelled payments.')
        return redirect('finance:payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment, tenant=request.tenant)
        formset = PaymentApplicationFormSet(request.POST, instance=payment)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Update journal entry if needed
            if payment.status == 'POSTED':
                payment_service = PaymentService(request.tenant)
                payment_service.update_payment_journal_entry(payment)
            
            messages.success(request, f'Payment {payment.payment_number} updated successfully.')
            return redirect('finance:payment_detail', payment_id=payment.id)
    else:
        form = PaymentForm(instance=payment, tenant=request.tenant)
        formset = PaymentApplicationFormSet(instance=payment)
    
    context = {
        'form': form,
        'formset': formset,
        'payment': payment,
        'customers': Customer.objects.filter(tenant=request.tenant, is_active=True),
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/payments/form.html', context)


@login_required
@tenant_required
def payment_delete(request, payment_id):
    """Delete payment (soft delete)"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if payment.status in ['CLEARED', 'POSTED']:
        messages.error(request, 'Cannot delete cleared or posted payments.')
        return redirect('finance:payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        payment.is_deleted = True
        payment.deleted_at = timezone.now()
        payment.save()
        
        messages.success(request, f'Payment {payment.payment_number} deleted successfully.')
        return redirect('finance:payment_list')
    
    context = {'payment': payment}
    return render(request, 'finance/payments/delete_confirm.html', context)


@login_required
@tenant_required
def payment_post(request, payment_id):
    """Post payment to general ledger"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if payment.status != 'DRAFT':
        messages.error(request, 'Only draft payments can be posted.')
        return redirect('finance:payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        try:
            payment_service = PaymentService(request.tenant)
            payment_service.post_payment(payment, request.user)
            
            messages.success(request, f'Payment {payment.payment_number} posted successfully.')
            return redirect('finance:payment_detail', payment_id=payment.id)
        except Exception as e:
            messages.error(request, f'Error posting payment: {str(e)}')
    
    context = {'payment': payment}
    return render(request, 'finance/payments/post_confirm.html', context)


@login_required
@tenant_required
def payment_clear(request, payment_id):
    """Mark payment as cleared"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if payment.status != 'POSTED':
        messages.error(request, 'Only posted payments can be cleared.')
        return redirect('finance:payment_detail', payment_id=payment.id)
    
    if request.method == 'POST':
        payment.status = 'CLEARED'
        payment.cleared_date = timezone.now()
        payment.save()
        
        # Update related invoices/bills
        payment_service = PaymentService(request.tenant)
        payment_service.apply_payment_to_documents(payment)
        
        messages.success(request, f'Payment {payment.payment_number} cleared successfully.')
        return redirect('finance:payment_detail', payment_id=payment.id)
    
    context = {'payment': payment}
    return render(request, 'finance/payments/clear_confirm.html', context)


@login_required
@tenant_required
def payment_apply(request, payment_id):
    """Apply payment to invoices/bills"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if request.method == 'POST':
        formset = PaymentApplicationFormSet(request.POST, instance=payment)
        
        if formset.is_valid():
            formset.save()
            
            # Recalculate payment amounts
            payment_service = PaymentService(request.tenant)
            payment_service.recalculate_payment_amounts(payment)
            
            messages.success(request, f'Payment applications updated successfully.')
            return redirect('finance:payment_detail', payment_id=payment.id)
    else:
        formset = PaymentApplicationFormSet(instance=payment)
    
    # Get available invoices/bills for application
    if payment.payment_type == 'RECEIVED':
        available_documents = Invoice.objects.filter(
            tenant=request.tenant,
            customer=payment.customer,
            status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
            amount_due__gt=0
        ).exclude(
            id__in=payment.applications.values_list('invoice_id', flat=True)
        )
    else:
        available_documents = Bill.objects.filter(
            tenant=request.tenant,
            vendor=payment.vendor,
            status__in=['OPEN', 'APPROVED', 'PARTIAL'],
            amount_due__gt=0
        ).exclude(
            id__in=payment.applications.values_list('bill_id', flat=True)
        )
    
    context = {
        'payment': payment,
        'formset': formset,
        'available_documents': available_documents,
    }
    
    return render(request, 'finance/payments/apply.html', context)


@login_required
@tenant_required
def payment_refund(request, payment_id):
    """Create refund for payment"""
    payment = get_object_or_404(Payment, id=payment_id, tenant=request.tenant)
    
    if request.method == 'POST':
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        refund_reason = request.POST.get('refund_reason', '')
        
        if refund_amount <= 0:
            messages.error(request, 'Refund amount must be greater than zero.')
        elif refund_amount > payment.base_currency_amount:
            messages.error(request, 'Refund amount cannot exceed payment amount.')
        else:
            try:
                payment_service = PaymentService(request.tenant)
                refund_payment = payment_service.create_refund(
                    payment, refund_amount, refund_reason, request.user
                )
                
                messages.success(request, f'Refund {refund_payment.payment_number} created successfully.')
                return redirect('finance:payment_detail', payment_id=refund_payment.id)
            except Exception as e:
                messages.error(request, f'Error creating refund: {str(e)}')
    
    context = {'payment': payment}
    return render(request, 'finance/payments/refund.html', context)


@login_required
@tenant_required
def payment_export(request):
    """Export payments to various formats"""
    payments = Payment.objects.filter(tenant=request.tenant).select_related(
        'customer', 'vendor', 'payment_method'
    ).order_by('-payment_date')
    
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        
        import csv
        writer = csv.writer(response)
        writer.writerow([
            'Payment Number', 'Type', 'Customer/Vendor', 'Amount', 'Payment Date',
            'Status', 'Payment Method', 'Reference'
        ])
        
        for payment in payments:
            entity_name = payment.customer.name if payment.customer else payment.vendor.name
            writer.writerow([
                payment.payment_number,
                payment.get_payment_type_display(),
                entity_name,
                payment.base_currency_amount,
                payment.payment_date,
                payment.get_status_display(),
                payment.payment_method.name if payment.payment_method else '',
                payment.reference
            ])
        
        return response
    
    elif format_type == 'excel':
        # Excel export implementation
        pass
    
    return redirect('finance:payment_list')


@login_required
@tenant_required
def payment_bulk_actions(request):
    """Handle bulk actions on payments"""
    if request.method == 'POST':
        action = request.POST.get('action')
        payment_ids = request.POST.getlist('payment_ids')
        
        if not payment_ids:
            messages.error(request, 'No payments selected.')
            return redirect('finance:payment_list')
        
        payments = Payment.objects.filter(id__in=payment_ids, tenant=request.tenant)
        
        if action == 'post':
            payment_service = PaymentService(request.tenant)
            posted_count = 0
            for payment in payments:
                try:
                    if payment.status == 'DRAFT':
                        payment_service.post_payment(payment, request.user)
                        posted_count += 1
                except Exception as e:
                    messages.error(request, f'Error posting payment {payment.payment_number}: {str(e)}')
            
            if posted_count > 0:
                messages.success(request, f'{posted_count} payments posted successfully.')
        
        elif action == 'clear':
            cleared_count = 0
            for payment in payments:
                try:
                    if payment.status == 'POSTED':
                        payment.status = 'CLEARED'
                        payment.cleared_date = timezone.now()
                        payment.save()
                        cleared_count += 1
                except Exception as e:
                    messages.error(request, f'Error clearing payment {payment.payment_number}: {str(e)}')
            
            if cleared_count > 0:
                messages.success(request, f'{cleared_count} payments cleared successfully.')
        
        elif action == 'delete':
            payments.update(is_deleted=True, deleted_at=timezone.now())
            messages.success(request, f'{payments.count()} payments deleted successfully.')
    
    return redirect('finance:payment_list')


@login_required
@tenant_required
def payment_api_data(request):
    """API endpoint for payment data (AJAX)"""
    payments = Payment.objects.filter(tenant=request.tenant).select_related(
        'customer', 'vendor', 'payment_method'
    ).order_by('-payment_date')
    
    # Apply filters
    payment_type = request.GET.get('payment_type')
    status = request.GET.get('status')
    
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    if status:
        payments = payments.filter(status=status)
    
    # Serialize data
    payment_data = []
    for payment in payments:
        entity_name = payment.customer.name if payment.customer else payment.vendor.name
        payment_data.append({
            'id': payment.id,
            'payment_number': payment.payment_number,
            'payment_type': payment.payment_type,
            'entity_name': entity_name,
            'amount': float(payment.base_currency_amount),
            'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
            'status': payment.status,
            'status_display': payment.get_status_display(),
            'payment_method': payment.payment_method.name if payment.payment_method else '',
            'url': f'/finance/payments/{payment.id}/'
        })
    
    return JsonResponse({'payments': payment_data})


@login_required
@tenant_required
def payment_dashboard_widget(request):
    """Dashboard widget for payments overview"""
    payments = Payment.objects.filter(tenant=request.tenant)
    
    # Calculate statistics
    total_payments = payments.count()
    total_amount = payments.aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    cleared_amount = payments.filter(status='CLEARED').aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    pending_amount = payments.filter(status='PENDING').aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    
    # Recent payments
    recent_payments = payments.order_by('-created_at')[:5]
    
    context = {
        'total_payments': total_payments,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'pending_amount': pending_amount,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'finance/dashboard/widgets/payments_overview.html', context)


@login_required
@tenant_required
def payment_reconciliation(request):
    """Payment reconciliation view"""
    # Get unreconciled payments
    unreconciled_payments = Payment.objects.filter(
        tenant=request.tenant,
        status='POSTED',
        applications__isnull=True
    ).select_related('customer', 'vendor')
    
    # Get open invoices and bills
    open_invoices = Invoice.objects.filter(
        tenant=request.tenant,
        status__in=['OPEN', 'SENT', 'VIEWED', 'PARTIAL'],
        amount_due__gt=0
    ).select_related('customer')
    
    open_bills = Bill.objects.filter(
        tenant=request.tenant,
        status__in=['OPEN', 'APPROVED', 'PARTIAL'],
        amount_due__gt=0
    ).select_related('vendor')
    
    context = {
        'unreconciled_payments': unreconciled_payments,
        'open_invoices': open_invoices,
        'open_bills': open_bills,
    }
    
    return render(request, 'finance/payments/reconciliation.html', context)
