from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('logs/', views.log_list, name='log_list'),
    path('logs/<int:pk>/', views.log_detail, name='log_detail'),
    path('schedule/', views.schedule_playbook, name='schedule_playbook'),
    path('playbooks/', views.playbook_list, name='playbook_list'),
    path('run/<int:pk>/', views.run_playbook, name='run_playbook'),
    # Admin-style routes for future expansion
    path('admin/playbooks/', views.playbook_list, name='admin_playbooks'),
    # Placeholder views for servers, inventory, credentials
    path('admin/servers/', views.not_implemented, name='admin_servers'),
    path('admin/inventory/', views.not_implemented, name='admin_inventory'),
    path('admin/credentials/', views.not_implemented, name='admin_credentials'),
    path('api/playbook/<int:pk>/', views.api_playbook_detail, name='api_playbook_detail'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
]
