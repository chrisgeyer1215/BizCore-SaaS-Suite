from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from apps.ecommerce.models import Cart, AbandonedCart
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Cleanup abandoned carts older than specified days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days after which to delete abandoned carts'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--create-abandoned',
            action='store_true',
            help='Create AbandonedCart records before cleanup'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        create_abandoned = options['create_abandoned']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            f'Processing abandoned carts older than {days} days (before {cutoff_date})'
        )

        # Find abandoned carts
        abandoned_carts = Cart.objects.filter(
            status='active',
            updated_at__lt=cutoff_date,
            customer__isnull=False  # Only process customer carts, not guest
        ).exclude(
            orders__isnull=False  # Exclude carts that became orders
        )

        if create_abandoned:
            self.create_abandoned_records(abandoned_carts, dry_run)

        # Now cleanup old carts
        old_carts = Cart.objects.filter(
            updated_at__lt=cutoff_date,
            status__in=['abandoned', 'expired']
        )

        count = old_carts.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {count} abandoned carts')
            )
            for cart in old_carts[:10]:  # Show first 10
                self.stdout.write(f'  - Cart {cart.cart_id} (Updated: {cart.updated_at})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            with transaction.atomic():
                deleted_count, _ = old_carts.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {deleted_count} abandoned carts')
                )
                logger.info(f'Cleanup completed: {deleted_count} carts deleted')

    def create_abandoned_records(self, carts, dry_run):
        """Create AbandonedCart records for tracking"""
        created_count = 0
        
        for cart in carts:
            if not hasattr(cart, 'abandoned_cart'):
                if not dry_run:
                    AbandonedCart.objects.get_or_create(
                        cart=cart,
                        defaults={
                            'tenant': cart.tenant,
                            'browser_info': {},
                        }
                    )
                created_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would create {created_count} abandoned cart records')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Created {created_count} abandoned cart tracking records')
            )
