# backend/apps/finance/apps.py

"""
Finance App Configuration
"""

from django.apps import AppConfig
from django.db.models.signals import post_migrate

class FinanceConfig(AppConfig):
    """Finance application configuration"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = 'Finance & Accounting'
    
    def ready(self):
        """Initialize the finance app"""
        # Import signals
        import apps.finance.signals
        
        # Import tasks for Celery
        import apps.finance.tasks
        
        # Register permissions
        self.register_permissions()
        
        # Connect post_migrate signal
        post_migrate.connect(self.create_default_data, sender=self)
    
    def register_permissions(self):
        """Register finance-specific permissions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        # This will be called when the app is ready
        try:
            # Get or create custom permissions
            finance_permissions = [
                # Module access
                ('view_finance_module', 'Can view finance module'),
                ('manage_finance', 'Can manage finance operations'),
                
                # Chart of Accounts
                ('view_chart_of_accounts', 'Can view chart of accounts'),
                ('manage_chart_of_accounts', 'Can manage chart of accounts'),
                
                # Journal Entries
                ('view_journal_entries', 'Can view journal entries'),
                ('create_journal_entries', 'Can create journal entries'),
                ('edit_journal_entries', 'Can edit journal entries'),
                ('post_journal_entries', 'Can post journal entries'),
                ('reverse_journal_entries', 'Can reverse journal entries'),
                
                # Invoices
                ('view_invoices', 'Can view invoices'),
                ('create_invoices', 'Can create invoices'),
                ('edit_invoices', 'Can edit invoices'),
                ('approve_invoices', 'Can approve invoices'),
                ('send_invoices', 'Can send invoices'),
                ('void_invoices', 'Can void invoices'),
                
                # Bills
                ('view_bills', 'Can view bills'),
                ('manage_bills', 'Can manage bills'),
                ('approve_bills', 'Can approve bills'),
                
                # Payments
                ('view_payments', 'Can view payments'),
                ('create_payments', 'Can create payments'),
                ('apply_payments', 'Can apply payments'),
                ('process_refunds', 'Can process refunds'),
                
                # Bank Reconciliation
                ('view_bank_reconciliation', 'Can view bank reconciliation'),
                ('perform_bank_reconciliation', 'Can perform bank reconciliation'),
                ('auto_match_bank_transactions', 'Can auto-match bank transactions'),
                
                # Financial Reports
                ('view_financial_reports', 'Can view financial reports'),
                ('view_financial_statements', 'Can view financial statements'),
                ('view_aging_reports', 'Can view aging reports'),
                ('view_trial_balance', 'Can view trial balance'),
                
                # Vendors
                ('view_vendors', 'Can view vendors'),
                ('manage_vendors', 'Can manage vendors'),
                
                # Settings
                ('view_finance_settings', 'Can view finance settings'),
                ('manage_finance_settings', 'Can manage finance settings'),
            ]
            
            # Create content type for finance permissions
            content_type, created = ContentType.objects.get_or_create(
                app_label='finance',
                model='financepermission'
            )
            
            for codename, name in finance_permissions:
                Permission.objects.get_or_create(
                    codename=codename,
                    name=name,
                    content_type=content_type
                )
                
        except Exception as e:
            # Permissions will be created after migrations
            pass
    
    def create_default_data(self, sender, **kwargs):
        """Create default finance data after migrations"""
        from django.contrib.auth.models import Group
        
        try:
            # Create default user groups
            finance_groups = [
                ('Finance Manager', [
                    'view_finance_module', 'manage_finance',
                    'view_chart_of_accounts', 'manage_chart_of_accounts',
                    'view_journal_entries', 'create_journal_entries',
                    'edit_journal_entries', 'post_journal_entries',
                    'reverse_journal_entries', 'view_invoices',
                    'create_invoices', 'edit_invoices', 'approve_invoices',
                    'send_invoices', 'void_invoices', 'view_bills',
                    'manage_bills', 'approve_bills', 'view_payments',
                    'create_payments', 'apply_payments', 'process_refunds',
                    'view_bank_reconciliation', 'perform_bank_reconciliation',
                    'auto_match_bank_transactions', 'view_financial_reports',
                    'view_financial_statements', 'view_aging_reports',
                    'view_trial_balance', 'view_vendors', 'manage_vendors',
                    'view_finance_settings', 'manage_finance_settings'
                ]),
                ('Accountant', [
                    'view_finance_module', 'view_chart_of_accounts',
                    'view_journal_entries', 'create_journal_entries',
                    'edit_journal_entries', 'post_journal_entries',
                    'view_invoices', 'create_invoices', 'edit_invoices',
                    'view_bills', 'manage_bills', 'view_payments',
                    'create_payments', 'apply_payments',
                    'view_bank_reconciliation', 'perform_bank_reconciliation',
                    'view_financial_reports', 'view_financial_statements',
                    'view_aging_reports', 'view_trial_balance',
                    'view_vendors', 'manage_vendors'
                ]),
                ('AP Clerk', [
                    'view_finance_module', 'view_bills', 'manage_bills',
                    'view_payments', 'create_payments', 'apply_payments',
                    'view_vendors', 'manage_vendors'
                ]),
                ('AR Clerk', [
                    'view_finance_module', 'view_invoices',
                    'create_invoices', 'edit_invoices', 'send_invoices',
                    'view_payments', 'create_payments', 'apply_payments',
                    'view_aging_reports'
                ]),
                ('Finance Viewer', [
                    'view_finance_module', 'view_chart_of_accounts',
                    'view_journal_entries', 'view_invoices', 'view_bills',
                    'view_payments', 'view_financial_reports',
                    'view_financial_statements', 'view_aging_reports',
                    'view_trial_balance', 'view_vendors'
                ])
            ]
            
            from django.contrib.auth.models import Permission
            
            for group_name, permission_codenames in finance_groups:
                group, created = Group.objects.get_or_create(name=group_name)
                
                if created:
                    # Add permissions to the group
                    permissions = Permission.objects.filter(
                        codename__in=permission_codenames,
                        content_type__app_label='finance'
                    )
                    group.permissions.set(permissions)
                    
        except Exception as e:
            # Groups will be created after migrations complete
            pass