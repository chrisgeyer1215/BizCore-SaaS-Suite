# apps/auth/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'auth'

urlpatterns = [
    # JWT Authentication
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User Management
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('tenants/', views.UserTenantsView.as_view(), name='user_tenants'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Tenant Management
    path('create-tenant/', views.TenantCreateView.as_view(), name='create_tenant'),
    
    # Email Verification
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    
    # Password Reset
    path('password-reset-request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
    
    # Invitations
    path('invite-user/', views.InviteUserView.as_view(), name='invite_user'),
    path('accept-invitation/', views.AcceptInvitationView.as_view(), name='accept_invitation'),
    path('invitation/<str:token>/', views.get_invitation_details, name='invitation_details'),
    
    # Tenant Members & Invitations
    path('members/', views.TenantMembersView.as_view(), name='tenant_members'),
    path('invitations/', views.TenantInvitationsView.as_view(), name='tenant_invitations'),
    
    # Handoff (tenant switching)
    path('handoff/', views.HandoffTokenView.as_view(), name='handoff'),
    path('handoff/consume/', views.ConsumeHandoffTokenView.as_view(), name='consume_handoff'),
]