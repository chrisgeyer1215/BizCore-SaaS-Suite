"""
CRM Territory ViewSets - Territory and Team Management
Handles sales territories, team assignments, and performance tracking
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone

from ..models import Territory, Team, TeamMembership, Lead, Opportunity
from ..serializers.territory import (
    TerritorySerializer, TeamSerializer, TeamMembershipSerializer
)
from ..permissions.territory import (
    CanManageTerritories, CanManageTeams, CanViewTerritoryAnalytics
)
from ..services.territory_service import TerritoryService
from ..utils.tenant_utils import get_tenant_context


class TerritoryViewSet(viewsets.ModelViewSet):
    """
    Territory Management ViewSet
    Handles sales territory definitions and assignments
    """
    serializer_class = TerritorySerializer
    permission_classes = [IsAuthenticated, CanManageTerritories]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Territory.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('manager', 'parent_territory')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get territory performance analytics"""
        territory = self.get_object()
        date_range = int(request.query_params.get('date_range', 90))
        
        try:
            service = TerritoryService(tenant=territory.tenant)
            performance = service.get_territory_performance(
                territory=territory,
                date_range=date_range
            )
            
            return Response({
                'success': True,
                'territory': {
                    'id': territory.id,
                    'name': territory.name,
                    'manager': territory.manager.get_full_name() if territory.manager else None
                },
                'performance': performance,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Performance calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign_leads(self, request, pk=None):
        """Assign leads to territory"""
        territory = self.get_object()
        lead_ids = request.data.get('lead_ids', [])
        
        try:
            service = TerritoryService(tenant=territory.tenant)
            result = service.assign_leads_to_territory(
                territory=territory,
                lead_ids=lead_ids,
                user=request.user
            )
            
            return Response({
                'success': True,
                'assigned_count': result['assigned_count'],
                'skipped_count': result['skipped_count'],
                'errors': result['errors']
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Lead assignment failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def team_members(self, request, pk=None):
        """Get territory team members"""
        territory = self.get_object()
        
        # Get all teams in this territory
        teams = Team.objects.filter(territory=territory, is_active=True)
        
        # Get all memberships for these teams
        memberships = TeamMembership.objects.filter(
            team__in=teams,
            is_active=True
        ).select_related('user', 'team')
        
        serializer = TeamMembershipSerializer(memberships, many=True)
        
        return Response({
            'success': True,
            'team_members': serializer.data,
            'total_members': memberships.count(),
            'teams_count': teams.count()
        })


class TeamViewSet(viewsets.ModelViewSet):
    """
    Team Management ViewSet
    Handles sales team creation and management
    """
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, CanManageTeams]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return Team.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('manager', 'territory').prefetch_related('members')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add member to team"""
        team = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'member')
        
        try:
            service = TerritoryService(tenant=team.tenant)
            membership = service.add_team_member(
                team=team,
                user_id=user_id,
                role=role,
                added_by=request.user
            )
            
            return Response({
                'success': True,
                'membership_id': membership.id,
                'message': 'Team member added successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Failed to add team member: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def remove_member(self, request, pk=None):
        """Remove member from team"""
        team = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            service = TerritoryService(tenant=team.tenant)
            service.remove_team_member(
                team=team,
                user_id=user_id,
                removed_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Team member removed successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Failed to remove team member: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get team performance analytics"""
        team = self.get_object()
        date_range = int(request.query_params.get('date_range', 90))
        
        try:
            service = TerritoryService(tenant=team.tenant)
            performance = service.get_team_performance(
                team=team,
                date_range=date_range,
                include_individual=request.query_params.get('include_individual', 'true').lower() == 'true'
            )
            
            return Response({
                'success': True,
                'team': {
                    'id': team.id,
                    'name': team.name,
                    'manager': team.manager.get_full_name() if team.manager else None,
                    'member_count': team.members.filter(is_active=True).count()
                },
                'performance': performance,
                'date_range': f"Last {date_range} days"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Performance calculation failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


class TeamMembershipViewSet(viewsets.ModelViewSet):
    """
    Team Membership ViewSet
    Handles individual team memberships and roles
    """
    serializer_class = TeamMembershipSerializer
    permission_classes = [IsAuthenticated, CanManageTeams]
    
    def get_queryset(self):
        tenant = get_tenant_context(self.request)
        return TeamMembership.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('user', 'team')
    
    def perform_create(self, serializer):
        tenant = get_tenant_context(self.request)
        serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def change_role(self, request, pk=None):
        """Change team member role"""
        membership = self.get_object()
        new_role = request.data.get('role')
        
        try:
            service = TerritoryService(tenant=membership.tenant)
            service.change_member_role(
                membership=membership,
                new_role=new_role,
                changed_by=request.user
            )
            
            return Response({
                'success': True,
                'new_role': new_role,
                'message': 'Member role updated successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Role change failed: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)