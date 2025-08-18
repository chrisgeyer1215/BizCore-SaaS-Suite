# apps/auth/views.py - Updated with JWT Authentication

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.utils import timezone
from .models import Membership
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer with tenant support"""
    
    def validate(self, attrs):
        # Get credentials
        email = attrs.get('email') or attrs.get('username')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError('Email and password are required')
        
        # Authenticate user
        user = authenticate(username=email, password=password)
        if not user:
            try:
                user = User.objects.get(email=email)
                if user.check_password(password):
                    pass  # User exists and password is correct
                else:
                    raise serializers.ValidationError('Invalid credentials')
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
        
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        
        # Create tokens
        refresh = RefreshToken.for_user(user)
        
        # Add custom claims
        refresh['email'] = user.email
        refresh['user_type'] = user.user_type
        refresh['full_name'] = user.full_name
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'user_type': user.user_type,
                'email_verified': user.email_verified
            }
        }


class LoginView(TokenObtainPairView):
    """JWT Login with tenant information"""
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            tokens_data = serializer.validated_data
            user_data = tokens_data.pop('user')
            
            # Get user's tenants
            user = User.objects.get(id=user_data['id'])
            memberships = Membership.objects.filter(
                user=user, 
                is_active=True, 
                status='active'
            ).select_related()
            
            available_tenants = []
            for membership in memberships:
                try:
                    from apps.core.models import Tenant
                    tenant = Tenant.objects.get(id=membership.tenant_id)
                    available_tenants.append({
                        'id': tenant.id,
                        'name': tenant.name,
                        'slug': tenant.slug,
                        'role': membership.role,
                        'plan': tenant.plan,
                        'status': tenant.status,
                        'is_trial_expired': tenant.is_trial_expired
                    })
                except Exception as e:
                    logger.warning(f"Error loading tenant {membership.tenant_id}: {e}")
                    continue
            
            return Response({
                'message': 'Login successful',
                'tokens': tokens_data,
                'user': user_data,
                'available_tenants': available_tenants,
                'tenant_count': len(available_tenants)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return Response({
                'error': 'Login failed',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserRegistrationView(APIView):
    """User registration with JWT response"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            first_name = request.data.get('first_name')
            last_name = request.data.get('last_name')
            
            # Validation
            if not all([email, password, first_name, last_name]):
                return Response({
                    'error': 'All fields (email, password, first_name, last_name) are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(password) < 8:
                return Response({
                    'error': 'Password must be at least 8 characters long'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user exists
            if User.objects.filter(email=email).exists():
                return Response({
                    'error': 'User with this email already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create user
            user = User.objects.create_user(
                email=email,
                username=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email_verified=True,  # Auto-verify for development
                is_active=True
            )
            
            # Create JWT tokens for the new user
            refresh = RefreshToken.for_user(user)
            refresh['email'] = user.email
            refresh['user_type'] = user.user_type
            refresh['full_name'] = user.full_name
            
            return Response({
                'message': 'User created successfully',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.full_name
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return Response({
                'error': f'Registration failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'message': 'Successfully logged out'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'message': 'Logged out (no refresh token provided)'
            }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'Logout failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """Get and update user profile with JWT auth"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'phone': user.phone or '',
            'bio': user.bio or '',
            'timezone': user.timezone,
            'language': user.language,
            'theme': user.theme,
            'user_type': user.user_type,
            'email_verified': user.email_verified,
            'phone_verified': user.phone_verified,
            'two_factor_enabled': user.two_factor_enabled,
            'is_active': user.is_active,
            'last_login': user.last_login,
            'created_at': user.created_at
        })
    
    def put(self, request):
        user = request.user
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'phone', 'bio', 'timezone', 'language', 'theme']
        updated_fields = []
        
        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
                updated_fields.append(field)
        
        if updated_fields:
            user.save(update_fields=updated_fields)
        
        return Response({
            'message': f'Profile updated successfully. Updated fields: {", ".join(updated_fields)}',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'bio': user.bio,
                'timezone': user.timezone,
                'language': user.language,
                'theme': user.theme
            }
        })


class UserTenantsView(APIView):
    """List user's tenant memberships with JWT auth"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        memberships = Membership.objects.filter(
            user=request.user,
            is_active=True,
            status='active'
        )
        
        tenants_data = []
        for membership in memberships:
            try:
                from apps.core.models import Tenant
                tenant = Tenant.objects.get(id=membership.tenant_id)
                tenants_data.append({
                    'tenant': {
                        'id': tenant.id,
                        'name': tenant.name,
                        'slug': tenant.slug,
                        'plan': tenant.plan,
                        'status': tenant.status,
                        'company_name': tenant.company_name or tenant.name,
                        'created_at': tenant.created_at,
                        'is_trial_expired': tenant.is_trial_expired
                    },
                    'membership': {
                        'role': membership.role,
                        'status': membership.status,
                        'joined_at': membership.joined_at,
                        'last_access': membership.last_access,
                        'permissions': membership.permissions
                    }
                })
            except Exception:
                continue
        
        return Response({
            'tenants': tenants_data,
            'total_tenants': len(tenants_data)
        })


class TenantCreateView(APIView):
    """Create a new tenant with JWT auth"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            from apps.core.models import Tenant, Domain, TenantSettings
            from django.utils.text import slugify
            import re
            
            name = request.data.get('name')
            description = request.data.get('description', '')
            company_name = request.data.get('company_name')
            
            # Validation
            if not name:
                return Response({
                    'error': 'Tenant name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(name.strip()) < 3:
                return Response({
                    'error': 'Tenant name must be at least 3 characters long'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Create clean slug and schema name
                slug = slugify(name).replace('-', '_')
                counter = 1
                original_slug = slug
                while Tenant.objects.filter(slug=slug).exists():
                    slug = f"{original_slug}_{counter}"
                    counter += 1
                
                # Create valid schema name
                schema_name = re.sub(r'[^a-zA-Z0-9_]', '_', slug.lower())
                if schema_name[0].isdigit():
                    schema_name = f"tenant_{schema_name}"
                
                schema_name = schema_name[:50]
                counter = 1
                original_schema = schema_name
                while Tenant.objects.filter(schema_name=schema_name).exists():
                    schema_name = f"{original_schema}_{counter}"
                    counter += 1
                
                # Create tenant
                tenant = Tenant.objects.create(
                    name=name.strip(),
                    slug=slug,
                    schema_name=schema_name,
                    description=description.strip(),
                    company_name=company_name or name.strip(),
                    contact_email=request.user.email,
                    status='trial',
                    plan='free',
                    max_users=5,
                    max_storage_gb=1,
                    max_api_calls_per_month=1000
                )
                
                # Create domain
                domain_name = f"{slug}.localhost"
                Domain.objects.create(
                    domain=domain_name,
                    tenant=tenant,
                    is_primary=True,
                    is_verified=True
                )
                
                # Create tenant settings
                TenantSettings.objects.create(
                    tenant=tenant,
                    primary_color='#3B82F6',
                    secondary_color='#64748B'
                )
                
                # Create membership for creator
                membership = Membership.objects.create(
                    user=request.user,
                    tenant_id=tenant.id,
                    role='owner',
                    status='active',
                    permissions={
                        'create_user': True,
                        'edit_user': True,
                        'delete_user': True,
                        'view_reports': True,
                        'manage_settings': True,
                        'manage_billing': True
                    }
                )
                
                # Create the schema
                try:
                    tenant.create_schema(check_if_exists=True)
                    logger.info(f"Created schema for tenant {tenant.name}")
                except Exception as e:
                    logger.warning(f"Schema creation warning: {e}")
                
                return Response({
                    'message': 'Tenant created successfully',
                    'tenant': {
                        'id': tenant.id,
                        'name': tenant.name,
                        'slug': tenant.slug,
                        'schema_name': tenant.schema_name,
                        'domain': domain_name,
                        'status': tenant.status,
                        'plan': tenant.plan,
                        'company_name': tenant.company_name,
                        'created_at': tenant.created_at
                    },
                    'membership': {
                        'role': membership.role,
                        'status': membership.status
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Tenant creation error: {e}")
            return Response({
                'error': f'Tenant creation failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Keep placeholder views for features we'll implement next
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request): 
        return Response({'message': 'Change password feature - coming soon!'})

class InviteUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request): 
        return Response({'message': 'Invite user feature - will implement next!'})

class AcceptInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request): 
        return Response({'message': 'Accept invitation feature - will implement next!'})

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request): 
        return Response({'message': 'Password reset feature - coming soon!'})

class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request): 
        return Response({'message': 'Password reset feature - coming soon!'})

class HandoffTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request): 
        return Response({'message': 'Tenant handoff feature - coming soon!'})

class ConsumeHandoffTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request): 
        return Response({'message': 'Consume handoff token feature - coming soon!'})

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_email(request, token):
    return Response({'message': 'Email verification feature - coming soon!'})

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def resend_verification_email(request):
    return Response({'message': 'Resend verification email feature - coming soon!'})

class TenantMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request): 
        return Response({'message': 'Tenant members feature - will implement next!'})

class TenantInvitationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request): 
        return Response({'message': 'Tenant invitations feature - will implement next!'})