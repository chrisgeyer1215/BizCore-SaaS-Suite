# backend/apps/finance/services/bank_reconciliation.py

"""
Bank Reconciliation Service - Auto-matching and Processing
"""

from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Optional
import re

from ..models import (
    BankAccount, BankStatement, BankTransaction, BankReconciliation,
    Payment, JournalEntry, ReconciliationRule
)
from .accounting import AccountingService


class BankReconciliationService(AccountingService):
    """Bank reconciliation and auto-matching service"""

    def auto_match_transaction(self, bank_transaction: BankTransaction) -> Dict:
        """Attempt to auto-match a bank transaction"""
        
        # Skip if already matched
        if bank_transaction.reconciliation_status != 'UNMATCHED':
            return {'matched': False, 'reason': 'Already processed'}
        
        # Apply reconciliation rules in priority order
        rules = ReconciliationRule.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).order_by('priority')
        
        for rule in rules:
            match_result = self._apply_rule(rule, bank_transaction)
            if match_result['matched']:
                # Update rule statistics
                rule.update_statistics(True, True, match_result['confidence'])
                return match_result
        
        # Try exact amount matching
        amount_match = self._match_by_amount(bank_transaction)
        if amount_match['matched']:
            return amount_match
        
        # Try reference number matching
        reference_match = self._match_by_reference(bank_transaction)
        if reference_match['matched']:
            return reference_match
        
        # Try description matching
        description_match = self._match_by_description(bank_transaction)
        if description_match['matched']:
            return description_match
        
        return {'matched': False, 'reason': 'No matching records found'}

    def _apply_rule(self, rule: ReconciliationRule, bank_transaction: BankTransaction) -> Dict:
        """Apply a specific reconciliation rule"""
        config = rule.rule_config
        tolerance = rule.amount_tolerance
        date_tolerance = rule.date_tolerance_days
        
        if rule.rule_type == 'AMOUNT_EXACT':
            return self._match_by_exact_amount(bank_transaction, tolerance)
        
        elif rule.rule_type == 'AMOUNT_RANGE':
            min_amount = Decimal(str(config.get('min_amount', 0)))
            max_amount = Decimal(str(config.get('max_amount', 999999)))
            return self._match_by_amount_range(bank_transaction, min_amount, max_amount, tolerance)
        
        elif rule.rule_type == 'DESCRIPTION_CONTAINS':
            keywords = config.get('keywords', [])
            return self._match_by_description_keywords(bank_transaction, keywords)
        
        elif rule.rule_type == 'DESCRIPTION_REGEX':
            pattern = config.get('pattern', '')
            return self._match_by_description_regex(bank_transaction, pattern)
        
        elif rule.rule_type == 'REFERENCE_MATCH':
            return self._match_by_reference_exact(bank_transaction)
        
        elif rule.rule_type == 'DATE_RANGE':
            return self._match_by_date_range(bank_transaction, date_tolerance)
        
        return {'matched': False, 'reason': f'Unknown rule type: {rule.rule_type}'}

    def _match_by_amount(self, bank_transaction: BankTransaction) -> Dict:
        """Match by exact amount"""
        amount = bank_transaction.amount
        date_range = self._get_date_range(bank_transaction.transaction_date, 5)
        
        # Look for payments first
        if bank_transaction.amount > 0:  # Deposit
            payments = Payment.objects.filter(
                tenant=self.tenant,
                payment_type='RECEIVED',
                amount=amount,
                payment_date__range=date_range,
                bank_transaction__isnull=True
            ).first()
            
            if payments:
                return self._create_match(bank_transaction, payments, 95.0)
        
        else:  # Withdrawal
            payments = Payment.objects.filter(
                tenant=self.tenant,
                payment_type='MADE',
                amount=abs(amount),
                payment_date__range=date_range,
                bank_transaction__isnull=True
            ).first()
            
            if payments:
                return self._create_match(bank_transaction, payments, 95.0)
        
        return {'matched': False, 'reason': 'No amount match found'}

    def _match_by_reference(self, bank_transaction: BankTransaction) -> Dict:
        """Match by reference number"""
        if not bank_transaction.reference_number:
            return {'matched': False, 'reason': 'No reference number'}
        
        ref_number = bank_transaction.reference_number.strip()
        
        # Look for payments with matching reference
        payment = Payment.objects.filter(
            tenant=self.tenant,
            reference_number__iexact=ref_number,
            bank_transaction__isnull=True
        ).first()
        
        if payment:
            return self._create_match(bank_transaction, payment, 100.0)
        
        # Look for journal entries with matching reference
        journal_entry = JournalEntry.objects.filter(
            tenant=self.tenant,
            reference_number__iexact=ref_number,
            status='POSTED'
        ).first()
        
        if journal_entry:
            return self._create_match(bank_transaction, journal_entry, 90.0)
        
        return {'matched': False, 'reason': 'No reference match found'}

    def _match_by_description(self, bank_transaction: BankTransaction) -> Dict:
        """Match by description patterns"""
        description = bank_transaction.description.upper()
        
        # Common patterns for payments
        patterns = [
            (r'CHECK\s+(\d+)', 'check_number'),
            (r'ACH\s+CREDIT\s+(\w+)', 'ach_credit'),
            (r'WIRE\s+(\w+)', 'wire_transfer'),
            (r'CARD\s+PURCHASE\s+(\w+)', 'card_purchase'),
        ]
        
        for pattern, match_type in patterns:
            match = re.search(pattern, description)
            if match:
                identifier = match.group(1)
                
                if match_type == 'check_number':
                    payment = Payment.objects.filter(
                        tenant=self.tenant,
                        check_number=identifier,
                        bank_transaction__isnull=True
                    ).first()
                    
                    if payment:
                        return self._create_match(bank_transaction, payment, 85.0)
        
        return {'matched': False, 'reason': 'No description pattern match'}

    def _create_match(self, bank_transaction: BankTransaction, matched_record, confidence: float) -> Dict:
        """Create a match between bank transaction and record"""
        
        bank_transaction.reconciliation_status = 'AUTO_MATCH'
        bank_transaction.match_confidence = Decimal(str(confidence))
        
        if isinstance(matched_record, Payment):
            bank_transaction.matched_payment = matched_record
        elif isinstance(matched_record, JournalEntry):
            bank_transaction.matched_journal_entry = matched_record
        
        bank_transaction.save()
        
        return {
            'matched': True,
            'record': matched_record,
            'confidence': confidence,
            'match_type': type(matched_record).__name__
        }

    def _get_date_range(self, center_date: date, days: int) -> tuple:
        """Get date range around center date"""
        start_date = center_date - timedelta(days=days)
        end_date = center_date + timedelta(days=days)
        return (start_date, end_date)

    def create_reconciliation(self, bank_account: BankAccount, 
                            bank_statement: BankStatement,
                            reconciliation_date: date)