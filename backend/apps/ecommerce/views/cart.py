# In apps/ecommerce/views/cart.py

from ..application.commands.cart_commands import AddToCartCommand, CartCommandHandler
from ..application.queries.cart_queries import CartDetailQuery, CartQueryHandler

class AddToCartView(AjaxView):
    """Add item to cart using Application Layer"""
    
    def handle_ajax_post(self):
        try:
            command = AddToCartCommand(
                product_id=self.request.POST.get('product_id'),
                quantity=int(self.request.POST.get('quantity', 1)),
                variant_id=self.request.POST.get('variant_id'),
                user_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                session_key=self.request.session.session_key
            )
            
            handler = CartCommandHandler(self.tenant)
            result = handler.handle_add_to_cart(command)
            
            return {
                'message': 'Item added to cart successfully',
                'cart_id': result['cart_id'],
                'item_count': result['item_count'],
                'total': result['total']
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))


class CartDetailView(EcommerceDetailView):
    """Cart detail using Query Handler"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get cart using query handler
        query = CartDetailQuery(
            user_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
            session_key=self.request.session.session_key
        )
        
        handler = CartQueryHandler(self.tenant)
        cart_data = handler.handle_cart_detail(query)
        
        context['cart'] = cart_data
        return context