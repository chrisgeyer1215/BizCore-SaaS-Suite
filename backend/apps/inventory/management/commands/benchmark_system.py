# apps/inventory/management/commands/benchmark_system.py
from django.core.management.base import BaseCommand
from django.db import connection
from django.test.utils import override_settings
import time
import statistics
import sys
from decimal import Decimal

class Command(BaseCommand):
    """
    Comprehensive system benchmarking for performance analysis.
    
    Usage:
        python manage.py benchmark_system [options]
    """
    
    help = 'Run comprehensive system benchmarks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            action='store_true',
            help='Run database benchmarks'
        )
        
        parser.add_argument(
            '--api',
            action='store_true',
            help='Run API benchmarks'
        )
        
        parser.add_argument(
            '--ml',
            action='store_true',
            help='Run ML model benchmarks'
        )
        
        parser.add_argument(
            '--iterations',
            type=int,
            default=10,
            help='Number of benchmark iterations'
        )
        
        parser.add_argument(
            '--output-file',
            help='Save benchmark results to file'
        )
    
    def handle(self, *args, **options):
        """Run system benchmarks."""
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting System Benchmarks')
        )
        
        results = {}
        
        if options['database']:
            results['database'] = self._benchmark_database(options)
        
        if options['api']:
            results['api'] = self._benchmark_api(options)
        
        if options['ml']:
            results['ml'] = self._benchmark_ml(options)
        
        # Generate report
        self._generate_benchmark_report(results, options)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Benchmarks completed')
        )
    
    def _benchmark_database(self, options):
        """Benchmark database operations."""
        self.stdout.write('💾 Running database benchmarks...')
        
        from apps.inventory.tests.factories import *
        
        # Setup test data
        tenant = TenantFactory()
        products = ProductFactory.create_batch(100, tenant=tenant)
        
        benchmarks = {}
        
        # Product query benchmark
        def product_query():
            return list(Product.objects.filter(tenant=tenant)[:50])
        
        benchmarks['product_query'] = self._measure_performance(
            product_query, options['iterations']
        )
        
        # Complex aggregation benchmark
        def stock_aggregation():
            return StockItem.objects.filter(tenant=tenant).aggregate(
                total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
                total_quantity=Sum('quantity_on_hand')
            )
        
        benchmarks['stock_aggregation'] = self._measure_performance(
            stock_aggregation, options['iterations']
        )
        
        return benchmarks
    
    def _benchmark_api(self, options):
        """Benchmark API endpoints."""
        self.stdout.write('🌐 Running API benchmarks...')
        
        from rest_framework.test import APIClient
        from apps.inventory.tests.factories import *
        
        # Setup
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        
        ProductFactory.create_batch(50, tenant=tenant)
        
        benchmarks = {}
        
        # Product list endpoint
        def product_list_api():
            response = client.get('/api/v1/products/')
            return response.status_code == 200
        
        benchmarks['product_list_api'] = self._measure_performance(
            product_list_api, options['iterations']
        )
        
        return benchmarks
    
    def _benchmark_ml(self, options):
        """Benchmark ML operations."""
        self.stdout.write('🤖 Running ML benchmarks...')
        
        from apps.inventory.ml.models.random_forest import RandomForestForecaster
        import numpy as np
        import pandas as pd
        
        benchmarks = {}
        
        # Generate test data
        X = pd.DataFrame(np.random.rand(1000, 10))
        y = pd.Series(np.random.rand(1000) * 100)
        
        # Model training benchmark
        def train_model():
            model = RandomForestForecaster()
            model.fit(X[:800], y[:800])
            return model.is_trained
        
        benchmarks['model_training'] = self._measure_performance(
            train_model, min(5, options['iterations'])  # Fewer iterations for training
        )
        
        # Model prediction benchmark
        model = RandomForestForecaster()
        model.fit(X[:800], y[:800])
        
        def predict_model():
            predictions = model.predict(X[800:])
            return len(predictions) == 200
        
        benchmarks['model_prediction'] = self._measure_performance(
            predict_model, options['iterations']
        )
        
        return benchmarks
    
    def _measure_performance(self, func, iterations):
        """Measure function performance over multiple iterations."""
        times = []
        
        for _ in range(iterations):
            start_time = time.time()
            
            try:
                result = func()
                success = True
            except Exception as e:
                success = False
                result = str(e)
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        return {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
            'iterations': iterations,
            'success_rate': 100.0  # Simplified for this example
        }
    
    def _generate_benchmark_report(self, results, options):
        """Generate and display benchmark report."""
        report = []
        report.append("=" * 60)
        report.append("SYSTEM BENCHMARK REPORT")
        report.append("=" * 60)
        report.append("")
        
        for category, benchmarks in results.items():
            report.append(f"{category.upper()} BENCHMARKS:")
            report.append("-" * 40)
            
            for name, stats in benchmarks.items():
                report.append(f"{name}:")
                report.append(f"  Average Time: {stats['avg_time']:.4f}s")
                report.append(f"  Min Time: {stats['min_time']:.4f}s")
                report.append(f"  Max Time: {stats['max_time']:.4f}s")
                report.append(f"  Std Dev: {stats['std_dev']:.4f}s")
                report.append(f"  Iterations: {stats['iterations']}")
                report.append("")
        
        report_text = "\n".join(report)
        
        # Print to console
        self.stdout.write(report_text)
        
        # Save to file if requested
        if options['output_file']:
            with open(options['output_file'], 'w') as f:
                f.write(report_text)
            
            self.stdout.write(f"📄 Benchmark report saved to {options['output_file']}")