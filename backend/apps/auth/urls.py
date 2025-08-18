# apps/auth/urls.py

from django.urls import path
from . import views

app_name = 'auth'

urlpatterns = [
    # Authentication - simplified for now
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # User Profile
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('tenants/', views.UserTenantsView.as_view(), name='user_tenants'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Email Verification
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    
    # Password Reset
    path('password-reset-request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
    
    # Tenant Management
    path('create-tenant/', views.TenantCreateView.as_view(), name='create_tenant'),
    
    # Invitations
    path('invite-user/', views.InviteUserView.as_view(), name='invite_user'),
    path('accept-invitation/', views.AcceptInvitationView.as_view(), name='accept_invitation'),
    
    # Tenant Members & Invitations
    path('members/', views.TenantMembersView.as_view(), name='tenant_members'),
    path('invitations/', views.TenantInvitationsView.as_view(), name='tenant_invitations'),
    
    # Handoff (tenant switching)
    path('handoff/', views.HandoffTokenView.as_view(), name='handoff'),
    path('handoff/consume/', views.ConsumeHandoffTokenView.as_view(), name='consume_handoff'),
]