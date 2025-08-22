"""
Vendor Management Views
Handle vendor relationships, contact information, and vendor performance
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json

from apps.core.decorators import tenant_required
from apps.core.utils import generate_code
from ..models import Vendor, VendorContact, Bill, Payment, Account
from ..forms.vendors import VendorForm, VendorContactFormSet
from ..services.vendor import VendorService


@login_required
@tenant_required
def vendor_list(request):
    """List all vendors with filtering and pagination"""
    vendors = Vendor.objects.filter(tenant=request.tenant).select_related(
        'default_account', 'tax_group'
    ).order_by('name')
    
    # Filtering
    status = request.GET.get('status')
    vendor_type = request.GET.get('vendor_type')
    search = request.GET.get('search')
    
    if status:
        vendors = vendors.filter(status=status)
    if vendor_type:
        vendors = vendors.filter(vendor_type=vendor_type)
    if search:
        vendors = vendors.filter(
            Q(name__icontains=search) |
            Q(vendor_number__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(vendors, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    total_vendors = vendors.count()
    active_vendors = vendors.filter(status='ACTIVE').count()
    total_spent = Bill.objects.filter(
        tenant=request.tenant,
        vendor__in=vendors,
        status='PAID'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    context = {
        'page_obj': page_obj,
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'total_spent': total_spent,
        'status_choices': Vendor.STATUS_CHOICES,
        'vendor_type_choices': Vendor.VENDOR_TYPE_CHOICES,
    }
    
    return render(request, 'finance/vendors/list.html', context)


@login_required
@tenant_required
def vendor_detail(request, vendor_id):
    """Show vendor details"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    # Get vendor contacts
    contacts = vendor.contacts.all().order_by('is_primary', 'name')
    
    # Get recent bills
    recent_bills = Bill.objects.filter(
        tenant=request.tenant,
        vendor=vendor
    ).order_by('-bill_date')[:10]
    
    # Get recent payments
    recent_payments = Payment.objects.filter(
        tenant=request.tenant,
        vendor=vendor
    ).order_by('-payment_date')[:10]
    
    # Calculate vendor statistics
    total_bills = Bill.objects.filter(tenant=request.tenant, vendor=vendor).count()
    total_amount = Bill.objects.filter(
        tenant=request.tenant,
        vendor=vendor
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    total_payments = Payment.objects.filter(
        tenant=request.tenant,
        vendor=vendor
    ).aggregate(total=Sum('base_currency_amount'))['total'] or Decimal('0.00')
    
    outstanding_amount = total_amount - total_payments
    
    # Get vendor performance metrics
    vendor_service = VendorService(request.tenant)
    performance_metrics = vendor_service.get_vendor_performance_metrics(vendor)
    
    context = {
        'vendor': vendor,
        'contacts': contacts,
        'recent_bills': recent_bills,
        'recent_payments': recent_payments,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'total_payments': total_payments,
        'outstanding_amount': outstanding_amount,
        'performance_metrics': performance_metrics,
    }
    
    return render(request, 'finance/vendors/detail.html', context)


@login_required
@tenant_required
def vendor_create(request):
    """Create new vendor"""
    if request.method == 'POST':
        form = VendorForm(request.POST, tenant=request.tenant)
        formset = VendorContactFormSet(request.POST, instance=Vendor(tenant=request.tenant))
        
        if form.is_valid() and formset.is_valid():
            vendor = form.save(commit=False)
            vendor.tenant = request.tenant
            vendor.vendor_number = generate_code('VEND', request.tenant)
            vendor.save()
            
            formset.instance = vendor
            formset.save()
            
            messages.success(request, f'Vendor {vendor.name} created successfully.')
            return redirect('finance:vendor_detail', vendor_id=vendor.id)
    else:
        form = VendorForm(tenant=request.tenant)
        formset = VendorContactFormSet(instance=Vendor(tenant=request.tenant))
    
    context = {
        'form': form,
        'formset': formset,
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/vendors/form.html', context)


@login_required
@tenant_required
def vendor_edit(request, vendor_id):
    """Edit existing vendor"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    if request.method == 'POST':
        form = VendorForm(request.POST, instance=vendor, tenant=request.tenant)
        formset = VendorContactFormSet(request.POST, instance=vendor)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            messages.success(request, f'Vendor {vendor.name} updated successfully.')
            return redirect('finance:vendor_detail', vendor_id=vendor.id)
    else:
        form = VendorForm(instance=vendor, tenant=request.tenant)
        formset = VendorContactFormSet(instance=vendor)
    
    context = {
        'form': form,
        'formset': formset,
        'vendor': vendor,
        'accounts': Account.objects.filter(tenant=request.tenant, is_active=True),
    }
    
    return render(request, 'finance/vendors/form.html', context)


@login_required
@tenant_required
def vendor_delete(request, vendor_id):
    """Delete vendor (soft delete)"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    # Check if vendor has any bills or payments
    has_bills = Bill.objects.filter(tenant=request.tenant, vendor=vendor).exists()
    has_payments = Payment.objects.filter(tenant=request.tenant, vendor=vendor).exists()
    
    if has_bills or has_payments:
        messages.error(request, 'Cannot delete vendor with existing bills or payments.')
        return redirect('finance:vendor_detail', vendor_id=vendor.id)
    
    if request.method == 'POST':
        vendor.is_deleted = True
        vendor.deleted_at = timezone.now()
        vendor.save()
        
        messages.success(request, f'Vendor {vendor.name} deleted successfully.')
        return redirect('finance:vendor_list')
    
    context = {'vendor': vendor}
    return render(request, 'finance/vendors/delete_confirm.html', context)


@login_required
@tenant_required
def vendor_bills(request, vendor_id):
    """Show vendor bills"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    bills = Bill.objects.filter(
        tenant=request.tenant,
        vendor=vendor
    ).order_by('-bill_date')
    
    # Filtering
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        bills = bills.filter(status=status)
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
    outstanding_amount = total_amount - paid_amount
    
    context = {
        'vendor': vendor,
        'page_obj': page_obj,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'outstanding_amount': outstanding_amount,
        'status_choices': Bill.STATUS_CHOICES,
    }
    
    return render(request, 'finance/vendors/bills.html', context)


@login_required
@tenant_required
def vendor_payments(request, vendor_id):
    """Show vendor payments"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    payments = Payment.objects.filter(
        tenant=request.tenant,
        vendor=vendor
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
        'vendor': vendor,
        'page_obj': page_obj,
        'total_payments': total_payments,
        'total_amount': total_amount,
        'cleared_amount': cleared_amount,
        'status_choices': Payment.STATUS_CHOICES,
    }
    
    return render(request, 'finance/vendors/payments.html', context)


@login_required
@tenant_required
def vendor_performance(request, vendor_id):
    """Show vendor performance analysis"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    vendor_service = VendorService(request.tenant)
    
    # Get performance metrics
    performance_metrics = vendor_service.get_vendor_performance_metrics(vendor)
    
    # Get monthly spending trends
    monthly_spending = vendor_service.get_monthly_spending_trends(vendor)
    
    # Get payment terms analysis
    payment_terms_analysis = vendor_service.get_payment_terms_analysis(vendor)
    
    # Get quality metrics
    quality_metrics = vendor_service.get_vendor_quality_metrics(vendor)
    
    context = {
        'vendor': vendor,
        'performance_metrics': performance_metrics,
        'monthly_spending': monthly_spending,
        'payment_terms_analysis': payment_terms_analysis,
        'quality_metrics': quality_metrics,
    }
    
    return render(request, 'finance/vendors/performance.html', context)


@login_required
@tenant_required
def vendor_export(request):
    """Export vendors to various formats"""
    vendors = Vendor.objects.filter(tenant=request.tenant).select_related(
        'default_account', 'tax_group'
    ).order_by('name')
    
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vendors.csv"'
        
        import csv
        writer = csv.writer(response)
        writer.writerow([
            'Vendor Number', 'Name', 'Type', 'Status', 'Email', 'Phone',
            'Default Account', 'Payment Terms', 'Credit Limit'
        ])
        
        for vendor in vendors:
            writer.writerow([
                vendor.vendor_number,
                vendor.name,
                vendor.get_vendor_type_display(),
                vendor.get_status_display(),
                vendor.email,
                vendor.phone,
                vendor.default_account.name if vendor.default_account else '',
                vendor.payment_terms,
                vendor.credit_limit
            ])
        
        return response
    
    elif format_type == 'excel':
        # Excel export implementation
        pass
    
    return redirect('finance:vendor_list')


@login_required
@tenant_required
def vendor_bulk_actions(request):
    """Handle bulk actions on vendors"""
    if request.method == 'POST':
        action = request.POST.get('action')
        vendor_ids = request.POST.getlist('vendor_ids')
        
        if not vendor_ids:
            messages.error(request, 'No vendors selected.')
            return redirect('finance:vendor_list')
        
        vendors = Vendor.objects.filter(id__in=vendor_ids, tenant=request.tenant)
        
        if action == 'activate':
            vendors.update(status='ACTIVE')
            messages.success(request, f'{vendors.count()} vendors activated successfully.')
        
        elif action == 'deactivate':
            vendors.update(status='INACTIVE')
            messages.success(request, f'{vendors.count()} vendors deactivated successfully.')
        
        elif action == 'delete':
            # Check if vendors have bills or payments
            vendors_with_transactions = []
            for vendor in vendors:
                if Bill.objects.filter(tenant=request.tenant, vendor=vendor).exists() or \
                   Payment.objects.filter(tenant=request.tenant, vendor=vendor).exists():
                    vendors_with_transactions.append(vendor.name)
            
            if vendors_with_transactions:
                messages.error(request, f'Cannot delete vendors with transactions: {", ".join(vendors_with_transactions)}')
            else:
                vendors.update(is_deleted=True, deleted_at=timezone.now())
                messages.success(request, f'{vendors.count()} vendors deleted successfully.')
    
    return redirect('finance:vendor_list')


@login_required
@tenant_required
def vendor_api_data(request):
    """API endpoint for vendor data (AJAX)"""
    vendors = Vendor.objects.filter(tenant=request.tenant).select_related(
        'default_account', 'tax_group'
    ).order_by('name')
    
    # Apply filters
    status = request.GET.get('status')
    vendor_type = request.GET.get('vendor_type')
    search = request.GET.get('search')
    
    if status:
        vendors = vendors.filter(status=status)
    if vendor_type:
        vendors = vendors.filter(vendor_type=vendor_type)
    if search:
        vendors = vendors.filter(
            Q(name__icontains=search) |
            Q(vendor_number__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Serialize data
    vendor_data = []
    for vendor in vendors:
        vendor_data.append({
            'id': vendor.id,
            'vendor_number': vendor.vendor_number,
            'name': vendor.name,
            'vendor_type': vendor.vendor_type,
            'status': vendor.status,
            'email': vendor.email,
            'phone': vendor.phone,
            'default_account': vendor.default_account.name if vendor.default_account else '',
            'url': f'/finance/vendors/{vendor.id}/'
        })
    
    return JsonResponse({'vendors': vendor_data})


@login_required
@tenant_required
def vendor_dashboard_widget(request):
    """Dashboard widget for vendors overview"""
    vendors = Vendor.objects.filter(tenant=request.tenant)
    
    # Calculate statistics
    total_vendors = vendors.count()
    active_vendors = vendors.filter(status='ACTIVE').count()
    inactive_vendors = vendors.filter(status='INACTIVE').count()
    
    # Recent vendors
    recent_vendors = vendors.order_by('-created_at')[:5]
    
    # Top vendors by spending
    top_vendors = Vendor.objects.filter(
        tenant=request.tenant,
        bills__status='PAID'
    ).annotate(
        total_spent=Sum('bills__total_amount')
    ).order_by('-total_spent')[:5]
    
    context = {
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'inactive_vendors': inactive_vendors,
        'recent_vendors': recent_vendors,
        'top_vendors': top_vendors,
    }
    
    return render(request, 'finance/dashboard/widgets/vendors_overview.html', context)


@login_required
@tenant_required
def vendor_import(request):
    """Import vendors from CSV/Excel"""
    if request.method == 'POST':
        if 'vendor_file' in request.FILES:
            vendor_file = request.FILES['vendor_file']
            
            try:
                vendor_service = VendorService(request.tenant)
                import_result = vendor_service.import_vendors_from_file(vendor_file)
                
                if import_result['success']:
                    messages.success(request, f'{import_result["imported_count"]} vendors imported successfully.')
                    if import_result['errors']:
                        for error in import_result['errors']:
                            messages.warning(request, error)
                else:
                    messages.error(request, f'Import failed: {import_result["error"]}')
                    
            except Exception as e:
                messages.error(request, f'Error importing vendors: {str(e)}')
        else:
            messages.error(request, 'Please select a file to import.')
    
    return render(request, 'finance/vendors/import.html')


@login_required
@tenant_required
def vendor_merge(request, vendor_id):
    """Merge vendor with another vendor"""
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=request.tenant)
    
    if request.method == 'POST':
        target_vendor_id = request.POST.get('target_vendor')
        if target_vendor_id:
            target_vendor = get_object_or_404(Vendor, id=target_vendor_id, tenant=request.tenant)
            
            try:
                vendor_service = VendorService(request.tenant)
                vendor_service.merge_vendors(vendor, target_vendor, request.user)
                
                messages.success(request, f'Vendor {vendor.name} merged into {target_vendor.name} successfully.')
                return redirect('finance:vendor_detail', vendor_id=target_vendor.id)
            except Exception as e:
                messages.error(request, f'Error merging vendors: {str(e)}')
    
    # Get potential target vendors
    potential_targets = Vendor.objects.filter(
        tenant=request.tenant,
        status='ACTIVE'
    ).exclude(id=vendor.id)
    
    context = {
        'vendor': vendor,
        'potential_targets': potential_targets,
    }
    
    return render(request, 'finance/vendors/merge.html')
