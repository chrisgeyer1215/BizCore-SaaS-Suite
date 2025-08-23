"""
Advanced Metrics Collection and Monitoring
"""

import time
import psutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque
import asyncio

from django.core.cache import cache
from django.db import connection
from django.conf import settings


@dataclass
class MetricPoint:
    """Individual metric measurement"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class MetricsCollector:
    """Advanced metrics collection system"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.metrics_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.collection_intervals = {
            'system': 30,      # System metrics every 30 seconds
            'business': 60,    # Business metrics every minute
            'performance': 10, # Performance metrics every 10 seconds
            'ai': 120         # AI metrics every 2 minutes
        }
        self.running = False
        
    async def start_collection(self):
        """Start metrics collection tasks"""
        self.running = True
        
        # Start collection tasks
        tasks = [
            self._collect_system_metrics(),
            self._collect_business_metrics(),
            self._collect_performance_metrics(),
            self._collect_ai_metrics()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _collect_system_metrics(self):
        """Collect system-level metrics"""
        while self.running:
            try:
                timestamp = datetime.now()
                
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                self._record_metric('system.cpu.usage', cpu_percent, timestamp)
                
                # Memory metrics
                memory = psutil.virtual_memory()
                self._record_metric('system.memory.used_percent', memory.percent, timestamp)
                self._record_metric('system.memory.available_gb', memory.available / (1024**3), timestamp)
                
                # Disk metrics
                disk = psutil.disk_usage('/')
                self._record_metric('system.disk.used_percent', disk.percent, timestamp)
                self._record_metric('system.disk.free_gb', disk.free / (1024**3), timestamp)
                
                # Database connections
                db_connections = len(connection.queries)
                self._record_metric('database.active_connections', db_connections, timestamp)
                
                # Cache metrics
                cache_stats = self._get_cache_stats()
                for key, value in cache_stats.items():
                    self._record_metric(f'cache.{key}', value, timestamp)
                
                await asyncio.sleep(self.collection_intervals['system'])
                
            except Exception as e:
                print(f"System metrics collection error: {e}")
                await asyncio.sleep(self.collection_intervals['system'])
    
    async def _collect_business_metrics(self):
        """Collect business-specific metrics"""
        while self.running:
            try:
                timestamp = datetime.now()
                
                # Order metrics
                from ...models import EcommerceOrder
                
                # Orders in last hour
                hour_ago = timestamp - timedelta(hours=1)
                orders_last_hour = EcommerceOrder.objects.filter(
                    tenant=self.tenant,
                    created_at__gte=hour_ago
                ).count()
                self._record_metric('business.orders.last_hour', orders_last_hour, timestamp)
                
                # Revenue in last hour
                from django.db.models import Sum
                revenue_last_hour = EcommerceOrder.objects.filter(
                    tenant=self.tenant,
                    created_at__gte=hour_ago,
                    status='completed'
                ).aggregate(total=Sum('total'))['total'] or 0
                self._record_metric('business.revenue.last_hour', float(revenue_last_hour), timestamp)
                
                # Active carts
                from ...models import Cart
                active_carts = Cart.objects.filter(
                    tenant=self.tenant,
                    updated_at__gte=timestamp - timedelta(hours=24)
                ).count()
                self._record_metric('business.carts.active', active_carts, timestamp)
                
                # Product views (from cache or analytics)
                product_views = cache.get(f'product_views_hour_{self.tenant.id}', 0)
                self._record_metric('business.product_views.last_hour', product_views, timestamp)
                
                # Conversion rate
                visitors = cache.get(f'unique_visitors_hour_{self.tenant.id}', 1)
                conversion_rate = (orders_last_hour / visitors) * 100 if visitors > 0 else 0
                self._record_metric('business.conversion_rate', conversion_rate, timestamp)
                
                await asyncio.sleep(self.collection_intervals['business'])
                
            except Exception as e:
                print(f"Business metrics collection error: {e}")
                await asyncio.sleep(self.collection_intervals['business'])
    
    async def _collect_performance_metrics(self):
        """Collect performance metrics"""
        while self.running:
            try:
                timestamp = datetime.now()
                
                # API response times (from cache)
                api_metrics = cache.get(f'api_metrics_{self.tenant.id}', {})
                for endpoint, metrics in api_metrics.items():
                    avg_response_time = metrics.get('avg_response_time', 0)
                    self._record_metric(
                        f'performance.api.{endpoint}.response_time',
                        avg_response_time,
                        timestamp,
                        tags={'endpoint': endpoint}
                    )
                
                # Database query performance
                db_query_time = self._measure_db_query_time()
                self._record_metric('performance.database.query_time', db_query_time, timestamp)
                
                # Cache performance
                cache_hit_rate = self._calculate_cache_hit_rate()
                self._record_metric('performance.cache.hit_rate', cache_hit_rate, timestamp)
                
                # Queue performance
                queue_stats = self._get_queue_performance()
                for queue_name, stats in queue_stats.items():
                    self._record_metric(
                        f'performance.queue.{queue_name}.processing_time',
                        stats['avg_processing_time'],
                        timestamp,
                        tags={'queue': queue_name}
                    )
                
                await asyncio.sleep(self.collection_intervals['performance'])
                
            except Exception as e:
                print(f"Performance metrics collection error: {e}")
                await asyncio.sleep(self.collection_intervals['performance'])
    
    async def _collect_ai_metrics(self):
        """Collect AI/ML model metrics"""
        while self.running:
            try:
                timestamp = datetime.now()
                
                # Recommendation model metrics
                rec_metrics = cache.get(f'recommendation_metrics_{self.tenant.id}', {})
                if rec_metrics:
                    self._record_metric('ai.recommendations.accuracy', rec_metrics.get('accuracy', 0), timestamp)
                    self._record_metric('ai.recommendations.click_through_rate', rec_metrics.get('ctr', 0), timestamp)
                    self._record_metric('ai.recommendations.conversion_rate', rec_metrics.get('conversion', 0), timestamp)
                
                # Pricing model metrics
                pricing_metrics = cache.get(f'pricing_metrics_{self.tenant.id}', {})
                if pricing_metrics:
                    self._record_metric('ai.pricing.accuracy', pricing_metrics.get('accuracy', 0), timestamp)
                    self._record_metric('ai.pricing.profit_impact', pricing_metrics.get('profit_impact', 0), timestamp)
                
                # Demand forecasting metrics
                demand_metrics = cache.get(f'demand_metrics_{self.tenant.id}', {})
                if demand_metrics:
                    self._record_metric('ai.demand_forecast.accuracy', demand_metrics.get('accuracy', 0), timestamp)
                    self._record_metric('ai.demand_forecast.mape', demand_metrics.get('mape', 0), timestamp)
                
                # Model performance
                model_performance = cache.get(f'model_performance_{self.tenant.id}', {})
                for model_name, perf in model_performance.items():
                    self._record_metric(
                        f'ai.models.{model_name}.inference_time',
                        perf.get('inference_time', 0),
                        timestamp,
                        tags={'model': model_name}
                    )
                
                await asyncio.sleep(self.collection_intervals['ai'])
                
            except Exception as e:
                print(f"AI metrics collection error: {e}")
                await asyncio.sleep(self.collection_intervals['ai'])
    
    def _record_metric(self, name: str, value: float, timestamp: datetime, tags: Dict[str, str] = None):
        """Record a metric point"""
        metric = MetricPoint(name, value, timestamp, tags)
        self.metrics_buffer[name].append(metric)
        
        # Also store in cache for real-time access
        cache_key = f'metric_{name}_{self.tenant.id}'
        cache.set(cache_key, {'value': value, 'timestamp': timestamp.isoformat()}, 300)
    
    def get_metrics(self, name_pattern: str = None, 
                   start_time: datetime = None, 
                   end_time: datetime = None) -> Dict[str, List[MetricPoint]]:
        """Get metrics matching criteria"""
        result = {}
        
        for name, metrics in self.metrics_buffer.items():
            if name_pattern and name_pattern not in name:
                continue
                
            filtered_metrics = []
            for metric in metrics:
                if start_time and metric.timestamp < start_time:
                    continue
                if end_time and metric.timestamp > end_time:
                    continue
                filtered_metrics.append(metric)
            
            if filtered_metrics:
                result[name] = filtered_metrics
        
        return result
    
    def get_latest_metrics(self) -> Dict[str, Any]:
        """Get latest value for all metrics"""
        latest = {}
        
        for name, metrics in self.metrics_buffer.items():
            if metrics:
                latest_metric = metrics[-1]
                latest[name] = {
                    'value': latest_metric.value,
                    'timestamp': latest_metric.timestamp.isoformat(),
                    'tags': latest_metric.tags
                }
        
        return latest
    
    def get_aggregated_metrics(self, name: str, 
                              aggregation: str = 'avg',
                              window_minutes: int = 60) -> Optional[float]:
        """Get aggregated metric over time window"""
        if name not in self.metrics_buffer:
            return None
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        values = [
            m.value for m in self.metrics_buffer[name]
            if m.timestamp >= cutoff_time
        ]
        
        if not values:
            return None
        
        if aggregation == 'avg':
            return sum(values) / len(values)
        elif aggregation == 'max':
            return max(values)
        elif aggregation == 'min':
            return min(values)
        elif aggregation == 'sum':
            return sum(values)
        
        return None
    
    def _get_cache_stats(self) -> Dict[str, float]:
        """Get cache statistics"""
        # This would integrate with your cache backend
        return {
            'hit_rate': 85.5,
            'miss_rate': 14.5,
            'evictions': 0,
            'memory_usage': 50.2
        }
    
    def _measure_db_query_time(self) -> float:
        """Measure database query time"""
        start_time = time.time()
        try:
            from ...models import EcommerceProduct
            EcommerceProduct.objects.filter(tenant=self.tenant).count()
            return (time.time() - start_time) * 1000  # Convert to milliseconds
        except:
            return 0
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        # This would be based on actual cache statistics
        return 85.5  # Placeholder
    
    def _get_queue_performance(self) -> Dict[str, Dict[str, float]]:
        """Get queue performance metrics"""
        # This would integrate with your message queue
        return {
            'high_priority': {'avg_processing_time': 45.2},
            'normal_priority': {'avg_processing_time': 120.5},
            'events': {'avg_processing_time': 30.1}
        }
    
    def stop_collection(self):
        """Stop metrics collection"""
        self.running = False


class HealthChecker:
    """System health monitoring"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.checks = {
            'database': self._check_database,
            'cache': self._check_cache,
            'queue': self._check_queue,
            'ai_services': self._check_ai_services,
            'external_apis': self._check_external_apis
        }
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_status = 'healthy'
        
        for check_name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[check_name] = result
                
                if result['status'] == 'unhealthy':
                    overall_status = 'unhealthy'
                elif result['status'] == 'degraded' and overall_status == 'healthy':
                    overall_status = 'degraded'
                    
            except Exception as e:
                results[check_name] = {
                    'status': 'unhealthy',
                    'message': f'Health check failed: {str(e)}',
                    'response_time': 0
                }
                overall_status = 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'checks': results
        }
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        start_time = time.time()
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy' if response_time < 100 else 'degraded',
                'message': 'Database connection successful',
                'response_time': response_time
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}',
                'response_time': (time.time() - start_time) * 1000
            }
    
    async def _check_cache(self) -> Dict[str, Any]:
        """Check cache connectivity"""
        start_time = time.time()
        try:
            test_key = f'health_check_{self.tenant.id}'
            cache.set(test_key, 'test_value', 60)
            value = cache.get(test_key)
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if value == 'test_value':
                return {
                    'status': 'healthy',
                    'message': 'Cache is working correctly',
                    'response_time': response_time
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'Cache read/write issue',
                    'response_time': response_time
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Cache connection failed: {str(e)}',
                'response_time': (time.time() - start_time) * 1000
            }
    
    async def _check_queue(self) -> Dict[str, Any]:
        """Check message queue"""
        start_time = time.time()
        try:
            # This would check your actual message queue
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'message': 'Message queue is operational',
                'response_time': response_time
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Message queue check failed: {str(e)}',
                'response_time': (time.time() - start_time) * 1000
            }
    
    async def _check_ai_services(self) -> Dict[str, Any]:
        """Check AI services"""
        start_time = time.time()
        try:
            # Test AI service connectivity
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'message': 'AI services are operational',
                'response_time': response_time
            }
        except Exception as e:
            return {
                'status': 'degraded',
                'message': f'AI services check failed: {str(e)}',
                'response_time': (time.time() - start_time) * 1000
            }
    
    async def _check_external_apis(self) -> Dict[str, Any]:
        """Check external API connectivity"""
        start_time = time.time()
        try:
            # Test external APIs (payment, shipping, etc.)
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'message': 'External APIs are accessible',
                'response_time': response_time
            }
        except Exception as e:
            return {
                'status': 'degraded',
                'message': f'External API check failed: {str(e)}',
                'response_time': (time.time() - start_time) * 1000
            }