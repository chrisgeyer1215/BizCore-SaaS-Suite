"""
Scoring Tasks
Handle lead scoring, opportunity probability updates, and predictive analytics
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q, F
from django.db import transaction
import logging
from datetime import timedelta
import numpy as np

from .base import TenantAwareTask, BatchProcessingTask, CacheAwareTask
from ..models import (
    Lead, Opportunity, Account, Contact, Activity, 
    LeadScoringRule, ProductBundle, Campaign
)
from ..services.scoring_service import ScoringService
from ..utils.tenant_utils import get_tenant_by_id

logger = logging.getLogger(__name__)


@shared_task(base=BatchProcessingTask, bind=True)
def calculate_lead_scores_task(self, tenant_id, lead_ids=None, scoring_rules=None, batch_size=100):
    """
    Calculate or recalculate lead scores using AI and rule-based scoring
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get leads to score
        if lead_ids:
            leads = Lead.objects.filter(id__in=lead_ids, tenant=tenant)
        else:
            # Score all leads that need scoring
            leads = Lead.objects.filter(
                tenant=tenant,
                status__in=['new', 'contacted', 'qualified'],
                is_deleted=False
            ).filter(
                Q(score__isnull=True) | 
                Q(score_updated_at__lt=timezone.now() - timedelta(hours=24))
            )
        
        def process_lead_batch(batch):
            """Process a batch of leads for scoring"""
            scored_leads = []
            
            for lead in batch:
                try:
                    # Calculate comprehensive score
                    score_data = service.calculate_lead_score(
                        lead=lead,
                        scoring_rules=scoring_rules
                    )
                    
                    # Update lead with new score
                    lead.score = score_data['total_score']
                    lead.score_breakdown = score_data['breakdown']
                    lead.score_updated_at = timezone.now()
                    lead.ai_confidence = score_data.get('ai_confidence', 0.5)
                    
                    scored_leads.append(lead)
                    
                except Exception as e:
                    logger.error(f"Failed to score lead {lead.id}: {e}")
            
            # Bulk update leads
            if scored_leads:
                Lead.objects.bulk_update(
                    scored_leads,
                    ['score', 'score_breakdown', 'score_updated_at', 'ai_confidence'],
                    batch_size=50
                )
            
            return len(scored_leads)
        
        # Process leads in batches
        result = self.process_in_batches(
            list(leads),
            batch_size=batch_size,
            process_func=process_lead_batch
        )
        
        logger.info(f"Scored {result['processed_items']} leads")
        
        return result
        
    except Exception as e:
        logger.error(f"Lead scoring task failed: {e}")
        raise


@shared_task(base=BatchProcessingTask, bind=True)
def update_opportunity_probabilities_task(self, tenant_id, opportunity_ids=None, batch_size=50):
    """
    Update opportunity close probabilities using ML models
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get opportunities to update
        if opportunity_ids:
            opportunities = Opportunity.objects.filter(id__in=opportunity_ids, tenant=tenant)
        else:
            opportunities = Opportunity.objects.filter(
                tenant=tenant,
                stage__is_closed=False
            )
        
        def process_opportunity_batch(batch):
            """Process a batch of opportunities"""
            updated_opportunities = []
            
            for opportunity in batch:
                try:
                    # Calculate probability using ML model
                    probability_data = service.calculate_opportunity_probability(opportunity)
                    
                    # Update opportunity
                    opportunity.probability = probability_data['probability']
                    opportunity.ai_probability = probability_data.get('ai_probability')
                    opportunity.probability_factors = probability_data.get('factors', {})
                    opportunity.probability_updated_at = timezone.now()
                    
                    updated_opportunities.append(opportunity)
                    
                except Exception as e:
                    logger.error(f"Failed to update probability for opportunity {opportunity.id}: {e}")
            
            # Bulk update opportunities
            if updated_opportunities:
                Opportunity.objects.bulk_update(
                    updated_opportunities,
                    ['probability', 'ai_probability', 'probability_factors', 'probability_updated_at'],
                    batch_size=25
                )
            
            return len(updated_opportunities)
        
        result = self.process_in_batches(
            list(opportunities),
            batch_size=batch_size,
            process_func=process_opportunity_batch
        )
        
        logger.info(f"Updated probabilities for {result['processed_items']} opportunities")
        
        return result
        
    except Exception as e:
        logger.error(f"Opportunity probability update task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def refresh_customer_health_scores_task(self, tenant_id, account_ids=None):
    """
    Refresh customer health scores based on latest activity and engagement data
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get accounts to refresh
        if account_ids:
            accounts = Account.objects.filter(id__in=account_ids, tenant=tenant)
        else:
            accounts = Account.objects.filter(
                tenant=tenant,
                status='active'
            )
        
        updated_count = 0
        
        for account in accounts:
            try:
                # Calculate comprehensive health score
                health_data = service.calculate_customer_health_score(account)
                
                # Update account
                account.health_score = health_data['score']
                account.health_status = health_data['status']
                account.health_factors = health_data['factors']
                account.churn_risk_score = health_data.get('churn_risk', 0)
                account.health_updated_at = timezone.now()
                account.save(update_fields=[
                    'health_score', 'health_status', 'health_factors',
                    'churn_risk_score', 'health_updated_at'
                ])
                
                updated_count += 1
                
                # Create alerts for at-risk customers
                if health_data.get('churn_risk', 0) > 70:
                    service.create_churn_risk_alert(account, health_data)
                
            except Exception as e:
                logger.error(f"Failed to update health score for account {account.id}: {e}")
        
        logger.info(f"Updated health scores for {updated_count} accounts")
        
        return {
            'status': 'completed',
            'updated_accounts': updated_count
        }
        
    except Exception as e:
        logger.error(f"Customer health score refresh failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def update_product_scores_task(self, tenant_id, days_back=90):
    """
    Update product performance and competitiveness scores
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get products to score
        from ..models import Product
        products = Product.objects.filter(tenant=tenant, is_active=True)
        
        updated_count = 0
        
        for product in products:
            try:
                # Calculate product performance score
                score_data = service.calculate_product_score(
                    product=product,
                    days_back=days_back
                )
                
                # Update product
                product.performance_score = score_data['performance_score']
                product.competitiveness_score = score_data['competitiveness_score']
                product.market_position = score_data['market_position']
                product.score_factors = score_data['factors']
                product.score_updated_at = timezone.now()
                product.save(update_fields=[
                    'performance_score', 'competitiveness_score', 
                    'market_position', 'score_factors', 'score_updated_at'
                ])
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update score for product {product.id}: {e}")
        
        logger.info(f"Updated scores for {updated_count} products")
        
        return {
            'status': 'completed',
            'updated_products': updated_count
        }
        
    except Exception as e:
        logger.error(f"Product score update failed: {e}")
        raise


@shared_task(base=CacheAwareTask, bind=True)
def generate_predictive_insights_task(self, tenant_id, insight_types=None):
    """
    Generate AI-powered predictive insights
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Check cache first
        cached_result = self.get_cached_result(tenant_id, insight_types)
        if cached_result:
            return cached_result
        
        # Default insight types
        if not insight_types:
            insight_types = ['churn_prediction', 'upsell_opportunities', 'deal_risk_assessment']
        
        insights = {}
        
        # Generate churn predictions
        if 'churn_prediction' in insight_types:
            insights['churn_prediction'] = service.predict_customer_churn()
        
        # Identify upsell opportunities
        if 'upsell_opportunities' in insight_types:
            insights['upsell_opportunities'] = service.identify_upsell_opportunities()
        
        # Assess deal risks
        if 'deal_risk_assessment' in insight_types:
            insights['deal_risk_assessment'] = service.assess_deal_risks()
        
        # Lead conversion predictions
        if 'lead_conversion' in insight_types:
            insights['lead_conversion'] = service.predict_lead_conversions()
        
        # Market opportunity analysis
        if 'market_opportunities' in insight_types:
            insights['market_opportunities'] = service.analyze_market_opportunities()
        
        # Revenue forecasting
        if 'revenue_forecast' in insight_types:
            insights['revenue_forecast'] = service.generate_revenue_predictions()
        
        result = {
            'status': 'completed',
            'insights': insights,
            'generated_at': timezone.now().isoformat(),
            'tenant_id': tenant_id
        }
        
        # Cache results for 4 hours
        self.set_cached_result(result, timeout=14400, tenant_id=tenant_id, insight_types=insight_types)
        
        logger.info(f"Generated {len(insights)} predictive insights for tenant {tenant.name}")
        
        return result
        
    except Exception as e:
        logger.error(f"Predictive insights generation failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def train_scoring_models_task(self, tenant_id, model_types=None):
    """
    Train or retrain ML models for scoring
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Default model types
        if not model_types:
            model_types = ['lead_scoring', 'opportunity_probability', 'churn_prediction']
        
        training_results = {}
        
        for model_type in model_types:
            try:
                logger.info(f"Training {model_type} model for tenant {tenant.name}")
                
                if model_type == 'lead_scoring':
                    result = service.train_lead_scoring_model()
                elif model_type == 'opportunity_probability':
                    result = service.train_opportunity_probability_model()
                elif model_type == 'churn_prediction':
                    result = service.train_churn_prediction_model()
                elif model_type == 'customer_lifetime_value':
                    result = service.train_clv_model()
                else:
                    continue
                
                training_results[model_type] = result
                
                logger.info(f"Successfully trained {model_type} model with accuracy: {result.get('accuracy', 0):.3f}")
                
            except Exception as e:
                logger.error(f"Failed to train {model_type} model: {e}")
                training_results[model_type] = {'status': 'failed', 'error': str(e)}
        
        return {
            'status': 'completed',
            'training_results': training_results,
            'trained_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Model training task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def update_lead_routing_scores_task(self, tenant_id):
    """
    Update scores for intelligent lead routing
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get unassigned leads
        unassigned_leads = Lead.objects.filter(
            tenant=tenant,
            assigned_to__isnull=True,
            status__in=['new', 'contacted']
        )
        
        # Get available sales reps
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        sales_reps = User.objects.filter(
            memberships__tenant=tenant,
            memberships__role__in=['sales_rep', 'sales_manager'],
            memberships__is_active=True,
            is_active=True
        )
        
        routing_recommendations = []
        
        for lead in unassigned_leads[:100]:  # Process up to 100 leads
            try:
                # Calculate routing scores for each rep
                rep_scores = service.calculate_routing_scores(lead, sales_reps)
                
                if rep_scores:
                    best_rep = max(rep_scores, key=rep_scores.get)
                    routing_recommendations.append({
                        'lead_id': lead.id,
                        'recommended_rep': best_rep.id,
                        'confidence_score': rep_scores[best_rep],
                        'all_scores': {rep.id: score for rep, score in rep_scores.items()}
                    })
                
            except Exception as e:
                logger.error(f"Failed to calculate routing for lead {lead.id}: {e}")
        
        logger.info(f"Generated {len(routing_recommendations)} routing recommendations")
        
        return {
            'status': 'completed',
            'recommendations': routing_recommendations
        }
        
    except Exception as e:
        logger.error(f"Lead routing scores update failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def calculate_territory_scores_task(self, tenant_id):
    """
    Calculate performance scores for sales territories
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        from ..models import Territory
        territories = Territory.objects.filter(tenant=tenant, is_active=True)
        
        updated_count = 0
        
        for territory in territories:
            try:
                # Calculate territory performance score
                score_data = service.calculate_territory_score(territory)
                
                # Update territory
                territory.performance_score = score_data['performance_score']
                territory.efficiency_score = score_data['efficiency_score']
                territory.growth_score = score_data['growth_score']
                territory.score_factors = score_data['factors']
                territory.score_updated_at = timezone.now()
                territory.save(update_fields=[
                    'performance_score', 'efficiency_score', 'growth_score',
                    'score_factors', 'score_updated_at'
                ])
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to calculate score for territory {territory.id}: {e}")
        
        logger.info(f"Updated scores for {updated_count} territories")
        
        return {
            'status': 'completed',
            'updated_territories': updated_count
        }
        
    except Exception as e:
        logger.error(f"Territory scoring task failed: {e}")
        raise


@shared_task(base=TenantAwareTask, bind=True)
def refresh_engagement_scores_task(self, tenant_id, days_back=30):
    """
    Refresh customer engagement scores based on recent interactions
    """
    try:
        tenant = get_tenant_by_id(tenant_id)
        service = ScoringService(tenant=tenant)
        
        # Get contacts to refresh
        contacts = Contact.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        updated_count = 0
        
        for contact in contacts:
            try:
                # Calculate engagement score
                engagement_data = service.calculate_engagement_score(
                    contact=contact,
                    days_back=days_back
                )
                
                # Update contact
                contact.engagement_score = engagement_data['score']
                contact.engagement_level = engagement_data['level']
                contact.last_engagement_date = engagement_data.get('last_engagement_date')
                contact.engagement_updated_at = timezone.now()
                contact.save(update_fields=[
                    'engagement_score', 'engagement_level',
                    'last_engagement_date', 'engagement_updated_at'
                ])
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update engagement score for contact {contact.id}: {e}")
        
        logger.info(f"Updated engagement scores for {updated_count} contacts")
        
        return {
            'status': 'completed',
            'updated_contacts': updated_count
        }
        
    except Exception as e:
        logger.error(f"Engagement score refresh failed: {e}")
        raise