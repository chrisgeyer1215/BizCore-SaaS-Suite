"""
Bill Management Views
Handle vendor bills, accounts payable, and bill processing
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
from ..models import Bill, BillItem, Vendor, Account, JournalEntry
from ..forms.bills import BillForm, BillItemFormSet
from ..services.bill import BillService


@login_required
@tenant_required
def bill_list(request):
    """List all bills with filtering and pagination"""
    bills = Bill.objects.filter(tenant=request.tenant).select_related(
        'vendor', 'account', 'tax_group'
    ).order_by('-bill_date')
    
    # Filtering
    status = request.GET.get('status')
    vendor_id = request.GET.get('vendor')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        bills = bills.filter(status=status)
    if vendor_id:
        bills = bills.filter(vendor_id=vendor_id)
    if date_from:
        bills = bills.filter(bill_date__gte=date_from)
    if date_to:
        bills = bills.filter(bill_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(bills, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    paid_amount = bills.filter(status='PAID').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    overdue_amount = bills.filter(
        due_date__lt=timezone.now().date(),
        status__in=['OPEN', 'APPROVED', 'PARTIAL']
    ).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    
    context = {
        'page_obj': page_obj,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'overdue_amount': overdue_amount,
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'status_choices': Bill.STATUS_CHOICES,
    }
    
    return render(request, 'finance/bills/list.html', context)


@login_required
@tenant_required
def bill_detail(request, bill_id):
    """Show bill details"""
    bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    # Get related payments
    payments = bill.payments.all().order_by('-payment_date')
    
    # Get journal entries
    journal_entries = JournalEntry.objects.filter(
        tenant=request.tenant,
        reference_type='BILL',
        reference_id=bill.id
    ).order_by('-entry_date')
    
    context = {
        'bill': bill,
        'payments': payments,
        'journal_entries': journal_entries,
    }
    
    return render(request, 'finance/bills/detail.html', context)


@login_required
@tenant_required
def bill_create(request):
    """Create new bill"""
    if request.method == 'POST':
        form = BillForm(request.POST, tenant=request.tenant)
        formset = BillItemFormSet(request.POST, instance=Bill(tenant=request.tenant))
        
        if form.is_valid() and formset.is_valid():
            bill = form.save(commit=False)
            bill.tenant = request.tenant
            bill.bill_number = generate_code('BILL', request.tenant)
            bill.save()
            
            formset.instance = bill
            formset.save()
            
            # Create journal entry
            bill_service = BillService(request.tenant)
            bill_service.create_bill_journal_entry(bill)
            
            messages.success(request, f'Bill {bill.bill_number} created successfully.')
            return redirect('finance:bill_detail', bill_id=bill.id)
    else:
        form = BillForm(tenant=request.tenant)
        formset = BillItemFormSet(instance=Bill(tenant=request.tenant))
    
    context = {
        'form': form,
        'formset': formset,
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/bills/form.html', context)


@login_required
@tenant_required
def bill_edit(request, bill_id):
    """Edit existing bill"""
    bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    if bill.status in ['PAID', 'CANCELLED']:
        messages.error(request, 'Cannot edit paid or cancelled bills.')
        return redirect('finance:bill_detail', bill_id=bill.id)
    
    if request.method == 'POST':
        form = BillForm(request.POST, instance=bill, tenant=request.tenant)
        formset = BillItemFormSet(request.POST, instance=bill)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Update journal entry if needed
            if bill.status == 'POSTED':
                bill_service = BillService(request.tenant)
                bill_service.update_bill_journal_entry(bill)
            
            messages.success(request, f'Bill {bill.bill_number} updated successfully.')
            return redirect('finance:bill_detail', bill_id=bill.id)
    else:
        form = BillForm(instance=bill, tenant=request.tenant)
        formset = BillItemFormSet(instance=bill)
    
    context = {
        'form': form,
        'formset': formset,
        'bill': bill,
        'vendors': Vendor.objects.filter(tenant=request.tenant, is_active=True),
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/bills/form.html', context)


@login_required
@tenant_required
def bill_delete(request, bill_id):
    """Delete bill (soft delete)"""
    bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    if bill.status in ['PAID', 'POSTED']:
        messages.error(request, 'Cannot delete paid or posted bills.')
        return redirect('finance:bill_detail', bill_id=bill.id)
    
    if request.method == 'POST':
        bill.is_deleted = True
        bill.deleted_at = timezone.now()
        bill.save()
        
        messages.success(request, f'Bill {bill.bill_number} deleted successfully.')
        return redirect('finance:bill_list')
    
    context = {'bill': bill}
    return render(request, 'finance/bills/delete_confirm.html', context)


@login_required
@tenant_required
def bill_approve(request, bill_id):
    """Approve bill for payment"""
    bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    if bill.status != 'OPEN':
        messages.error(request, 'Only open bills can be approved.')
        return redirect('finance:bill_detail', bill_id=bill.id)
    
    if request.method == 'POST':
        bill.status = 'APPROVED'
        bill.approved_by = request.user
        bill.approved_date = timezone.now()
        bill.save()
        
        messages.success(request, f'Bill {bill.bill_number} approved successfully.')
        return redirect('finance:bill_detail', bill_id=bill.id)
    
    context = {'bill': bill}
    return render(request, 'finance/bills/approve_confirm.html', context)


@login_required
@tenant_required
def bill_post(request, bill_id):
    """Post bill to general ledger"""
    bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    if bill.status != 'APPROVED':
        messages.error(request, 'Only approved bills can be posted.')
        return redirect('finance:bill_detail', bill_id=bill.id)
    
    if request.method == 'POST':
        try:
            bill_service = BillService(request.tenant)
            bill_service.post_bill(bill, request.user)
            
            messages.success(request, f'Bill {bill.bill_number} posted successfully.')
            return redirect('finance:bill_detail', bill_id=bill.id)
        except Exception as e:
            messages.error(request, f'Error posting bill: {str(e)}')
    
    context = {'bill': bill}
    return render(request, 'finance/bills/post_confirm.html', context)


@login_required
@tenant_required
def bill_duplicate(request, bill_id):
    """Duplicate existing bill"""
    original_bill = get_object_or_404(Bill, id=bill_id, tenant=request.tenant)
    
    if request.method == 'POST':
        # Create new bill with same data
        new_bill = Bill.objects.create(
            tenant=request.tenant,
            vendor=original_bill.vendor,
            bill_number=generate_code('BILL', request.tenant),
            bill_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            reference=original_bill.reference,
            notes=f"Duplicated from {original_bill.bill_number}",
            status='DRAFT'
        )
        
        # Copy bill items
        for item in original_bill.items.all():
            BillItem.objects.create(
                bill=new_bill,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
                account=item.account
            )
        
        messages.success(request, f'Bill duplicated successfully as {new_bill.bill_number}.')
        return redirect('finance:bill_edit', bill_id=new_bill.id)
    
    context = {'bill': original_bill}
    return render(request, 'finance/bills/duplicate_confirm.html', context)


@login_required
@tenant_required
def bill_export(request):
    """Export bills to various formats"""
    bills = Bill.objects.filter(tenant=request.tenant).select_related(
        'vendor', 'account'
    ).order_by('-bill_date')
    
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bills.csv"'
        
        import csv
        writer = csv.writer(response)
        writer.writerow([
            'Bill Number', 'Vendor', 'Bill Date', 'Due Date', 'Amount', 
            'Status', 'Reference', 'Notes'
        ])
        
        for bill in bills:
            writer.writerow([
                bill.bill_number,
                bill.vendor.name,
                bill.bill_date,
                bill.due_date,
                bill.total_amount,
                bill.get_status_display(),
                bill.reference,
                bill.notes
            ])
        
        return response
    
    elif format_type == 'excel':
        # Excel export implementation
        pass
    
    return redirect('finance:bill_list')


@login_required
@tenant_required
def bill_bulk_actions(request):
    """Handle bulk actions on bills"""
    if request.method == 'POST':
        action = request.POST.get('action')
        bill_ids = request.POST.getlist('bill_ids')
        
        if not bill_ids:
            messages.error(request, 'No bills selected.')
            return redirect('finance:bill_list')
        
        bills = Bill.objects.filter(id__in=bill_ids, tenant=request.tenant)
        
        if action == 'approve':
            bills.update(
                status='APPROVED',
                approved_by=request.user,
                approved_date=timezone.now()
            )
            messages.success(request, f'{bills.count()} bills approved successfully.')
        
        elif action == 'post':
            bill_service = BillService(request.tenant)
            posted_count = 0
            for bill in bills:
                try:
                    if bill.status == 'APPROVED':
                        bill_service.post_bill(bill, request.user)
                        posted_count += 1
                except Exception as e:
                    messages.error(request, f'Error posting bill {bill.bill_number}: {str(e)}')
            
            if posted_count > 0:
                messages.success(request, f'{posted_count} bills posted successfully.')
        
        elif action == 'delete':
            bills.update(is_deleted=True, deleted_at=timezone.now())
            messages.success(request, f'{bills.count()} bills deleted successfully.')
    
    return redirect('finance:bill_list')


@login_required
@tenant_required
def bill_api_data(request):
    """API endpoint for bill data (AJAX)"""
    bills = Bill.objects.filter(tenant=request.tenant).select_related(
        'vendor', 'account'
    ).order_by('-bill_date')
    
    # Apply filters
    status = request.GET.get('status')
    vendor_id = request.GET.get('vendor')
    
    if status:
        bills = bills.filter(status=status)
    if vendor_id:
        bills = bills.filter(vendor_id=vendor_id)
    
    # Serialize data
    bill_data = []
    for bill in bills:
        bill_data.append({
            'id': bill.id,
            'bill_number': bill.bill_number,
            'vendor_name': bill.vendor.name,
            'bill_date': bill.bill_date.strftime('%Y-%m-%d'),
            'due_date': bill.due_date.strftime('%Y-%m-%d'),
            'total_amount': float(bill.total_amount),
            'amount_due': float(bill.amount_due),
            'status': bill.status,
            'status_display': bill.get_status_display(),
            'reference': bill.reference,
            'url': f'/finance/bills/{bill.id}/'
        })
    
    return JsonResponse({'bills': bill_data})


@login_required
@tenant_required
def bill_dashboard_widget(request):
    """Dashboard widget for bills overview"""
    bills = Bill.objects.filter(tenant=request.tenant)
    
    # Calculate statistics
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    overdue_amount = bills.filter(
        due_date__lt=timezone.now().date(),
        status__in=['OPEN', 'APPROVED', 'PARTIAL']
    ).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    
    # Recent bills
    recent_bills = bills.order_by('-created_at')[:5]
    
    context = {
        'total_bills': total_bills,
        'total_amount': total_amount,
        'overdue_amount': overdue_amount,
        'recent_bills': recent_bills,
    }
    
    return render(request, 'finance/dashboard/widgets/bills_overview.html', context)
