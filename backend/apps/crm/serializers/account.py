# ============================================================================
# backend/apps/crm/serializers/account.py - Account Management Serializers
# ============================================================================

from rest_framework import serializers
from django.db import transaction
from ..models import Industry, Account, Contact
from .user import UserBasicSerializer


class IndustrySerializer(serializers.ModelSerializer):
    """Industry serializer with hierarchy support"""
    
    parent_industry_name = serializers.CharField(source='parent_industry.name', read_only=True)
    sub_industries_count = serializers.SerializerMethodField()
    hierarchy_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Industry
        fields = [
            'id', 'name', 'code', 'description', 'parent_industry', 
            'parent_industry_name', 'level', 'is_active', 'sort_order',
            'total_accounts', 'total_revenue', 'sub_industries_count',
            'hierarchy_path', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'level', 'parent_industry_name', 'total_accounts',
            'total_revenue', 'sub_industries_count', 'hierarchy_path',
            'created_at', 'updated_at'
        ]
    
    def get_sub_industries_count(self, obj):
        """Get count of sub-industries"""
        return obj.sub_industries.filter(is_active=True).count()
    
    def get_hierarchy_path(self, obj):
        """Get full hierarchy path"""
        path = []
        current = obj
        while current:
            path.insert(0, current.name)
            current = current.parent_industry
        return " > ".join(path)


class ContactBasicSerializer(serializers.ModelSerializer):
    """Basic contact serializer for nested relationships"""
    
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'salutation', 'first_name', 'last_name', 'full_name',
            'display_name', 'email', 'phone', 'mobile', 'job_title',
            'is_primary', 'is_decision_maker'
        ]


class AccountSerializer(serializers.ModelSerializer):
    """Comprehensive account serializer"""
    
    industry_details = IndustrySerializer(source='industry', read_only=True)
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    parent_account_name = serializers.CharField(source='parent_account.name', read_only=True)
    territory_name = serializers.CharField(source='territory.name', read_only=True)
    
    # Calculated fields
    primary_contact = ContactBasicSerializer(read_only=True)
    contacts_count = serializers.SerializerMethodField()
    opportunities_count = serializers.SerializerMethodField()
    open_opportunities_count = serializers.SerializerMethodField()
    win_rate = serializers.ReadOnlyField()
    days_as_customer = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'account_number', 'name', 'legal_name', 'account_type', 'status',
            'industry', 'industry_details', 'website', 'company_size', 
            'annual_revenue', 'employee_count',
            # Contact info
            'phone', 'fax', 'email', 'billing_address', 'shipping_address',
            # Social media
            'linkedin_url', 'twitter_handle', 'facebook_url',
            # Business info
            'tax_id', 'business_license', 'duns_number',
            # Ownership
            'owner', 'owner_details', 'parent_account', 'parent_account_name',
            # Relationship
            'customer_since', 'last_activity_date', 'relationship_strength',
            # Finance integration
            'finance_customer_id', 'credit_limit', 'payment_terms',
            # Performance
            'total_opportunities', 'total_won_opportunities', 'total_revenue',
            'average_deal_size', 'last_purchase_date', 'win_rate',
            # Territory
            'territory', 'territory_name',
            # Preferences
            'preferred_contact_method', 'do_not_call', 'do_not_email',
            # Additional
            'description', 'tags', 'custom_fields', 'lead_source',
            'original_lead_id',
            # Calculated fields
            'primary_contact', 'contacts_count', 'opportunities_count',
            'open_opportunities_count', 'days_as_customer',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'account_number', 'industry_details', 'owner_details',
            'parent_account_name', 'territory_name', 'total_opportunities',
            'total_won_opportunities', 'total_revenue', 'average_deal_size',
            'win_rate', 'primary_contact', 'contacts_count', 'opportunities_count',
            'open_opportunities_count', 'days_as_customer', 'created_at', 'updated_at'
        ]
    
    def get_contacts_count(self, obj):
        """Get total contacts count"""
        return obj.contacts.filter(is_active=True).count()
    
    def get_opportunities_count(self, obj):
        """Get total opportunities count"""
        return obj.opportunities.filter(is_active=True).count()
    
    def get_open_opportunities_count(self, obj):
        """Get open opportunities count"""
        return obj.opportunities.filter(is_active=True, is_closed=False).count()
    
    def get_days_as_customer(self, obj):
        """Calculate days as customer"""
        if obj.customer_since:
            from django.utils import timezone
            return (timezone.now().date() - obj.customer_since).days
        return None
    
    def validate_annual_revenue(self, value):
        """Validate annual revenue"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Annual revenue cannot be negative")
        return value
    
    def validate_employee_count(self, value):
        """Validate employee count"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Employee count cannot be negative")
        return value


class ContactSerializer(serializers.ModelSerializer):
    """Comprehensive contact serializer"""
    
    account_details = serializers.SerializerMethodField()
    owner_details = UserBasicSerializer(source='owner', read_only=True)
    reports_to_details = ContactBasicSerializer(source='reports_to', read_only=True)
    
    # Calculated fields
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    direct_reports_count = serializers.SerializerMethodField()
    activities_count = serializers.SerializerMethodField()
    opportunities_count = serializers.SerializerMethodField()
    days_since_last_contact = serializers.SerializerMethodField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'account', 'account_details', 
            # Personal info
            'salutation', 'first_name', 'last_name', 'middle_name', 'nickname',
            'full_name', 'display_name',
            # Contact details
            'email', 'secondary_email', 'phone', 'mobile', 'fax',
            # Professional info
            'job_title', 'department', 'reports_to', 'reports_to_details',
            # Classification
            'contact_type', 'is_primary', 'is_decision_maker',
            # Address
            'mailing_address',
            # Preferences
            'preferred_contact_method', 'do_not_call', 'do_not_email', 'do_not_text',
            # Social media
            'linkedin_url', 'twitter_handle',
            # Personal
            'birthday', 'anniversary', 'interests',
            # Relationship
            'relationship_strength', 'last_contact_date', 'next_contact_date',
            # Performance
            'total_activities', 'total_opportunities', 'total_revenue_influenced',
            # Additional
            'description', 'tags', 'custom_fields',
            # Ownership
            'owner', 'owner_details',
            # Calculated fields
            'direct_reports_count', 'activities_count', 'opportunities_count',
            'days_since_last_contact',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'account_details', 'full_name', 'display_name',
            'reports_to_details', 'owner_details', 'total_activities',
            'total_opportunities', 'total_revenue_influenced',
            'direct_reports_count', 'activities_count', 'opportunities_count',
            'days_since_last_contact', 'created_at', 'updated_at'
        ]
    
    def get_account_details(self, obj):
        """Get basic account details"""
        return {
            'id': obj.account.id,
            'name': obj.account.name,
            'account_type': obj.account.account_type
        }
    
    def get_direct_reports_count(self, obj):
        """Get count of direct reports"""
        return obj.direct_reports.filter(is_active=True).count()
    
    def get_activities_count(self, obj):
        """Get total activities count"""
        # This would need to be implemented based on your activity tracking
        return 0
    
    def get_opportunities_count(self, obj):
        """Get opportunities count where this contact is primary"""
        return obj.opportunities.filter(is_active=True).count()
    
    def get_days_since_last_contact(self, obj):
        """Calculate days since last contact"""
        if obj.last_contact_date:
            from django.utils import timezone
            return (timezone.now() - obj.last_contact_date).days
        return None
    
    def validate_email(self, value):
        """Validate email uniqueness within account"""
        if self.instance:
            if Contact.objects.filter(
                tenant=self.context['request'].user.tenant,
                account=self.validated_data.get('account', self.instance.account),
                email=value
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Email must be unique within account")
        return value
    
    def validate(self, data):
        """Validate contact data"""
        # Ensure only one primary contact per account
        if data.get('is_primary') and self.instance:
            if Contact.objects.filter(
                tenant=self.context['request'].user.tenant,
                account=data.get('account', self.instance.account),
                is_primary=True
            ).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError({
                    'is_primary': 'Only one primary contact allowed per account'
                })
        
        return data


class AccountDetailSerializer(AccountSerializer):
    """Detailed account serializer with related data"""
    
    contacts = ContactBasicSerializer(many=True, read_only=True)
    recent_opportunities = serializers.SerializerMethodField()
    recent_activities = serializers.SerializerMethodField()
    
    class Meta(AccountSerializer.Meta):
        fields = AccountSerializer.Meta.fields + [
            'contacts', 'recent_opportunities', 'recent_activities'
        ]
    
    def get_recent_opportunities(self, obj):
        """Get recent opportunities"""
        recent_opps = obj.opportunities.filter(is_active=True).order_by('-created_at')[:5]
        return [
            {
                'id': opp.id,
                'name': opp.name,
                'amount': opp.amount,
                'stage': opp.stage.name if opp.stage else None,
                'close_date': opp.close_date,
                'probability': opp.probability
            }
            for opp in recent_opps
        ]
    
    def get_recent_activities(self, obj):
        """Get recent activities"""
        # This would need to be implemented based on your activity tracking
        return []


class ContactDetailSerializer(ContactSerializer):
    """Detailed contact serializer with related data"""
    
    direct_reports = ContactBasicSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    
    class Meta(ContactSerializer.Meta):
        fields = ContactSerializer.Meta.fields + [
            'direct_reports', 'recent_activities'
        ]
    
    def get_recent_activities(self, obj):
        """Get recent activities"""
        # This would need to be implemented based on your activity tracking
        return []