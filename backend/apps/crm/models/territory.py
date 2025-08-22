"""
CRM Territory Models - Complete Implementation
Models: TerritoryType, Territory, TerritoryAssignment, Team, TeamMembership
Completion of Stage 2 CRM development
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

from apps.core.models import TenantBaseModel, SoftDeleteMixin

User = get_user_model()


class TerritoryType(TenantBaseModel):
    """Territory type classification system"""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color for UI
    icon = models.CharField(max_length=50, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # Configuration
    allow_overlap = models.BooleanField(default=False)
    auto_assignment_enabled = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Territory Type'
        verbose_name_plural = 'Territory Types'
        
    def __str__(self):
        return self.name


class Territory(TenantBaseModel, SoftDeleteMixin):
    """Sales territories with geographic and business rule boundaries"""
    
    TERRITORY_TYPES = [
        ('GEOGRAPHIC', 'Geographic Territory'),
        ('PRODUCT', 'Product-based Territory'),
        ('INDUSTRY', 'Industry-based Territory'),
        ('ACCOUNT_SIZE', 'Account Size Territory'),
        ('CHANNEL', 'Channel Territory'),
        ('NAMED_ACCOUNTS', 'Named Accounts'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending Approval'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    territory_type = models.ForeignKey(
        TerritoryType,
        on_delete=models.PROTECT,
        related_name='territories'
    )
    
    # Status & Management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_territories'
    )
    
    # Geographic Boundaries
    countries = models.JSONField(default=list, blank=True)
    states_provinces = models.JSONField(default=list, blank=True)
    cities = models.JSONField(default=list, blank=True)
    postal_codes = models.JSONField(default=list, blank=True)
    zip_code_ranges = models.JSONField(default=list, blank=True)
    
    # Business Rules
    criteria = models.JSONField(default=dict, blank=True)
    assignment_rules = models.JSONField(default=dict, blank=True)
    
    # Targets & Goals
    annual_revenue_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    quarterly_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    monthly_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Performance Tracking
    current_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    ytd_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Settings
    allow_overlap = models.BooleanField(default=False)
    auto_assign_leads = models.BooleanField(default=True)
    auto_assign_accounts = models.BooleanField(default=True)
    priority_score = models.IntegerField(default=50)
    
    # Parent/Child Hierarchy
    parent_territory = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_territories'
    )
    level = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Territory'
        verbose_name_plural = 'Territories'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_territory_code_per_tenant'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'territory_type']),
            models.Index(fields=['tenant', 'manager']),
            models.Index(fields=['tenant', 'parent_territory']),
        ]
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Calculate hierarchy level
        if self.parent_territory:
            self.level = self.parent_territory.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)
    
    @property
    def target_achievement_percentage(self):
        """Calculate target achievement percentage"""
        if self.annual_revenue_target and self.annual_revenue_target > 0:
            return (self.current_revenue / self.annual_revenue_target) * 100
        return Decimal('0.00')
    
    @property
    def is_over_target(self):
        """Check if territory is over annual target"""
        return self.target_achievement_percentage > 100
    
    def get_assigned_users(self):
        """Get all users assigned to this territory"""
        return User.objects.filter(
            territory_assignments__territory=self,
            territory_assignments__is_active=True
        ).distinct()
    
    def get_total_team_size(self):
        """Get total number of active team members"""
        return self.assignments.filter(is_active=True).count()
    
    def check_geographic_match(self, address_data):
        """Check if an address matches this territory's geographic criteria"""
        if not address_data:
            return False
        
        # Check countries
        if self.countries and address_data.get('country'):
            if address_data['country'] not in self.countries:
                return False
        
        # Check states/provinces
        if self.states_provinces and address_data.get('state'):
            if address_data['state'] not in self.states_provinces:
                return False
        
        # Check cities
        if self.cities and address_data.get('city'):
            if address_data['city'] not in self.cities:
                return False
        
        # Check postal codes
        if self.postal_codes and address_data.get('postal_code'):
            if address_data['postal_code'] not in self.postal_codes:
                return False
        
        return True


class TerritoryAssignment(TenantBaseModel):
    """Assign users to territories with roles and effective dates"""
    
    ASSIGNMENT_ROLES = [
        ('MANAGER', 'Territory Manager'),
        ('REP', 'Sales Representative'),
        ('SUPPORT', 'Support Representative'),
        ('OVERLAY', 'Overlay Specialist'),
        ('BACKUP', 'Backup Representative'),
        ('OBSERVER', 'Observer'),
    ]
    
    ASSIGNMENT_TYPES = [
        ('PRIMARY', 'Primary Assignment'),
        ('SECONDARY', 'Secondary Assignment'),
        ('TEMPORARY', 'Temporary Assignment'),
        ('BACKUP', 'Backup Assignment'),
    ]
    
    # Core Assignment
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='territory_assignments'
    )
    territory = models.ForeignKey(
        Territory,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    # Assignment Details
    role = models.CharField(max_length=20, choices=ASSIGNMENT_ROLES, default='REP')
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES, default='PRIMARY')
    
    # Dates & Status
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Permissions & Access
    can_view_all_accounts = models.BooleanField(default=True)
    can_edit_accounts = models.BooleanField(default=True)
    can_create_opportunities = models.BooleanField(default=True)
    can_manage_leads = models.BooleanField(default=True)
    can_assign_territories = models.BooleanField(default=False)
    
    # Performance & Targets
    individual_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Assignment Metadata
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='territory_assignments_made'
    )
    assignment_reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Territory Assignment'
        verbose_name_plural = 'Territory Assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'user', 'territory', 'assignment_type'],
                condition=models.Q(is_active=True),
                name='unique_active_territory_assignment'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_active']),
            models.Index(fields=['tenant', 'territory', 'is_active']),
            models.Index(fields=['tenant', 'start_date', 'end_date']),
        ]
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.territory.name} ({self.role})"
    
    def clean(self):
        """Validate territory assignment"""
        from django.core.exceptions import ValidationError
        
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError('End date cannot be before start date')
        
        # Check for overlapping primary assignments
        if self.assignment_type == 'PRIMARY' and self.is_active:
            overlapping = TerritoryAssignment.objects.filter(
                tenant=self.tenant,
                user=self.user,
                territory=self.territory,
                assignment_type='PRIMARY',
                is_active=True
            ).exclude(pk=self.pk)
            
            if overlapping.exists():
                raise ValidationError(
                    'User already has an active primary assignment to this territory'
                )
    
    @property
    def is_current(self):
        """Check if assignment is currently active"""
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True
    
    @property
    def days_remaining(self):
        """Calculate days remaining in assignment"""
        if not self.end_date:
            return None
        today = timezone.now().date()
        return (self.end_date - today).days
    
    def deactivate_assignment(self, end_reason=None):
        """Deactivate the territory assignment"""
        self.is_active = False
        self.end_date = timezone.now().date()
        if end_reason:
            self.notes = f"{self.notes}\nDeactivated: {end_reason}".strip()
        self.save()


class Team(TenantBaseModel, SoftDeleteMixin):
    """Team management and hierarchy system"""
    
    TEAM_TYPES = [
        ('SALES', 'Sales Team'),
        ('SUPPORT', 'Support Team'),
        ('MARKETING', 'Marketing Team'),
        ('MANAGEMENT', 'Management Team'),
        ('PRODUCT', 'Product Team'),
        ('OPERATIONS', 'Operations Team'),
        ('FINANCE', 'Finance Team'),
        ('TECHNICAL', 'Technical Team'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('FORMING', 'Forming'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    team_type = models.CharField(max_length=20, choices=TEAM_TYPES, default='SALES')
    
    # Status & Management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    team_lead = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_teams'
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams'
    )
    
    # Team Hierarchy
    parent_team = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_teams'
    )
    level = models.IntegerField(default=0)
    
    # Targets & Goals
    team_revenue_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    team_goals = models.JSONField(default=dict, blank=True)
    
    # Performance Metrics
    current_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    ytd_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Team Settings
    max_team_size = models.IntegerField(null=True, blank=True)
    auto_assign_leads = models.BooleanField(default=False)
    shared_commission_pool = models.BooleanField(default=False)
    requires_approval_to_join = models.BooleanField(default=True)
    
    # Collaboration
    slack_channel = models.CharField(max_length=100, blank=True)
    email_list = models.EmailField(blank=True)
    meeting_schedule = models.JSONField(default=dict, blank=True)
    
    # Location & Timezone
    primary_location = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    class Meta:
        ordering = ['level', 'name']
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'code'],
                name='unique_team_code_per_tenant'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status', 'team_type']),
            models.Index(fields=['tenant', 'team_lead']),
            models.Index(fields=['tenant', 'parent_team']),
        ]
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Calculate hierarchy level
        if self.parent_team:
            self.level = self.parent_team.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)
    
    @property
    def total_members(self):
        """Get total number of active team members"""
        return self.memberships.filter(is_active=True).count()
    
    @property
    def target_achievement_percentage(self):
        """Calculate team target achievement percentage"""
        if self.team_revenue_target and self.team_revenue_target > 0:
            return (self.current_revenue / self.team_revenue_target) * 100
        return Decimal('0.00')
    
    @property
    def available_spots(self):
        """Calculate available spots in team"""
        if self.max_team_size:
            return self.max_team_size - self.total_members
        return None
    
    @property
    def is_full(self):
        """Check if team is at capacity"""
        if self.max_team_size:
            return self.total_members >= self.max_team_size
        return False
    
    def get_all_members(self):
        """Get all active team members"""
        return User.objects.filter(
            team_memberships__team=self,
            team_memberships__is_active=True
        ).distinct()
    
    def get_members_by_role(self, role):
        """Get team members by specific role"""
        return User.objects.filter(
            team_memberships__team=self,
            team_memberships__role=role,
            team_memberships__is_active=True
        ).distinct()
    
    def add_member(self, user, role='MEMBER', assigned_by=None):
        """Add a new member to the team"""
        if self.is_full:
            raise ValueError("Team is at maximum capacity")
        
        membership, created = TeamMembership.objects.get_or_create(
            tenant=self.tenant,
            team=self,
            user=user,
            defaults={
                'role': role,
                'assigned_by': assigned_by,
                'is_active': True,
                'join_date': timezone.now().date()
            }
        )
        
        if not created and not membership.is_active:
            membership.is_active = True
            membership.rejoin_date = timezone.now().date()
            membership.save()
        
        return membership


class TeamMembership(TenantBaseModel):
    """Team member assignments with roles and permissions"""
    
    MEMBERSHIP_ROLES = [
        ('LEADER', 'Team Leader'),
        ('SENIOR', 'Senior Member'),
        ('MEMBER', 'Team Member'),
        ('JUNIOR', 'Junior Member'),
        ('INTERN', 'Intern'),
        ('CONTRACTOR', 'Contractor'),
        ('OBSERVER', 'Observer'),
    ]
    
    MEMBERSHIP_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDED', 'Suspended'),
        ('PENDING', 'Pending Approval'),
        ('ON_LEAVE', 'On Leave'),
    ]
    
    # Core Membership
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    
    # Membership Details
    role = models.CharField(max_length=20, choices=MEMBERSHIP_ROLES, default='MEMBER')
    status = models.CharField(max_length=20, choices=MEMBERSHIP_STATUS, default='ACTIVE')
    
    # Dates
    join_date = models.DateField(default=timezone.now)
    leave_date = models.DateField(null=True, blank=True)
    rejoin_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Assignment Details
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_assignments_made'
    )
    assignment_reason = models.CharField(max_length=200, blank=True)
    
    # Permissions
    can_view_team_data = models.BooleanField(default=True)
    can_edit_team_settings = models.BooleanField(default=False)
    can_add_members = models.BooleanField(default=False)
    can_remove_members = models.BooleanField(default=False)
    can_assign_leads = models.BooleanField(default=False)
    can_view_team_revenue = models.BooleanField(default=True)
    
    # Performance & Targets
    individual_target = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-join_date']
        verbose_name = 'Team Membership'
        verbose_name_plural = 'Team Memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'team', 'user'],
                condition=models.Q(is_active=True),
                name='unique_active_team_membership'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'team', 'is_active']),
            models.Index(fields=['tenant', 'user', 'is_active']),
            models.Index(fields=['tenant', 'role', 'status']),
        ]
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.team.name} ({self.role})"
    
    def clean(self):
        """Validate team membership"""
        from django.core.exceptions import ValidationError
        
        if self.leave_date and self.join_date > self.leave_date:
            raise ValidationError('Leave date cannot be before join date')
        
        # Check team capacity
        if self.is_active and self.team.is_full:
            existing_membership = TeamMembership.objects.filter(
                team=self.team,
                user=self.user,
                is_active=True
            ).exclude(pk=self.pk)
            
            if not existing_membership.exists():
                raise ValidationError('Team is at maximum capacity')
    
    @property
    def tenure_days(self):
        """Calculate tenure in days"""
        end_date = self.leave_date or timezone.now().date()
        return (end_date - self.join_date).days
    
    @property
    def is_leader(self):
        """Check if member has leadership role"""
        return self.role in ['LEADER', 'SENIOR']
    
    @property
    def can_manage_team(self):
        """Check if member can manage team settings"""
        return self.can_edit_team_settings or self.role == 'LEADER'
    
    def deactivate_membership(self, leave_reason=None):
        """Deactivate team membership"""
        self.is_active = False
        self.status = 'INACTIVE'
        self.leave_date = timezone.now().date()
        if leave_reason:
            self.notes = f"{self.notes}\nLeft team: {leave_reason}".strip()
        self.save()
    
    def promote_to_leader(self, promoted_by=None):
        """Promote member to team leader"""
        self.role = 'LEADER'
        self.can_edit_team_settings = True
        self.can_add_members = True
        self.can_remove_members = True
        self.can_assign_leads = True
        
        if promoted_by:
            self.notes = f"{self.notes}\nPromoted to leader by {promoted_by.get_full_name()}".strip()
        
        self.save()
        
        # Update team leader if this is the first leader
        if not self.team.team_lead:
            self.team.team_lead = self.user
            self.team.save()