from django.contrib import admin
from .models import UserProfile, SavedRoute, RouteAlternative, TrafficCheckLog, DeviceToken
from .models import UserFcmDevice
from .models import TrafficAlert


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'fcm_token', 'phone_number', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('created_at',)


@admin.register(SavedRoute)
class SavedRouteAdmin(admin.ModelAdmin):
    list_display = ('route_id', 'user', 'origin', 'destination', 'leaving_time', 'alert_enabled', 'last_checked', 'last_checked_duration')
    search_fields = ('user__username', 'origin', 'destination')
    list_display = ('route_id', 'user', 'origin', 'destination', 'leaving_time', 'alert_time', 'alert_enabled', 'last_alert_sent', 'alert_status')
    list_filter = ('user', 'alert_enabled', 'alert_status', 'created_at', 'leaving_time')
    ordering = ('-created_at',)
    readonly_fields = ('route_id', 'created_at', 'last_checked', 'last_alert_sent')
    actions = ['force_check']

    def force_check(self, request, queryset):
        # enqueue checks for selected routes
        from .tasks import check_all_saved_routes
        check_all_saved_routes()
        self.message_user(request, 'Triggered check for selected routes (run synchronously).')


@admin.register(RouteAlternative)
class RouteAlternativeAdmin(admin.ModelAdmin):
    list_display = ('alt_id', 'saved_route', 'summary', 'distance_km', 'duration_text')
    search_fields = ('summary',)


@admin.register(TrafficCheckLog)
class TrafficCheckLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'saved_route', 'checked_at', 'old_duration', 'new_duration', 'diff_seconds', 'congestion_flag')
    search_fields = ('saved_route__user__username', 'saved_route__origin', 'saved_route__destination')
    list_filter = ('congestion_flag', 'checked_at')


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at')
    search_fields = ('user__username', 'token')
    readonly_fields = ('created_at',)


@admin.register(UserFcmDevice)
class UserFcmDeviceAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'fcm_token', 'updated_at')
    search_fields = ('user_profile__user__username', 'fcm_token')
    readonly_fields = ('updated_at',)


@admin.register(TrafficAlert)
class TrafficAlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'severity', 'timestamp', 'is_read')
    search_fields = ('user__username', 'message', 'title')
    readonly_fields = ('timestamp',)
