# backend/apps/finance/integrations/ecommerce_integration.py

"""
E-commerce Finance Integration Service
Automated financial recording for e-commerce operations with AI-powered insights
"""

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta
import logging
import json
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class EcommerceFinanceIntegrationService:
    """Complete integration between e-commerce and finance modules"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.auto_create_invoices = True
        self.auto_record_payments = True
        self.auto_calculate_taxes = True
        self.auto_recognize_revenue = True
    
    @transaction.atomic
    def process_order_financial_transaction(self, order):
        """Process complete financial transaction for e-commerce order"""
        try:
            logger.info(f"Processing financial transaction for order {order.id}")
            
            financial_result = {
                'order_id': order.id,
                'invoice': None,
                'journal_entries': [],
                'tax_entries': [],
                'revenue_recognition': None,
                'ai_insights': {},
                'status': 'processing'
            }
            
            # Step 1: Create customer invoice
            if self.auto_create_invoices:
                invoice = self._create_invoice_from_order(order)
                financial_result['invoice'] = invoice.id if invoice else None
            
            # Step 2: Record revenue recognition
            if self.auto_recognize_revenue:
                revenue_entry = self._create_revenue_recognition_entry(order)
                if revenue_entry:
                    financial_result['journal_entries'].append(revenue_entry.id)
            
            # Step 3: Calculate and record taxes
            if self.auto_calculate_taxes:
                tax_entries = self._process_order_taxes(order)
                financial_result['tax_entries'] = [entry.id for entry in tax_entries]
            
            # Step 4: Record COGS if applicable
            cogs_entries = self._create_cogs_entries(order)
            if cogs_entries:
                financial_result['journal_entries'].extend([entry.id for entry in cogs_entries])
            
            # Step 5: Generate AI insights
            ai_insights = self._generate_order_financial_insights(order, financial_result)
            financial_result['ai_insights'] = ai_insights
            
            # Step 6: Update order with finance integration data
            self._update_order_finance_integration(order, financial_result)
            
            financial_result['status'] = 'completed'
            logger.info(f"Financial transaction completed for order {order.id}")
            
            return financial_result
            
        except Exception as e:
            logger.error(f"Financial transaction failed for order {order.id}: {str(e)}")
            financial_result['status'] = 'failed'
            financial_result['error'] = str(e)
            return financial_result
    
    def _create_invoice_from_order(self, order):
        """Create finance invoice from e-commerce order"""
        try:
            from ..models import Invoice, InvoiceItem
            from apps.ecommerce.models import EcommerceProduct
            
            # Get or create customer
            customer = order.customer
            
            # Create invoice
            invoice = Invoice.objects.create(
                tenant=self.tenant,
                customer=customer,
                customer_email=order.email,
                invoice_date=order.created_at.date(),
                due_date=order.created_at.date() + timedelta(days=30),
                currency_id=1,  # Assume base currency, should be configurable
                status='OPEN',
                invoice_type='STANDARD',
                description=f'E-commerce Order #{order.order_number}',
                reference_number=order.order_number,
                
                # Order financial data
                subtotal=order.subtotal,
                tax_amount=order.tax_amount,
                shipping_amount=order.shipping_amount or Decimal('0.00'),
                discount_amount=order.discount_amount or Decimal('0.00'),
                total_amount=order.total_amount,
                
                # Integration metadata
                source_document_type='ECOMMERCE_ORDER',
                source_document_id=order.id,
                auto_created=True,
                
                # AI enhancement fields
                payment_probability=self._predict_payment_probability(order),
                predicted_payment_date=self._predict_payment_date(order),
            )
            
            # Create invoice items from order items
            line_number = 1
            for order_item in order.items.all():
                # Get product from e-commerce to inventory mapping
                inventory_product = self._get_inventory_product(order_item.product)
                
                InvoiceItem.objects.create(
                    tenant=self.tenant,
                    invoice=invoice,
                    line_number=line_number,
                    product=inventory_product,
                    description=order_item.product.title,
                    quantity=order_item.quantity,
                    unit_price=order_item.price,
                    line_total=order_item.total_price,
                    sku=order_item.product.sku,
                    
                    # Tax information
                    tax_rate=order_item.tax_rate or Decimal('0.00'),
                    tax_amount=order_item.tax_amount or Decimal('0.00'),
                    
                    # AI insights
                    profitability_score=self._calculate_item_profitability(order_item),
                )
                line_number += 1
            
            # Update invoice totals
            invoice.calculate_totals()
            
            # Run AI analysis on invoice
            invoice.run_comprehensive_ai_analysis()
            
            logger.info(f"Created invoice {invoice.invoice_number} for order {order.id}")
            return invoice
            
        except Exception as e:
            logger.error(f"Failed to create invoice for order {order.id}: {str(e)}")
            return None
    
    def _create_revenue_recognition_entry(self, order):
        """Create revenue recognition journal entry"""
        try:
            from ..models import JournalEntry, JournalEntryLine, Account
            
            # Get revenue and receivables accounts
            revenue_account = self._get_revenue_account()
            receivables_account = self._get_receivables_account()
            
            if not revenue_account or not receivables_account:
                logger.warning("Revenue or receivables account not found")
                return None
            
            # Create journal entry
            entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=order.created_at.date(),
                entry_type='INVOICE',
                description=f'Revenue recognition for order {order.order_number}',
                currency_id=1,  # Base currency
                source_document_type='ECOMMERCE_ORDER',
                source_document_id=order.id,
                created_by_id=1,  # System user
                is_system_generated=True,
            )
            
            # Debit: Accounts Receivable
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=1,
                account=receivables_account,
                description=f'A/R for order {order.order_number}',
                debit_amount=order.total_amount,
                credit_amount=Decimal('0.00'),
                customer=order.customer,
            )
            
            # Credit: Revenue (split by product categories if needed)
            revenue_amount = order.subtotal
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=2,
                account=revenue_account,
                description=f'Revenue for order {order.order_number}',
                debit_amount=Decimal('0.00'),
                credit_amount=revenue_amount,
                customer=order.customer,
            )
            
            # Credit: Sales Tax Payable (if applicable)
            if order.tax_amount > 0:
                tax_account = self._get_tax_payable_account()
                if tax_account:
                    JournalEntryLine.objects.create(
                        tenant=self.tenant,
                        journal_entry=entry,
                        line_number=3,
                        account=tax_account,
                        description=f'Sales tax for order {order.order_number}',
                        debit_amount=Decimal('0.00'),
                        credit_amount=order.tax_amount,
                        customer=order.customer,
                    )
            
            # Calculate totals and post entry
            entry.calculate_totals()
            entry.post_entry(user_id=1)  # System user
            
            # Run AI analysis
            entry.run_comprehensive_ai_analysis()
            
            logger.info(f"Created revenue recognition entry {entry.entry_number} for order {order.id}")
            return entry
            
        except Exception as e:
            logger.error(f"Failed to create revenue recognition for order {order.id}: {str(e)}")
            return None
    
    def _process_order_taxes(self, order):
        """Process tax calculations and create tax entries"""
        try:
            tax_entries = []
            
            # Calculate taxes by jurisdiction
            tax_breakdown = self._calculate_order_taxes(order)
            
            for jurisdiction, tax_data in tax_breakdown.items():
                if tax_data['amount'] > 0:
                    tax_entry = self._create_tax_journal_entry(order, jurisdiction, tax_data)
                    if tax_entry:
                        tax_entries.append(tax_entry)
            
            return tax_entries
            
        except Exception as e:
            logger.error(f"Failed to process taxes for order {order.id}: {str(e)}")
            return []
    
    def _create_cogs_entries(self, order):
        """Create Cost of Goods Sold entries for order items"""
        try:
            from ..services.cogs import COGSService
            
            cogs_service = COGSService(self.tenant)
            cogs_entries = []
            
            for order_item in order.items.all():
                # Get inventory product
                inventory_product = self._get_inventory_product(order_item.product)
                
                if inventory_product and inventory_product.track_inventory:
                    # Create COGS entry
                    cogs_entry = cogs_service.create_sales_cogs_entry(
                        product_id=inventory_product.id,
                        quantity_sold=order_item.quantity,
                        sale_date=order.created_at.date(),
                        source_document_type='ECOMMERCE_ORDER',
                        source_document_id=order.id
                    )
                    
                    if cogs_entry and cogs_entry.get('journal_entry'):
                        cogs_entries.append(cogs_entry['journal_entry'])
            
            return cogs_entries
            
        except Exception as e:
            logger.error(f"Failed to create COGS entries for order {order.id}: {str(e)}")
            return []
    
    @transaction.atomic
    def process_payment_transaction(self, ecommerce_payment):
        """Process e-commerce payment in finance system"""
        try:
            logger.info(f"Processing payment transaction {ecommerce_payment.id}")
            
            from ..models import Payment, PaymentApplication
            
            # Create finance payment record
            finance_payment = Payment.objects.create(
                tenant=self.tenant,
                payment_type='RECEIVED',
                payment_method=self._map_payment_method(ecommerce_payment.payment_method),
                payment_date=ecommerce_payment.created_at.date(),
                amount=ecommerce_payment.amount,
                currency_id=1,  # Base currency
                
                # Customer information
                customer=ecommerce_payment.order.customer,
                
                # Payment details
                reference_number=ecommerce_payment.transaction_id,
                external_transaction_id=ecommerce_payment.gateway_transaction_id,
                confirmation_number=ecommerce_payment.confirmation_number,
                
                # Integration metadata
                source_document_type='ECOMMERCE_PAYMENT',
                source_document_id=ecommerce_payment.id,
                
                # AI enhancements
                status='CLEARED' if ecommerce_payment.status == 'completed' else 'PENDING',
            )
            
            # Apply payment to invoice if exists
            if hasattr(ecommerce_payment.order, 'finance_invoice_id'):
                invoice = self._get_order_invoice(ecommerce_payment.order)
                if invoice:
                    PaymentApplication.objects.create(
                        tenant=self.tenant,
                        payment=finance_payment,
                        invoice=invoice,
                        amount_applied=ecommerce_payment.amount,
                        application_date=ecommerce_payment.created_at.date(),
                    )
                    
                    # Update invoice status
                    invoice.update_payment_status()
            
            # Create cash receipt journal entry
            cash_entry = self._create_cash_receipt_entry(finance_payment)
            
            # Run AI analysis
            finance_payment.run_comprehensive_ai_analysis()
            
            logger.info(f"Payment transaction completed for payment {ecommerce_payment.id}")
            return {
                'finance_payment_id': finance_payment.id,
                'journal_entry_id': cash_entry.id if cash_entry else None,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Payment transaction failed for payment {ecommerce_payment.id}: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    def process_refund_transaction(self, ecommerce_refund):
        """Process e-commerce refund in finance system"""
        try:
            logger.info(f"Processing refund transaction {ecommerce_refund.id}")
            
            from ..models import Invoice
            
            # Create credit note
            credit_note = Invoice.objects.create(
                tenant=self.tenant,
                customer=ecommerce_refund.order.customer,
                customer_email=ecommerce_refund.order.email,
                invoice_date=ecommerce_refund.created_at.date(),
                due_date=ecommerce_refund.created_at.date(),
                currency_id=1,
                status='OPEN',
                invoice_type='CREDIT_NOTE',
                description=f'Refund for order {ecommerce_refund.order.order_number}',
                reference_number=f'REF-{ecommerce_refund.order.order_number}',
                
                # Refund amounts (negative)
                subtotal=-ecommerce_refund.amount,
                total_amount=-ecommerce_refund.amount,
                
                # Integration metadata
                source_document_type='ECOMMERCE_REFUND',
                source_document_id=ecommerce_refund.id,
                auto_created=True,
            )
            
            # Create refund journal entries
            refund_entry = self._create_refund_journal_entry(ecommerce_refund)
            
            logger.info(f"Refund transaction completed for refund {ecommerce_refund.id}")
            return {
                'credit_note_id': credit_note.id,
                'journal_entry_id': refund_entry.id if refund_entry else None,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Refund transaction failed for refund {ecommerce_refund.id}: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    def sync_customer_financial_data(self, ecommerce_customer):
        """Sync e-commerce customer data with finance customer profile"""
        try:
            from ..models.crm_integration import CustomerFinancialProfile
            
            # Get or create financial profile
            profile, created = CustomerFinancialProfile.objects.get_or_create(
                tenant=self.tenant,
                customer=ecommerce_customer,
                defaults={
                    'credit_limit': Decimal('5000.00'),  # Default credit limit
                    'payment_terms_days': 30,
                    'credit_rating': 'UNRATED',
                    'invoice_delivery_method': 'EMAIL',
                    'preferred_payment_method': 'CREDIT_CARD',
                    'auto_send_statements': True,
                    'send_payment_reminders': True,
                }
            )
            
            # Update profile with e-commerce data
            if not created:
                # Update customer information
                self._update_customer_financial_metrics(profile, ecommerce_customer)
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to sync customer financial data: {str(e)}")
            return None
    
    # ============================================================================
    # AI-POWERED HELPER METHODS
    # ============================================================================
    
    def _generate_order_financial_insights(self, order, financial_result):
        """Generate AI insights for order financial transaction"""
        try:
            insights = {
                'order_analysis': {
                    'order_value_percentile': self._calculate_order_value_percentile(order),
                    'customer_segment': self._identify_customer_segment(order.customer),
                    'profitability_score': self._calculate_order_profitability(order),
                    'payment_risk_score': self._assess_payment_risk(order),
                },
                'revenue_insights': {
                    'revenue_category': self._categorize_revenue(order),
                    'seasonality_factor': self._calculate_seasonality_factor(order),
                    'growth_contribution': self._calculate_growth_contribution(order),
                },
                'predictions': {
                    'payment_probability': self._predict_payment_probability(order),
                    'collection_difficulty': self._predict_collection_difficulty(order),
                    'repeat_purchase_likelihood': self._predict_repeat_purchase(order),
                },
                'recommendations': self._generate_order_recommendations(order),
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate order insights: {str(e)}")
            return {}
    
    def _predict_payment_probability(self, order):
        """AI prediction for payment probability"""
        try:
            # Factors affecting payment probability
            factors = []
            
            # Customer history
            customer_orders = self._get_customer_order_history(order.customer)
            if customer_orders:
                payment_rate = self._calculate_customer_payment_rate(customer_orders)
                factors.append(payment_rate * 0.4)  # 40% weight
            else:
                factors.append(0.7)  # Default for new customers
            
            # Order amount factor
            if order.total_amount <= 100:
                factors.append(0.95)  # Small orders more likely to be paid
            elif order.total_amount <= 500:
                factors.append(0.90)
            elif order.total_amount <= 1000:
                factors.append(0.85)
            else:
                factors.append(0.80)  # Large orders slightly riskier
            
            # Payment method factor
            payment_method_scores = {
                'credit_card': 0.95,
                'paypal': 0.92,
                'bank_transfer': 0.88,
                'cash_on_delivery': 0.75,
            }
            
            payment_method = getattr(order, 'payment_method', 'credit_card').lower()
            factors.append(payment_method_scores.get(payment_method, 0.85))
            
            # Calculate weighted average
            probability = sum(factors) / len(factors)
            return Decimal(str(round(probability * 100, 1)))
            
        except Exception as e:
            logger.error(f"Payment probability prediction failed: {str(e)}")
            return Decimal('85.0')  # Default probability
    
    def _predict_payment_date(self, order):
        """AI prediction for payment date"""
        try:
            # Base payment terms
            base_days = 30  # Default net 30
            
            # Customer history adjustment
            customer_avg_days = self._get_customer_average_payment_days(order.customer)
            if customer_avg_days:
                adjustment = customer_avg_days - base_days
                predicted_days = base_days + (adjustment * 0.7)  # 70% weight to history
            else:
                predicted_days = base_days
            
            # Payment method adjustment
            method_adjustments = {
                'credit_card': -25,  # Immediate
                'paypal': -25,       # Immediate
                'bank_transfer': -5, # Slightly faster
                'cash_on_delivery': 0,  # Standard terms
            }
            
            payment_method = getattr(order, 'payment_method', 'credit_card').lower()
            predicted_days += method_adjustments.get(payment_method, 0)
            
            # Ensure positive days
            predicted_days = max(1, predicted_days)
            
            return order.created_at.date() + timedelta(days=int(predicted_days))
            
        except Exception as e:
            logger.error(f"Payment date prediction failed: {str(e)}")
            return order.created_at.date() + timedelta(days=30)
    
    def _calculate_item_profitability(self, order_item):
        """Calculate profitability score for order item"""
        try:
            # Get product cost
            inventory_product = self._get_inventory_product(order_item.product)
            if not inventory_product or not inventory_product.unit_cost:
                return Decimal('50.0')  # Default score
            
            # Calculate margin
            cost = float(inventory_product.unit_cost)
            price = float(order_item.price)
            
            if price > 0:
                margin = ((price - cost) / price) * 100
                
                # Convert margin to profitability score (0-100)
                if margin >= 50:
                    return Decimal('95.0')
                elif margin >= 30:
                    return Decimal('85.0')
                elif margin >= 20:
                    return Decimal('70.0')
                elif margin >= 10:
                    return Decimal('55.0')
                elif margin >= 0:
                    return Decimal('40.0')
                else:
                    return Decimal('20.0')  # Negative margin
            
            return Decimal('50.0')
            
        except Exception as e:
            logger.error(f"Profitability calculation failed: {str(e)}")
            return Decimal('50.0')
    
    # ============================================================================
    # UTILITY AND HELPER METHODS
    # ============================================================================
    
    def _get_inventory_product(self, ecommerce_product):
        """Get corresponding inventory product for e-commerce product"""
        try:
            # E-commerce products should inherit from or link to inventory products
            # This assumes the e-commerce product has an inventory_product field
            if hasattr(ecommerce_product, 'inventory_product'):
                return ecommerce_product.inventory_product
            
            # Alternative: lookup by SKU
            if hasattr(ecommerce_product, 'sku') and ecommerce_product.sku:
                from apps.inventory.models import Product
                return Product.objects.filter(
                    tenant=self.tenant,
                    sku=ecommerce_product.sku
                ).first()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get inventory product: {str(e)}")
            return None
    
    def _get_revenue_account(self):
        """Get the main revenue account"""
        from ..models import Account
        return Account.objects.filter(
            tenant=self.tenant,
            account_type='REVENUE',
            is_active=True
        ).first()
    
    def _get_receivables_account(self):
        """Get the accounts receivable account"""
        from ..models import Account
        return Account.objects.filter(
            tenant=self.tenant,
            account_type='CURRENT_ASSET',
            name__icontains='receivable',
            is_active=True
        ).first()
    
    def _get_tax_payable_account(self):
        """Get the tax payable account"""
        from ..models import Account
        return Account.objects.filter(
            tenant=self.tenant,
            account_type='CURRENT_LIABILITY',
            name__icontains='tax',
            is_active=True
        ).first()
    
    def _map_payment_method(self, ecommerce_method):
        """Map e-commerce payment method to finance payment method"""
        method_mapping = {
            'credit_card': 'CREDIT_CARD',
            'debit_card': 'DEBIT_CARD',
            'paypal': 'PAYPAL',
            'stripe': 'STRIPE',
            'bank_transfer': 'BANK_TRANSFER',
            'cash': 'CASH',
        }
        
        return method_mapping.get(ecommerce_method.lower(), 'OTHER')
    
    def _calculate_order_taxes(self, order):
        """Calculate taxes for order by jurisdiction"""
        # Simplified tax calculation - in production would integrate with tax services
        return {
            'default': {
                'rate': order.tax_rate if hasattr(order, 'tax_rate') else Decimal('8.25'),
                'amount': order.tax_amount or Decimal('0.00'),
                'jurisdiction': 'Default'
            }
        }
    
    def _create_tax_journal_entry(self, order, jurisdiction, tax_data):
        """Create journal entry for tax"""
        # Implementation would create appropriate tax journal entries
        # For now, taxes are handled in the main revenue recognition entry
        return None
    
    def _create_cash_receipt_entry(self, payment):
        """Create cash receipt journal entry"""
        try:
            from ..models import JournalEntry, JournalEntryLine, Account
            
            # Get cash and receivables accounts
            cash_account = Account.objects.filter(
                tenant=self.tenant,
                account_type__in=['CASH', 'BANK'],
                is_active=True
            ).first()
            
            receivables_account = self._get_receivables_account()
            
            if not cash_account or not receivables_account:
                return None
            
            # Create journal entry
            entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_date=payment.payment_date,
                entry_type='RECEIPT',
                description=f'Cash receipt - {payment.payment_number}',
                currency=payment.currency,
                source_document_type='PAYMENT',
                source_document_id=payment.id,
                created_by_id=1,  # System user
                is_system_generated=True,
            )
            
            # Debit: Cash
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=1,
                account=cash_account,
                description=f'Cash received - {payment.payment_method}',
                debit_amount=payment.amount,
                credit_amount=Decimal('0.00'),
                customer=payment.customer,
            )
            
            # Credit: Accounts Receivable
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=entry,
                line_number=2,
                account=receivables_account,
                description=f'A/R payment received',
                debit_amount=Decimal('0.00'),
                credit_amount=payment.amount,
                customer=payment.customer,
            )
            
            # Calculate totals and post
            entry.calculate_totals()
            entry.post_entry(user_id=1)
            
            return entry
            
        except Exception as e:
            logger.error(f"Failed to create cash receipt entry: {str(e)}")
            return None
    
    def _create_refund_journal_entry(self, refund):
        """Create journal entry for refund"""
        # Implementation for refund journal entries
        # Would reverse the original revenue recognition
        return None
    
    def _update_order_finance_integration(self, order, financial_result):
        """Update order with finance integration data"""
        try:
            # Add finance integration fields to order
            if hasattr(order, 'finance_invoice_id'):
                order.finance_invoice_id = financial_result.get('invoice')
            
            if hasattr(order, 'finance_status'):
                order.finance_status = financial_result.get('status')
            
            if hasattr(order, 'finance_integration_data'):
                order.finance_integration_data = financial_result
            
            # Save if fields exist
            update_fields = []
            for field in ['finance_invoice_id', 'finance_status', 'finance_integration_data']:
                if hasattr(order, field):
                    update_fields.append(field)
            
            if update_fields:
                order.save(update_fields=update_fields)
                
        except Exception as e:
            logger.error(f"Failed to update order finance integration: {str(e)}")
    
    # Placeholder methods for AI calculations
    def _calculate_order_value_percentile(self, order): return 75
    def _identify_customer_segment(self, customer): return 'regular'
    def _calculate_order_profitability(self, order): return Decimal('25.5')
    def _assess_payment_risk(self, order): return Decimal('15.0')
    def _categorize_revenue(self, order): return 'product_sales'
    def _calculate_seasonality_factor(self, order): return 1.0
    def _calculate_growth_contribution(self, order): return 0.05
    def _predict_collection_difficulty(self, order): return Decimal('20.0')
    def _predict_repeat_purchase(self, order): return Decimal('65.0')
    def _generate_order_recommendations(self, order): return []
    def _get_customer_order_history(self, customer): return []
    def _calculate_customer_payment_rate(self, orders): return 0.85
    def _get_customer_average_payment_days(self, customer): return 28
    def _get_order_invoice(self, order): return None
    def _update_customer_financial_metrics(self, profile, customer): pass