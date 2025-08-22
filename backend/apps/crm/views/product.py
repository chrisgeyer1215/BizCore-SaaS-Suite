# ============================================================================
# backend/apps/crm/views/product.py - Product Management Views
# ============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.db.models import Q, Count, Sum, Avg, F, Case, When, DecimalField
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .base import CRMBaseMixin, CRMBaseViewSet
from ..models import ProductCategory, Product, PricingModel, ProductBundle
from ..serializers import ProductCategorySerializer, ProductSerializer, PricingModelSerializer, ProductBundleSerializer
from ..permissions import ProductPermission
from ..filters import ProductFilter, ProductCategoryFilter
from ..services import ProductService


class ProductCategoryListView(CRMBaseMixin, ListView):
    """Product Category list view with hierarchy"""
    
    model = ProductCategory
    template_name = 'crm/product/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations
        queryset = queryset.annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            subcategory_count=Count('children'),
            total_revenue=Sum(
                Case(
                    When(
                        products__opportunity_products__opportunity__is_won=True,
                        then=F('products__opportunity_products__price') * F('products__opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).select_related('parent').prefetch_related('children')
        
        # Apply search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filter by parent category
        parent_id = self.request.GET.get('parent')
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        elif self.request.GET.get('root_only'):
            queryset = queryset.filter(parent__isnull=True)
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        categories = self.get_queryset()
        context.update({
            'total_categories': categories.count(),
            'active_categories': categories.filter(is_active=True).count(),
            'root_categories': categories.filter(parent__isnull=True),
            'category_hierarchy': self.build_category_hierarchy(),
            'category_performance': self.get_category_performance_data(),
        })
        
        return context
    
    def build_category_hierarchy(self):
        """Build hierarchical category structure"""
        def build_tree(parent_id=None):
            categories = self.request.tenant.product_categories.filter(
                parent_id=parent_id,
                is_active=True
            ).annotate(
                product_count=Count('products', filter=Q(products__is_active=True))
            )
            
            tree = []
            for category in categories:
                tree.append({
                    'id': category.id,
                    'name': category.name,
                    'product_count': category.product_count,
                    'children': build_tree(category.id)
                })
            
            return tree
        
        return build_tree()
    
    def get_category_performance_data(self):
        """Get performance data for top categories"""
        categories = self.get_queryset().order_by('-total_revenue')[:10]
        
        performance = []
        for category in categories:
            performance.append({
                'name': category.name,
                'product_count': category.product_count,
                'revenue': float(category.total_revenue or 0),
                'subcategories': category.subcategory_count,
            })
        
        return performance


class ProductListView(CRMBaseMixin, ListView):
    """Product list view with comprehensive filtering and analytics"""
    
    model = Product
    template_name = 'crm/product/list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations for analytics
        queryset = queryset.annotate(
            opportunities_count=Count('opportunity_products', distinct=True),
            total_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            avg_selling_price=Avg(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then='opportunity_products__price'
                    ),
                    default=None,
                    output_field=DecimalField()
                )
            ),
            last_sold=Case(
                When(
                    opportunity_products__opportunity__is_won=True,
                    then='opportunity_products__opportunity__closed_date'
                ),
                default=None
            )
        ).select_related('category').prefetch_related('bundles_containing')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(description__icontains=search)
            )
        
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        price_range = self.request.GET.get('price_range')
        if price_range:
            min_price, max_price = price_range.split('-')
            queryset = queryset.filter(
                base_price__gte=float(min_price),
                base_price__lte=float(max_price)
            )
        
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif status_filter == 'top_selling':
            queryset = queryset.filter(opportunities_count__gt=0).order_by('-total_revenue')
        elif status_filter == 'never_sold':
            queryset = queryset.filter(opportunities_count=0)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')
        if sort_by == 'revenue':
            queryset = queryset.order_by('-total_revenue')
        elif sort_by == 'price':
            queryset = queryset.order_by('-base_price')
        elif sort_by == 'popularity':
            queryset = queryset.order_by('-opportunities_count')
        else:
            queryset = queryset.order_by('name')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        products = self.get_queryset()
        context.update({
            'total_products': products.count(),
            'active_products': products.filter(is_active=True).count(),
            'categories': self.request.tenant.product_categories.filter(is_active=True),
            'product_stats': self.get_product_statistics(),
            'top_products': self.get_top_products(),
            'price_ranges': self.get_price_ranges(),
        })
        
        return context
    
    def get_product_statistics(self):
        """Get overall product statistics"""
        products = self.request.tenant.products.all()
        
        return {
            'total_value': products.aggregate(Sum('base_price'))['base_price__sum'] or 0,
            'avg_price': products.aggregate(Avg('base_price'))['base_price__avg'] or 0,
            'never_sold_count': products.annotate(
                sales_count=Count('opportunity_products')
            ).filter(sales_count=0).count(),
            'top_performers': products.annotate(
                revenue=Sum(
                    Case(
                        When(
                            opportunity_products__opportunity__is_won=True,
                            then=F('opportunity_products__price') * F('opportunity_products__quantity')
                        ),
                        default=0,
                        output_field=DecimalField()
                    )
                )
            ).filter(revenue__gt=0).count()
        }
    
    def get_top_products(self):
        """Get top performing products"""
        return self.request.tenant.products.annotate(
            revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(revenue__gt=0).order_by('-revenue')[:5]
    
    def get_price_ranges(self):
        """Get price range distribution"""
        products = self.request.tenant.products.filter(is_active=True)
        
        ranges = [
            ('0-100', 0, 100),
            ('100-500', 100, 500),
            ('500-1000', 500, 1000),
            ('1000-5000', 1000, 5000),
            ('5000+', 5000, float('inf')),
        ]
        
        range_data = []
        for label, min_price, max_price in ranges:
            if max_price == float('inf'):
                count = products.filter(base_price__gte=min_price).count()
            else:
                count = products.filter(
                    base_price__gte=min_price,
                    base_price__lt=max_price
                ).count()
            
            range_data.append({
                'label': label,
                'count': count,
                'value': f"{min_price}-{max_price}" if max_price != float('inf') else f"{min_price}+"
            })
        
        return range_data


class ProductDetailView(CRMBaseMixin, DetailView):
    """Product detail view with comprehensive analytics"""
    
    model = Product
    template_name = 'crm/product/detail.html'
    context_object_name = 'product'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().select_related('category').prefetch_related(
                'opportunity_products__opportunity',
                'bundles_containing__bundle',
                'pricing_models'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        
        context.update({
            'product_analytics': self.get_product_analytics(product),
            'sales_performance': self.get_sales_performance(product),
            'pricing_analysis': self.get_pricing_analysis(product),
            'opportunity_history': self.get_opportunity_history(product),
            'bundle_information': self.get_bundle_information(product),
            'competitive_analysis': self.get_competitive_analysis(product),
            'monthly_trends': self.get_monthly_trends(product),
        })
        
        return context
    
    def get_product_analytics(self, product):
        """Get comprehensive product analytics"""
        opportunity_products = product.opportunity_products.select_related('opportunity')
        
        total_opportunities = opportunity_products.count()
        won_opportunities = opportunity_products.filter(opportunity__is_won=True)
        
        return {
            'total_opportunities': total_opportunities,
            'won_opportunities': won_opportunities.count(),
            'win_rate': (won_opportunities.count() / total_opportunities * 100) if total_opportunities > 0 else 0,
            'total_revenue': won_opportunities.aggregate(
                total=Sum(F('price') * F('quantity'))
            )['total'] or 0,
            'avg_selling_price': won_opportunities.aggregate(Avg('price'))['price__avg'] or 0,
            'total_quantity_sold': won_opportunities.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            'last_sold_date': won_opportunities.aggregate(
                last_sold=Case(
                    When(opportunity__closed_date__isnull=False, then='opportunity__closed_date'),
                    default=None
                )
            )['last_sold'],
        }
    
    def get_sales_performance(self, product):
        """Get sales performance metrics"""
        won_opportunities = product.opportunity_products.filter(opportunity__is_won=True)
        
        # Sales by month for last 12 months
        monthly_sales = []
        current_date = timezone.now().date().replace(day=1)
        
        for i in range(12):
            month_start = (current_date - timezone.timedelta(days=30*i)).replace(day=1)
            next_month = (month_start + timezone.timedelta(days=32)).replace(day=1)
            
            month_revenue = won_opportunities.filter(
                opportunity__closed_date__gte=month_start,
                opportunity__closed_date__lt=next_month
            ).aggregate(
                revenue=Sum(F('price') * F('quantity'))
            )['revenue'] or 0
            
            month_quantity = won_opportunities.filter(
                opportunity__closed_date__gte=month_start,
                opportunity__closed_date__lt=next_month
            ).aggregate(Sum('quantity'))['quantity__sum'] or 0
            
            monthly_sales.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': float(month_revenue),
                'quantity': month_quantity,
            })
        
        return {
            'monthly_sales': list(reversed(monthly_sales)),
            'best_month': max(monthly_sales, key=lambda x: x['revenue']) if monthly_sales else None,
            'sales_trend': self.calculate_sales_trend(monthly_sales),
        }
    
    def get_pricing_analysis(self, product):
        """Get pricing analysis and recommendations"""
        opportunity_products = product.opportunity_products.filter(opportunity__is_won=True)
        
        if not opportunity_products.exists():
            return {
                'base_price': product.base_price,
                'pricing_models': product.pricing_models.filter(is_active=True),
                'recommendations': ['No sales data available for pricing analysis']
            }
        
        selling_prices = opportunity_products.values_list('price', flat=True)
        
        analysis = {
            'base_price': product.base_price,
            'avg_selling_price': sum(selling_prices) / len(selling_prices),
            'min_selling_price': min(selling_prices),
            'max_selling_price': max(selling_prices),
            'price_variance': max(selling_prices) - min(selling_prices),
            'pricing_models': product.pricing_models.filter(is_active=True),
        }
        
        # Pricing recommendations
        recommendations = []
        if analysis['avg_selling_price'] > product.base_price * 1.1:
            recommendations.append('Consider increasing base price - selling above list price consistently')
        elif analysis['avg_selling_price'] < product.base_price * 0.9:
            recommendations.append('Review pricing strategy - selling below list price frequently')
        
        if analysis['price_variance'] > product.base_price * 0.3:
            recommendations.append('High price variance detected - consider standardizing pricing')
        
        analysis['recommendations'] = recommendations
        return analysis
    
    def get_opportunity_history(self, product):
        """Get opportunity history for product"""
        return product.opportunity_products.select_related(
            'opportunity__account', 'opportunity__owner'
        ).order_by('-opportunity__created_at')[:20]
    
    def get_bundle_information(self, product):
        """Get bundle information"""
        bundles = product.bundles_containing.select_related('bundle').filter(
            bundle__is_active=True
        )
        
        bundle_data = []
        for bundle_product in bundles:
            bundle = bundle_product.bundle
            bundle_data.append({
                'id': bundle.id,
                'name': bundle.name,
                'description': bundle.description,
                'bundle_price': bundle.bundle_price,
                'individual_price': bundle.individual_price,
                'discount_amount': bundle.discount_amount,
                'product_quantity': bundle_product.quantity,
            })
        
        return bundle_data
    
    def get_competitive_analysis(self, product):
        """Get competitive analysis (placeholder for future enhancement)"""
        # This would integrate with external data sources
        return {
            'market_position': 'Competitive',
            'price_compared_to_market': 'Average',
            'unique_features': product.features or 'Not specified',
            'recommendations': [
                'Monitor competitor pricing regularly',
                'Highlight unique value propositions',
                'Consider market positioning adjustments'
            ]
        }
    
    def get_monthly_trends(self, product):
        """Get monthly trend analysis"""
        trends = []
        current_date = timezone.now().date().replace(day=1)
        
        for i in range(6):  # Last 6 months
            month_start = (current_date - timezone.timedelta(days=30*i)).replace(day=1)
            next_month = (month_start + timezone.timedelta(days=32)).replace(day=1)
            
            month_data = product.opportunity_products.filter(
                opportunity__created_at__gte=month_start,
                opportunity__created_at__lt=next_month
            ).aggregate(
                total_opportunities=Count('id'),
                won_opportunities=Count('id', filter=Q(opportunity__is_won=True)),
                revenue=Sum(
                    Case(
                        When(opportunity__is_won=True, then=F('price') * F('quantity')),
                        default=0,
                        output_field=DecimalField()
                    )
                )
            )
            
            trends.append({
                'month': month_start.strftime('%B %Y'),
                'opportunities': month_data['total_opportunities'],
                'won': month_data['won_opportunities'],
                'revenue': float(month_data['revenue'] or 0),
                'win_rate': (month_data['won_opportunities'] / month_data['total_opportunities'] * 100) 
                           if month_data['total_opportunities'] > 0 else 0
            })
        
        return list(reversed(trends))
    
    def calculate_sales_trend(self, monthly_sales):
        """Calculate sales trend direction"""
        if len(monthly_sales) < 2:
            return 'insufficient_data'
        
        recent_months = monthly_sales[-3:]  # Last 3 months
        older_months = monthly_sales[-6:-3]  # Previous 3 months
        
        recent_avg = sum(m['revenue'] for m in recent_months) / len(recent_months)
        older_avg = sum(m['revenue'] for m in older_months) / len(older_months)
        
        if recent_avg > older_avg * 1.1:
            return 'increasing'
        elif recent_avg < older_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'


class ProductViewSet(CRMBaseViewSet):
    """Enhanced Product API viewset"""
    
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_class = ProductFilter
    search_fields = ['name', 'sku', 'description']
    ordering_fields = ['name', 'base_price', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('category').prefetch_related(
            'opportunity_products', 'bundles_containing'
        ).annotate(
            opportunities_count=Count('opportunity_products'),
            total_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get product analytics"""
        product = self.get_object()
        service = ProductService()
        
        analytics_data = service.get_product_analytics(product)
        return Response(analytics_data)
    
    @action(detail=True, methods=['get'])
    def pricing_history(self, request, pk=None):
        """Get pricing history for product"""
        product = self.get_object()
        
        # Get pricing models history
        pricing_history = product.pricing_models.all().order_by('-created_at')
        
        history_data = []
        for pricing_model in pricing_history:
            history_data.append({
                'date': pricing_model.created_at,
                'model_name': pricing_model.name,
                'base_price': pricing_model.base_price,
                'discount_percentage': pricing_model.discount_percentage,
                'minimum_price': pricing_model.minimum_price,
                'is_active': pricing_model.is_active,
            })
        
        return Response(history_data)
    
    @action(detail=True, methods=['get'])
    def sales_performance(self, request, pk=None):
        """Get sales performance metrics"""
        product = self.get_object()
        
        # Time period from query params
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        performance = product.opportunity_products.filter(
            opportunity__created_at__gte=start_date
        ).aggregate(
            total_opportunities=Count('id'),
            won_opportunities=Count('id', filter=Q(opportunity__is_won=True)),
            total_revenue=Sum(
                Case(
                    When(opportunity__is_won=True, then=F('price') * F('quantity')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            avg_deal_size=Avg(
                Case(
                    When(opportunity__is_won=True, then=F('price') * F('quantity')),
                    default=None,
                    output_field=DecimalField()
                )
            )
        )
        
        performance['win_rate'] = (
            performance['won_opportunities'] / performance['total_opportunities'] * 100
            if performance['total_opportunities'] > 0 else 0
        )
        
        return Response(performance)
    
    @action(detail=False, methods=['get'])
    def top_performers(self, request):
        """Get top performing products"""
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        top_products = self.get_queryset().filter(
            opportunity_products__opportunity__created_at__gte=start_date
        ).annotate(
            period_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        opportunity_products__opportunity__created_at__gte=start_date,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        ).filter(period_revenue__gt=0).order_by('-period_revenue')[:limit]
        
        serializer = self.get_serializer(top_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def price_optimization(self, request):
        """Get price optimization recommendations"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'Product IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = ProductService()
            optimization_results = service.optimize_pricing(
                product_ids=product_ids,
                tenant=request.tenant
            )
            
            return Response({
                'success': True,
                'optimization_results': optimization_results,
                'message': 'Price optimization analysis completed'
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_pricing(self, request, pk=None):
        """Update product pricing"""
        product = self.get_object()
        
        new_price = request.data.get('base_price')
        pricing_model_data = request.data.get('pricing_model', {})
        
        if not new_price:
            return Response(
                {'error': 'Base price is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Update product base price
                product.base_price = new_price
                product.updated_by = request.user
                product.save()
                
                # Create new pricing model if provide Deactivate existing pricing models
                    product.pricing_models.update(is_active=False)
                    
                    # Create new pricing model
                    from ..models import PricingModel
                    PricingModel.objects.create(
                        product=product,
                        name=pricing_model_data.get('name', f'Pricing Update {timezone.now().date()}'),
                        base_price=new_price,
                        discount_percentage=pricing_model_data.get('discount_percentage', 0),
                        minimum_price=pricing_model_data.get('minimum_price', new_price * 0.8),
                        tenant=request.tenant,
                        created_by=request.user
                    )
                
                return Response({
                    'success': True,
                    'message': 'Product pricing updated successfully',
                    'new_price': new_price
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ProductBundleListView(CRMBaseMixin, ListView):
    """Product Bundle list view"""
    
    model = ProductBundle
    template_name = 'crm/product/bundle_list.html'
    context_object_name = 'bundles'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add annotations
        queryset = queryset.annotate(
            product_count=Count('products'),
            opportunities_count=Count('opportunity_products'),
            total_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            savings_amount=F('individual_price') - F('bundle_price')
        ).prefetch_related('products__product')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        bundles = self.get_queryset()
        context.update({
            'total_bundles': bundles.count(),
            'active_bundles': bundles.filter(is_active=True).count(),
            'bundle_stats': self.get_bundle_statistics(bundles),
            'top_bundles': bundles.filter(total_revenue__gt=0).order_by('-total_revenue')[:5],
        })
        
        return context
    
    def get_bundle_statistics(self, bundles):
        """Get bundle statistics"""
        return {
            'total_savings': bundles.aggregate(Sum('savings_amount'))['savings_amount__sum'] or 0,
            'avg_bundle_price': bundles.aggregate(Avg('bundle_price'))['bundle_price__avg'] or 0,
            'total_products_bundled': bundles.aggregate(Sum('product_count'))['product_count__sum'] or 0,
            'total_bundle_revenue': bundles.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0,
        }


class ProductBundleDetailView(CRMBaseMixin, DetailView):
    """Product Bundle detail view"""
    
    model = ProductBundle
    template_name = 'crm/product/bundle_detail.html'
    context_object_name = 'bundle'
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset().prefetch_related(
                'products__product__category',
                'opportunity_products__opportunity'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bundle = self.object
        
        context.update({
            'bundle_analytics': self.get_bundle_analytics(bundle),
            'product_details': self.get_product_details(bundle),
            'sales_history': self.get_sales_history(bundle),
            'pricing_analysis': self.get_pricing_analysis(bundle),
        })
        
        return context
    
    def get_bundle_analytics(self, bundle):
        """Get bundle analytics"""
        opportunity_products = bundle.opportunity_products.all()
        won_opportunities = opportunity_products.filter(opportunity__is_won=True)
        
        return {
            'total_opportunities': opportunity_products.count(),
            'won_opportunities': won_opportunities.count(),
            'win_rate': (won_opportunities.count() / opportunity_products.count() * 100) if opportunity_products.count() > 0 else 0,
            'total_revenue': won_opportunities.aggregate(
                total=Sum(F('price') * F('quantity'))
            )['total'] or 0,
            'avg_selling_price': won_opportunities.aggregate(Avg('price'))['price__avg'] or 0,
            'total_quantity_sold': won_opportunities.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            'customer_savings': (bundle.individual_price - bundle.bundle_price) * (won_opportunities.aggregate(Sum('quantity'))['quantity__sum'] or 0),
        }
    
    def get_product_details(self, bundle):
        """Get detailed product information in bundle"""
        products = []
        
        for bundle_product in bundle.products.select_related('product__category'):
            product = bundle_product.product
            products.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else '',
                'base_price': product.base_price,
                'quantity': bundle_product.quantity,
                'total_price': product.base_price * bundle_product.quantity,
                'description': product.description,
            })
        
        return products
    
    def get_sales_history(self, bundle):
        """Get sales history for bundle"""
        return bundle.opportunity_products.select_related(
            'opportunity__account', 'opportunity__owner'
        ).order_by('-opportunity__created_at')[:20]
    
    def get_pricing_analysis(self, bundle):
        """Get pricing analysis for bundle"""
        individual_total = sum(
            bp.product.base_price * bp.quantity 
            for bp in bundle.products.select_related('product')
        )
        
        return {
            'individual_price': individual_total,
            'bundle_price': bundle.bundle_price,
            'savings_amount': individual_total - bundle.bundle_price,
            'discount_percentage': ((individual_total - bundle.bundle_price) / individual_total * 100) if individual_total > 0 else 0,
            'pricing_recommendations': self.get_pricing_recommendations(bundle, individual_total)
        }
    
    def get_pricing_recommendations(self, bundle, individual_total):
        """Get pricing recommendations"""
        recommendations = []
        
        discount_percentage = ((individual_total - bundle.bundle_price) / individual_total * 100) if individual_total > 0 else 0
        
        if discount_percentage < 5:
            recommendations.append('Consider increasing bundle discount to attract more customers')
        elif discount_percentage > 30:
            recommendations.append('Bundle discount may be too high - review profitability')
        
        # Check sales performance
        won_opportunities = bundle.opportunity_products.filter(opportunity__is_won=True).count()
        if won_opportunities == 0:
            recommendations.append('Bundle has no sales - review pricing and product mix')
        
        return recommendations


class ProductBundleViewSet(CRMBaseViewSet):
    """Product Bundle API viewset"""
    
    queryset = ProductBundle.objects.all()
    serializer_class = ProductBundleSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'bundle_price', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product').annotate(
            product_count=Count('products'),
            total_revenue=Sum(
                Case(
                    When(
                        opportunity_products__opportunity__is_won=True,
                        then=F('opportunity_products__price') * F('opportunity_products__quantity')
                    ),
                    default=0,
                    output_field=DecimalField()
                )
            )
        )
    
    @action(detail=True, methods=['post'])
    def add_product(self, request, pk=None):
        """Add product to bundle"""
        bundle = self.get_object()
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        
        if not product_id:
            return Response(
                {'error': 'Product ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from ..models import Product, BundleProduct
            product = Product.objects.get(id=product_id, tenant=request.tenant)
            
            # Check if product already in bundle
            if bundle.products.filter(product=product).exists():
                return Response(
                    {'error': 'Product already in bundle'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Add product to bundle
            bundle_product = BundleProduct.objects.create(
                bundle=bundle,
                product=product,
                quantity=quantity,
                tenant=request.tenant,
                created_by=request.user
            )
            
            # Recalculate bundle pricing
            self.recalculate_bundle_pricing(bundle)
            
            return Response({
                'success': True,
                'message': f'{product.name} added to {bundle.name}',
                'bundle_product_id': bundle_product.id
            })
        
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_product(self, request, pk=None):
        """Remove product from bundle"""
        bundle = self.get_object()
        product_id = request.data.get('product_id')
        
        if not product_id:
            return Response(
                {'error': 'Product ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bundle_product = bundle.products.get(product_id=product_id)
            product_name = bundle_product.product.name
            bundle_product.delete()
            
            # Recalculate bundle pricing
            self.recalculate_bundle_pricing(bundle)
            
            return Response({
                'success': True,
                'message': f'{product_name} removed from {bundle.name}'
            })
        
        except bundle.products.model.DoesNotExist:
            return Response(
                {'error': 'Product not found in bundle'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def recalculate_bundle_pricing(self, bundle):
        """Recalculate bundle individual price"""
        individual_price = sum(
            bp.product.base_price * bp.quantity 
            for bp in bundle.products.select_related('product')
        )
        
        bundle.individual_price = individual_price
        bundle.discount_amount = individual_price - bundle.bundle_price
        bundle.save()


class ProductCategoryViewSet(CRMBaseViewSet):
    """Product Category API viewset"""
    
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    filterset_class = ProductCategoryFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('parent').prefetch_related('children').annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        )
    
    @action(detail=False, methods=['get'])
    def hierarchy(self, request):
        """Get category hierarchy"""
        def build_tree(parent_id=None):
            categories = self.get_queryset().filter(parent_id=parent_id)
            
            tree = []
            for category in categories:
                tree.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'product_count': category.product_count,
                    'children': build_tree(category.id)
                })
            
            return tree
        
        return Response(build_tree())
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products in category"""
        category = self.get_object()
        
        # Include subcategory products if requested
        include_subcategories = request.query_params.get('include_subcategories', 'false').lower() == 'true'
        
        if include_subcategories:
            # Get all descendant categories
            def get_descendant_ids(cat_id):
                descendants = [cat_id]
                children = ProductCategory.objects.filter(parent_id=cat_id, tenant=request.tenant)
                for child in children:
                    descendants.extend(get_descendant_ids(child.id))
                return descendants
            
            category_ids = get_descendant_ids(category.id)
            products = Product.objects.filter(
                category_id__in=category_ids,
                tenant=request.tenant,
                is_active=True
            )
        else:
            products = category.products.filter(is_active=True)
        
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class PricingModelViewSet(CRMBaseViewSet):
    """Pricing Model API viewset"""
    
    queryset = PricingModel.objects.all()
    serializer_class = PricingModelSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'base_price', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('product')