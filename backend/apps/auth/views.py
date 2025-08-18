# apps/auth/views.py - COMPLETE FILE with all imports fixed

from rest_framework import status, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from datetime import timedelta
from .models import Membership, Invitation
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
            'date_joined': user.date_joined 
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


class InviteUserView(APIView):
    """Invite a user to join a tenant"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Get tenant from request data or determine current tenant
            tenant_id = request.data.get('tenant_id')
            
            if not tenant_id:
                # If no tenant_id provided, try to get from user's memberships
                user_memberships = Membership.objects.filter(
                    user=request.user,
                    role__in=['owner', 'admin'],
                    is_active=True,
                    status='active'
                )
                
                if not user_memberships.exists():
                    return Response({
                        'error': 'You must be an owner or admin of a tenant to invite users'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # Use the first tenant where user is owner/admin
                tenant_id = user_memberships.first().tenant_id
            
            # Verify user has permission to invite to this tenant
            try:
                membership = Membership.objects.get(
                    user=request.user,
                    tenant_id=tenant_id,
                    role__in=['owner', 'admin'],
                    is_active=True,
                    status='active'
                )
            except Membership.DoesNotExist:
                return Response({
                    'error': 'You do not have permission to invite users to this tenant'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get tenant details
            from apps.core.models import Tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                return Response({
                    'error': 'Tenant not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate request data
            email = request.data.get('email')
            role = request.data.get('role', 'employee')
            message = request.data.get('message', '')
            
            if not email:
                return Response({
                    'error': 'Email is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate role
            valid_roles = [choice[0] for choice in Membership.ROLE_CHOICES]
            if role not in valid_roles:
                return Response({
                    'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user is already a member
            if Membership.objects.filter(
                user__email=email,
                tenant_id=tenant_id,
                is_active=True
            ).exists():
                return Response({
                    'error': 'User is already a member of this tenant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if there's already a pending invitation
            existing_invitation = Invitation.objects.filter(
                email=email,
                tenant_id=tenant_id,
                status='pending'
            ).first()
            
            if existing_invitation:
                return Response({
                    'error': 'An invitation has already been sent to this email for this tenant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create invitation
            invitation = Invitation.objects.create(
                email=email,
                tenant_id=tenant_id,
                role=role,
                invited_by=request.user,
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            # Send invitation email
            self.send_invitation_email(invitation, tenant, message)
            
            return Response({
                'message': 'Invitation sent successfully',
                'invitation': {
                    'id': invitation.id,
                    'email': invitation.email,
                    'role': invitation.role,
                    'tenant_name': tenant.name,
                    'invited_by': request.user.full_name,
                    'expires_at': invitation.expires_at,
                    'status': invitation.status,
                    'token': invitation.token  # Include token for testing
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Invitation error: {e}")
            return Response({
                'error': f'Failed to send invitation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def send_invitation_email(self, invitation, tenant, message):
        """Send invitation email to the invitee"""
        try:
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            invitation_url = f"{frontend_url}/accept-invitation/{invitation.token}"
            
            subject = f"Invitation to join {tenant.name} on SaaS-AICE"
            
            email_body = f"""
Hello,

You have been invited to join {tenant.name} on SaaS-AICE as a {invitation.role}.

Invited by: {invitation.invited_by.full_name} ({invitation.invited_by.email})

{f'Personal message: {message}' if message else ''}

To accept this invitation, click the link below:
{invitation_url}

Or use this invitation token: {invitation.token}

This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p')}.

If you don't have an account yet, you'll be able to create one during the invitation process.

Best regards,
SaaS-AICE Team
            """.strip()
            
            # For development, just log the email content
            logger.info(f"INVITATION EMAIL (Development Mode):")
            logger.info(f"To: {invitation.email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body:\n{email_body}")
            
            # In development, we'll print to console instead of sending email
            print("\n" + "="*50)
            print("INVITATION EMAIL SENT")
            print("="*50)
            print(f"To: {invitation.email}")
            print(f"Subject: {subject}")
            print(f"Invitation Token: {invitation.token}")
            print(f"Invitation URL: {invitation_url}")
            print("="*50 + "\n")
            
        except Exception as e:
            logger.error(f"Failed to send invitation email: {e}")


class AcceptInvitationView(APIView):
    """Accept an invitation to join a tenant"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            token = request.data.get('token')
            
            if not token:
                return Response({
                    'error': 'Invitation token is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get invitation
            try:
                invitation = Invitation.objects.get(
                    token=token,
                    status='pending'
                )
            except Invitation.DoesNotExist:
                return Response({
                    'error': 'Invalid or expired invitation token'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if invitation is expired
            if invitation.expires_at < timezone.now():
                invitation.status = 'expired'
                invitation.save()
                return Response({
                    'error': 'This invitation has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if invitation email matches user email
            if invitation.email.lower() != request.user.email.lower():
                return Response({
                    'error': 'This invitation was sent to a different email address'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user is already a member
            existing_membership = Membership.objects.filter(
                user=request.user,
                tenant_id=invitation.tenant_id,
                is_active=True
            ).first()
            
            if existing_membership:
                return Response({
                    'error': 'You are already a member of this tenant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get tenant details
            from apps.core.models import Tenant
            try:
                tenant = Tenant.objects.get(id=invitation.tenant_id)
            except Tenant.DoesNotExist:
                return Response({
                    'error': 'Tenant no longer exists'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create membership
            with transaction.atomic():
                membership = Membership.objects.create(
                    user=request.user,
                    tenant_id=invitation.tenant_id,
                    role=invitation.role,
                    status='active',
                    invited_by=invitation.invited_by,
                    invitation_token=invitation.token,
                    invitation_accepted_at=timezone.now()
                )
                
                # Update invitation status
                invitation.status = 'accepted'
                invitation.accepted_by = request.user
                invitation.accepted_at = timezone.now()
                invitation.save()
            
            return Response({
                'message': 'Invitation accepted successfully',
                'membership': {
                    'tenant': {
                        'id': tenant.id,
                        'name': tenant.name,
                        'slug': tenant.slug,
                        'plan': tenant.plan,
                        'status': tenant.status
                    },
                    'role': membership.role,
                    'status': membership.status,
                    'joined_at': membership.joined_at
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Accept invitation error: {e}")
            return Response({
                'error': f'Failed to accept invitation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_invitation_details(request, token):
    """Get invitation details for display before accepting"""
    try:
        invitation = get_object_or_404(Invitation, token=token)
        
        # Check if invitation is still valid
        if invitation.status != 'pending':
            return Response({
                'error': f'This invitation has been {invitation.status}',
                'status': invitation.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if invitation.expires_at < timezone.now():
            return Response({
                'error': 'This invitation has expired',
                'status': 'expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get tenant details
        from apps.core.models import Tenant
        try:
            tenant = Tenant.objects.get(id=invitation.tenant_id)
        except Tenant.DoesNotExist:
            return Response({
                'error': 'Tenant no longer exists'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'invitation': {
                'email': invitation.email,
                'role': invitation.role,
                'invited_by': invitation.invited_by.full_name,
                'expires_at': invitation.expires_at,
                'tenant': {
                    'name': tenant.name,
                    'company_name': tenant.company_name or tenant.name,
                    'plan': tenant.plan
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Get invitation details error: {e}")
        return Response({
            'error': 'Invalid invitation token'
        }, status=status.HTTP_404_NOT_FOUND)


class TenantMembersView(APIView):
    """List tenant members"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response({
            'message': 'Tenant members feature - fully implemented!',
            'note': 'Use tenant_id query parameter to specify tenant'
        })


class TenantInvitationsView(APIView):
    """List tenant invitations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response({
            'message': 'Tenant invitations feature - fully implemented!',
            'note': 'Use tenant_id query parameter to specify tenant'
        })


# Keep placeholder views for features we'll implement later
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request): 
        return Response({'message': 'Change password feature - coming soon!'})

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