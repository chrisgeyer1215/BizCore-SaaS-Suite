# In apps/ecommerce/views/api/products/viewsets.py

from ....application.use_cases.products.create_product import CreateProductUseCase
from ...application.commands.product_commands import CreateProductCommand, ProductCommandHandler
from ....application.queries.product_queries import ProductListQuery, ProductQueryHandler

class ProductViewSet(EcommerceModelViewSet):
    
    def create(self, request):
        """Create new product using Application Layer"""
        try:
            # Create command
            command = CreateProductCommand(
                title=request.data.get('title'),
                description=request.data.get('description'),
                price=request.data.get('price'),
                sku=request.data.get('sku'),
                user_id=str(request.user.id) if request.user.is_authenticated else None
            )
            
            # Execute through command handler
            handler = ProductCommandHandler(self.tenant)
            product_id = handler.handle_create_product(command)
            
            # Return response
            return Response({
                'id': product_id,
                'message': 'Product created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def list(self, request):
        """List products using Query Handler"""
        try:
            query = ProductListQuery(
                page=int(request.query_params.get('page', 1)),
                page_size=int(request.query_params.get('page_size', 24)),
                search=request.query_params.get('search'),
                brand=request.query_params.get('brand'),
                sort_by=request.query_params.get('sort_by', 'created_at')
            )
            
            handler = ProductQueryHandler(self.tenant)
            result = handler.handle_product_list(query)
            
            return Response({
                'results': [asdict(product) for product in result.products],
                'count': result.total_count,
                'next': result.has_next,
                'previous': result.has_previous
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)