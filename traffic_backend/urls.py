"""
URL configuration for traffic_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from traffic import views as traffic_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('traffic.urls')),            # keep homepage at site root
    path('api/traffic/', include('traffic.urls')),  # expose API at /api/traffic/
    # convenience alias so clients that call /api/alerts/ (no 'traffic' prefix)
    # still reach the authenticated stored alerts endpoint
    path('api/alerts/', traffic_views.get_alerts),
    # convenience alias for deleting a single alert (accepts UUID)
    path('api/alerts/<uuid:alert_id>/', traffic_views.delete_alert),
    # convenience alias for alert detail and user alert list
    path('api/alerts/<uuid:alert_id>/detail/', traffic_views.alert_detail),
    path('api/alerts/user/<int:user_id>/', traffic_views.user_alerts),
    # convenience alias to accept Flutter's default path
    path('api/save_route/', traffic_views.save_route),
    path('api/sync_route/', traffic_views.sync_route_view),
    path('api/save_fcm_token/', traffic_views.save_token),
    path('api/save_token/', traffic_views.save_token),
]
