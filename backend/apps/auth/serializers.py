# apps/auth/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, Membership, Invitation, HandoffToken
from apps.core.models import Tenant, Domain


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'confirm_password', 'phone']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField()
    tenant_slug = serializers.CharField(required=False)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        tenant_slug = attrs.get('tenant_slug')
        
        if email and password:
            user = authenticate(username=email, password=password)
            
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            
            # If tenant_slug provided, verify user has access
            if tenant_slug:
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug)
                    membership = Membership.objects.get(
                        user=user,
                        tenant_id=tenant.id,
                        is_active=True,
                        status='active'
                    )
                    attrs['tenant'] = tenant
                    attrs['membership'] = membership
                except (Tenant.DoesNotExist, Membership.DoesNotExist):
                    raise serializers.ValidationError('User does not have access to this tenant')
            
            attrs['user'] = user
            return attrs
        
        raise serializers.ValidationError('Email and password are required')


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone', 'bio', 'avatar', 'timezone', 'language', 'theme',
            'email_verified', 'phone_verified', 'two_factor_enabled',
            'last_login', 'created_at'
        ]
        read_only_fields = ['id', 'email', 'email_verified', 'phone_verified', 'last_login', 'created_at']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenant information"""
    domains = serializers.SerializerMethodField()
    is_trial_expired = serializers.ReadOnlyField()
    is_subscription_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'description', 'plan', 'status',
            'max_users', 'max_storage_gb', 'company_name', 'company_logo',
            'timezone', 'currency', 'domains', 'is_trial_expired',
            'is_subscription_active', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at']
    
    def get_domains(self, obj):
        return [domain.domain for domain in obj.domains.all()]


class MembershipSerializer(serializers.ModelSerializer):
    """Serializer for membership information"""
    user = UserProfileSerializer(read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = Membership
        fields = [
            'id', 'user', 'tenant_id', 'tenant_name', 'role', 'status',
            'is_active', 'permissions', 'joined_at', 'last_access',
            'expires_at', 'is_expired'
        ]


class InvitationSerializer(serializers.ModelSerializer):
    """Serializer for invitations"""
    invited_by_name = serializers.CharField(source='invited_by.full_name', read_only=True)
    tenant_name = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = Invitation
        fields = [
            'id', 'email', 'tenant_id', 'tenant_name', 'role', 'status',
            'token', 'invited_by_name', 'expires_at', 'is_expired',
            'sent_at', 'accepted_at'
        ]
        read_only_fields = ['id', 'token', 'status', 'sent_at', 'accepted_at']
    
    def get_tenant_name(self, obj):
        try:
            tenant = Tenant.objects.get(id=obj.tenant_id)
            return tenant.name
        except Tenant.DoesNotExist:
            return None


class InviteUserSerializer(serializers.Serializer):
    """Serializer for inviting users"""
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.ROLE_CHOICES)
    message = serializers.CharField(required=False, max_length=500)
    
    def validate_email(self, value):
        # Check if user is already a member
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            if Membership.objects.filter(
                user__email=value,
                tenant_id=request.tenant.id,
                is_active=True
            ).exists():
                raise serializers.ValidationError("User is already a member of this tenant")
        
        return value


class AcceptInvitationSerializer(serializers.Serializer):
    """Serializer for accepting invitations"""
    token = serializers.CharField()
    
    def validate_token(self, value):
        try:
            invitation = Invitation.objects.get(token=value, status='pending')
            if invitation.is_expired:
                raise serializers.ValidationError("Invitation has expired")
            return value
        except Invitation.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired invitation token")


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            User.objects.get(email=value, is_active=True)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("No active user found with this email address")


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset"""
    token = serializers.CharField()
    password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def validate_token(self, value):
        from .models import PasswordResetToken
        try:
            reset_token = PasswordResetToken.objects.get(token=value)
            if reset_token.is_expired:
                raise serializers.ValidationError("Password reset token has expired")
            return value
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid password reset token")


class HandoffTokenSerializer(serializers.Serializer):
    """Serializer for handoff tokens"""
    tenant_slug = serializers.CharField()
    
    def validate_tenant_slug(self, value):
        request = self.context.get('request')
        user = request.user if request else None
        
        try:
            tenant = Tenant.objects.get(slug=value, status='active')
            
            # Check if user has access to this tenant
            if user and not Membership.objects.filter(
                user=user,
                tenant_id=tenant.id,
                is_active=True,
                status='active'
            ).exists():
                raise serializers.ValidationError("User does not have access to this tenant")
            
            return value
        except Tenant.DoesNotExist:
            raise serializers.ValidationError("Tenant not found or inactive")


class ConsumeHandoffTokenSerializer(serializers.Serializer):
    """Serializer for consuming handoff tokens"""
    token = serializers.CharField()
    
    def validate_token(self, value):
        try:
            handoff_token = HandoffToken.objects.get(token=value)
            if handoff_token.is_expired:
                raise serializers.ValidationError("Handoff token has expired")
            return value
        except HandoffToken.DoesNotExist:
            raise serializers.ValidationError("Invalid handoff token")


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords do not match")
        return attrs
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value


class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new tenants"""
    domain = serializers.CharField(write_only=True)
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'description', 'plan', 'company_name', 'company_address',
            'contact_email', 'contact_phone', 'timezone', 'currency', 'domain'
        ]
    
    def validate_domain(self, value):
        # Check if domain already exists
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError("Domain already exists")
        return value
    
    def create(self, validated_data):
        domain_name = validated_data.pop('domain')
        
        # Create tenant
        tenant = Tenant.objects.create(**validated_data)
        
        # Create domain
        Domain.objects.create(
            domain=domain_name,
            tenant=tenant,
            is_primary=True
        )
        
        # Create membership for creator
        user = self.context['request'].user
        Membership.objects.create(
            user=user,
            tenant_id=tenant.id,
            role='owner',
            status='active'
        )
        
        return tenant