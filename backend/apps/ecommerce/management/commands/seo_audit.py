"""
SEO Audit Management Command
"""

import asyncio
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from ...models import EcommerceProduct, SEOAuditLog
from ...infrastructure.seo.seo_analyzer import AdvancedSEOAnalyzer
from ...domain.services.seo_service import SEOService


class Command(BaseCommand):
    help = 'Run SEO audit for products'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Tenant ID to run audit for',
        )
        parser.add_argument(
            '--product-ids',
            nargs='+',
            type=int,
            help='Specific product IDs to audit',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of products to process in each batch',
        )
        parser.add_argument(
            '--full-audit',
            action='store_true',
            help='Run comprehensive audit including external tools',
        )
        parser.add_argument(
            '--update-scores',
            action='store_true',
            help='Update product SEO scores in database',
        )
        parser.add_argument(
            '--export-report',
            type=str,
            help='Export audit results to CSV file',
        )
    
    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        if not tenant_id:
            raise CommandError('Tenant ID is required')
        
        try:
            from apps.core.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant {tenant_id} not found')
        
        # Get products to audit
        if options.get('product_ids'):
            products = EcommerceProduct.objects.filter(
                tenant=tenant,
                id__in=options['product_ids'],
                is_active=True
            )
        else:
            products = EcommerceProduct.objects.filter(
                tenant=tenant,
                is_active=True,
                is_published=True
            )
        
        if not products.exists():
            self.stdout.write(
                self.style.WARNING('No products found for audit')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting SEO audit for {products.count()} products...'
            )
        )
        
        # Run audit
        asyncio.run(self._run_audit(
            tenant=tenant,
            products=products,
            batch_size=options.get('batch_size', 10),
            full_audit=options.get('full_audit', False),
            update_scores=options.get('update_scores', False),
            export_report=options.get('export_report')
        ))
        
        self.stdout.write(
            self.style.SUCCESS('SEO audit completed successfully')
        )
    
    async def _run_audit(self, tenant, products, batch_size, full_audit, update_scores, export_report):
        """Run the actual SEO audit"""
        seo_analyzer = AdvancedSEOAnalyzer(tenant)
        seo_service = SEOService(tenant)
        
        audit_results = []
        processed_count = 0
        
        # Process products in batches
        for i in range(0, products.count(), batch_size):
            batch = products[i:i + batch_size]
            
            batch_tasks = []
            for product in batch:
                if full_audit:
                    # Run comprehensive audit with external tools
                    product_url = f"https://{tenant.domain}{product.get_absolute_url()}"
                    task = seo_analyzer.perform_comprehensive_audit(product_url)
                else:
                    # Run basic domain-level audit
                    task = self._run_basic_audit(seo_service, product)
                
                batch_tasks.append((product, task))
            
            # Execute batch
            for product, task in batch_tasks:
                try:
                    if full_audit:
                        audit_result = await task
                    else:
                        audit_result = task
                    
                    # Store audit result
                    audit_results.append({
                        'product': product,
                        'result': audit_result
                    })
                    
                    # Update product SEO score if requested
                    if update_scores:
                        product.seo_score = audit_result.score if hasattr(audit_result, 'score') else audit_result.get('score', 0)
                        product.seo_last_analyzed = timezone.now()
                        product.save(update_fields=['seo_score', 'seo_last_analyzed'])
                    
                    # Log audit
                    self._log_audit_result(product, audit_result)
                    
                    processed_count += 1
                    
                    if processed_count % 10 == 0:
                        self.stdout.write(f'Processed {processed_count} products...')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Failed to audit product {product.id}: {str(e)}'
                        )
                    )
            
            # Small delay between batches to avoid rate limiting
            await asyncio.sleep(1)
        
        # Export report if requested
        if export_report:
            self._export_audit_report(audit_results, export_report)
    
    def _run_basic_audit(self, seo_service, product):
        """Run basic SEO audit using domain service"""
        return seo_service.analyze_product_seo(product)
    
    def _log_audit_result(self, product, audit_result):
        """Log audit result to database"""
        try:
            if hasattr(audit_result, 'score'):
                # Comprehensive audit result
                SEOAuditLog.objects.create(
                    product=product,
                    audit_type='comprehensive',
                    score=audit_result.score,
                    performance_score=audit_result.performance_score,
                    seo_score=audit_result.seo_score,
                    accessibility_score=audit_result.accessibility_score,
                    issues=audit_result.issues,
                    opportunities=audit_result.opportunities,
                    audited_at=timezone.now()
                )
            else:
                # Basic audit result
                SEOAuditLog.objects.create(
                    product=product,
                    audit_type='basic',
                    score=audit_result.score,
                    issues=[{'message': issue} for issue in audit_result.issues],
                    recommendations=[{'message': rec} for rec in audit_result.recommendations],
                    audited_at=timezone.now()
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to log audit for product {product.id}: {str(e)}')
            )
    
    def _export_audit_report(self, audit_results, filename):
        """Export audit results to CSV"""
        import csv
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'product_id', 'product_title', 'seo_score', 
                    'performance_score', 'accessibility_score',
                    'issues_count', 'opportunities_count', 'top_issues'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result_data in audit_results:
                    product = result_data['product']
                    result = result_data['result']
                    
                    if hasattr(result, 'score'):
                        # Comprehensive audit
                        top_issues = '; '.join([
                            issue.get('title', issue.get('message', ''))
                            for issue in result.issues[:3]
                        ])
                        
                        writer.writerow({
                            'product_id': product.id,
                            'product_title': product.title,
                            'seo_score': result.score,
                            'performance_score': result.performance_score,
                            'accessibility_score': result.accessibility_score,
                            'issues_count': len(result.issues),
                            'opportunities_count': len(result.opportunities),
                            'top_issues': top_issues
                        })
                    else:
                        # Basic audit
                        writer.writerow({
                            'product_id': product.id,
                            'product_title': product.title,
                            'seo_score': result.score,
                            'performance_score': 0,
                            'accessibility_score': 0,
                            'issues_count': len(result.issues),
                            'opportunities_count': len(result.recommendations),
                            'top_issues': '; '.join(result.issues[:3])
                        })
            
            self.stdout.write(
                self.style.SUCCESS(f'Audit report exported to {filename}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to export report: {str(e)}')
            )