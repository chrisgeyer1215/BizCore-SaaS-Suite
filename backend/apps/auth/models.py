# apps/auth/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings
import shortuuid
from datetime import timedelta


class User(AbstractUser):
    """Custom User model stored in public schema"""
    
    USER_TYPE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('tenant_admin', 'Tenant Admin'),
        ('user', 'Regular User'),
    ]
    
    # Basic Info
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # User Type
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='user')
    
    # Profile
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    bio = models.TextField(blank=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    theme = models.CharField(max_length=10, default='light')  # light, dark
    
    # Security
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # SSO Integration
    sso_provider = models.CharField(max_length=50, blank=True)  # google, microsoft, etc.
    sso_id = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'public.auth_user'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_tenant_memberships(self):
        """Get all tenant memberships for this user"""
        return self.memberships.filter(is_active=True)
    
    def is_tenant_admin(self, tenant_id):
        """Check if user is admin of specific tenant"""
        return self.memberships.filter(
            tenant_id=tenant_id,
            role__in=['admin', 'owner'],
            is_active=True
        ).exists()


class Membership(models.Model):
    """Links users to tenants with roles - stored in public schema"""
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'), 
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('viewer', 'Viewer'),
        ('guest', 'Guest'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
    ]
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    tenant_id = models.PositiveIntegerField()  # Reference to tenant without FK
    
    # Role & Status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)
    
    # Permissions
    permissions = models.JSONField(default=dict)  # Custom permissions per tenant
    
    # Invitation details
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_invitations')
    invitation_token = models.CharField(max_length=100, blank=True)
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Dates
    joined_at = models.DateTimeField(default=timezone.now)
    last_access = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'public.auth_membership'
        unique_together = ['user', 'tenant_id']
        indexes = [
            models.Index(fields=['tenant_id', 'role']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - Tenant {self.tenant_id} ({self.role})"
    
    def save(self, *args, **kwargs):
        if not self.invitation_token:
            self.invitation_token = shortuuid.uuid()
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def has_permission(self, permission_name):
        """Check if membership has specific permission"""
        # Role-based permissions
        role_permissions = {
            'owner': ['*'],  # All permissions
            'admin': ['create_user', 'edit_user', 'delete_user', 'view_reports', 'manage_settings'],
            'manager': ['create_user', 'edit_user', 'view_reports'],
            'employee': ['view_data', 'edit_own_data'],
            'viewer': ['view_data'],
            'guest': ['view_limited'],
        }
        
        # Check role permissions
        if self.role in role_permissions:
            if '*' in role_permissions[self.role] or permission_name in role_permissions[self.role]:
                return True
        
        # Check custom permissions
        return self.permissions.get(permission_name, False)


class Invitation(models.Model):
    """Invitation model for inviting users to tenants"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Invitation details
    email = models.EmailField()
    tenant_id = models.PositiveIntegerField()
    role = models.CharField(max_length=20, choices=Membership.ROLE_CHOICES, default='employee')
    token = models.CharField(max_length=100, unique=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Relationships
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitations_sent')
    accepted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invitations_accepted')
    
    # Dates
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'public.auth_invitation'
        unique_together = ['email', 'tenant_id', 'status']
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = shortuuid.uuid()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # 7 days expiry
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Invitation to {self.email} for Tenant {self.tenant_id}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def accept(self, user):
        """Accept the invitation"""
        if self.is_expired:
            raise ValueError("Invitation has expired")
        
        if self.status != 'pending':
            raise ValueError("Invitation is not pending")
        
        # Create membership
        membership, created = Membership.objects.get_or_create(
            user=user,
            tenant_id=self.tenant_id,
            defaults={
                'role': self.role,
                'status': 'active',
                'invitation_token': self.token,
                'invitation_accepted_at': timezone.now(),
                'invited_by': self.invited_by,
            }
        )
        
        # Update invitation
        self.status = 'accepted'
        self.accepted_by = user
        self.accepted_at = timezone.now()
        self.save()
        
        return membership


class PasswordResetToken(models.Model):
    """Password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_passwordresettoken'
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = shortuuid.uuid()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)  # 24 hours expiry
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at or self.used


class EmailVerificationToken(models.Model):
    """Email verification tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_emailverificationtoken'
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = shortuuid.uuid()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # 7 days expiry
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at or self.used


class HandoffToken(models.Model):
    """Handoff tokens for tenant switching"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tenant_id = models.PositiveIntegerField()
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_handofftoken'
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = shortuuid.uuid()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)  # 5 minutes expiry
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at or self.used