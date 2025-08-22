"""
Finance Reconciliation Utilities
Bank reconciliation utilities
"""

from decimal import Decimal
from typing import List, Dict, Tuple
from django.db.models import Q


class ReconciliationMatcher:
    """Bank reconciliation matching utilities"""
    
    @staticmethod
    def find_matching_transactions(bank_transaction, book_transactions, 
                                 tolerance: Decimal = Decimal('0.01')) -> List[Dict]:
        """Find potential matches for bank transaction"""
        matches = []
        
        for book_transaction in book_transactions:
            score = ReconciliationMatcher.calculate_match_score(
                bank_transaction, book_transaction
            )
            
            if score > 0.7:  # 70% match threshold
                matches.append({
                    'transaction': book_transaction,
                    'score': score,
                    'reasons': ReconciliationMatcher.get_match_reasons(
                        bank_transaction, book_transaction
                    )
                })
        
        # Sort by score (highest first)
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches
    
    @staticmethod
    def calculate_match_score(bank_transaction, book_transaction) -> float:
        """Calculate match score between bank and book transactions"""
        score = 0.0
        
        # Amount match (exact = 1.0, within tolerance = 0.8, otherwise = 0.0)
        if abs(bank_transaction.amount - book_transaction.amount) <= Decimal('0.01'):
            score += 0.4
        elif abs(bank_transaction.amount - book_transaction.amount) <= Decimal('1.00'):
            score += 0.2
        
        # Date match (same day = 1.0, within 1 day = 0.8, within 3 days = 0.6)
        date_diff = abs((bank_transaction.transaction_date - book_transaction.transaction_date).days)
        if date_diff == 0:
            score += 0.3
        elif date_diff <= 1:
            score += 0.2
        elif date_diff <= 3:
            score += 0.1
        
        # Description match (exact = 1.0, contains = 0.6, partial = 0.3)
        if bank_transaction.description and book_transaction.description:
            bank_desc = bank_transaction.description.lower()
            book_desc = book_transaction.description.lower()
            
            if bank_desc == book_desc:
                score += 0.3
            elif bank_desc in book_desc or book_desc in bank_desc:
                score += 0.2
            elif any(word in book_desc for word in bank_desc.split()):
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def get_match_reasons(bank_transaction, book_transaction) -> List[str]:
        """Get reasons why transactions match"""
        reasons = []
        
        # Amount match
        if abs(bank_transaction.amount - book_transaction.amount) <= Decimal('0.01'):
            reasons.append('Exact amount match')
        elif abs(bank_transaction.amount - book_transaction.amount) <= Decimal('1.00'):
            reasons.append('Amount within tolerance')
        
        # Date match
        date_diff = abs((bank_transaction.transaction_date - book_transaction.transaction_date).days)
        if date_diff == 0:
            reasons.append('Same transaction date')
        elif date_diff <= 1:
            reasons.append('Transaction date within 1 day')
        elif date_diff <= 3:
            reasons.append('Transaction date within 3 days')
        
        # Description match
        if bank_transaction.description and book_transaction.description:
            bank_desc = bank_transaction.description.lower()
            book_desc = book_transaction.description.lower()
            
            if bank_desc == book_desc:
                reasons.append('Exact description match')
            elif bank_desc in book_desc or book_desc in bank_desc:
                reasons.append('Description contains match')
            elif any(word in book_desc for word in bank_desc.split()):
                reasons.append('Partial description match')
        
        return reasons


class ReconciliationRules:
    """Bank reconciliation rule engine"""
    
    @staticmethod
    def apply_auto_matching_rules(bank_transactions, book_transactions) -> List[Dict]:
        """Apply automatic matching rules"""
        auto_matches = []
        
        for bank_transaction in bank_transactions:
            if bank_transaction.is_matched:
                continue
            
            # Rule 1: Exact amount and date match
            exact_matches = ReconciliationRules.find_exact_matches(
                bank_transaction, book_transactions
            )
            
            if exact_matches:
                auto_matches.append({
                    'bank_transaction': bank_transaction,
                    'book_transactions': exact_matches,
                    'rule': 'Exact amount and date match',
                    'confidence': 0.95
                })
                continue
            
            # Rule 2: Amount match within tolerance and date within 1 day
            close_matches = ReconciliationRules.find_close_matches(
                bank_transaction, book_transactions
            )
            
            if close_matches:
                auto_matches.append({
                    'bank_transaction': bank_transaction,
                    'book_transactions': close_matches,
                    'rule': 'Amount match within tolerance and date within 1 day',
                    'confidence': 0.85
                })
        
        return auto_matches
    
    @staticmethod
    def find_exact_matches(bank_transaction, book_transactions) -> List:
        """Find exact matches (amount and date)"""
        matches = []
        
        for book_transaction in book_transactions:
            if book_transaction.is_matched:
                continue
            
            if (abs(bank_transaction.amount - book_transaction.amount) <= Decimal('0.01') and
                bank_transaction.transaction_date == book_transaction.transaction_date):
                matches.append(book_transaction)
        
        return matches
    
    @staticmethod
    def find_close_matches(bank_transaction, book_transactions) -> List:
        """Find close matches (amount within tolerance, date within 1 day)"""
        matches = []
        
        for book_transaction in book_transactions:
            if book_transaction.is_matched:
                continue
            
            amount_match = abs(bank_transaction.amount - book_transaction.amount) <= Decimal('1.00')
            date_match = abs((bank_transaction.transaction_date - book_transaction.transaction_date).days) <= 1
            
            if amount_match and date_match:
                matches.append(book_transaction)
        
        return matches


class ReconciliationValidator:
    """Reconciliation validation utilities"""
    
    @staticmethod
    def validate_reconciliation(bank_account, reconciliation_date) -> Dict:
        """Validate reconciliation data"""
        errors = []
        warnings = []
        
        # Check for unmatched bank transactions
        unmatched_bank = bank_account.transactions.filter(
            transaction_date__lte=reconciliation_date,
            is_matched=False
        ).count()
        
        if unmatched_bank > 0:
            warnings.append(f'{unmatched_bank} unmatched bank transactions')
        
        # Check for unmatched book transactions
        unmatched_book = bank_account.book_transactions.filter(
            transaction_date__lte=reconciliation_date,
            is_matched=False
        ).count()
        
        if unmatched_book > 0:
            warnings.append(f'{unmatched_book} unmatched book transactions')
        
        # Check for balanced reconciliation
        bank_balance = bank_account.get_bank_balance(reconciliation_date)
        book_balance = bank_account.get_book_balance(reconciliation_date)
        
        if abs(bank_balance - book_balance) > Decimal('0.01'):
            errors.append('Bank and book balances do not match')
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'bank_balance': bank_balance,
            'book_balance': book_balance,
            'difference': bank_balance - book_balance
        }
    
    @staticmethod
    def check_reconciliation_quality(reconciliation) -> Dict:
        """Check quality of reconciliation"""
        quality_score = 0.0
        issues = []
        
        # Check percentage of transactions matched
        total_transactions = reconciliation.bank_transactions.count() + reconciliation.book_transactions.count()
        matched_transactions = reconciliation.matched_transactions.count()
        
        if total_transactions > 0:
            match_percentage = (matched_transactions / total_transactions) * 100
            quality_score += min(match_percentage / 100, 1.0) * 0.5
            
            if match_percentage < 80:
                issues.append(f'Low match percentage: {match_percentage:.1f}%')
        
        # Check for large unmatched amounts
        unmatched_amount = abs(reconciliation.bank_balance - reconciliation.book_balance)
        if unmatched_amount > Decimal('100.00'):
            issues.append(f'Large unmatched amount: {unmatched_amount}')
            quality_score -= 0.2
        
        # Check for old unmatched transactions
        from datetime import date
        cutoff_date = date.today() - timedelta(days=30)
        old_unmatched = reconciliation.bank_transactions.filter(
            transaction_date__lt=cutoff_date,
            is_matched=False
        ).count()
        
        if old_unmatched > 0:
            issues.append(f'{old_unmatched} old unmatched transactions')
            quality_score -= 0.1
        
        return {
            'quality_score': max(quality_score, 0.0),
            'issues': issues,
            'match_percentage': match_percentage if total_transactions > 0 else 0,
            'unmatched_amount': unmatched_amount
        }
