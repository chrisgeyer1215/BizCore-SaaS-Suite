# apps/core/serializers.py

from rest_framework import serializers
from .models import Tenant, Domain, TenantSettings, TenantUsage
from apps.auth.models import Membership


class TenantBaseSerializer(serializers.ModelSerializer):
    """Base serializer for tenant-aware models"""
    
    class Meta:
        abstract = True
    
    def create(self, validated_data):
        # In a real implementation, you would set the tenant from request
        # For now, just create normally
        return super().create(validated_data)


class DomainSerializer(serializers.ModelSerializer):
    """Serializer for Domain model"""
    
    class Meta:
        model = Domain
        fields = [
            'id', 'domain', 'tenant', 'is_primary', 'domain_type',
            'is_verified', 'verification_token', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'verification_token', 'created_at', 'updated_at']
    
    def validate_domain(self, value):
        """Validate domain format and uniqueness"""
        import re
        
        # Basic domain validation
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, value):
            raise serializers.ValidationError("Invalid domain format")
        
        # Check if domain already exists
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError("Domain already exists")
        
        return value


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Serializer for TenantSettings model"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'id', 'tenant', 'primary_color', 'secondary_color', 'logo_url', 'favicon_url',
            'business_hours_start', 'business_hours_end', 'business_days',
            'email_notifications', 'sms_notifications', 'push_notifications',
            'api_rate_limit', 'webhook_url', 'webhook_secret', 'integrations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
    
    def validate_primary_color(self, value):
        """Validate hex color format"""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError("Invalid hex color format")
        return value
    
    def validate_secondary_color(self, value):
        """Validate hex color format"""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError("Invalid hex color format")
        return value
    
    def validate_business_days(self, value):
        """Validate business days (1-7, Monday-Sunday)"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Business days must be a list")
        
        for day in value:
            if not isinstance(day, int) or day < 1 or day > 7:
                raise serializers.ValidationError("Business days must be integers between 1-7")
        
        return value


class TenantUsageSerializer(serializers.ModelSerializer):
    """Serializer for TenantUsage model"""
    
    class Meta:
        model = TenantUsage
        fields = [
            'id', 'tenant', 'active_users_count', 'storage_used_gb', 'api_calls_count',
            'emails_sent', 'sms_sent', 'reports_generated',
            'billing_period_start', 'billing_period_end', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""
    domains = DomainSerializer(many=True, read_only=True)
    is_trial_expired = serializers.ReadOnlyField()
    is_subscription_active = serializers.ReadOnlyField()
    current_usage = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'description', 'plan', 'status',
            'max_users', 'max_storage_gb', 'max_api_calls_per_month',
            'trial_end_date', 'subscription_start_date', 'subscription_end_date',
            'features', 'contact_email', 'contact_phone', 'company_name',
            'company_address', 'company_logo', 'timezone', 'currency',
            'domains', 'is_trial_expired', 'is_subscription_active',
            'current_usage', 'member_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_current_usage(self, obj):
        """Get current month usage"""
        from django.utils import timezone
        from datetime import datetime
        
        now = timezone.now()
        period_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        
        try:
            usage = TenantUsage.objects.get(
                tenant=obj,
                billing_period_start=period_start
            )
            return TenantUsageSerializer(usage).data
        except TenantUsage.DoesNotExist:
            return None
    
    def get_member_count(self, obj):
        """Get active member count"""
        return Membership.objects.filter(
            tenant_id=obj.id,
            is_active=True,
            status='active'
        ).count()


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
        """Validate domain format and uniqueness"""
        import re
        
        # Basic domain validation
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, value):
            raise serializers.ValidationError("Invalid domain format")
        
        # Check if domain already exists
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError("Domain already exists")
        
        return value
    
    def validate_name(self, value):
        """Validate tenant name"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Tenant name must be at least 3 characters long")
        return value.strip()
    
    def create(self, validated_data):
        from django.utils.text import slugify
        from django.db import transaction
        from apps.auth.models import Membership
        
        domain_name = validated_data.pop('domain')
        
        with transaction.atomic():
            # Generate unique slug
            base_slug = slugify(validated_data['name'])
            slug = base_slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            validated_data['slug'] = slug
            
            # Set default values for new tenant
            validated_data.setdefault('status', 'trial')
            validated_data.setdefault('max_users', 5)
            validated_data.setdefault('max_storage_gb', 1)
            validated_data.setdefault('max_api_calls_per_month', 1000)
            
            # Set trial end date
            if not validated_data.get('trial_end_date'):
                from datetime import datetime, timedelta
                validated_data['trial_end_date'] = datetime.now() + timedelta(days=30)
            
            # Create tenant
            tenant = Tenant.objects.create(**validated_data)
            
            # Create domain
            Domain.objects.create(
                domain=domain_name,
                tenant=tenant,
                is_primary=True,
                domain_type='subdomain' if '.' not in domain_name else 'custom'
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


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating tenant details"""
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'description', 'company_name', 'company_address',
            'contact_email', 'contact_phone', 'timezone', 'currency',
            'company_logo', 'features'
        ]
    
    def validate_name(self, value):
        """Validate tenant name"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Tenant name must be at least 3 characters long")
        return value.strip()
    
    def validate_features(self, value):
        """Validate features JSON"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Features must be a JSON object")
        
        # Define allowed features based on plan
        allowed_features = {
            'free': ['crm', 'inventory'],
            'starter': ['crm', 'inventory', 'ecommerce', 'finance'],
            'professional': ['crm', 'inventory', 'ecommerce', 'finance', 'ai_analytics', 'api_access'],
            'enterprise': ['crm', 'inventory', 'ecommerce', 'finance', 'ai_analytics', 'api_access', 'sso', 'white_label', 'custom_reports']
        }
        
        tenant = self.instance
        plan_features = allowed_features.get(tenant.plan, [])
        
        # Validate that enabled features are allowed for current plan
        for feature, enabled in value.items():
            if enabled and feature not in plan_features:
                raise serializers.ValidationError(f"Feature '{feature}' is not available in {tenant.plan} plan")
        
        return value