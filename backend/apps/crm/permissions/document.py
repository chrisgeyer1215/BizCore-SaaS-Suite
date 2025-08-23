# backend/apps/crm/permissions/document.py
from rest_framework import permissions
from .base import CRMPermission, TenantPermission, ObjectLevelPermission
from ..models import Document, DocumentCategory, DocumentShare

class DocumentPermission(CRMPermission):
    """Permission class for Document model."""
    
    MODEL_PERMS = {
        'view_document': 'Can view documents',
        'add_document': 'Can add documents',
        'change_document': 'Can change documents',
        'delete_document': 'Can delete documents',
        'download_document': 'Can download documents',
        'share_document': 'Can share documents',
        'version_document': 'Can manage document versions',
        'access_confidential': 'Can access confidential documents',
    }
    
    def has_permission(self, request, view):
        """Check document permissions."""
        if not super().has_permission(request, view):
            return False
        
        if view.action == 'list':
            return self.has_perm(request.user, 'view_document')
        elif view.action == 'create':
            return self.has_perm(request.user, 'add_document')
        elif view.action in ['update', 'partial_update']:
            return self.has_perm(request.user, 'change_document')
        elif view.action == 'destroy':
            return self.has_perm(request.user, 'delete_document')
        elif view.action == 'download':
            return self.has_perm(request.user, 'download_document')
        elif view.action == 'share':
            return self.has_perm(request.user, 'share_document')
        elif view.action in ['upload_version', 'manage_versions']:
            return self.has_perm(request.user, 'version_document')
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check document object permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check confidential document access
        if hasattr(obj, 'confidentiality_level'):
            if obj.confidentiality_level == 'confidential':
                if not self.has_perm(request.user, 'access_confidential'):
                    return False
            elif obj.confidentiality_level == 'restricted':
                if not self.can_access_restricted_document(request.user, obj):
                    return False
        
        # Check document sharing permissions
        if view.action == 'share':
            return self.can_share_document(request.user, obj)
        
        # Check ownership
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Check shared access
        if self.has_shared_access(request.user, obj):
            return True
        
        # Check related object access
        if hasattr(obj, 'related_to') and obj.related_to:
            return self.can_access_related_object(request.user, obj)
        
        # Check team/department access
        return self.has_team_document_access(request.user, obj)
    
    def can_share_document(self, user, document):
        """Check if user can share document."""
        if not self.has_perm(user, 'share_document'):
            return False
        
        # Owner can share
        if hasattr(document, 'created_by') and document.created_by == user:
            return True
        
        # Check if user has explicit sharing permission on this document
        if hasattr(document, 'shares'):
            user_share = document.shares.filter(
                shared_with=user, 
                can_share=True
            ).first()
            return user_share is not None
        
        return False
    
    def can_access_restricted_document(self, user, document):
        """Check access to restricted documents."""
        # Department-based access
        if hasattr(user, 'crm_profile') and hasattr(document, 'department'):
            user_department = user.crm_profile.department
            return user_department == document.department
        
        # Role-based access
        if hasattr(user, 'crm_profile') and hasattr(document, 'required_roles'):
            user_role = user.crm_profile.role
            return user_role in document.required_roles
        
        return False
    
    def has_shared_access(self, user, document):
        """Check if document is shared with user."""
        if hasattr(document, 'shares'):
            return document.shares.filter(shared_with=user).exists()
        return False
    
    def can_access_related_object(self, user, document):
        """Check access based on related object."""
        related_object = document.related_to
        if not related_object:
            return True
        
        # Import permission classes to avoid circular imports
        from .account import AccountPermission
        from .opportunity import OpportunityPermission
        from .ticket import TicketPermission
        
        # Check permission based on related object type
        if hasattr(related_object, '_meta'):
            model_name = related_object._meta.model_name
            
            if model_name == 'account':
                permission = AccountPermission()
                return permission.has_object_permission(None, None, related_object)
            elif model_name == 'opportunity':
                permission = OpportunityPermission()
                return permission.has_object_permission(None, None, related_object)
            elif model_name == 'ticket':
                permission = TicketPermission()
                return permission.has_object_permission(None, None, related_object)
        
        return True
    
    def has_team_document_access(self, user, document):
        """Check team-based document access."""
        if not hasattr(user, 'crm_profile'):
            return False
        
        user_team = user.crm_profile.team
        if not user_team:
            return False
        
        # Check if document belongs to team folder
        if hasattr(document, 'team') and document.team:
            return document.team == user_team
        
        # Check if document owner is in same team
        if hasattr(document, 'created_by') and document.created_by:
            creator_profile = getattr(document.created_by, 'crm_profile', None)
            if creator_profile:
                creator_team = creator_profile.team
                return creator_team == user_team
        
        return False

class DocumentCategoryPermission(CRMPermission):
    """Permission class for DocumentCategory model."""
    
    MODEL_PERMS = {
        'view_documentcategory': 'Can view document categories',
        'add_documentcategory': 'Can add document categories',
        'change_documentcategory': 'Can change document categories',
        'delete_documentcategory': 'Can delete document categories',
    }
    
    def has_permission(self, request, view):
        """Document category permissions."""
        if not super().has_permission(request, view):
            return False
        
        # View permissions for all users
        if view.action in ['list', 'retrieve']:
            return self.has_perm(request.user, 'view_documentcategory')
        
        # Modification requires admin access
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return (request.user.is_staff or 
                   self.has_document_admin_role(request.user) or
                   self.has_perm(request.user, f'{view.action}_documentcategory'))
        
        return True
    
    def has_document_admin_role(self, user):
        """Check if user has document admin role."""
        if hasattr(user, 'crm_profile'):
            return user.crm_profile.role in ['document_admin', 'system_admin']
        return False

class DocumentSharePermission(CRMPermission):
    """Permission class for DocumentShare model."""
    
    MODEL_PERMS = {
        'view_documentshare': 'Can view document shares',
        'add_documentshare': 'Can create document shares',
        'change_documentshare': 'Can change document shares',
        'delete_documentshare': 'Can delete document shares',
    }
    
    def has_object_permission(self, request, view, obj):
        """Check document share permissions."""
        if not super().has_object_permission(request, view, obj):
            return False
        
        # Check access to parent document
        if hasattr(obj, 'document'):
            document_permission = DocumentPermission()
            if not document_permission.has_object_permission(
                request, view, obj.document
            ):
                return False
        
        # Only document owner or shared users can manage shares
        if hasattr(obj, 'shared_by') and obj.shared_by == request.user:
            return True
        
        if hasattr(obj, 'shared_with') and obj.shared_with == request.user:
            # Shared users can only view their own share records
            return view.action in ['retrieve', 'list']
        
        return False