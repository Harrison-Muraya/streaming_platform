"""
User app URL configuration
"""
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # User profile
    path('me/', views.UserViewSet.as_view({'get': 'me'}), name='user-profile'),
    path('stats/', views.UserViewSet.as_view({'get': 'stats'}), name='user-stats'),
    
    # Device management
    path('devices/', views.UserViewSet.as_view({'post': 'register_device'}), name='register-device'),
]