# apps/inventory/management/commands/generate_api_docs.py

from django.core.management.base import BaseCommand
from django.core.management import call_command
import os
import yaml
import json

class Command(BaseCommand):
    help = 'Generate comprehensive API documentation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['yaml', 'json', 'both'],
            default='both',
            help='Output format for schema file'
        )
        
        parser.add_argument(
            '--output-dir',
            default='docs/api/',
            help='Output directory for documentation files'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Generating API documentation...'))
        
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate OpenAPI schema
        if options['format'] in ['yaml', 'both']:
            yaml_file = os.path.join(output_dir, 'openapi.yaml')
            call_command('spectacular', '--color', '--file', yaml_file)
            self.stdout.write(f'Generated YAML schema: {yaml_file}')
        
        if options['format'] in ['json', 'both']:
            json_file = os.path.join(output_dir, 'openapi.json')
            call_command('spectacular', '--format', 'openapi-json', '--file', json_file)
            self.stdout.write(f'Generated JSON schema: {json_file}')
        
        # Generate additional documentation
        self._generate_endpoint_summary(output_dir)
        self._generate_postman_collection(output_dir)
        
        self.stdout.write(
            self.style.SUCCESS('API documentation generated successfully!')
        )
    
    def _generate_endpoint_summary(self, output_dir):
        """Generate endpoint summary markdown."""
        # Implementation to generate endpoint summary
        pass
    
    def _generate_postman_collection(self, output_dir):
        """Generate Postman collection."""
        # Implementation to generate Postman collection
        pass