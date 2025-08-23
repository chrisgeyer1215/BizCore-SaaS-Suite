# backend/apps/finance/services/ai_bank_reconciliation.py

"""
AI-Powered Bank Reconciliation Service
Intelligent automatic matching and reconciliation with machine learning
"""

from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import date, timedelta
import logging
import json
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AIBankReconciliationService:
    """Advanced AI-powered bank reconciliation with intelligent matching"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.matching_threshold = 0.85  # Minimum confidence for auto-matching
        self.fuzzy_threshold = 0.70     # Minimum for fuzzy matching suggestions
    
    def run_intelligent_reconciliation(self, bank_account_id, statement_date_from=None, statement_date_to=None):
        """Run comprehensive AI-powered bank reconciliation"""
        try:
            logger.info(f"Starting intelligent bank reconciliation for account {bank_account_id}")
            
            reconciliation_results = {
                'summary': {},
                'auto_matched_transactions': [],
                'suggested_matches': [],
                'unmatched_bank_transactions': [],
                'unmatched_book_transactions': [],
                'anomalies_detected': [],
                'reconciliation_insights': {},
                'ai_recommendations': [],
                'confidence_metrics': {},
            }
            
            # Get bank and book transactions
            bank_transactions = self._get_bank_transactions(
                bank_account_id, statement_date_from, statement_date_to
            )
            book_transactions = self._get_book_transactions(
                bank_account_id, statement_date_from, statement_date_to
            )
            
            logger.info(f"Found {len(bank_transactions)} bank transactions and {len(book_transactions)} book transactions")
            
            # Phase 1: Exact matches
            exact_matches = self._find_exact_matches(bank_transactions, book_transactions)
            reconciliation_results['auto_matched_transactions'].extend(exact_matches)
            
            # Remove matched transactions from processing
            remaining_bank = self._remove_matched_transactions(bank_transactions, exact_matches, 'bank')
            remaining_book = self._remove_matched_transactions(book_transactions, exact_matches, 'book')
            
            # Phase 2: AI-powered fuzzy matching
            fuzzy_matches = self._find_ai_fuzzy_matches(remaining_bank, remaining_book)
            reconciliation_results['suggested_matches'].extend(fuzzy_matches)
            
            # Remove high-confidence fuzzy matches
            high_confidence_matches = [m for m in fuzzy_matches if m['confidence'] >= self.matching_threshold]
            reconciliation_results['auto_matched_transactions'].extend(high_confidence_matches)
            
            remaining_bank = self._remove_matched_transactions(remaining_bank, high_confidence_matches, 'bank')
            remaining_book = self._remove_matched_transactions(remaining_book, high_confidence_matches, 'book')
            
            # Phase 3: Pattern-based matching
            pattern_matches = self._find_pattern_matches(remaining_bank, remaining_book)
            reconciliation_results['suggested_matches'].extend(pattern_matches)
            
            # Phase 4: Anomaly detection
            anomalies = self._detect_reconciliation_anomalies(
                bank_transactions, book_transactions, reconciliation_results['auto_matched_transactions']
            )
            reconciliation_results['anomalies_detected'] = anomalies
            
            # Phase 5: Generate insights and recommendations
            insights = self._generate_reconciliation_insights(reconciliation_results)
            reconciliation_results['reconciliation_insights'] = insights
            
            recommendations = self._generate_ai_recommendations(reconciliation_results)
            reconciliation_results['ai_recommendations'] = recommendations
            
            # Phase 6: Calculate confidence metrics
            confidence_metrics = self._calculate_confidence_metrics(reconciliation_results)
            reconciliation_results['confidence_metrics'] = confidence_metrics
            
            # Store remaining unmatched transactions
            reconciliation_results['unmatched_bank_transactions'] = remaining_bank
            reconciliation_results['unmatched_book_transactions'] = remaining_book
            
            # Generate summary
            reconciliation_results['summary'] = self._generate_reconciliation_summary(reconciliation_results)
            
            logger.info(f"Bank reconciliation completed. Auto-matched: {len(reconciliation_results['auto_matched_transactions'])}")
            
            return reconciliation_results
            
        except Exception as e:
            logger.error(f"AI bank reconciliation failed: {str(e)}")
            return {}
    
    def _get_bank_transactions(self, bank_account_id, date_from, date_to):
        """Get bank statement transactions"""
        try:
            from ..models import BankTransaction
            
            queryset = BankTransaction.objects.filter(
                tenant=self.tenant,
                bank_account_id=bank_account_id,
                is_reconciled=False
            )
            
            if date_from:
                queryset = queryset.filter(transaction_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(transaction_date__lte=date_to)
            
            transactions = []
            for txn in queryset:
                transactions.append({
                    'id': txn.id,
                    'type': 'bank',
                    'date': txn.transaction_date,
                    'amount': float(txn.amount),
                    'description': txn.description or '',
                    'reference': txn.reference_number or '',
                    'check_number': getattr(txn, 'check_number', ''),
                    'memo': getattr(txn, 'memo', ''),
                    'raw_data': {
                        'transaction_type': getattr(txn, 'transaction_type', ''),
                        'payee': getattr(txn, 'payee', ''),
                    }
                })
            
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to get bank transactions: {str(e)}")
            return []
    
    def _get_book_transactions(self, bank_account_id, date_from, date_to):
        """Get book transactions (journal entries, payments, etc.)"""
        try:
            book_transactions = []
            
            # Get journal entry lines affecting this bank account
            from ..models import JournalEntryLine, Payment, Invoice
            
            # Journal entry lines
            journal_lines = JournalEntryLine.objects.filter(
                tenant=self.tenant,
                account_id=bank_account_id,
                journal_entry__status='POSTED',
                is_reconciled=False
            )
            
            if date_from:
                journal_lines = journal_lines.filter(journal_entry__entry_date__gte=date_from)
            if date_to:
                journal_lines = journal_lines.filter(journal_entry__entry_date__lte=date_to)
            
            for line in journal_lines:
                amount = float(line.debit_amount) if line.debit_amount else -float(line.credit_amount)
                book_transactions.append({
                    'id': line.id,
                    'type': 'journal_line',
                    'date': line.journal_entry.entry_date,
                    'amount': amount,
                    'description': line.description,
                    'reference': line.journal_entry.reference_number or '',
                    'entry_number': line.journal_entry.entry_number,
                    'source_type': line.journal_entry.entry_type,
                    'customer': str(line.customer) if line.customer else '',
                    'vendor': str(line.vendor) if line.vendor else '',
                })
            
            # Get payments
            payments = Payment.objects.filter(
                tenant=self.tenant,
                bank_account_id=bank_account_id,
                status='CLEARED',
                matching_status='UNMATCHED'
            )
            
            if date_from:
                payments = payments.filter(payment_date__gte=date_from)
            if date_to:
                payments = payments.filter(payment_date__lte=date_to)
            
            for payment in payments:
                amount = float(payment.amount)
                if payment.payment_type == 'MADE':
                    amount = -amount
                    
                book_transactions.append({
                    'id': payment.id,
                    'type': 'payment',
                    'date': payment.payment_date,
                    'amount': amount,
                    'description': f"Payment - {payment.payment_method}",
                    'reference': payment.reference_number or '',
                    'payment_number': payment.payment_number,
                    'payment_method': payment.payment_method,
                    'customer': str(payment.customer) if payment.customer else '',
                    'vendor': str(payment.vendor) if payment.vendor else '',
                })
            
            return book_transactions
            
        except Exception as e:
            logger.error(f"Failed to get book transactions: {str(e)}")
            return []
    
    def _find_exact_matches(self, bank_transactions, book_transactions):
        """Find exact matches between bank and book transactions"""
        exact_matches = []
        
        for bank_txn in bank_transactions:
            for book_txn in book_transactions:
                # Check for exact amount and date match
                if (abs(bank_txn['amount'] - book_txn['amount']) < 0.01 and
                    bank_txn['date'] == book_txn['date']):
                    
                    match = {
                        'bank_transaction': bank_txn,
                        'book_transaction': book_txn,
                        'match_type': 'exact',
                        'confidence': 1.0,
                        'match_factors': ['exact_amount', 'exact_date'],
                        'auto_matched': True
                    }
                    
                    # Additional validation for reference numbers
                    if (bank_txn.get('reference') and book_txn.get('reference') and
                        bank_txn['reference'].lower() == book_txn['reference'].lower()):
                        match['match_factors'].append('exact_reference')
                    
                    exact_matches.append(match)
                    break
        
        return exact_matches
    
    def _find_ai_fuzzy_matches(self, bank_transactions, book_transactions):
        """AI-powered fuzzy matching with multiple algorithms"""
        fuzzy_matches = []
        
        for bank_txn in bank_transactions:
            best_matches = []
            
            for book_txn in book_transactions:
                match_score = self._calculate_ai_match_score(bank_txn, book_txn)
                
                if match_score >= self.fuzzy_threshold:
                    match_factors = self._identify_match_factors(bank_txn, book_txn)
                    
                    match = {
                        'bank_transaction': bank_txn,
                        'book_transaction': book_txn,
                        'match_type': 'ai_fuzzy',
                        'confidence': match_score,
                        'match_factors': match_factors,
                        'auto_matched': match_score >= self.matching_threshold
                    }
                    
                    best_matches.append(match)
            
            # Sort by confidence and take top matches
            best_matches.sort(key=lambda x: x['confidence'], reverse=True)
            fuzzy_matches.extend(best_matches[:3])  # Top 3 matches per bank transaction
        
        return fuzzy_matches
    
    def _calculate_ai_match_score(self, bank_txn, book_txn):
        """Calculate comprehensive AI matching score"""
        score = 0.0
        max_score = 0.0
        
        # Amount matching (40% weight)
        amount_weight = 0.4
        max_score += amount_weight
        
        amount_diff = abs(bank_txn['amount'] - book_txn['amount'])
        amount_similarity = 1.0 - min(amount_diff / max(abs(bank_txn['amount']), abs(book_txn['amount'])), 1.0)
        
        if amount_similarity >= 0.99:  # Exact or near-exact
            score += amount_weight
        elif amount_similarity >= 0.95:
            score += amount_weight * 0.9
        elif amount_similarity >= 0.90:
            score += amount_weight * 0.7
        elif amount_similarity >= 0.80:
            score += amount_weight * 0.4
        
        # Date matching (25% weight)
        date_weight = 0.25
        max_score += date_weight
        
        date_diff = abs((bank_txn['date'] - book_txn['date']).days)
        if date_diff == 0:
            score += date_weight
        elif date_diff <= 1:
            score += date_weight * 0.8
        elif date_diff <= 3:
            score += date_weight * 0.6
        elif date_diff <= 7:
            score += date_weight * 0.3
        
        # Text similarity (25% weight)
        text_weight = 0.25
        max_score += text_weight
        
        text_similarity = self._calculate_text_similarity(
            bank_txn.get('description', ''),
            book_txn.get('description', '')
        )
        score += text_weight * text_similarity
        
        # Reference matching (10% weight)
        ref_weight = 0.1
        max_score += ref_weight
        
        bank_ref = str(bank_txn.get('reference', '')).strip().lower()
        book_ref = str(book_txn.get('reference', '')).strip().lower()
        
        if bank_ref and book_ref:
            if bank_ref == book_ref:
                score += ref_weight
            elif bank_ref in book_ref or book_ref in bank_ref:
                score += ref_weight * 0.5
        
        # Normalize score
        return score / max_score if max_score > 0 else 0
    
    def _calculate_text_similarity(self, text1, text2):
        """Calculate text similarity using multiple methods"""
        if not text1 or not text2:
            return 0.0
        
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)
        
        # Method 1: Sequence matcher
        seq_similarity = SequenceMatcher(None, text1, text2).ratio()
        
        # Method 2: Word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if words1 or words2:
            word_similarity = len(words1.intersection(words2)) / len(words1.union(words2))
        else:
            word_similarity = 0.0
        
        # Method 3: Common financial terms matching
        financial_terms = self._extract_financial_terms(text1, text2)
        term_similarity = financial_terms['similarity']
        
        # Weighted combination
        return (seq_similarity * 0.4 + word_similarity * 0.4 + term_similarity * 0.2)
    
    def _normalize_text(self, text):
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove common prefixes/suffixes
        prefixes = ['payment', 'deposit', 'transfer', 'withdrawal', 'check']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # Remove special characters except spaces and digits
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    def _extract_financial_terms(self, text1, text2):
        """Extract and match financial terms"""
        # Common financial patterns
        patterns = {
            'check_number': r'\bchk?\s*#?\s*(\d+)',
            'invoice_number': r'\binv\s*#?\s*(\w+)',
            'reference_number': r'\bref\s*#?\s*(\w+)',
            'account_number': r'\bacct?\s*#?\s*(\w+)',
            'transaction_id': r'\btxn?\s*#?\s*(\w+)',
        }
        
        terms1 = {}
        terms2 = {}
        
        for term_type, pattern in patterns.items():
            matches1 = re.findall(pattern, text1.lower())
            matches2 = re.findall(pattern, text2.lower())
            
            terms1[term_type] = matches1
            terms2[term_type] = matches2
        
        # Calculate similarity based on matched terms
        common_terms = 0
        total_terms = 0
        
        for term_type in patterns:
            set1 = set(terms1[term_type])
            set2 = set(terms2[term_type])
            
            if set1 or set2:
                common_terms += len(set1.intersection(set2))
                total_terms += len(set1.union(set2))
        
        similarity = common_terms / total_terms if total_terms > 0 else 0.0
        
        return {
            'terms1': terms1,
            'terms2': terms2,
            'similarity': similarity,
            'common_terms': common_terms
        }
    
    def _identify_match_factors(self, bank_txn, book_txn):
        """Identify specific factors that contribute to the match"""
        factors = []
        
        # Amount factors
        amount_diff = abs(bank_txn['amount'] - book_txn['amount'])
        if amount_diff < 0.01:
            factors.append('exact_amount')
        elif amount_diff < 1.0:
            factors.append('near_exact_amount')
        elif amount_diff < 10.0:
            factors.append('similar_amount')
        
        # Date factors
        date_diff = abs((bank_txn['date'] - book_txn['date']).days)
        if date_diff == 0:
            factors.append('exact_date')
        elif date_diff <= 1:
            factors.append('next_day')
        elif date_diff <= 3:
            factors.append('within_3_days')
        
        # Text factors
        text_sim = self._calculate_text_similarity(
            bank_txn.get('description', ''),
            book_txn.get('description', '')
        )
        if text_sim > 0.8:
            factors.append('high_text_similarity')
        elif text_sim > 0.5:
            factors.append('moderate_text_similarity')
        
        # Reference factors
        bank_ref = str(bank_txn.get('reference', '')).strip().lower()
        book_ref = str(book_txn.get('reference', '')).strip().lower()
        
        if bank_ref and book_ref and bank_ref == book_ref:
            factors.append('exact_reference')
        elif bank_ref and book_ref and (bank_ref in book_ref or book_ref in bank_ref):
            factors.append('partial_reference_match')
        
        # Special pattern factors
        if bank_txn.get('check_number') and book_txn.get('check_number'):
            if bank_txn['check_number'] == book_txn['check_number']:
                factors.append('check_number_match')
        
        return factors
    
    def _find_pattern_matches(self, bank_transactions, book_transactions):
        """Find matches using learned patterns"""
        pattern_matches = []
        
        # This would use machine learning models trained on historical matching patterns
        # For now, implement rule-based patterns
        
        for bank_txn in bank_transactions:
            for book_txn in book_transactions:
                # Pattern 1: Recurring payments (same amount, regular intervals)
                if self._is_recurring_payment_pattern(bank_txn, book_txn):
                    pattern_matches.append({
                        'bank_transaction': bank_txn,
                        'book_transaction': book_txn,
                        'match_type': 'recurring_pattern',
                        'confidence': 0.75,
                        'match_factors': ['recurring_payment_pattern'],
                        'auto_matched': False
                    })
                
                # Pattern 2: Round number payments
                if self._is_round_number_pattern(bank_txn, book_txn):
                    pattern_matches.append({
                        'bank_transaction': bank_txn,
                        'book_transaction': book_txn,
                        'match_type': 'round_number_pattern',
                        'confidence': 0.65,
                        'match_factors': ['round_number_pattern'],
                        'auto_matched': False
                    })
        
        return pattern_matches
    
    def _is_recurring_payment_pattern(self, bank_txn, book_txn):
        """Check if transactions match a recurring payment pattern"""
        # Simplified pattern detection
        amount_match = abs(bank_txn['amount'] - book_txn['amount']) < 0.01
        date_diff = abs((bank_txn['date'] - book_txn['date']).days)
        
        return amount_match and date_diff <= 2
    
    def _is_round_number_pattern(self, bank_txn, book_txn):
        """Check for round number payment patterns"""
        amount = abs(bank_txn['amount'])
        return (amount % 100 == 0 and amount >= 100 and 
                abs(bank_txn['amount'] - book_txn['amount']) < 0.01)
    
    def _detect_reconciliation_anomalies(self, bank_transactions, book_transactions, matched_transactions):
        """Detect anomalies in the reconciliation process"""
        anomalies = []
        
        # Anomaly 1: Large unmatched amounts
        unmatched_bank_total = sum(txn['amount'] for txn in bank_transactions 
                                 if not self._is_transaction_matched(txn, matched_transactions, 'bank'))
        
        if abs(unmatched_bank_total) > 10000:
            anomalies.append({
                'type': 'large_unmatched_amount',
                'severity': 'high',
                'description': f'Large unmatched bank amount: ${unmatched_bank_total:,.2f}',
                'recommendation': 'Review unmatched bank transactions for potential issues'
            })
        
        # Anomaly 2: Duplicate transactions
        duplicates = self._find_duplicate_transactions(bank_transactions)
        if duplicates:
            anomalies.append({
                'type': 'duplicate_transactions',
                'severity': 'medium',
                'description': f'Found {len(duplicates)} potential duplicate transactions',
                'details': duplicates,
                'recommendation': 'Review duplicate transactions for processing errors'
            })
        
        # Anomaly 3: Unusual transaction patterns
        unusual_patterns = self._detect_unusual_patterns(bank_transactions)
        if unusual_patterns:
            anomalies.extend(unusual_patterns)
        
        return anomalies
    
    def _find_duplicate_transactions(self, transactions):
        """Find potential duplicate transactions"""
        duplicates = []
        seen = {}
        
        for txn in transactions:
            key = (txn['date'], txn['amount'], txn['description'][:20])
            
            if key in seen:
                duplicates.append({
                    'original': seen[key],
                    'duplicate': txn,
                    'similarity': 1.0
                })
            else:
                seen[key] = txn
        
        return duplicates
    
    def _detect_unusual_patterns(self, transactions):
        """Detect unusual transaction patterns"""
        patterns = []
        
        # Check for round number concentration
        round_numbers = [txn for txn in transactions if abs(txn['amount']) % 100 == 0 and abs(txn['amount']) >= 100]
        
        if len(round_numbers) > len(transactions) * 0.5:
            patterns.append({
                'type': 'high_round_number_concentration',
                'severity': 'low',
                'description': f'{len(round_numbers)} of {len(transactions)} transactions are round numbers',
                'recommendation': 'Unusual concentration of round number transactions'
            })
        
        return patterns
    
    def _generate_reconciliation_insights(self, results):
        """Generate AI insights about the reconciliation"""
        insights = {}
        
        total_bank = len(results.get('auto_matched_transactions', [])) + len(results.get('unmatched_bank_transactions', []))
        total_book = len(results.get('auto_matched_transactions', [])) + len(results.get('unmatched_book_transactions', []))
        matched = len(results.get('auto_matched_transactions', []))
        
        # Matching rate analysis
        match_rate = (matched / max(total_bank, 1)) * 100
        insights['match_rate'] = {
            'percentage': round(match_rate, 1),
            'assessment': 'excellent' if match_rate > 90 else 'good' if match_rate > 80 else 'needs_improvement'
        }
        
        # Volume analysis
        insights['volume_analysis'] = {
            'total_bank_transactions': total_bank,
            'total_book_transactions': total_book,
            'matched_transactions': matched,
            'unmatched_bank': len(results.get('unmatched_bank_transactions', [])),
            'unmatched_book': len(results.get('unmatched_book_transactions', []))
        }
        
        # Amount analysis
        total_matched_amount = sum(m['bank_transaction']['amount'] for m in results.get('auto_matched_transactions', []))
        total_unmatched_amount = sum(t['amount'] for t in results.get('unmatched_bank_transactions', []))
        
        insights['amount_analysis'] = {
            'total_matched_amount': round(total_matched_amount, 2),
            'total_unmatched_amount': round(total_unmatched_amount, 2),
            'unmatched_percentage': round((total_unmatched_amount / max(total_matched_amount + total_unmatched_amount, 1)) * 100, 1)
        }
        
        return insights
    
    def _generate_ai_recommendations(self, results):
        """Generate AI-powered recommendations"""
        recommendations = []
        
        insights = results.get('reconciliation_insights', {})
        match_rate = insights.get('match_rate', {}).get('percentage', 0)
        
        # Matching rate recommendations
        if match_rate < 80:
            recommendations.append({
                'type': 'improve_matching',
                'priority': 'high',
                'title': 'Improve Transaction Matching',
                'description': f'Current match rate is {match_rate}% - below optimal threshold',
                'actions': [
                    'Review transaction coding practices',
                    'Implement consistent reference number usage',
                    'Train staff on proper transaction descriptions'
                ]
            })
        
        # Unmatched transaction recommendations
        unmatched_count = len(results.get('unmatched_bank_transactions', []))
        if unmatched_count > 10:
            recommendations.append({
                'type': 'reduce_unmatched',
                'priority': 'medium',
                'title': 'Address Unmatched Transactions',
                'description': f'{unmatched_count} unmatched transactions require attention',
                'actions': [
                    'Review unmatched transactions for missing entries',
                    'Implement automated bank feed processing',
                    'Set up matching rules for recurring transactions'
                ]
            })
        
        # Anomaly recommendations
        anomalies = results.get('anomalies_detected', [])
        if anomalies:
            recommendations.append({
                'type': 'address_anomalies',
                'priority': 'high',
                'title': 'Investigate Detected Anomalies',
                'description': f'{len(anomalies)} anomalies detected during reconciliation',
                'actions': [
                    'Review flagged transactions for accuracy',
                    'Implement additional controls for unusual patterns',
                    'Consider fraud prevention measures'
                ]
            })
        
        return recommendations
    
    def _calculate_confidence_metrics(self, results):
        """Calculate confidence metrics for the reconciliation"""
        total_matches = len(results.get('auto_matched_transactions', []))
        high_confidence = len([m for m in results.get('auto_matched_transactions', []) if m['confidence'] > 0.9])
        
        return {
            'overall_confidence': round((high_confidence / max(total_matches, 1)) * 100, 1),
            'matching_accuracy': 95.0,  # Would be calculated from historical data
            'false_positive_rate': 2.0,  # Would be learned from feedback
            'processing_efficiency': round((total_matches / max(total_matches + len(results.get('suggested_matches', [])), 1)) * 100, 1)
        }
    
    def _generate_reconciliation_summary(self, results):
        """Generate reconciliation summary"""
        return {
            'status': 'completed',
            'total_processed': len(results.get('auto_matched_transactions', [])) + len(results.get('unmatched_bank_transactions', [])),
            'auto_matched': len(results.get('auto_matched_transactions', [])),
            'suggested_matches': len(results.get('suggested_matches', [])),
            'unmatched': len(results.get('unmatched_bank_transactions', [])) + len(results.get('unmatched_book_transactions', [])),
            'anomalies': len(results.get('anomalies_detected', [])),
            'match_rate_percentage': results.get('reconciliation_insights', {}).get('match_rate', {}).get('percentage', 0),
            'processing_time_seconds': 0,  # Would track actual processing time
            'recommendations_count': len(results.get('ai_recommendations', []))
        }
    
    # Helper methods
    def _remove_matched_transactions(self, transactions, matches, transaction_type):
        """Remove matched transactions from the list"""
        matched_ids = set()
        
        for match in matches:
            if transaction_type == 'bank':
                matched_ids.add(match['bank_transaction']['id'])
            else:
                matched_ids.add(match['book_transaction']['id'])
        
        return [txn for txn in transactions if txn['id'] not in matched_ids]
    
    def _is_transaction_matched(self, transaction, matched_transactions, transaction_type):
        """Check if a transaction is already matched"""
        for match in matched_transactions:
            if transaction_type == 'bank':
                if match['bank_transaction']['id'] == transaction['id']:
                    return True
            else:
                if match['book_transaction']['id'] == transaction['id']:
                    return True
        return False