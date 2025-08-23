from ....application.queries.cart_queries import CartDetailQuery, CartQueryHandler

class CartDetailAPIView(APIView):
    """Cart detail using Query Handler"""
    
    def get(self, request):
        try:
            query = CartDetailQuery(
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                session_key=request.session.session_key,
                include_product_details=request.query_params.get('include_products', 'true').lower() == 'true',
                include_pricing_breakdown=request.query_params.get('include_pricing', 'true').lower() == 'true',
                include_shipping_options=request.query_params.get('include_shipping', 'false').lower() == 'true'
            )
            
            handler = CartQueryHandler(self.get_tenant())
            cart_data = handler.handle_cart_detail(query)
            
            if({'cart': None}, status=status.HTTP_200_OK)
            
            return Response({'cart': asdict(cart_data)}, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AbandonedCartsAPIView(APIView):
    """Abandoned carts for marketing recovery"""
    
    def get(self, request):
        try:
            query = AbandonedCartsQuery(
                hours_since_update=int(request.query_params.get('hours', 24)),
                min_cart_value=float(request.query_params.get('min_value', 0)),
                page=int(request.query_params.get('page', 1)),
                page_size=int(request.query_params.get('page_size', 50))
            )
            
            handler = CartQueryHandler(self.get_tenant())
            result = handler.handle_abandoned_carts(query)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)