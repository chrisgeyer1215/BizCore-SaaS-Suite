# ============================================================================
# backend/apps/crm/services/product_service.py - Advanced Product Management Service
# ============================================================================

import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField, Max, Min
from django.core.cache import cache
import logging

from .base import BaseService, ServiceException
from ..models import (
    Product, ProductCategory, PricingModel, ProductBundle, ProductVariant,
    ProductPrice, PriceRule, ProductPerformance, ProductRecommendation,
    ProductInventory, ProductDiscount, ProductMetrics, BundleComponent
)

logger = logging.getLogger(__name__)


class ProductException(ServiceException):
    """Product management specific errors"""
    pass


class PricingEngine:
    """Advanced pricing engine with dynamic strategies"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.pricing_strategies = {
            'cost_plus': self._cost_plus_pricing,
            'value_based': self._value_based_pricing,
            'competition_based': self._competition_based_pricing,
            'dynamic': self._dynamic_pricing,
            'bundle_optimization': self._bundle_optimization_pricing,
            'customer_segment': self._customer_segment_pricing
        }
    
    def calculate_optimal_price(self, product, strategy: str, parameters: Dict = None) -> Dict:
        """Calculate optimal price using specified strategy"""
        try:
            if strategy not in self.pricing_strategies:
                raise ProductException(f"Unknown pricing strategy: {strategy}")
            
            pricing_function = self.pricing_strategies[strategy]
            result = pricing_function(product, parameters or {})
            
            # Add confidence score and recommendations
            result['confidence_score'] = self._calculate_confidence_score(product, result, strategy)
            result['pricing_recommendations'] = self._generate_pricing_recommendations(
                product, result, strategy
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Pricing calculation failed: {e}", exc_info=True)
            raise ProductException(f"Pricing calculation failed: {str(e)}")
    
    def _cost_plus_pricing(self, product, parameters: Dict) -> Dict:
        """Cost-plus pricing strategy"""
        base_cost = product.cost or Decimal('0.00')
        margin_percentage = parameters.get('margin_percentage', 30)  # 30% default margin
        
        markup = base_cost * (Decimal(margin_percentage) / 100)
        suggested_price = base_cost + markup
        
        return {
            'strategy': 'cost_plus',
            'base_cost': base_cost,
            'margin_percentage': margin_percentage,
            'markup_amount': markup,
            'suggested_price': suggested_price,
            'minimum_price': base_cost * Decimal('1.10'),  # 10% minimum margin
            'competitive_position': 'cost_focused'
        }
    
    def _dynamic_pricing(self, product, parameters: Dict) -> Dict:
        """Dynamic pricing based on demand, inventory, and market conditions"""
        base_price = product.base_price or Decimal('100.00')
        
        # Demand factor (from recent sales)
        recent_sales = self._get_recent_sales_data(product, days=30)
        demand_factor = min(1.5, max(0.8, recent_sales['velocity_factor']))
        
        # Inventory factor
        inventory_level = getattr(product, 'inventory_level', 100)
        if inventory_level < 10:
            inventory_factor = 1.2  # Price increase for low stock
        elif inventory_level > 100:
            inventory_factor = 0.9  # Price decrease for high stock
        else:
            inventory_factor = 1.0
        
        # Competition factor
        competition_factor = self._calculate_competition_factor(product)
        
        # Seasonal factor
        seasonal_factor = self._calculate_seasonal_factor(product, timezone.now())
        
        # Calculate dynamic price
        dynamic_multiplier = demand_factor * inventory_factor * competition_factor * seasonal_factor
        suggested_price = base_price * Decimal(str(dynamic_multiplier))
        
        return {
            'strategy': 'dynamic',
            'base_price': base_price,
            'demand_factor': demand_factor,
            'inventory_factor': inventory_factor,
            'competition_factor': competition_factor,
            'seasonal_factor': seasonal_factor,
            'dynamic_multiplier': dynamic_multiplier,
            'suggested_price': suggested_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'price_range': {
                'min': base_price * Decimal('0.8'),
                'max': base_price * Decimal('1.4')
            }
        }


class ProductAnalytics:
    """Advanced product analytics and insights"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def analyze_product_performance(self, product, period_days: int = 90) -> Dict:
        """Comprehensive product performance analysis"""
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Sales metrics
        sales_metrics = self._calculate_sales_metrics(product, start_date)
        
        # Customer analytics
        customer_analytics = self._analyze_customer_behavior(product, start_date)
        
        # Revenue analytics
        revenue_analytics = self._calculate_revenue_metrics(product, start_date)
        
        # Competitive analysis
        competitive_analysis = self._analyze_competitive_position(product)
        
        # Trend analysis
        trend_analysis = self._analyze_performance_trends(product, start_date, period_days)
        
        # Predictions
        predictions = self._generate_performance_predictions(product, trend_analysis)
        
        return {
            'product_id': product.id,
            'product_name': product.name,
            'analysis_period': f'{period_days} days',
            'sales_metrics': sales_metrics,
            'customer_analytics': customer_analytics,
            'revenue_analytics': revenue_analytics,
            'competitive_analysis': competitive_analysis,
            'trend_analysis': trend_analysis,
            'predictions': predictions,
            'generated_at': timezone.now().isoformat()
        }
    
    def _calculate_sales_metrics(self, product, start_date: datetime) -> Dict:
        """Calculate comprehensive sales metrics"""
        from apps.inventory.models import StockMovement
        from apps.ecommerce.models import OrderItem
        
        # Get sales data (assuming integration with order system)
        sales_data = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=start_date,
            order__status='COMPLETED'
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('price') * F('quantity')),
            average_quantity=Avg('quantity'),
            total_orders=Count('order', distinct=True)
        )
        
        return {
            'units_sold': sales_data['total_quantity'] or 0,
            'total_revenue': sales_data['total_revenue'] or Decimal('0.00'),
            'average_order_quantity': sales_data['average_quantity'] or 0,
            'total_orders': sales_data['total_orders'] or 0,
            'average_selling_price': (
                sales_data['total_revenue'] / sales_data['total_quantity'] 
                if sales_data['total_quantity'] else Decimal('0.00')
            )
        }


class ProductRecommendationEngine:
    """AI-powered product recommendation system"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def generate_product_recommendations(self, context: Dict) -> List[Dict]:
        """Generate intelligent product recommendations"""
        recommendation_type = context.get('type', 'cross_sell')
        
        if recommendation_type == 'cross_sell':
            return self._generate_cross_sell_recommendations(context)
        elif recommendation_type == 'upsell':
            return self._generate_upsell_recommendations(context)
        elif recommendation_type == 'bundle':
            return self._generate_bundle_recommendations(context)
        elif recommendation_type == 'similar':
            return self._generate_similar_product_recommendations(context)
        else:
            return self._generate_general_recommendations(context)
    
    def _generate_cross_sell_recommendations(self, context: Dict) -> List[Dict]:
        """Generate cross-selling recommendations"""
        base_product_id = context.get('product_id')
        customer_id = context.get('customer_id')
        limit = context.get('limit', 5)
        
        try:
            # Find frequently bought together products
            # This would involve analyzing order history for product combinations
            base_product = Product.objects.get(id=base_product_id, tenant=self.tenant)
            
            # Simplified recommendation logic (can be enhanced with ML)
            recommendations = Product.objects.filter(
                tenant=self.tenant,
                category=base_product.category,
                is_active=True
            ).exclude(
                id=base_product_id
            ).order_by('-popularity_score')[:limit]
            
            return [
                {
                    'product_id': product.id,
                    'product_name': product.name,
                    'recommendation_score': 0.85,  # Would be calculated by ML model
                    'reason': f'Frequently bought with {base_product.name}',
                    'expected_conversion_rate': 0.23
                }
                for product in recommendations
            ]
            
        except Exception as e:
            logger.error(f"Cross-sell recommendation failed: {e}")
            return []


class ProductService(BaseService):
    """Comprehensive product management service with advanced features"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pricing_engine = PricingEngine(self.tenant)
        self.analytics = ProductAnalytics(self.tenant)
        self.recommendation_engine = ProductRecommendationEngine(self.tenant)
    
    # ============================================================================
    # PRODUCT MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_ variants: List[Dict] = None,
                      pricing_rules: List[Dict] = None, initial_inventory: Dict = None) -> Product:
        """
        Create product with variants, pricing rules, and inventory
        
        Args information
            variants: Product variants (size, color, etc.)
            pricing_rules: Dynamic pricing rules
            initial_inventory: Initial inventory levels
        
        Returns:
            Product instance
        """
        self.context.operation = 'create_product'
        
        try:
            self.validate_user_permission('crm.add_product')
            
            # Validate required fields
            required_fields = ['name', 'category_id']
            is_valid, errors = self.validate_data(product_data, {
                field: {'required': True} for field in required_fields
            })
            
            if not is_valid:
                raise ProductException(f"Validation failed: {', '.join(errors)}")
            
            # Check for duplicate SKU
            sku = product_data.get('sku')
            if sku and Product.objects.filter(sku=sku, tenant=self.tenant).exists():
                raise ProductException(f"Product with SKU '{sku}' already exists")
            
            # Generate SKU if not provided
            if not sku:
                sku = self._generate_product_sku(product_data)
            
            # Create product
            product = Product.objects.create(
                tenant=self.tenant,
                name=product_data['name'],
                description=product_data.get('description', ''),
                sku=sku,
                category_id=product_data['category_id'],
                base_price=product_data.get('base_price', Decimal('0.00')),
                cost=product_data.get('cost', Decimal('0.00')),
                weight=product_data.get('weight'),
                dimensions=product_data.get('dimensions', {}),
                is_active=product_data.get('is_active', True),
                is_digital=product_data.get('is_digital', False),
                track_inventory=product_data.get('track_inventory', True),
                minimum_stock=product_data.get('minimum_stock', 0),
                maximum_stock=product_data.get('maximum_stock'),
                reorder_point=product_data.get('reorder_point'),
                tags=product_data.get('tags', []),
                metadata={
                    'creation_source': 'manual',
                    'created_by_user': self.user.id,
                    **(product_data.get('metadata', {}))
                },
                created_by=self.user
            )
            
            # Create variants
            if variants:
                self._create_product_variants(product, variants)
            
            # Create pricing rules
            if pricing_rules:
                self._create_pricing_rules(product, pricing_rules)
            
            # Set up initial inventory
            if initial_inventory and product.track_inventory:
                self._setup_initial_inventory(product, initial_inventory)
            
            # Initialize performance tracking
            self._initialize_product_performance_tracking(product)
            
            # Generate AI-powered recommendations for pricing and positioning
            ai_insights = self._generate_product_ai_insights(product)
            
            self.log_activity(
                'product_created',
                'Product',
                product.id,
                {
                    'name': product.name,
                    'sku': product.sku,
                    'category': product.category.name,
                    'variants_count': len(variants) if variants else 0,
                    'ai_insights': ai_insights
                }
            )
            
            return product
            
        except Exception as e:
            logger.error(f"Product creation failed: {e}", exc_info=True)
            raise ProductException(f"Product creation failed: {str(e)}")
    
    def get_product_catalog(self, filters: Dict = None, sort_by: str = 'name',
                           include_variants: bool = True, include_pricing: bool = True) -> Dict:
        """
        Get comprehensive product catalog with advanced filtering
        
        Args:
            filters: Filter criteria
            sort_by: Sort field
            include_variants: Include product variants
            include_pricing: Include pricing information
        
        Returns:
            Product catalog data
        """
        try:
            # Build base query
            queryset = Product.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).select_related('category').prefetch_related('variants', 'pricing_models')
            
            # Apply filters
            if filters:
                if 'category_id' in filters:
                    queryset = queryset.filter(category_id=filters['category_id'])
                
                if 'price_range' in filters:
                    min_price, max_price = filters['price_range']
                    queryset = queryset.filter(
                        base_price__gte=min_price,
                        base_price__lte=max_price
                    )
                
                if 'tags' in filters:
                    for tag in filters['tags']:
                        queryset = queryset.filter(tags__contains=[tag])
                
                if 'search' in filters:
                    search_term = filters['search']
                    queryset = queryset.filter(
                        Q(name__icontains=search_term) |
                        Q(description__icontains=search_term) |
                        Q(sku__icontains=search_term)
                    )
                
                if 'availability' in filters:
                    if filters['availability'] == 'in_stock':
                        queryset = queryset.filter(inventory_level__gt=0)
                    elif filters['availability'] == 'low_stock':
                        queryset = queryset.filter(
                            inventory_level__lte=F('minimum_stock'),
                            inventory_level__gt=0
                        )
                    elif filters['availability'] == 'out_of_stock':
                        queryset = queryset.filter(inventory_level=0)
            
            # Apply sorting
            sort_options = {
                'name': 'name',
                'price_asc': 'base_price',
                'price_desc': '-base_price',
                'popularity': '-popularity_score',
                'newest': '-created_at',
                'best_selling': '-total_sales'
            }
            
            if sort_by in sort_options:
                queryset = queryset.order_by(sort_options[sort_by])
            
            # Format products
            products = []
            for product in queryset:
                product_data = {
                    'id': product.id,
                    'name': product.name,
                    'description': product.description,
                    'sku': product.sku,
                    'base_price': product.base_price,
                    'category': {
                        'id': product.category.id,
                        'name': product.category.name,
                        'color': getattr(product.category, 'color', '#6366f1')
                    },
                    'is_digital': product.is_digital,
                    'inventory_level': getattr(product, 'inventory_level', 0),
                    'minimum_stock': product.minimum_stock,
                    'tags': product.tags,
                    'popularity_score': getattr(product, 'popularity_score', 0),
                    'rating': getattr(product, 'average_rating', 0),
                    'images': product.metadata.get('images', []) if product.metadata else []
                }
                
                # Include variants if requested
                if include_variants and product.variants.exists():
                    product_data['variants'] = [
                        {
                            'id': variant.id,
                            'name': variant.name,
                            'sku': variant.sku,
                            'price_adjustment': variant.price_adjustment,
                            'attributes': variant.attributes
                        }
                        for variant in product.variants.filter(is_active=True)
                    ]
                
                # Include pricing if requested
                if include_pricing:
                    pricing_data = self._get_product_pricing_data(product)
                    product_data['pricing'] = pricing_data
                
                products.append(product_data)
            
            # Catalog metadata
            catalog_metadata = {
                'total_products': len(products),
                'categories': self._get_catalog_categories_summary(),
                'price_range': self._get_catalog_price_range(),
                'filters_applied': filters or {},
                'sort_by': sort_by
            }
            
            return {
                'products': products,
                'metadata': catalog_metadata,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Catalog retrieval failed: {e}", exc_info=True)
            raise ProductException(f"Catalog retrieval failed: {str(e)}")
    
    # ============================================================================
    # PRICING MANAGEMENT
    # ============================================================================
    
    @transaction.atomic
    def create_pricing_strategy(self, product_id: int PricingModel:
        """
        Create dynamic pricing strategy for product
        
        Args:
            product_id: Product ID
             Pricing strategy configuration
        
        Returns:
            PricingModel instance
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            self.validate_user_permission('crm.change_product', product)
            
            # Calculate optimal prices using the pricing engine
            pricing_result = self.pricing_engine.calculate_optimal_price(
                product, 
                strategy_data['strategy_type'],
                strategy_data.get('parameters', {})
            )
            
            # Create pricing model
            pricing_model = PricingModel.objects.create(
                product=product,
                name=strategy_data['name'],
                strategy_type=strategy_data['strategy_type'],
                base_price=pricing_result['suggested_price'],
                minimum_price=pricing_result.get('minimum_price', product.base_price * Decimal('0.8')),
                maximum_price=pricing_result.get('maximum_price', product.base_price * Decimal('1.5')),
                parameters=strategy_data.get('parameters', {}),
                is_active=strategy_data.get('is_active', True),
                effective_date=strategy_data.get('effective_date', timezone.now()),
                expires_date=strategy_data.get('expires_date'),
                tenant=self.tenant,
                created_by=self.user,
                metadata={
                    'pricing_calculation': pricing_result,
                    'confidence_score': pricing_result.get('confidence_score', 0.7)
                }
            )
            
            # Update product base price if this is the primary pricing model
            if strategy_data.get('is_primary', False):
                product.base_price = pricing_result['suggested_price']
                product.save(update_fields=['base_price'])
            
            # Create pricing rules based on strategy
            self._create_dynamic_pricing_rules(pricing_model, pricing_result)
            
            self.log_activity(
                'pricing_strategy_created',
                'PricingModel',
                pricing_model.id,
                {
                    'product_name': product.name,
                    'strategy_type': strategy_data['strategy_type'],
                    'suggested_price': pricing_result['suggested_price'],
                    'confidence_score': pricing_result.get('confidence_score', 0)
                }
            )
            
            return pricing_model
            
        except Product.DoesNotExist:
            raise ProductException("Product not found")
        except Exception as e:
            logger.error(f"Pricing strategy creation failed: {e}", exc_info=True)
            raise ProductException(f"Pricing strategy creation failed: {str(e)}")
    
    def calculate_dynamic_price(self, product_id: int, context: Dict = None) -> Dict:
        """
        Calculate dynamic price based on current market conditions
        
        Args:
            product_id: Product ID
            context: Pricing context (customer, quantity, etc.)
        
        Returns:
            Dynamic pricing information
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            # Get active pricing models
            active_pricing_models = product.pricing_models.filter(
                is_active=True,
                effective_date__lte=timezone.now()
            ).filter(
                Q(expires_date__isnull=True) | Q(expires_date__gt=timezone.now())
            ).order_by('-created_at')
            
            if not active_pricing_models.exists():
                # Use base price if no dynamic pricing
                return {
                    'base_price': product.base_price,
                    'final_price': product.base_price,
                    'pricing_type': 'static',
                    'discounts_applied': [],
                    'calculated_at': timezone.now().isoformat()
                }
            
            primary_model = active_pricing_models.first()
            
            # Calculate dynamic price using the pricing engine
            pricing_result = self.pricing_engine.calculate_optimal_price(
                product,
                primary_model.strategy_type,
                {
                    **primary_model.parameters,
                    **(context or {})
                }
            )
            
            # Apply additional discounts and rules
            final_price = pricing_result['suggested_price']
            discounts_applied = []
            
            # Customer segment discounts
            if context and 'customer_id' in context:
                customer_discounts = self._calculate_customer_discounts(
                    product, context['customer_id']
                )
                if customer_discounts:
                    final_price *= (1 - customer_discounts['discount_percentage'] / 100)
                    discounts_applied.extend(customer_discounts['applied_discounts'])
            
            # Quantity discounts
            if context and 'quantity' in context:
                quantity_discount = self._calculate_quantity_discount(product, context['quantity'])
                if quantity_discount:
                    final_price *= (1 - quantity_discount['discount_percentage'] / 100)
                    discounts_applied.append(quantity_discount)
            
            # Ensure price bounds
            final_price = max(primary_model.minimum_price, min(primary_model.maximum_price, final_price))
            
            return {
                'base_price': product.base_price,
                'suggested_price': pricing_result['suggested_price'],
                'final_price': final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'pricing_type': primary_model.strategy_type,
                'pricing_factors': pricing_result,
                'discounts_applied': discounts_applied,
                'savings_amount': product.base_price - final_price,
                'savings_percentage': float((product.base_price - final_price) / product.base_price * 100) if product.base_price > 0 else 0,
                'calculated_at': timezone.now().isoformat()
            }
            
        except Product.DoesNotExist:
            raise ProductException("Product not found")
        except Exception as e:
            logger.error(f"Dynamic pricing calculation failed: {e}", exc_info=True)
            raise ProductException(f"Dynamic pricing calculation failed: {str(e)}")
    
    # ============================================================================
    # PRODUCT BUNDLES
    # ============================================================================
    
    @transaction.atomic
    def create_product_bundle(self, bundle: List[Dict]) -> ProductBundle:
        """
        Create product bundle with intelligent pricing optimization
        
        Args:
            
            components: List of component products with quantities
        
        Returns:
            ProductBundle instance
        """
        try:
            self.validate_user_permission('crm.add_productbundle')
            
            # Validate components
            if not components:
                raise ProductException("Bundle must have at least one component")
            
            # Get component products
            component_products = []
            total_individual_price = Decimal('0.00')
            
            for component in components:
                product = Product.objects.get(
                    id=component['product_id'], 
                    tenant=self.tenant,
                    is_active=True
                )
                quantity = component.get('quantity', 1)
                component_products.append((product, quantity))
                total_individual_price += product.base_price * quantity
            
            # Calculate optimal bundle price
            suggested_bundle_price = self._calculate_optimal_bundle_price(
                component_products, bundle_data.get('target_discount_percentage', 15)
            )
            
            # Create bundle
            bundle = ProductBundle.objects.create(
                tenant=self.tenant,
                name=bundle_data['name'],
                description=bundle_data.get('description', ''),
                bundle_type=bundle_data.get('bundle_type', 'FIXED'),
                bundle_price=bundle_data.get('bundle_price', suggested_bundle_price),
                individual_price=total_individual_price,
                discount_percentage=float((total_individual_price - suggested_bundle_price) / total_individual_price * 100),
                is_active=bundle_data.get('is_active', True),
                minimum_quantity=bundle_data.get('minimum_quantity', 1),
                maximum_quantity=bundle_data.get('maximum_quantity'),
                metadata={
                    'pricing_optimization': {
                        'suggested_price': suggested_bundle_price,
                        'total_individual_price': total_individual_price,
                        'optimization_strategy': 'demand_elasticity'
                    }
                },
                created_by=self.user
            )
            
            # Create bundle components
            for product, quantity in component_products:
                BundleComponent.objects.create(
                    bundle=bundle,
                    product=product,
                    quantity=quantity,
                    is_required=True,
                    tenant=self.tenant
                )
            
            # Generate bundle recommendations
            bundle_insights = self._generate_bundle_insights(bundle, component_products)
            
            self.log_activity(
                'product_bundle_created',
                'ProductBundle',
                bundle.id,
                {
                    'name': bundle.name,
                    'components_count': len(components),
                    'bundle_price': suggested_bundle_price,
                    'discount_percentage': bundle.discount_percentage,
                    'insights': bundle_insights
                }
            )
            
            return bundle
            
        except Product.DoesNotExist:
            raise ProductException("One or more component products not found")
        except Exception as e:
            logger.error(f"Bundle creation failed: {e}", exc_info=True)
            raise ProductException(f"Bundle creation failed: {str(e)}")
    
    def optimize_bundle_pricing(self, bundle_id: int, optimization_criteria: Dict = None) -> Dict:
        """
        Optimize bundle pricing using advanced analytics
        
        Args:
            bundle_id: Bundle ID
            optimization_criteria: Optimization parameters
        
        Returns:
            Optimization results and recommendations
        """
        try:
            bundle = ProductBundle.objects.get(id=bundle_id, tenant=self.tenant)
            self.validate_user_permission('crm.change_productbundle', bundle)
            
            # Get bundle components
            components = bundle.components.select_related('product').filter(is_active=True)
            
            # Calculate current metrics
            current_metrics = self._calculate_bundle_performance_metrics(bundle)
            
            # Generate pricing scenarios
            pricing_scenarios = self._generate_bundle_pricing_scenarios(
                bundle, components, optimization_criteria or {}
            )
            
            # Select optimal scenario
            optimal_scenario = self._select_optimal_pricing_scenario(pricing_scenarios, current_metrics)
            
            # Calculate impact projections
            impact_projections = self._calculate_bundle_optimization_impact(
                bundle, optimal_scenario, current_metrics
            )
            
            return {
                'bundle_id': bundle.id,
                'bundle_name': bundle.name,
                'current_metrics': current_metrics,
                'pricing_scenarios': pricing_scenarios,
                'optimal_scenario': optimal_scenario,
                'impact_projections': impact_projections,
                'recommendations': self._generate_bundle_optimization_recommendations(
                    bundle, optimal_scenario
                ),
                'generated_at': timezone.now().isoformat()
            }
            
        except ProductBundle.DoesNotExist:
            raise ProductException("Bundle not found")
        except Exception as e:
            logger.error(f"Bundle optimization failed: {e}", exc_info=True)
            raise ProductException(f"Bundle optimization failed: {str(e)}")
    
    # ============================================================================
    # PRODUCT ANALYTICS AND INSIGHTS
    # ============================================================================
    
    def get_product_performance_analytics(self, product_id: int = None, 
                                        period: str = '90d') -> Dict:
        """
        Get comprehensive product performance analytics
        
        Args:
            product_id: Specific product (all products if None)
            period: Analysis period
        
        Returns:
            Performance analytics data
        """
        try:
            # Calculate date range
            period_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = period_days.get(period, 90)
            
            if product_id:
                product = Product.objects.get(id=product_id, tenant=self.tenant)
                analytics_data = self.analytics.analyze_product_performance(product, days)
                return {
                    'single_product': True,
                    'analytics': analytics_data
                }
            else:
                # Analyze all products
                products = Product.objects.filter(
                    tenant=self.tenant,
                    is_active=True
                ).select_related('category')
                
                all_analytics = []
                for product in products:
                    product_analytics = self.analytics.analyze_product_performance(product, days)
                    all_analytics.append(product_analytics)
                
                # Generate summary insights
                summary_insights = self._generate_portfolio_insights(all_analytics)
                
                return {
                    'single_product': False,
                    'product_analytics': all_analytics,
                    'portfolio_insights': summary_insights,
                    'period': period,
                    'total_products_analyzed': len(all_analytics)
                }
            
        except Product.DoesNotExist:
            raise ProductException("Product not found")
        except Exception as e:
            logger.error(f"Analytics generation failed: {e}", exc_info=True)
            raise ProductException(f"Analytics generation failed: {str(e)}")
    
    def generate_product_recommendations(self, context: Dict) -> List[Dict]:
        """
        Generate AI-powered product recommendations
        
        Args:
            context: Recommendation context
        
        Returns:
            List of product recommendations
        """
        try:
            return self.recommendation_engine.generate_product_recommendations(context)
            
        except Exception as e:
            logger.error(f"Product recommendations failed: {e}", exc_info=True)
            raise ProductException(f"Recommendations failed: {str(e)}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_product_sku(self, product_data: Dict) -> str:
        """Generate unique product SKU"""
        category_id = product_data.get('category_id')
        if category_id:
            try:
                category = ProductCategory.objects.get(id=category_id)
                category_code = category.name[:3].upper()
            except ProductCategory.DoesNotExist:
                category_code = 'GEN'
        else:
            category_code = 'GEN'
        
        # Generate sequential number
        last_product = Product.objects.filter(
            tenant=self.tenant,
            sku__startswith=category_code
        ).order_by('-created_at').first()
        
        if last_product and last_product.sku:
            try:
                last_number = int(last_product.sku[-4:])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1
        
        return f"{category_code}-{next_number:04d}"
    
    def _create_product_variants(self, product: Product, variants: List[Dict]):
        """Create product variants"""
        for variant_data in variants:
            ProductVariant.objects.create(
                product=product,
                name=variant_data['name'],
                sku=variant_data.get('sku', f"{product.sku}-{variant_data['name'][:3].upper()}"),
                price_adjustment=variant_data.get('price_adjustment', Decimal('0.00')),
                cost_adjustment=variant_data.get('cost_adjustment', Decimal('0.00')),
                attributes=variant_data.get('attributes', {}),
                is_active=variant_data.get('is_active', True),
                tenant=self.tenant
            )
    
    def _calculate_optimal_bundle_price(self, component_products: List[Tuple], 
                                      target_discount: float) -> Decimal:
        """Calculate optimal bundle price using demand elasticity"""
        total_individual_price = sum(
            product.base_price * quantity 
            for product, quantity in component_products
        )
        
        # Apply target discount
        bundle_price = total_individual_price * (1 - target_discount / 100)
        
        # Apply demand elasticity adjustments (simplified model)
        # In a real implementation, this would use ML models and historical data
        elasticity_adjustment = 0.95  # Slightly reduce price to increase demand
        
        return (bundle_price * Decimal(str(elasticity_adjustment))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    
    def _generate_product_ai_insights(self, product: Product) -> Dict:
        """Generate AI insights for new product"""
        insights = {}
        
        try:
            # Category-based insights
            category_products = Product.objects.filter(
                category=product.category,
                tenant=self.tenant
            ).exclude(id=product.id)
            
            if category_products.exists():
                avg_price = category_products.aggregate(Avg('base_price'))['base_price__avg']
                insights['price_positioning'] = (
                    'premium' if product.base_price > avg_price * 1.2 else
                    'budget' if product.base_price < avg_price * 0.8 else
                    'competitive'
                )
                
                insights['category_benchmarks'] = {
                    'average_price': avg_price,
                    'price_variance': float((product.base_price - avg_price) / avg_price * 100) if avg_price else 0
                }
            
            # Market opportunity
            insights['market_opportunity'] = self._assess_market_opportunity(product)
            
            # Pricing recommendations
            insights['pricing_recommendations'] = [
                f"Consider {product.category.name} category pricing trends",
                "Monitor competitor pricing for similar products",
                "Test different price points to optimize conversion"
            ]
            
        except Exception as e:
            logger.error(f"AI insights generation failed: {e}")
            insights['error'] = 'AI insights temporarily unavailable'
        
        return insights
    
    def _assess_market_opportunity(self, product: Product) -> str:
        """Assess market opportunity for product"""
        # Simplified market assessment
        category_product_count = Product.objects.filter(
            category=product.category,
            tenant=self.tenant,
            is_active=True
        ).count()
        
        if category_product_count < 5:
            return 'High - Low competition in category'
        elif category_product_count < 15:
            return 'Medium - Moderate competition'
        else:
            return 'Competitive - High competition, differentiation needed'
    
    def _get_product_pricing_data(self, product: Product) -> Dict:
        """Get comprehensive pricing data for product"""
        # Get current pricing models
        pricing_models = product.pricing_models.filter(is_active=True)
        
        pricing_data = {
            'base_price': product.base_price,
            'current_price': product.base_price,  # Would be calculated dynamically
            'pricing_strategies': [],
            'price_history': [],
            'discounts_available': []
        }
        
        # Add pricing strategies
        for model in pricing_models:
            pricing_data['pricing_strategies'].append({
                'name': model.name,
                'strategy_type': model.strategy_type,
                'minimum_price': model.minimum_price,
                'maximum_price': model.maximum_price
            })
        
        return pricing_data
    
    def _get_catalog_categories_summary(self) -> List[Dict]:
        """Get catalog categories summary"""
        categories = ProductCategory.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')
        
        return [
            {
                'id': category.id,
                'name': category.name,
                'product_count': category.product_count,
                'color': getattr(category, 'color', '#6366f1')
            }
            for category in categories
        ]
    
    def _get_catalog_price_range(self) -> Dict:
        """Get catalog price range"""
        price_stats = Product.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).aggregate(
            min_price=Min('base_price'),
            max_price=Max('base_price'),
            avg_price=Avg('base_price')
        )
        
        return {
            'minimum': price_stats['min_price'] or Decimal('0.00'),
            'maximum': price_stats['max_price'] or Decimal('0.00'),
            'average': price_stats['avg_price'] or Decimal('0.00')
        }