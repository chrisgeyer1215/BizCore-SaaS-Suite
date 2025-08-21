# apps/inventory/tests/management/commands/test_run_tests.py
import pytest
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.test.utils import override_settings
from io import StringIO
import sys
import subprocess
import coverage
import os

class Command(BaseCommand):
    """
    Advanced test runner with comprehensive reporting and CI/CD integration.
    
    Usage:
        python manage.py run_tests [options]
    """
    
    help = 'Run comprehensive test suite with reporting'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--coverage',
            action='store_true',
            help='Generate coverage report'
        )
        
        parser.add_argument(
            '--performance',
            action='store_true',
            help='Run performance tests'
        )
        
        parser.add_argument(
            '--ml',
            action='store_true',
            help='Run ML-specific tests'
        )
        
        parser.add_argument(
            '--integration',
            action='store_true',
            help='Run integration tests'
        )
        
        parser.add_argument(
            '--unit',
            action='store_true',
            help='Run unit tests only'
        )
        
        parser.add_argument(
            '--fast',
            action='store_true',
            help='Run fast tests only (exclude slow tests)'
        )
        
        parser.add_argument(
            '--parallel',
            type=int,
            default=4,
            help='Number of parallel processes (default: 4)'
        )
        
        parser.add_argument(
            '--output-dir',
            default='test-results',
            help='Output directory for test results'
        )
        
        parser.add_argument(
            '--format',
            choices=['junit', 'html', 'json', 'console'],
            default='console',
            help='Output format for test results'
        )
        
        parser.add_argument(
            '--benchmark',
            action='store_true',
            help='Run benchmark tests and generate performance report'
        )
        
        parser.add_argument(
            '--failfast',
            action='store_true',
            help='Stop on first test failure'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        """Execute test suite with specified options."""
        self.stdout.write(
            self.style.SUCCESS('🧪 Starting Comprehensive Test Suite')
        )
        
        # Create output directory
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Build pytest arguments
        pytest_args = self._build_pytest_args(options)
        
        # Initialize coverage if requested
        if options['coverage']:
            cov = coverage.Coverage()
            cov.start()
        
        try:
            # Run tests
            test_results = self._run_tests(pytest_args, options)
            
            # Generate reports
            self._generate_reports(test_results, options)
            
            # Performance benchmarks
            if options['benchmark']:
                self._run_benchmarks(options)
            
            # Coverage report
            if options['coverage']:
                cov.stop()
                cov.save()
                self._generate_coverage_report(cov, options)
            
            self.stdout.write(
                self.style.SUCCESS('✅ Test Suite Completed Successfully')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Test Suite Failed: {str(e)}')
            )
            sys.exit(1)
    
    def _build_pytest_args(self, options):
        """Build pytest command arguments."""
        args = []
        
        # Test selection
        if options['unit']:
            args.extend(['-m', 'unit'])
        elif options['integration']:
            args.extend(['-m', 'integration'])
        elif options['ml']:
            args.extend(['-m', 'ml'])
        elif options['performance']:
            args.extend(['-m', 'performance'])
        
        # Fast tests only
        if options['fast']:
            args.extend(['-m', 'not slow'])
        
        # Parallel execution
        if options['parallel'] > 1:
            args.extend(['-n', str(options['parallel'])])
        
        # Output format
        if options['format'] == 'junit':
            args.extend([
                '--junit-xml', 
                os.path.join(options['output_dir'], 'junit.xml')
            ])
        elif options['format'] == 'html':
            args.extend([
                '--html', 
                os.path.join(options['output_dir'], 'report.html')
            ])
        elif options['format'] == 'json':
            args.extend([
                '--json-report',
                '--json-report-file',
                os.path.join(options['output_dir'], 'report.json')
            ])
        
        # Additional options
        if options['failfast']:
            args.append('-x')
        
        if options['verbose']:
            args.append('-v')
        
        # Coverage options
        if options['coverage']:
            args.extend([
                '--cov=apps/inventory',
                '--cov-report=html',
                f'--cov-report=html:{options["output_dir"]}/coverage_html',
                '--cov-report=xml',
                f'--cov-report=xml:{options["output_dir"]}/coverage.xml',
                '--cov-fail-under=85'
            ])
        
        return args
    
    def _run_tests(self, pytest_args, options):
        """Execute pytest with specified arguments."""
        self.stdout.write('🏃 Running tests...')
        
        # Run pytest
        exit_code = pytest.main(pytest_args)
        
        if exit_code != 0:
            raise Exception(f"Tests failed with exit code {exit_code}")
        
        return {'exit_code': exit_code}
    
    def _generate_reports(self, test_results, options):
        """Generate additional test reports."""
        self.stdout.write('📊 Generating test reports...')
        
        output_dir = options['output_dir']
        
        # Generate test summary
        summary_file = os.path.join(output_dir, 'test_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("Test Execution Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Timestamp: {timezone.now()}\n")
            f.write(f"Exit Code: {test_results['exit_code']}\n")
            f.write(f"Output Directory: {output_dir}\n")
        
        self.stdout.write(f'📄 Test summary saved to {summary_file}')
    
    def _run_benchmarks(self, options):
        """Run performance benchmarks."""
        self.stdout.write('⚡ Running performance benchmarks...')
        
        # Run specific benchmark tests
        benchmark_args = [
            '-m', 'performance',
            '--benchmark-only',
            '--benchmark-json', 
            os.path.join(options['output_dir'], 'benchmarks.json')
        ]
        
        pytest.main(benchmark_args)
        
        self.stdout.write('📈 Benchmark results saved')
    
    def _generate_coverage_report(self, cov, options):
        """Generate coverage reports."""
        self.stdout.write('📋 Generating coverage reports...')
        
        output_dir = options['output_dir']
        
        # Generate HTML coverage report
        html_dir = os.path.join(output_dir, 'coverage_html')
        cov.html_report(directory=html_dir)
        
        # Generate XML coverage report (for CI/CD)
        xml_file = os.path.join(output_dir, 'coverage.xml')
        cov.xml_report(outfile=xml_file)
        
        # Generate console coverage report
        console_output = StringIO()
        cov.report(file=console_output)
        
        # Save console report to file
        console_file = os.path.join(output_dir, 'coverage_console.txt')
        with open(console_file, 'w') as f:
            f.write(console_output.getvalue())
        
        self.stdout.write(f'📊 Coverage reports generated in {output_dir}')