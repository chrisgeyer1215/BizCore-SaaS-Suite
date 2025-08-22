"""
Lead Scoring Calculation Management Command
Batch calculation and recalculation of lead scores with performance optimization.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min

from crm.models.lead_model import Lead, LeadScoringRule
from crm.models.account_model import Account
from crm.models.activity_model import Activity
from crm.services.lead_service import LeadService
from crm.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Calculate and update lead scores with advanced algorithms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--lead-ids',
            type=str,
            help='Comma-separated lead IDs to recalculate',
            default=None
        )
        
        parser.add_argument(
            '--all-leads',
            action='store_true',
            help='Recalculate scores for all leads',
        )
        
        parser.add_argument(
            '--unscored-only',
            action='store_true',
            help='Only calculate scores for leads without scores',
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            help='Number of leads to process in each batch',
            default=100
        )
        
        parser.add_argument(
            '--rules-update',
            action='store_true',
            help='Update scoring rules before calculation',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate scoring without saving results',
        )
        
        parser.add_argument(
            '--since-days',
            type=int,
            help='Only score leads created/modified in last N days',
            default=None
        )
        
        parser.add_argument(
            '--min-score',
            type=int,
            help='Minimum score threshold for processing',
            default=None
        )
        
        parser.add_argument(
            '--max-score',
            type=int,
            help='Maximum score threshold for processing',
            default=None
        )
        
        parser.add_argument(
            '--export-results',
            type=str,
            help='Export scoring results to CSV file',
            default=None
        )

    def handle(self, *args, **options):
        try:
            self.lead_service = LeadService()
            self.scoring_service = ScoringService()
            
            self.calculate_lead_scores(**options)
            
        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            raise CommandError(f'Score calculation failed: {str(e)}')

    def calculate_lead_scores(self, **options):
        """Main scoring orchestrator"""
        self.stdout.write('🎯 Starting lead score calculation...')
        
        # Update scoring rules if requested
        if options['rules_update']:
            self._update_scoring_rules()
        
        # Get leads to process
        leads_queryset = self._get_leads_queryset(options)
        total_leads = leads_queryset.count()
        
        if total_leads == 0:
            self.stdout.write(self.style.WARNING('⚠️ No leads found matching criteria'))
            return
        
        self.stdout.write(f'📊 Found {total_leads:,} leads to process')
        
        # Process in batches
        results = self._process_leads_in_batches(leads_queryset, options)
        
        # Export results if requested
        if options['export_results']:
            self._export_scoring_results(results, options['export_results'])
        
        # Print summary
        self._print_scoring_summary(results, total_leads, options)

    def _get_leads_queryset(self, options: Dict):
        """Build queryset for leads to process"""
        queryset = Lead.objects.select_related('source', 'assigned_to').all()
        
        # Apply specific lead IDs filter
        if options['lead_ids']:
            try:
                lead_ids = [int(id.strip()) for id in options['lead_ids'].split(',')]
                queryset = queryset.filter(id__in=lead_ids)
            except ValueError:
                raise CommandError('Invalid lead IDs format. Use comma-separated integers.')
        
        # Apply unscored filter
        if options['unscored_only']:
            queryset = queryset.filter(Q(score__isnull=True) | Q(score=0))
        
        # Apply date filter
        if options['since_days']:
            since_date = timezone.now() - timedelta(days=options['since_days'])
            queryset = queryset.filter(
                Q(created_at__gte=since_date) | Q(updated_at__gte=since_date)
            )
        
        # Apply score range filters
        if options['min_score'] is not None:
            queryset = queryset.filter(score__gte=options['min_score'])
        
        if options['max_score'] is not None:
            queryset = queryset.filter(score__lte=options['max_score'])
        
        # Exclude converted/unqualified leads unless specifically requested
        if not options['all_leads']:
            queryset = queryset.exclude(status__in=['CONVERTED', 'UNQUALIFIED'])
        
        return queryset.order_by('id')

    def _update_scoring_rules(self):
        """Update and optimize scoring rules"""
        self.stdout.write('🔧 Updating scoring rules...')
        
        # Get current scoring rules
        rules = LeadScoringRule.objects.filter(is_active=True)
        
        for rule in rules:
            try:
                # Analyze rule performance
                rule_performance = self._analyze_rule_performance(rule)
                
                # Auto-adjust weights based on performance
                if rule_performance['accuracy'] < 0.6:
                    # Reduce weight for poor performing rules
                    new_weight = max(0.05, rule.weight * 0.8)
                    rule.weight = Decimal(str(new_weight))
                    rule.save(update_fields=['weight'])
                    
                    self.stdout.write(
                        f'  📉 Reduced weight for rule: {rule.name} '
                        f'(accuracy: {rule_performance["accuracy"]:.2%})'
                    )
                
                elif rule_performance['accuracy'] > 0.85:
                    # Increase weight for high performing rules
                    new_weight = min(0.5, rule.weight * 1.1)
                    rule.weight = Decimal(str(new_weight))
                    rule.save(update_fields=['weight'])
                    
                    self.stdout.write(
                        f'  📈 Increased weight for rule: {rule.name} '
                        f'(accuracy: {rule_performance["accuracy"]:.2%})'
                    )
                
            except Exception as e:
                logger.warning(f"Failed to analyze rule {rule.name}: {str(e)}")
        
        self.stdout.write('✅ Scoring rules updated')

    def _analyze_rule_performance(self, rule: LeadScoringRule) -> Dict:
        """Analyze scoring rule performance"""
        # Get sample of leads with known outcomes
        sample_leads = Lead.objects.filter(
            status__in=['CONVERTED', 'UNQUALIFIED']
        ).select_related('source')[:1000]
        
        correct_predictions = 0
        total_predictions = len(sample_leads)
        
        if total_predictions == 0:
            return {'accuracy': 0.5, 'sample_size': 0}
        
        for lead in sample_leads:
            # Calculate rule score for this lead
            rule_score = self._calculate_single_rule_score(lead, rule)
            
            # Determine if prediction was correct
            is_high_score = rule_score > 25  # Threshold for "good" lead
            was_converted = lead.status == 'CONVERTED'
            
            if (is_high_score and was_converted) or (not is_high_score and not was_converted):
                correct_predictions += 1
        
        accuracy = correct_predictions / total_predictions
        
        return {
            'accuracy': accuracy,
            'sample_size': total_predictions,
            'correct_predictions': correct_predictions
        }

    def _calculate_single_rule_score(self, lead: Lead, rule: LeadScoringRule) -> float:
        """Calculate score for a single rule"""
        try:
            field_value = getattr(lead, rule.field_name, None)
            
            if field_value is None:
                return 0
            
            # Apply rule logic based on type
            if rule.rule_type == 'VALUE_MAPPING':
                return rule.conditions.get(str(field_value), 0)
            
            elif rule.rule_type == 'NUMERIC_RANGE':
                for range_key, score in rule.conditions.items():
                    if self._value_in_range(field_value, range_key):
                        return score
                return 0
            
            elif rule.rule_type == 'DATE_BASED':
                if isinstance(field_value, datetime):
                    days_diff = (timezone.now() - field_value).days
                    
                    for condition, score in rule.conditions.items():
                        if self._days_in_condition(days_diff, condition):
                            return score
                return 0
            
            return 0
            
        except Exception:
            return 0

    def _value_in_range(self, value, range_key: str) -> bool:
        """Check if value falls in specified range"""
        try:
            if '-' in range_key:
                min_val, max_val = range_key.split('-')
                min_val = float(min_val)
                
                if '+' in max_val:
                    return float(value) >= min_val
                else:
                    max_val = float(max_val)
                    return min_val <= float(value) <= max_val
            
            return str(value) == range_key
        except (ValueError, AttributeError):
            return False

    def _days_in_condition(self, days: int, condition: str) -> bool:
        """Check if days value matches condition"""
        try:
            if 'days_since_activity_' in condition:
                range_part = condition.replace('days_since_activity_', '')
                
                if '+' in range_part:
                    min_days = int(range_part.replace('+', ''))
                    return days >= min_days
                elif '_' in range_part:
                    min_days, max_days = range_part.split('_')
                    return int(min_days) <= days <= int(max_days)
            
            return False
        except (ValueError, AttributeError):
            return False

    def _process_leads_in_batches(self, queryset, options: Dict) -> Dict:
        """Process leads in batches for performance"""
        batch_size = options['batch_size']
        total_leads = queryset.count()
        
        results = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'scores_calculated': [],
            'processing_time': 0,
        }
        
        start_time = timezone.now()
        
        for i in range(0, total_leads, batch_size):
            batch = queryset[i:i + batch_size]
            batch_results = self._process_batch(batch, options)
            
            # Accumulate results
            results['processed'] += batch_results['processed']
            results['updated'] += batch_results['updated']
            results['errors'] += batch_results['errors']
            results['scores_calculated'].extend(batch_results['scores_calculated'])
            
            # Progress update
            progress = min(100, (results['processed'] / total_leads) * 100)
            self.stdout.write(
                f'📈 Progress: {progress:.1f}% '
                f'({results["processed"]:,}/{total_leads:,})'
            )
        
        results['processing_time'] = (timezone.now() - start_time).total_seconds()
        return results

    def _process_batch(self, batch, options: Dict) -> Dict:
        """Process a single batch of leads"""
        batch_results = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'scores_calculated': []
        }
        
        if not options['dry_run']:
            with transaction.atomic():
                for lead in batch:
                    try:
                        # Calculate new score
                        old_score = lead.score
                        new_score = self.scoring_service.calculate_lead_score(lead)
                        
                        # Store result for analysis
                        score_result = {
                            'lead_id': lead.id,
                            'email': lead.email,
                            'old_score': float(old_score) if old_score else 0,
                            'new_score': float(new_score),
                            'score_change': float(new_score) - (float(old_score) if old_score else 0),
                            'company': lead.company,
                            'status': lead.status,
                            'source': lead.source.name if lead.source else '',
                        }
                        
                        batch_results['scores_calculated'].append(score_result)
                        
                        # Update lead if score changed significantly
                        if abs(score_result['score_change']) > 1:  # Threshold for update
                            lead.score = new_score
                            lead.save(update_fields=['score', 'updated_at'])
                            batch_results['updated'] += 1
                        
                        batch_results['processed'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing lead {lead.id}: {str(e)}")
                        batch_results['errors'] += 1
        else:
            # Dry run - just calculate without saving
            for lead in batch:
                try:
                    old_score = lead.score
                    new_score = self.scoring_service.calculate_lead_score(lead)
                    
                    score_result = {
                        'lead_id': lead.id,
                        'email': lead.email,
                        'old_score': float(old_score) if old_score else 0,
                        'new_score': float(new_score),
                        'score_change': float(new_score) - (float(old_score) if old_score else 0),
                        'company': lead.company,
                        'status': lead.status,
                        'source': lead.source.name if lead.source else '',
                    }
                    
                    batch_results['scores_calculated'].append(score_result)
                    batch_results['processed'] += 1
                    
                    # Count as "would be updated" for dry run
                    if abs(score_result['score_change']) > 1:
                        batch_results['updated'] += 1
                
                except Exception as e:
                    logger.error(f"Error calculating score for lead {lead.id}: {str(e)}")
                    batch_results['errors'] += 1
        
        return batch_results

    def _export_scoring_results(self, results: Dict, export_path: str):
        """Export scoring results to CSV"""
        import csv
        
        with open(export_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'lead_id', 'email', 'company', 'status', 'source',
                'old_score', 'new_score', 'score_change', 'score_category'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for score_data in results['scores_calculated']:
                # Add score category
                new_score = score_data['new_score']
                if new_score >= 80:
                    category = 'Hot'
                elif new_score >= 60:
                    category = 'Warm'
                elif new_score >= 40:
                    category = 'Cold'
                else:
                    category = 'Poor'
                
                row = {
                    **score_data,
                    'score_category': category
                }
                
                writer.writerow(row)
        
        self.stdout.write(f'💾 Scoring results exported to: {export_path}')

    def _print_scoring_summary(self, results: Dict, total_leads: int, options: Dict):
        """Print comprehensive scoring summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🎯 SCORING SUMMARY')
        self.stdout.write('='*60)
        
        # Basic stats
        self.stdout.write(f'Total Leads Processed: {results["processed"]:,}')
        self.stdout.write(f'Leads Updated: {results["updated"]:,}')
        self.stdout.write(f'Errors: {results["errors"]:,}')
        self.stdout.write(f'Processing Time: {results["processing_time"]:.1f} seconds')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No changes were saved'))
        
        # Score analysis
        if results['scores_calculated']:
            scores = [r['new_score'] for r in results['scores_calculated']]
            score_changes = [r['score_change'] for r in results['scores_calculated']]
            
            self.stdout.write('\n📊 Score Analysis:')
            self.stdout.write(f'  Average Score: {sum(scores) / len(scores):.1f}')
            self.stdout.write(f'  Highest Score: {max(scores):.1f}')
            self.stdout.write(f'  Lowest Score: {min(scores):.1f}')
            self.stdout.write(f'  Average Change: {sum(score_changes) / len(score_changes):.1f}')
            
            # Score distribution
            hot_leads = len([s for s in scores if s >= 80])
            warm_leads = len([s for s in scores if 60 <= s < 80])
            cold_leads = len([s for s in scores if 40 <= s < 60])
            poor_leads = len([s for s in scores if s < 40])
            
            self.stdout.write('\n🌡️ Score Distribution:')
            self.stdout.write(f'  🔥 Hot (80+): {hot_leads:,} ({hot_leads/len(scores)*100:.1f}%)')
            self.stdout.write(f'  🔶 Warm (60-79): {warm_leads:,} ({warm_leads/len(scores)*100:.1f}%)')
            self.stdout.write(f'  ❄️ Cold (40-59): {cold_leads:,} ({cold_leads/len(scores)*100:.1f}%)')
            self.stdout.write(f'  📉 Poor (<40): {poor_leads:,} ({poor_leads/len(scores)*100:.1f}%)')
            
            # Top scoring leads
            top_leads = sorted(
                results['scores_calculated'], 
                key=lambda x: x['new_score'], 
                reverse=True
            )[:5]
            
            self.stdout.write('\n🏆 Top Scoring Leads:')
            for i, lead in enumerate(top_leads, 1):
                self.stdout.write(
                    f'  {i}. {lead["email"]} - {lead["company"]} '
                    f'(Score: {lead["new_score"]:.1f})'
                )
            
            # Biggest improvements
            biggest_improvements = sorted(
                results['scores_calculated'],
                key=lambda x: x['score_change'],
                reverse=True
            )[:3]
            
            if any(imp['score_change'] > 0 for imp in biggest_improvements):
                self.stdout.write('\n📈 Biggest Score Improvements:')
                for i, lead in enumerate(biggest_improvements, 1):
                    if lead['score_change'] > 0:
                        self.stdout.write(
                            f'  {i}. {lead["email"]} '
                            f'(+{lead["score_change"]:.1f} points)'
                        )
        
        self.stdout.write('='*60)
        
        if results['errors'] == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Scoring completed successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ Scoring completed with {results["errors"]} errors'
                )
            )
        
        # Recommendations
        if results['scores_calculated']:
            self.stdout.write('\n💡 Recommendations:')
            
            if hot_leads > 0:
                self.stdout.write(f'  🎯 Focus on {hot_leads} hot leads for immediate conversion')
            
            if poor_leads > len(scores) * 0.3:  # More than 30% poor leads
                self.stdout.write('  📋 Consider reviewing lead sources - many poor quality leads')
            
            if sum(abs(c) for c in score_changes) / len(score_changes) > 10:
                self.stdout.write('  🔄 Significant score changes detected - review scoring rules')