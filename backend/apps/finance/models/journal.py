"""
Journal Entry and Transaction Models
Double-entry bookkeeping with multi-currency support
"""

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date
import uuid

from apps.core.models import TenantBaseModel, SoftDeleteMixin
from apps.core.utils import generate_code
from .currency import Currency
from .base import (
    AIFinanceBaseMixin, 
    SmartCategorizationMixin, 
    PredictiveAnalyticsMixin, 
    IntelligentMatchingMixin
)

User = get_user_model()


class JournalEntry(TenantBaseModel, SoftDeleteMixin, AIFinanceBaseMixin, 
                   SmartCategorizationMixin, PredictiveAnalyticsMixin, IntelligentMatchingMixin):
    """AI-Enhanced journal entries with intelligent automation and analytics"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('POSTED', 'Posted'),
        ('REVERSED', 'Reversed'),
        ('PENDING_APPROVAL', 'Pending Approval'),
    ]
    
    ENTRY_TYPE_CHOICES = [
        ('MANUAL', 'Manual Entry'),
        ('AUTOMATIC', 'System Generated'),
        ('INVOICE', 'Sales Invoice'),
        ('BILL', 'Purchase Bill'),
        ('PAYMENT', 'Payment'),
        ('RECEIPT', 'Receipt'),
        ('INVENTORY', 'Inventory Adjustment'),
        ('COGS', 'Cost of Goods Sold'),
        ('DEPRECIATION', 'Depreciation'),
        ('ADJUSTMENT', 'Adjusting Entry'),
        ('CLOSING', 'Closing Entry'),
        ('REVERSAL', 'Reversal Entry'),
        ('BANK_RECONCILIATION', 'Bank Reconciliation'),
        ('CURRENCY_REVALUATION', 'Currency Revaluation'),
    ]
    
    # Entry Identification
    entry_number = models.CharField(max_length=50)
    reference_number = models.CharField(max_length=100, blank=True)
    entry_date = models.DateField()
    
    # Entry Classification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    entry_type = models.CharField(max_length=25, choices=ENTRY_TYPE_CHOICES, default='MANUAL')
    
    # Description & Notes
    description = models.TextField()
    notes = models.TextField(blank=True)
    
    # Source Information
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.IntegerField(null=True, blank=True)
    source_document_number = models.CharField(max_length=100, blank=True)
    
    # Financial Information
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Multi-Currency Support
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    base_currency_total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    base_currency_total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Approval & Control
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_journal_entries'
    )
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_journal_entries'
    )
    posted_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_journal_entries'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Reversal Information
    reversed_entry = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversing_entries'
    )
    reversal_reason = models.TextField(blank=True)
    
    # Financial Period
    financial_period = models.ForeignKey(
        'finance.FinancialPeriod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Recurring Entry Information
    is_recurring = models.BooleanField(default=False)
    recurring_template = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_entries'
    )
    next_occurrence_date = models.DateField(null=True, blank=True)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
        ],
        blank=True
    )
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Audit Fields
    version = models.PositiveIntegerField(default=1)
    is_system_generated = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-entry_date', '-entry_number']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'
        db_table = 'finance_journal_entries'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'entry_number'],
                name='unique_tenant_journal_entry'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'entry_date', 'status']),
            models.Index(fields=['tenant', 'entry_type', 'status']),
            models.Index(fields=['tenant', 'source_document_type', 'source_document_id']),
            models.Index(fields=['tenant', 'created_by', 'entry_date']),
        ]
        
    def __str__(self):
        return f'{self.entry_number} - {self.description[:50]}'
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            self.entry_number = self.generate_entry_number()
        
        # Set financial period if not set
        if not self.financial_period:
            self.set_financial_period()
        
        super().save(*args, **kwargs)
    
    def generate_entry_number(self):
        """Generate unique journal entry number"""
        return generate_code('JE', self.tenant_id)
    
    def set_financial_period(self):
        """Set the appropriate financial period"""
        from .core import FinancialPeriod
        
        period = FinancialPeriod.objects.filter(
            tenant=self.tenant,
            start_date__lte=self.entry_date,
            end_date__gte=self.entry_date,
            status='OPEN'
        ).first()
        
        if period:
            self.financial_period = period
    
    def clean(self):
        """Validate journal entry"""
        if self.status == 'POSTED':
            if abs(self.total_debit - self.total_credit) > Decimal('0.01'):
                raise ValidationError('Journal entry must be balanced (debits = credits)')
            
            if abs(self.base_currency_total_debit - self.base_currency_total_credit) > Decimal('0.01'):
                raise ValidationError('Base currency amounts must be balanced')
        
        # Check if financial period is open
        if self.financial_period and self.financial_period.status != 'OPEN':
            raise ValidationError('Cannot post entries to closed financial periods')
        
        # Validate entry date
        if self.entry_date > date.today():
            raise ValidationError('Entry date cannot be in the future')
    
    @transaction.atomic
    def post_entry(self, user):
        """Post the journal entry"""
        if self.status == 'POSTED':
            raise ValidationError('Journal entry is already posted')
        
        # Validate that entry is balanced
        self.calculate_totals()
        self.clean()
        
        # Update account balances
        for line in self.journal_lines.all():
            line.update_account_balance()
        
        self.status = 'POSTED'
        self.posted_by = user
        self.posted_date = timezone.now()
        self.save()
        
        # Update inventory cost layers if applicable
        if self.entry_type == 'INVENTORY':
            self.update_inventory_cost_layers()
        
        # Create recurring entry if needed
        if self.is_recurring and self.next_occurrence_date:
            self.create_next_recurring_entry()
        
        return True
    
    def calculate_totals(self):
        """Calculate and update total debits and credits"""
        totals = self.journal_lines.aggregate(
            total_debit=models.Sum('debit_amount'),
            total_credit=models.Sum('credit_amount'),
            base_total_debit=models.Sum('base_currency_debit_amount'),
            base_total_credit=models.Sum('base_currency_credit_amount')
        )
        
        self.total_debit = totals['total_debit'] or Decimal('0.00')
        self.total_credit = totals['total_credit'] or Decimal('0.00')
        self.base_currency_total_debit = totals['base_total_debit'] or Decimal('0.00')
        self.base_currency_total_credit = totals['base_total_credit'] or Decimal('0.00')
        
        self.save(update_fields=[
            'total_debit', 'total_credit',
            'base_currency_total_debit', 'base_currency_total_credit'
        ])
    
    def update_inventory_cost_layers(self):
        """Update inventory cost layers for inventory-related entries"""
        from ..services.inventory_costing import InventoryCostingService
        
        service = InventoryCostingService(self.tenant)
        service.process_journal_entry(self)
    
    @transaction.atomic
    def reverse_entry(self, user, reason):
        """Create a reversal entry"""
        if self.status != 'POSTED':
            raise ValidationError('Only posted entries can be reversed')
        
        if self.reversed_entry:
            raise ValidationError('Entry has already been reversed')
        
        # Create reversal entry
        reversal = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=date.today(),
            entry_type='REVERSAL',
            description=f'Reversal of {self.entry_number}',
            notes=reason,
            currency=self.currency,
            exchange_rate=self.exchange_rate,
            created_by=user,
            reversed_entry=self
        )
        
        # Create reversal lines (swap debits and credits)
        for line in self.journal_lines.all():
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=reversal,
                account=line.account,
                description=f'Reversal: {line.description}',
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                base_currency_debit_amount=line.base_currency_credit_amount,
                base_currency_credit_amount=line.base_currency_debit_amount,
                line_number=line.line_number,
                customer=line.customer,
                vendor=line.vendor,
                product=line.product,
                project=line.project,
                department=line.department,
                location=line.location
            )
        
        # Post reversal entry
        reversal.calculate_totals()
        reversal.post_entry(user)
        
        # Mark original as reversed
        self.status = 'REVERSED'
        self.save()
        
        return reversal
    
    def create_next_recurring_entry(self):
        """Create the next occurrence of a recurring entry"""
        if not self.is_recurring or not self.next_occurrence_date:
            return None
        
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        # Calculate next date based on frequency
        next_date = self.next_occurrence_date
        
        if self.recurring_frequency == 'DAILY':
            self.next_occurrence_date = next_date + timedelta(days=1)
        elif self.recurring_frequency == 'WEEKLY':
            self.next_occurrence_date = next_date + timedelta(weeks=1)
        elif self.recurring_frequency == 'MONTHLY':
            self.next_occurrence_date = next_date + relativedelta(months=1)
        elif self.recurring_frequency == 'QUARTERLY':
            self.next_occurrence_date = next_date + relativedelta(months=3)
        elif self.recurring_frequency == 'ANNUALLY':
            self.next_occurrence_date = next_date + relativedelta(years=1)
        
        self.save()
        
        # Create new entry
        new_entry = JournalEntry.objects.create(
            tenant=self.tenant,
            entry_date=next_date,
            entry_type=self.entry_type,
            description=self.description,
            notes=self.notes,
            currency=self.currency,
            recurring_template=self.recurring_template or self,
            created_by=self.created_by,
            is_system_generated=True
        )
        
        # Copy lines
        for line in self.journal_lines.all():
            JournalEntryLine.objects.create(
                tenant=self.tenant,
                journal_entry=new_entry,
                account=line.account,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                line_number=line.line_number,
                customer=line.customer,
                vendor=line.vendor,
                product=line.product,
                project=line.project,
                department=line.department,
                location=line.location
            )
        
        return new_entry
    
    @property
    def is_balanced(self):
        """Check if journal entry is balanced"""
        return abs(self.total_debit - self.total_credit) <= Decimal('0.01')
    
    @property
    def can_be_posted(self):
        """Check if entry can be posted"""
        return (
            self.status == 'DRAFT' and
            self.is_balanced and
            self.journal_lines.exists() and
            (not self.financial_period or self.financial_period.status == 'OPEN')
        )
    
    # ============================================================================
    # AI-ENHANCED METHODS AND INTELLIGENT FEATURES
    # ============================================================================
    
    def extract_ai_features(self):
        """Extract AI features specific to journal entries"""
        super().extract_ai_features()
        
        features = self.ml_features.copy()
        
        # Entry-specific features
        features.update({
            'entry_type': self.entry_type,
            'total_amount': float(self.total_debit + self.total_credit) / 2,
            'line_count': self.journal_lines.count(),
            'is_system_generated': self.is_system_generated,
            'is_recurring': self.is_recurring,
            'currency_code': self.currency.code if self.currency else 'USD',
            'exchange_rate': float(self.exchange_rate),
            'entry_date_month': self.entry_date.month,
            'entry_date_weekday': self.entry_date.weekday(),
            'has_source_document': bool(self.source_document_id),
        })
        
        # Account distribution analysis
        account_types = []
        for line in self.journal_lines.all():
            if hasattr(line.account, 'account_type'):
                account_types.append(line.account.account_type)
        
        features['account_types'] = list(set(account_types))
        features['involves_cash'] = any('CASH' in acct_type or 'BANK' in acct_type for acct_type in account_types)
        features['involves_revenue'] = any('REVENUE' in acct_type for acct_type in account_types)
        features['involves_expense'] = any('EXPENSE' in acct_type for acct_type in account_types)
        
        # Tracking dimension analysis
        features.update({
            'has_customer_tracking': any(line.customer for line in self.journal_lines.all()),
            'has_vendor_tracking': any(line.vendor for line in self.journal_lines.all()),
            'has_project_tracking': any(line.project for line in self.journal_lines.all()),
            'has_department_tracking': any(line.department for line in self.journal_lines.all()),
        })
        
        self.ml_features = features
    
    def intelligent_entry_validation(self):
        """AI-powered validation and anomaly detection"""
        try:
            # Extract features for analysis
            self.extract_ai_features()
            
            # Detect unusual patterns
            validation_issues = []
            
            # Amount-based anomalies
            total_amount = float(self.total_debit + self.total_credit) / 2
            if total_amount > 100000:
                validation_issues.append({
                    'type': 'high_amount',
                    'severity': 'medium',
                    'message': f'High amount entry: ${total_amount:,.2f}',
                    'recommendation': 'Consider requiring additional approval for high-value entries'
                })
            
            # Unusual entry patterns
            if self.entry_type == 'MANUAL' and total_amount > 50000:
                validation_issues.append({
                    'type': 'large_manual_entry',
                    'severity': 'high',
                    'message': 'Large manual journal entry detected',
                    'recommendation': 'Verify source documentation and authorization'
                })
            
            # Weekend/off-hours entries
            if self.entry_date.weekday() >= 5:  # Saturday or Sunday
                validation_issues.append({
                    'type': 'weekend_entry',
                    'severity': 'low',
                    'message': 'Entry created on weekend',
                    'recommendation': 'Review for business necessity'
                })
            
            # Round amount analysis (potential fraud indicator)
            if total_amount > 1000 and total_amount % 100 == 0:
                validation_issues.append({
                    'type': 'round_amount',
                    'severity': 'low',
                    'message': 'Entry amount is perfectly round',
                    'recommendation': 'Verify accuracy of amount calculation'
                })
            
            # Unusual account combinations
            self._analyze_account_combinations(validation_issues)
            
            # Update AI insights
            if not isinstance(self.ai_insights, dict):
                self.ai_insights = {}
            
            self.ai_insights['validation_issues'] = validation_issues
            self.ai_insights['validation_timestamp'] = timezone.now().isoformat()
            
            # Calculate risk score based on issues
            risk_score = sum(
                {'low': 5, 'medium': 15, 'high': 30, 'critical': 50}.get(issue['severity'], 0)
                for issue in validation_issues
            )
            self.ai_risk_score = Decimal(str(min(100, risk_score)))
            
            return validation_issues
            
        except Exception as e:
            logger.error(f"Intelligent validation failed for journal entry {self.id}: {str(e)}")
            return []
    
    def _analyze_account_combinations(self, validation_issues):
        """Analyze unusual account combinations"""
        account_types = []
        for line in self.journal_lines.all():
            if hasattr(line.account, 'account_type'):
                account_types.append(line.account.account_type)
        
        # Check for unusual combinations
        if 'CASH' in account_types and 'REVENUE' in account_types and self.entry_type == 'MANUAL':
            validation_issues.append({
                'type': 'cash_revenue_manual',
                'severity': 'medium',
                'message': 'Manual entry affecting cash and revenue accounts',
                'recommendation': 'Ensure proper sales process documentation'
            })
        
        if account_types.count('CASH') > 1:
            validation_issues.append({
                'type': 'multiple_cash_accounts',
                'severity': 'medium',
                'message': 'Entry affects multiple cash accounts',
                'recommendation': 'Verify if cash transfer is properly documented'
            })
    
    def suggest_categorization_improvements(self):
        """AI-powered suggestions for better categorization"""
        try:
            suggestions = []
            
            # Analyze journal lines for categorization opportunities
            for line in self.journal_lines.all():
                # Check if line could benefit from additional tracking
                if not line.department and 'expense' in line.account.account_type.lower():
                    suggestions.append({
                        'line_number': line.line_number,
                        'type': 'missing_department',
                        'message': 'Consider adding department tracking for expense analysis',
                        'priority': 'medium'
                    })
                
                if not line.project and line.amount > 5000:
                    suggestions.append({
                        'line_number': line.line_number,
                        'type': 'missing_project',
                        'message': 'Large amount - consider project tracking for better cost allocation',
                        'priority': 'high'
                    })
                
                # Tax code suggestions
                if not line.tax_code and 'expense' in line.account.account_type.lower():
                    suggestions.append({
                        'line_number': line.line_number,
                        'type': 'missing_tax_code',
                        'message': 'Consider adding tax code for proper tax reporting',
                        'priority': 'low'
                    })
            
            # Update AI insights
            if not isinstance(self.ai_insights, dict):
                self.ai_insights = {}
            
            self.ai_insights['categorization_suggestions'] = suggestions
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Categorization analysis failed for journal entry {self.id}: {str(e)}")
            return []
    
    def predict_posting_impact(self):
        """Predict the impact of posting this journal entry"""
        try:
            impact_analysis = {
                'account_impacts': [],
                'financial_statement_effects': {},
                'cash_flow_impact': 0,
                'profitability_impact': 0,
            }
            
            # Analyze impact on each account
            for line in self.journal_lines.all():
                account_impact = {
                    'account_name': line.account.name,
                    'account_type': getattr(line.account, 'account_type', 'Unknown'),
                    'amount_change': float(line.amount),
                    'direction': 'increase' if line.is_debit else 'decrease',
                    'new_balance_estimate': float(line.account.current_balance) + 
                                         (float(line.amount) if line.is_debit else -float(line.amount))
                }
                impact_analysis['account_impacts'].append(account_impact)
                
                # Calculate financial statement effects
                account_type = getattr(line.account, 'account_type', '')
                amount = float(line.amount)
                
                if 'ASSET' in account_type:
                    impact_analysis['financial_statement_effects']['total_assets'] = \
                        impact_analysis['financial_statement_effects'].get('total_assets', 0) + \
                        (amount if line.is_debit else -amount)
                        
                elif 'LIABILITY' in account_type:
                    impact_analysis['financial_statement_effects']['total_liabilities'] = \
                        impact_analysis['financial_statement_effects'].get('total_liabilities', 0) + \
                        (amount if not line.is_debit else -amount)
                        
                elif 'EQUITY' in account_type:
                    impact_analysis['financial_statement_effects']['total_equity'] = \
                        impact_analysis['financial_statement_effects'].get('total_equity', 0) + \
                        (amount if not line.is_debit else -amount)
                        
                elif 'REVENUE' in account_type:
                    revenue_impact = amount if not line.is_debit else -amount
                    impact_analysis['profitability_impact'] += revenue_impact
                    
                elif 'EXPENSE' in account_type:
                    expense_impact = amount if line.is_debit else -amount
                    impact_analysis['profitability_impact'] -= expense_impact
                
                # Cash flow impact
                if 'CASH' in account_type or 'BANK' in account_type:
                    cash_impact = amount if line.is_debit else -amount
                    impact_analysis['cash_flow_impact'] += cash_impact
            
            # Store predictions
            if not isinstance(self.ai_predictions, dict):
                self.ai_predictions = {}
            
            self.ai_predictions['posting_impact'] = impact_analysis
            self.ai_predictions['impact_timestamp'] = timezone.now().isoformat()
            
            return impact_analysis
            
        except Exception as e:
            logger.error(f"Impact prediction failed for journal entry {self.id}: {str(e)}")
            return {}
    
    def generate_audit_trail_insights(self):
        """Generate AI insights for audit trail analysis"""
        try:
            audit_insights = {
                'creation_pattern': 'normal',
                'timing_analysis': {},
                'user_behavior': {},
                'compliance_flags': []
            }
            
            # Timing analysis
            creation_hour = self.created_at.hour if self.created_at else 12
            if creation_hour < 6 or creation_hour > 22:
                audit_insights['timing_analysis']['off_hours_creation'] = True
                audit_insights['compliance_flags'].append('Created during off-business hours')
            
            # User behavior analysis
            if self.created_by:
                # Analyze user's typical entry patterns
                user_entries = JournalEntry.objects.filter(
                    tenant=self.tenant,
                    created_by=self.created_by,
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).exclude(id=self.id)
                
                avg_amount = user_entries.aggregate(
                    avg=models.Avg(models.F('total_debit') + models.F('total_credit'))
                )['avg'] or 0
                
                current_amount = float(self.total_debit + self.total_credit)
                
                if current_amount > avg_amount * 3:
                    audit_insights['user_behavior']['unusual_amount'] = True
                    audit_insights['compliance_flags'].append('Amount significantly higher than user average')
            
            # Entry type analysis
            if self.entry_type == 'MANUAL' and current_amount > 25000:
                audit_insights['compliance_flags'].append('Large manual entry - requires enhanced review')
            
            # Update AI insights
            if not isinstance(self.ai_insights, dict):
                self.ai_insights = {}
            
            self.ai_insights['audit_trail'] = audit_insights
            
            return audit_insights
            
        except Exception as e:
            logger.error(f"Audit trail analysis failed for journal entry {self.id}: {str(e)}")
            return {}
    
    def run_comprehensive_ai_analysis(self):
        """Execute comprehensive AI analysis for journal entries"""
        try:
            logger.info(f"Starting comprehensive AI analysis for journal entry {self.id}")
            
            # Run all AI analysis methods
            results = {
                'validation_issues': self.intelligent_entry_validation(),
                'categorization_suggestions': self.suggest_categorization_improvements(),
                'posting_impact': self.predict_posting_impact(),
                'audit_insights': self.generate_audit_trail_insights(),
            }
            
            # Run base AI analysis
            base_analysis = super().analyze_with_ai()
            
            # Update comprehensive insights
            if not isinstance(self.ai_insights, dict):
                self.ai_insights = {}
            
            self.ai_insights.update({
                'comprehensive_analysis': {
                    'timestamp': timezone.now().isoformat(),
                    'analysis_complete': base_analysis,
                    'total_validation_issues': len(results['validation_issues']),
                    'total_suggestions': len(results['categorization_suggestions']),
                    'compliance_flags': results['audit_insights'].get('compliance_flags', []),
                }
            })
            
            # Calculate overall confidence
            confidence_factors = [
                85 if self.is_system_generated else 70,  # System entries more reliable
                90 if self.source_document_id else 60,   # Source document availability
                95 - len(results['validation_issues']) * 10,  # Validation issues reduce confidence
                80 if self.is_balanced else 30,  # Balance check
            ]
            
            self.ai_confidence_level = Decimal(str(
                max(0, min(100, sum(confidence_factors) / len(confidence_factors)))
            ))
            
            self.save(update_fields=[
                'ai_insights', 'ai_predictions', 'ai_confidence_level', 
                'ai_risk_score', 'last_ai_analysis'
            ])
            
            logger.info(f"Comprehensive AI analysis completed for journal entry {self.id}")
            return results
            
        except Exception as e:
            logger.error(f"Comprehensive AI analysis failed for journal entry {self.id}: {str(e)}")
            return {}


class JournalEntryLine(TenantBaseModel, SmartCategorizationMixin):
    """AI-Enhanced journal entry lines with intelligent categorization"""
    
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='journal_lines'
    )
    line_number = models.IntegerField()
    
    # Account Information
    account = models.ForeignKey('finance.Account', on_delete=models.PROTECT)
    
    # Transaction Details
    description = models.TextField()
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Multi-Currency Support
    base_currency_debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    base_currency_credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Tracking
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    vendor = models.ForeignKey(
        'finance.Vendor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    project = models.ForeignKey(
        'finance.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    department = models.ForeignKey(
        'finance.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    location = models.ForeignKey(
        'finance.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Tax Information
    tax_code = models.ForeignKey(
        'finance.TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Quantity (for inventory items)
    quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciled_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['journal_entry', 'line_number']
        db_table = 'finance_journal_entry_lines'
        indexes = [
            models.Index(fields=['journal_entry', 'line_number']),
            models.Index(fields=['tenant', 'account', 'debit_amount']),
            models.Index(fields=['tenant', 'account', 'credit_amount']),
        ]
        
    def __str__(self):
        return f'{self.journal_entry.entry_number} - Line {self.line_number}'
    
    def save(self, *args, **kwargs):
        # Calculate base currency amounts if not provided
        if not self.base_currency_debit_amount and self.debit_amount:
            self.base_currency_debit_amount = self.debit_amount * self.journal_entry.exchange_rate
        
        if not self.base_currency_credit_amount and self.credit_amount:
            self.base_currency_credit_amount = self.credit_amount * self.journal_entry.exchange_rate
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate journal entry line"""
        if self.debit_amount and self.credit_amount:
            raise ValidationError('A line cannot have both debit and credit amounts')
        if not self.debit_amount and not self.credit_amount:
            raise ValidationError('A line must have either debit or credit amount')
        
        if self.debit_amount < 0 or self.credit_amount < 0:
            raise ValidationError('Amounts cannot be negative')
    
    @property
    def amount(self):
        """Get the line amount (debit or credit)"""
        return self.debit_amount if self.debit_amount else self.credit_amount
    
    @property
    def base_amount(self):
        """Get the base currency amount"""
        return self.base_currency_debit_amount if self.base_currency_debit_amount else self.base_currency_credit_amount
    
    @property
    def is_debit(self):
        """Check if this is a debit entry"""
        return bool(self.debit_amount)
    
    def update_account_balance(self):
        """Update the account balance when entry is posted"""
        if not self.account:
            return
        
        if self.is_debit:
            if self.account.normal_balance == 'DEBIT':
                self.account.current_balance += self.base_currency_debit_amount
            else:
                self.account.current_balance -= self.base_currency_debit_amount
        else:
            if self.account.normal_balance == 'CREDIT':
                self.account.current_balance += self.base_currency_credit_amount
            else:
                self.account.current_balance -= self.base_currency_credit_amount
        
        self.account.save(update_fields=['current_balance'])
    
    def get_tracking_display(self):
        """Get formatted tracking information"""
        tracking = []
        if self.customer:
            tracking.append(f"Customer: {self.customer.name}")
        if self.vendor:
            tracking.append(f"Vendor: {self.vendor.company_name}")
        if self.project:
            tracking.append(f"Project: {self.project.name}")
        if self.department:
            tracking.append(f"Department: {self.department.name}")
        if self.location:
            tracking.append(f"Location: {self.location.name}")
        
        return " | ".join(tracking) if tracking else "No tracking"