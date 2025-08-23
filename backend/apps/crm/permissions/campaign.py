# backend/apps/crm/permissions/campaign.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Campaign, CampaignMember

class CampaignPermission(CRMPermission):
    """Permission class for Campaign model."""
    
    MODEL_PERMS = {
        'view_campaign': 'Can view campaigns',
        'add_campaign': 'Can add campaigns',
        'change_campaign': 'Can change campaigns',
        'delete_campaign': 'Can delete campaigns',
        'launch_campaign': 'Can launch campaigns',
        'pause_campaign': 'Can pause campaigns',
        'clone_campaign': 'Can clone campaigns',
        'view_campaign_analytics': 'Can view campaign analytics',
    }
    
    def has_permission(self, request, view):
        """Check campaign permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_campaign')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_campaign')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_campaign')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_campaign')
        elif view.action == 'launch':
            return self.has_perm(request.user, 'launch_campaign')
        elif view.action == 'pause':
            return self.has_perm(request.user, 'pause_campaign')
        elif view.action == 'clone':
            return self.has_perm(request.user, 'clone_campaign')
        elif view.action in ['analytics', 'performance']:
            return self.has_perm(request.user, 'view_campaign_analytics')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check campaign object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Campaign launch/pause requires special checks
        if view.action == 'launch':
            return self.can_launch_campaign(request.user, obj)
        elif view.action == 'pause':
            return self.can_pause_campaign(request.user, obj)
        
        # Check ownership
        if hasattr(obj, 'owner') and obj.owner:
            if obj.owner.user == request.user:
                return True
        
        # Check if user has marketing role
        if self.has_marketing_role(request.user):
            return True
        
        # Check team access for marketing teams
        return self.has_marketing_team_access(request.user, obj)
    
    def can_launch_campaign(self, user, campaign):
        """Check if user can launch campaign."""
        if not self.has_perm(user, 'launch_campaign'):
            return False
        
        # Campaign must be in draft status
        if campaign.status != 'draft':
            return False
        
        # Check if user owns or manages the campaign
        if hasattr(campaign, 'owner') and campaign.owner:
            if campaign.owner.user == user:
                return True
        
        # Marketing managers can launch team campaigns
        return self.has_marketing_manager_role(user)
    
    def can_pause_campaign(self, user, campaign):
        """Check if user can pause campaign."""
        if not self.has_perm(user, 'pause_campaign'):
            return False
        
        # Campaign must be active
        if campaign.status != 'active':
            return False
        
        # Check ownership or management
        if hasattr(campaign, 'owner') and campaign.owner:
            if campaign.owner.user == user:
                return True
        
        return self.has_marketing_manager_role(user)
    
    def has_marketing_role(self, user):
        """Check if user has marketing role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in [
                'marketing_manager', 'marketing_coordinator', 
                'marketing_specialist'
            ]
        return False
    
    def has_marketing_manager_role(self, user):
        """Check if user has marketing manager role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role == 'marketing_manager'
        return False
    
    def has_marketing_team_access(self, user, campaign):
        """Check marketing team access."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_team = user.crm_profile.team
        if not user_team or user_team.team_type != 'marketing':
            return False
        
        # Check if campaign owner is in same team
        if hasattr(campaign, 'owner') and campaign.owner:
            owner_team = getattr(campaign.owner, 'team', None)
            return owner_team == user_team
        
        return False

class CampaignMemberPermission(CRMPermission):
    """Permission class for CampaignMember model."""
    
    MODEL_PERMS = {
        'view_campaignmember': 'Can view campaign members',
        'add_campaignmember': 'Can add campaign members',
        'change_campaignmember': 'Can change campaign members',
        'delete_campaignmember': 'Can delete campaign members',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check campaign member permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check access to parent campaign
        if hasattr(obj, 'campaign'):
            campaign_permission = CampaignPermission()
            return campaign_permission.has_object_permission(
                request, view, obj.campaign
            )
        
        return True