# apps/auth/backends.py

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using their email address.
    """
    
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        """
        Authenticate a user by email and password
        """
        if email is None:
            email = username
        
        if email is None or password is None:
            return None
        
        try:
            # Try to find user by email
            user = User.objects.get(
                Q(email__iexact=email) | Q(username__iexact=email)
            )
            
            # Check password
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
                
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user
            User().set_password(password)
            return None
        
        return None
    
    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don't have
        an is_active field are allowed.
        """
        return getattr(user, 'is_active', True)
    
    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        return user if self.user_can_authenticate(user) else None