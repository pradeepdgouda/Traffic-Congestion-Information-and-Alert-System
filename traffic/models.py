from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

try:
    # Django 3.1+ JSONField
    from django.db.models import JSONField
except Exception:
    # for older versions fallback
    from django.contrib.postgres.fields import JSONField


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    fcm_token = models.CharField(max_length=512, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


# Backwards-compatible models used by existing views/admin
class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    success = models.BooleanField(default=True)

    class Meta:
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.username} @ {self.login_time.isoformat()}"


class Route(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='routes')
    start = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    travel_time = models.DateTimeField()  # time of the route / scheduled time
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.start} -> {self.destination} @ {self.travel_time.isoformat()}"


class UserDevice(models.Model):
    token = models.CharField(max_length=512, unique=True)
    device = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='devices')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device} - {self.token[:20]}..."


class SavedRoute(models.Model):
    route_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    # explicit username field for compatibility with Flutter payloads
    username = models.CharField(max_length=150, db_index=True, blank=True)
    # link to Django user (preferred when available)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_routes', null=True, blank=True)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    distance_km = models.FloatField(null=True, blank=True)
    duration_text = models.CharField(max_length=100, blank=True)
    polyline = models.TextField(blank=True)
    primary_route = JSONField(blank=True, null=True, default=dict)
    selected_routes = JSONField(blank=True, null=True, default=list)
    leaving_time = models.TimeField(null=True, blank=True)
    alert_time = models.TimeField(null=True, blank=True)
    alert_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_checked_duration = models.IntegerField(null=True, blank=True)  # seconds
    # fields for automated alerts
    last_alert_sent = models.DateTimeField(null=True, blank=True)
    alert_status = models.CharField(max_length=32, default='pending')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user_display = self.username or (self.user.username if self.user else 'unknown')
        return f"{user_display} | {self.origin} -> {self.destination} ({self.route_id})"


class RouteAlternative(models.Model):
    alt_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    saved_route = models.ForeignKey(SavedRoute, on_delete=models.CASCADE, related_name='alternatives')
    summary = models.CharField(max_length=255, blank=True)
    distance_km = models.FloatField(null=True, blank=True)
    duration_text = models.CharField(max_length=100, blank=True)
    polyline_data = models.TextField(blank=True)

    def __str__(self):
        return f"Alt {self.alt_id} for {self.saved_route.route_id}"


class TrafficCheckLog(models.Model):
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    saved_route = models.ForeignKey(SavedRoute, on_delete=models.CASCADE, related_name='check_logs')
    checked_at = models.DateTimeField(auto_now_add=True)
    old_duration = models.IntegerField(null=True, blank=True)
    new_duration = models.IntegerField(null=True, blank=True)
    diff_seconds = models.IntegerField(null=True, blank=True)
    congestion_flag = models.BooleanField(default=False)
    api_response_snippet = models.TextField(blank=True)

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        return f"Log {self.log_id} for {self.saved_route.route_id} at {self.checked_at}"


class DeviceToken(models.Model):
    # allow null/blank so existing rows can be migrated without a one-off default
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='device_token', null=True, blank=True)
    token = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:24]}"


class UserFcmDevice(models.Model):
    """Stores latest FCM token per user profile. Multiple devices per profile allowed."""
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='fcm_devices')
    fcm_token = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user_profile.user.username} - {self.fcm_token[:24]}"


class TrafficAlert(models.Model):
    """Stores each backend-generated traffic alert for users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='traffic_alerts')
    route = models.ForeignKey(SavedRoute, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    title = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    severity = models.CharField(max_length=50, blank=True)
    # human-friendly short description stored with the alert
    description = models.TextField(blank=True, null=True)
    # store origin/destination snapshot for quick display
    origin = models.CharField(max_length=255, blank=True, null=True)
    destination = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Alert {self.id} for {self.user.username} - {self.severity}"
