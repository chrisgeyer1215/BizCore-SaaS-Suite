# apps/auth/models.py - COMPLETE REPLACEMENT

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
import shortuuid
from datetime import timedelta


class UserManager(BaseUserManager):
    """Custom user manager that uses email instead of username"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)  # Set username to email
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        
        # Set default values for required fields
        extra_fields.setdefault('first_name', 'Admin')
        extra_fields.setdefault('last_name', 'User')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model stored in public schema"""
    
    USER_TYPE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('tenant_admin', 'Tenant Admin'),
        ('user', 'Regular User'),
    ]
    
    # Override email to be unique and required
    email = models.EmailField(unique=True)
    
    # Profile fields
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # User type
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='user')
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    theme = models.CharField(max_length=10, default='light')
    
    # Security
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    
    # Activity tracking
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # SSO Integration
    sso_provider = models.CharField(max_length=50, blank=True)
    sso_id = models.CharField(max_length=100, blank=True)
    
    # Fix the conflicts with built-in User model
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_users',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_users',
        related_query_name='custom_user',
    )
    
    # Use email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    # Use our custom manager
    objects = UserManager()
    
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
    permissions = models.JSONField(default=dict)
    
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
    
    def __str__(self):
        return f"{self.user.email} - Tenant {self.tenant_id} ({self.role})"
    
    def save(self, *args, **kwargs):
        if not self.invitation_token:
            self.invitation_token = shortuuid.uuid()
        super().save(*args, **kwargs)


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
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)


# Other token models...
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_passwordresettoken'


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_emailverificationtoken'


class HandoffToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tenant_id = models.PositiveIntegerField()
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'public.auth_handofftoken'