# traffic/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),            # homepage
    path('signup/', views.signup, name='signup'),
    path('register/', views.signup, name='register'),
    path('login/', views.login, name='login'),
    path('routes/', views.routes, name='routes'),
    path('get_route/', views.get_route, name='get_route'),

    # new endpoints required by prompt
    path('save_route/', views.save_route, name='save_route'),
    path('save_fcm_token/', views.save_fcm_token, name='save_fcm_token'),
    path('check_route_status/<str:username>/', views.check_route_status, name='check_route_status'),
    # Authenticated alerts listing (stored backend alerts)
    path('alerts/', views.get_alerts, name='get_alerts'),
    path('alerts/mark_read/', views.mark_alert_read, name='mark_alert_read'),
    path('alerts/<uuid:alert_id>/', views.delete_alert, name='delete_alert'),
    path('alerts/user/<int:user_id>/', views.user_alerts, name='user_alerts'),
    path('alerts/<uuid:alert_id>/detail/', views.alert_detail, name='alert_detail'),
    path('sync_routes/', views.sync_routes, name='sync_routes'),
    path('save_token/', views.save_token, name='save_token'),  # new endpoint
    path('my_routes/', views.my_routes, name='my_routes'),
]
