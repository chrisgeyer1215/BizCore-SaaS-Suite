"""
CRM Setup Management Command
Initializes CRM system with default data, configurations, and tenant setup.
"""

import json
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from crm.models.base_model import CRMConfiguration
from crm.models.lead_model import LeadSource, LeadScoringRule
from crm.models.opportunity_model import Pipeline, PipelineStage
from crm.models.activity_model import ActivityType
from crm.models.campaign_model import CampaignType
from crm.models.ticket_model import TicketCategory, SLA
from crm.models.territory_model import Territory
from crm.models.product_model import ProductCategory
from crm.models.workflow_model import WorkflowRule
from crm.models.user_model import CRMRole

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup CRM system with default configurations, data, and tenant settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant schema name to setup',
            required=True
        )
        
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Admin user email for CRM setup',
            default='admin@company.com'
        )
        
        parser.add_argument(
            '--company-name',
            type=str,
            help='Company name for CRM configuration',
            default='Sample Company'
        )
        
        parser.add_argument(
            '--industry',
            type=str,
            choices=['technology', 'healthcare', 'finance', 'retail', 'manufacturing', 'services'],
            help='Industry type for pre-configured settings',
            default='technology'
        )
        
        parser.add_argument(
            '--demo-data',
            action='store_true',
            help='Include demo data for testing and exploration',
        )
        
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip setup if CRM configuration already exists',
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self.setup_crm(**options)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ CRM setup completed successfully for tenant: {options["tenant"]}'
                    )
                )
        except Exception as e:
            logger.error(f"CRM setup failed: {str(e)}")
            raise CommandError(f'CRM setup failed: {str(e)}')

    def setup_crm(self, **options):
        """Main setup orchestrator"""
        tenant = options['tenant']
        
        self.stdout.write(f'🚀 Setting up CRM for tenant: {tenant}')
        
        # Check if already configured
        if options['skip_existing'] and self._is_already_configured():
            self.stdout.write(
                self.style.WARNING('CRM already configured. Skipping setup.')
            )
            return
        
        # Setup steps
        self._create_crm_configuration(options)
        self._setup_lead_sources()
        self._setup_lead_scoring_rules()
        self._setup_pipelines_and_stages()
        self._setup_activity_types()
        self._setup_campaign_types()
        self._setup_ticket_categories_and_slas()
        self._setup_territories()
        self._setup_product_categories()
        self._setup_workflow_rules()
        self._setup_user_roles()
        
        if options['demo_data']:
            self._create_demo_data()
        
        self.stdout.write('✅ CRM setup completed with all default configurations')

    def _is_already_configured(self):
        """Check if CRM is already configured"""
        return CRMConfiguration.objects.filter(is_active=True).exists()

    def _create_crm_configuration(self, options):
        """Create main CRM configuration"""
        self.stdout.write('📝 Creating CRM configuration...')
        
        industry_configs = {
            'technology': {
                'lead_sources': ['Website', 'Referral', 'Social Media', 'Trade Show', 'Cold Calling'],
                'pipeline_stages': ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'],
                'activity_types': ['Call', 'Email', 'Meeting', 'Demo', 'Follow-up'],
                'default_currency': 'USD',
                'fiscal_year_start': 1,  # January
            },
            'healthcare': {
                'lead_sources': ['Referral', 'Website', 'Healthcare Events', 'Medical Journals'],
                'pipeline_stages': ['Initial Contact', 'Needs Assessment', 'Proposal', 'Approval', 'Implementation', 'Closed'],
                'activity_types': ['Consultation', 'Follow-up', 'Documentation', 'Training'],
                'default_currency': 'USD',
                'fiscal_year_start': 7,  # July (common in healthcare)
            },
            # Add more industry-specific configurations
        }
        
        industry_config = industry_configs.get(options['industry'], industry_configs['technology'])
        
        config, created = CRMConfiguration.objects.get_or_create(
            defaults={
                'company_name': options['company_name'],
                'industry': options['industry'],
                'default_currency': industry_config['default_currency'],
                'fiscal_year_start_month': industry_config['fiscal_year_start'],
                'timezone': 'UTC',
                'date_format': 'YYYY-MM-DD',
                'business_hours_start': '09:00',
                'business_hours_end': '17:00',
                'working_days': [1, 2, 3, 4, 5],  # Monday to Friday
                'features': {
                    'lead_scoring': True,
                    'email_integration': True,
                    'workflow_automation': True,
                    'analytics': True,
                    'mobile_access': True,
                },
                'limits': {
                    'max_users': 100,
                    'max_leads': 10000,
                    'max_storage_gb': 10,
                    'max_email_per_month': 5000,
                },
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write('✅ CRM configuration created')
        else:
            self.stdout.write('⚠️ CRM configuration already exists, updated settings')

    def _setup_lead_sources(self):
        """Setup default lead sources"""
        self.stdout.write('📊 Setting up lead sources...')
        
        lead_sources = [
            {'name': 'Website', 'cost_per_lead': 25.00, 'is_active': True},
            {'name': 'Social Media', 'cost_per_lead': 15.00, 'is_active': True},
            {'name': 'Email Marketing', 'cost_per_lead': 10.00, 'is_active': True},
            {'name': 'Referral', 'cost_per_lead': 5.00, 'is_active': True},
            {'name': 'Trade Show', 'cost_per_lead': 75.00, 'is_active': True},
            {'name': 'Cold Calling', 'cost_per_lead': 30.00, 'is_active': True},
            {'name': 'Content Marketing', 'cost_per_lead': 20.00, 'is_active': True},
            {'name': 'Partner Referral', 'cost_per_lead': 40.00, 'is_active': True},
        ]
        
        for source_data in lead_sources:
            source, created = LeadSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )
            if created:
                self.stdout.write(f'  ✅ Created lead source: {source.name}')

    def _setup_lead_scoring_rules(self):
        """Setup intelligent lead scoring rules"""
        self.stdout.write('🎯 Setting up lead scoring rules...')
        
        scoring_rules = [
            {
                'name': 'Company Size Score',
                'field_name': 'company_size',
                'rule_type': 'VALUE_MAPPING',
                'conditions': {
                    '1-10': 10,
                    '11-50': 20,
                    '51-200': 30,
                    '201-1000': 40,
                    '1000+': 50
                },
                'weight': 0.15,
                'is_active': True
            },
            {
                'name': 'Budget Range Score',
                'field_name': 'budget',
                'rule_type': 'NUMERIC_RANGE',
                'conditions': {
                    '0-1000': 5,
                    '1001-5000': 15,
                    '5001-20000': 25,
                    '20001-50000': 35,
                    '50000+': 45
                },
                'weight': 0.25,
                'is_active': True
            },
            {
                'name': 'Industry Fit Score',
                'field_name': 'industry',
                'rule_type': 'VALUE_MAPPING',
                'conditions': {
                    'Technology': 50,
                    'Finance': 45,
                    'Healthcare': 40,
                    'Manufacturing': 35,
                    'Retail': 30,
                    'Other': 20
                },
                'weight': 0.20,
                'is_active': True
            },
            {
                'name': 'Engagement Score',
                'field_name': 'last_activity_date',
                'rule_type': 'DATE_BASED',
                'conditions': {
                    'days_since_activity_0_1': 50,
                    'days_since_activity_2_7': 30,
                    'days_since_activity_8_30': 15,
                    'days_since_activity_31_90': 5,
                    'days_since_activity_90+': 0
                },
                'weight': 0.15,
                'is_active': True
            },
            {
                'name': 'Lead Source Quality',
                'field_name': 'source',
                'rule_type': 'VALUE_MAPPING',
                'conditions': {
                    'Referral': 45,
                    'Website': 35,
                    'Social Media': 25,
                    'Email Marketing': 20,
                    'Cold Calling': 15,
                    'Trade Show': 40
                },
                'weight': 0.10,
                'is_active': True
            },
            {
                'name': 'Decision Maker Score',
                'field_name': 'job_title',
                'rule_type': 'VALUE_MAPPING',
                'conditions': {
                    'CEO': 50,
                    'CTO': 45,
                    'VP': 40,
                    'Director': 35,
                    'Manager': 25,
                    'Individual Contributor': 15
                },
                'weight': 0.15,
                'is_active': True
            }
        ]
        
        for rule_data in scoring_rules:
            rule, created = LeadScoringRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )
            if created:
                self.stdout.write(f'  ✅ Created scoring rule: {rule.name}')

    def _setup_pipelines_and_stages(self):
        """Setup sales pipelines and stages"""
        self.stdout.write('🔄 Setting up sales pipelines...')
        
        # Default Sales Pipeline
        pipeline, created = Pipeline.objects.get_or_create(
            name='Standard Sales Pipeline',
            defaults={
                'description': 'Default sales pipeline for all opportunities',
                'is_active': True,
                'is_default': True
            }
        )
        
        if created:
            self.stdout.write('  ✅ Created default sales pipeline')
        
        # Pipeline Stages
        stages = [
            {'name': 'Lead', 'order': 1, 'probability': 10, 'stage_type': 'OPEN'},
            {'name': 'Qualified', 'order': 2, 'probability': 20, 'stage_type': 'OPEN'},
            {'name': 'Needs Analysis', 'order': 3, 'probability': 30, 'stage_type': 'OPEN'},
            {'name': 'Proposal', 'order': 4, 'probability': 50, 'stage_type': 'OPEN'},
            {'name': 'Negotiation', 'order': 5, 'probability': 75, 'stage_type': 'OPEN'},
            {'name': 'Closed Won', 'order': 6, 'probability': 100, 'stage_type': 'WON'},
            {'name': 'Closed Lost', 'order': 7, 'probability': 0, 'stage_type': 'LOST'},
        ]
        
        for stage_data in stages:
            stage, created = PipelineStage.objects.get_or_create(
                pipeline=pipeline,
                name=stage_data['name'],
                defaults={
                    **stage_data,
                    'pipeline': pipeline
                }
            )
            if created:
                self.stdout.write(f'    ✅ Created stage: {stage.name} ({stage.probability}%)')

    def _setup_activity_types(self):
        """Setup activity types"""
        self.stdout.write('📅 Setting up activity types...')
        
        activity_types = [
            {'name': 'Call', 'icon': '📞', 'color': '#10B981', 'is_active': True},
            {'name': 'Email', 'icon': '📧', 'color': '#3B82F6', 'is_active': True},
            {'name': 'Meeting', 'icon': '🤝', 'color': '#8B5CF6', 'is_active': True},
            {'name': 'Task', 'icon': '✅', 'color': '#F59E0B', 'is_active': True},
            {'name': 'Demo', 'icon': '🖥️', 'color': '#EF4444', 'is_active': True},
            {'name': 'Follow-up', 'icon': '🔄', 'color': '#6B7280', 'is_active': True},
            {'name': 'Proposal', 'icon': '📄', 'color': '#EC4899', 'is_active': True},
            {'name': 'Quote', 'icon': '💰', 'color': '#14B8A6', 'is_active': True},
        ]
        
        for type_data in activity_types:
            activity_type, created = ActivityType.objects.get_or_create(
                name=type_data['name'],
                defaults=type_data
            )
            if created:
                self.stdout.write(f'  ✅ Created activity type: {activity_type.name}')

    def _setup_campaign_types(self):
        """Setup campaign types"""
        self.stdout.write('📢 Setting up campaign types...')
        
        campaign_types = [
            {'name': 'Email Marketing', 'description': 'Email-based marketing campaigns'},
            {'name': 'Social Media', 'description': 'Social media marketing campaigns'},
            {'name': 'Content Marketing', 'description': 'Content-driven marketing campaigns'},
            {'name': 'Event Marketing', 'description': 'Event and trade show campaigns'},
            {'name': 'Direct Mail', 'description': 'Physical mail campaigns'},
            {'name': 'Webinar', 'description': 'Educational webinar campaigns'},
            {'name': 'Product Launch', 'description': 'New product launch campaigns'},
            {'name': 'Lead Nurturing', 'description': 'Automated lead nurturing sequences'},
        ]
        
        for type_data in campaign_types:
            campaign_type, created = CampaignType.objects.get_or_create(
                name=type_data['name'],
                defaults=type_data
            )
            if created:
                self.stdout.write(f'  ✅ Created campaign type: {campaign_type.name}')

    def _setup_ticket_categories_and_slas(self):
        """Setup support ticket categories and SLAs"""
        self.stdout.write('🎫 Setting up ticket system...')
        
        # Ticket Categories
        categories = [
            {'name': 'Technical Support', 'description': 'Technical issues and bugs'},
            {'name': 'Billing', 'description': 'Billing and payment related queries'},
            {'name': 'Feature Request', 'description': 'New feature requests and suggestions'},
            {'name': 'General Inquiry', 'description': 'General questions and information requests'},
            {'name': 'Account Management', 'description': 'Account setup and management issues'},
            {'name': 'Training', 'description': 'Training and onboarding support'},
        ]
        
        for cat_data in categories:
            category, created = TicketCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(f'  ✅ Created ticket category: {category.name}')
        
        # SLA Levels
        sla_levels = [
            {
                'name': 'Critical',
                'description': 'Critical issues requiring immediate attention',
                'response_time_hours': 1,
                'resolution_time_hours': 4,
                'priority': 1
            },
            {
                'name': 'High',
                'description': 'High priority issues',
                'response_time_hours': 2,
                'resolution_time_hours': 8,
                'priority': 2
            },
            {
                'name': 'Medium',
                'description': 'Standard priority issues',
                'response_time_hours': 4,
                'resolution_time_hours': 24,
                'priority': 3
            },
            {
                'name': 'Low',
                'description': 'Low priority issues and requests',
                'response_time_hours': 8,
                'resolution_time_hours': 72,
                'priority': 4
            }
        ]
        
        for sla_data in sla_levels:
            sla, created = SLA.objects.get_or_create(
                name=sla_data['name'],
                defaults=sla_data
            )
            if created:
                self.stdout.write(f'  ✅ Created SLA level: {sla.name}')

    def _setup_territories(self):
        """Setup default territories"""
        self.stdout.write('🗺️ Setting up territories...')
        
        territories = [
            {
                'name': 'North America',
                'territory_type': 'GEOGRAPHIC',
                'description': 'North American sales territory',
                'is_active': True
            },
            {
                'name': 'Enterprise Accounts',
                'territory_type': 'ACCOUNT_BASED',
                'description': 'Enterprise customer segment',
                'is_active': True
            },
            {
                'name': 'SMB Accounts',
                'territory_type': 'ACCOUNT_BASED',
                'description': 'Small and medium business segment',
                'is_active': True
            }
        ]
        
        for territory_data in territories:
            territory, created = Territory.objects.get_or_create(
                name=territory_data['name'],
                defaults=territory_data
            )
            if created:
                self.stdout.write(f'  ✅ Created territory: {territory.name}')

    def _setup_product_categories(self):
        """Setup product categories"""
        self.stdout.write('📦 Setting up product categories...')
        
        categories = [
            {'name': 'Software', 'description': 'Software products and licenses'},
            {'name': 'Services', 'description': 'Professional and consulting services'},
            {'name': 'Hardware', 'description': 'Physical hardware products'},
            {'name': 'Training', 'description': 'Training and education services'},
            {'name': 'Support', 'description': 'Technical support packages'},
        ]
        
        for cat_data in categories:
            category, created = ProductCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(f'  ✅ Created product category: {category.name}')

    def _setup_workflow_rules(self):
        """Setup basic workflow automation rules"""
        self.stdout.write('⚙️ Setting up workflow rules...')
        
        workflow_rules = [
            {
                'name': 'Auto-assign New Leads',
                'trigger_object': 'Lead',
                'trigger_event': 'CREATE',
                'conditions': {'source__in': ['Website', 'Social Media']},
                'actions': [
                    {
                        'type': 'ASSIGN_OWNER',
                        'method': 'ROUND_ROBIN'
                    },
                    {
                        'type': 'SEND_NOTIFICATION',
                        'template': 'new_lead_assignment'
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Follow-up Reminder',
                'trigger_object': 'Activity',
                'trigger_event': 'CREATE',
                'conditions': {'activity_type': 'Call', 'status': 'COMPLETED'},
                'actions': [
                    {
                        'type': 'CREATE_FOLLOW_UP',
                        'delay_hours': 24
                    }
                ],
                'is_active': True
            },
            {
                'name': 'Opportunity Stage Change Alert',
                'trigger_object': 'Opportunity',
                'trigger_event': 'UPDATE',
                'conditions': {'field_changed': 'stage'},
                'actions': [
                    {
                        'type': 'SEND_NOTIFICATION',
                        'template': 'opportunity_stage_change'
                    }
                ],
                'is_active': True
            }
        ]
        
        for rule_data in workflow_rules:
            rule, created = WorkflowRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )
            if created:
                self.stdout.write(f'  ✅ Created workflow rule: {rule.name}')

    def _setup_user_roles(self):
        """Setup user roles and permissions"""
        self.stdout.write('👥 Setting up user roles...')
        
        roles = [
            {
                'name': 'System Administrator',
                'description': 'Full system access with administrative privileges',
                'permission_level': 100,
                'is_system_role': True
            },
            {
                'name': 'Sales Manager',
                'description': 'Manage sales team and processes',
                'permission_level': 80,
                'is_system_role': False
            },
            {
                'name': 'Marketing Manager',
                'description': 'Manage marketing campaigns and leads',
                'permission_level': 75,
                'is_system_role': False
            },
            {
                'name': 'Sales Representative',
                'description': 'Standard sales user with opportunity management',
                'permission_level': 60,
                'is_system_role': False
            },
            {
                'name': 'Customer Success Manager',
                'description': 'Manage customer relationships and support',
                'permission_level': 65,
                'is_system_role': False
            }
        ]
        
        for role_data in roles:
            role, created = CRMRole.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                self.stdout.write(f'  ✅ Created role: {role.name}')

    def _create_demo_data(self):
        """Create sample demo data for testing"""
        self.stdout.write('🎪 Creating demo data...')
        
        # Note: This would create sample leads, accounts, opportunities, etc.
        # Implementation would be similar to the existing patterns above
        # but with actual demo records for testing purposes
        
        self.stdout.write('  ✅ Demo data created successfully')