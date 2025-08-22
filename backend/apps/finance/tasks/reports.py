"""
Finance Reports Tasks
Celery tasks for scheduled report generation
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_scheduled_reports(self, tenant_id: int = None):
    """Generate scheduled financial reports for all tenants or specific tenant"""
    try:
        from ..models import ReportSchedule, FinancialReport
        from apps.core.models import Tenant
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()
        
        total_generated = 0
        total_errors = 0
        
        for tenant in tenants:
            try:
                tenant.activate()
                
                # Get due report schedules
                due_schedules = ReportSchedule.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    next_run__lte=timezone.now()
                )
                
                for schedule in due_schedules:
                    try:
                        with transaction.atomic():
                            # Generate the report
                            report = _generate_scheduled_report(schedule)
                            
                            # Update schedule
                            _update_report_schedule(schedule)
                            
                            total_generated += 1
                            logger.info(f"Generated report {report.id} for schedule {schedule.id}")
                            
                    except Exception as e:
                        logger.error(f"Error generating report for schedule {schedule.id}: {str(e)}")
                        total_errors += 1
                        continue
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}")
                total_errors += 1
                continue
        
        logger.info(f"Scheduled report generation completed. Generated: {total_generated}, Errors: {total_errors}")
        return {
            'success': True,
            'total_generated': total_generated,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"Error in generate_scheduled_reports task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _generate_scheduled_report(schedule):
    """Generate a scheduled report"""
    from ..models import FinancialReport, ReportTemplate
    from ..utils.reporting import ReportGenerator
    
    # Get report template
    template = schedule.report_template
    
    # Determine report period
    start_date, end_date = _calculate_report_period(schedule)
    
    # Generate report data based on type
    if schedule.report_type == 'TRIAL_BALANCE':
        report_data = ReportGenerator.generate_trial_balance(end_date)
    elif schedule.report_type == 'BALANCE_SHEET':
        report_data = ReportGenerator.generate_balance_sheet(end_date)
    elif schedule.report_type == 'INCOME_STATEMENT':
        report_data = ReportGenerator.generate_income_statement(start_date, end_date)
    elif schedule.report_type == 'CASH_FLOW':
        report_data = ReportGenerator.generate_cash_flow_statement(start_date, end_date)
    elif schedule.report_type == 'AGING_REPORT':
        report_data = ReportGenerator.generate_aging_report(end_date)
    else:
        # Default to summary report
        report_data = ReportGenerator.generate_summary_report(
            schedule.tenant, start_date, end_date
        )
    
    # Create report record
    report = FinancialReport.objects.create(
        tenant=schedule.tenant,
        name=f"{schedule.name} - {end_date.strftime('%Y-%m-%d')}",
        report_type=schedule.report_type,
        report_data=report_data,
        generated_date=timezone.now(),
        generated_by=schedule.created_by,
        status='COMPLETED'
    )
    
    return report


def _calculate_report_period(schedule):
    """Calculate report period based on schedule frequency"""
    today = date.today()
    
    if schedule.frequency == 'DAILY':
        start_date = today
        end_date = today
    elif schedule.frequency == 'WEEKLY':
        # Week ending on today
        end_date = today
        start_date = today - timedelta(days=today.weekday())
    elif schedule.frequency == 'MONTHLY':
        # Month ending on today
        end_date = today
        start_date = today.replace(day=1)
    elif schedule.frequency == 'QUARTERLY':
        # Quarter ending on today
        quarter = (today.month - 1) // 3
        start_month = quarter * 3 + 1
        end_date = today
        start_date = today.replace(month=start_month, day=1)
    elif schedule.frequency == 'YEARLY':
        # Year ending on today
        end_date = today
        start_date = today.replace(month=1, day=1)
    else:
        # Default to monthly
        end_date = today
        start_date = today.replace(day=1)
    
    return start_date, end_date


def _update_report_schedule(schedule):
    """Update next run date for report schedule"""
    from ..utils.reporting import ReportScheduler
    
    schedule.last_run = timezone.now()
    schedule.next_run = ReportScheduler.get_next_run_date(schedule.frequency, schedule.last_run)
    schedule.last_run_status = 'SUCCESS'
    schedule.save()


@shared_task
def generate_month_end_reports():
    """Generate month-end financial reports for all tenants"""
    try:
        from ..models import FinancialReport
        from apps.core.models import Tenant
        from ..utils.reporting import ReportGenerator
        
        total_generated = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Check if it's month end
                today = date.today()
                tomorrow = today + timedelta(days=1)
                
                if tomorrow.day == 1:  # It's month end
                    # Generate month-end reports
                    month_start = today.replace(day=1)
                    
                    # Trial Balance
                    trial_balance = ReportGenerator.generate_trial_balance(today)
                    FinancialReport.objects.create(
                        tenant=tenant,
                        name=f"Trial Balance - {today.strftime('%B %Y')}",
                        report_type='TRIAL_BALANCE',
                        report_data=trial_balance,
                        generated_date=timezone.now(),
                        status='COMPLETED'
                    )
                    
                    # Income Statement
                    income_statement = ReportGenerator.generate_income_statement(month_start, today)
                    FinancialReport.objects.create(
                        tenant=tenant,
                        name=f"Income Statement - {today.strftime('%B %Y')}",
                        report_type='INCOME_STATEMENT',
                        report_data=income_statement,
                        generated_date=timezone.now(),
                        status='COMPLETED'
                    )
                    
                    total_generated += 2
                    logger.info(f"Generated month-end reports for tenant {tenant.schema_name}")
                
            except Exception as e:
                logger.error(f"Error generating month-end reports for tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Month-end report generation completed. Generated: {total_generated}")
        return {'success': True, 'total_generated': total_generated}
        
    except Exception as e:
        logger.error(f"Error in generate_month_end_reports task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def generate_quarter_end_reports():
    """Generate quarter-end financial reports for all tenants"""
    try:
        from ..models import FinancialReport
        from apps.core.models import Tenant
        from ..utils.reporting import ReportGenerator
        
        total_generated = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Check if it's quarter end
                today = date.today()
                tomorrow = today + timedelta(days=1)
                
                if tomorrow.day == 1 and tomorrow.month in [1, 4, 7, 10]:  # Quarter end
                    # Calculate quarter start
                    quarter = (today.month - 1) // 3
                    quarter_start_month = quarter * 3 + 1
                    quarter_start = today.replace(month=quarter_start_month, day=1)
                    
                    # Generate quarter-end reports
                    income_statement = ReportGenerator.generate_income_statement(quarter_start, today)
                    FinancialReport.objects.create(
                        tenant=tenant,
                        name=f"Quarterly Income Statement - Q{quarter + 1} {today.year}",
                        report_type='INCOME_STATEMENT',
                        report_data=income_statement,
                        generated_date=timezone.now(),
                        status='COMPLETED'
                    )
                    
                    total_generated += 1
                    logger.info(f"Generated quarter-end report for tenant {tenant.schema_name}")
                
            except Exception as e:
                logger.error(f"Error generating quarter-end report for tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Quarter-end report generation completed. Generated: {total_generated}")
        return {'success': True, 'total_generated': total_generated}
        
    except Exception as e:
        logger.error(f"Error in generate_quarter_end_reports task: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_reports():
    """Clean up old financial reports based on retention policy"""
    try:
        from ..models import FinancialReport
        from apps.core.models import Tenant
        
        # Default retention: 7 years
        cutoff_date = date.today() - timedelta(days=7*365)
        total_cleaned = 0
        
        for tenant in Tenant.objects.all():
            try:
                tenant.activate()
                
                # Find old reports
                old_reports = FinancialReport.objects.filter(
                    tenant=tenant,
                    generated_date__date__lt=cutoff_date
                )
                
                # Archive instead of deleting
                for report in old_reports:
                    report.status = 'ARCHIVED'
                    report.notes = f"ARCHIVED - {report.notes or ''}"
                    report.save()
                    total_cleaned += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {total_cleaned} old reports")
        return {'success': True, 'cleaned_up': total_cleaned}
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_reports task: {str(e)}")
        return {'success': False, 'error': str(e)}
