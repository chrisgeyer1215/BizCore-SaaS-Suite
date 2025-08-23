# backend/apps/core/management/commands/run_integration_tests.py
from django.core.management.base import BaseCommand
from django.test.utils import get_runner
from django.conf import settings
import sys

class Command(BaseCommand):
    help = 'Run comprehensive integration tests for SaaS-AICE CRM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--coverage',
            action='store_true',
            help='Run tests with coverage report'
        )
        parser.add_argument(
            '--module',
            type=str,
            help='Run tests for specific module only'
        )
        parser.add_argument(
            '--performance',
            action='store_true',
            help='Include performance benchmark tests'
        )

    def handle(self, *args, **options):
        
        if options['coverage']:
            try:
                import coverage
                cov = coverage.Coverage()
                cov.start()
                self.stdout.write('Running tests with coverage...')
            except ImportError:
                self.stdout.write(
                    self.style.WARNING('Coverage not available. Install with: pip install coverage')
                )
                options['coverage'] = False
        
        # Configure test runner
        test_runner = get_runner(settings)()
        
        # Define test modules
        test_modules = [
            'tests.integration.test_account_integration',
            'tests.integration.test_lead_conversion_integration', 
            'tests.integration.test_campaign_integration',
            'tests.integration.test_cross_module_integration',
            'tests.integration.test_system_health',
        ]
        
        if options['performance']:
            test_modules.append('tests.integration.test_performance')
        
        if options['module']:
            test_modules = [f'tests.integration.test_{options["module"]}_integration']
        
        # Run tests
        self.stdout.write(f'Running integration tests for modules: {", ".join(test_modules)}')
        
        failures = test_runner.run_tests(test_modules)
        
        if options['coverage']:
            cov.stop()
            cov.save()
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write('COVERAGE REPORT')
            self.stdout.write('='*50)
            cov.report()
            
            # Generate HTML coverage report
            cov.html_report(directory='htmlcov')
            self.stdout.write('\nHTML coverage report generated in htmlcov/')
        
        if failures:
            self.stdout.write(
                self.style.ERROR(f'\n{failures} test(s) failed!')
            )
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS('\nAll integration tests passed!')
            )