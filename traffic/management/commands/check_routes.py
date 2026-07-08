"""Management command to run periodic checks for saved routes and send FCM alerts.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from traffic.models import SavedRoute, UserFcmDevice
from traffic.notification_service import send_congestion_alert_for_route
from traffic.utils.google_directions import get_live_traffic


class Command(BaseCommand):
    help = "Check saved routes and send alerts when leaving_time is reached."

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f"Running check_routes at {now.isoformat()}")

        routes = SavedRoute.objects.filter(alert_enabled=True)

        for route in routes:
            try:
                # Build today's leaving datetime from route.leaving_time (time field)
                should_alert = False
                if route.leaving_time:
                    today = now.date()
                    # create naive datetime then make it timezone-aware using Django utilities
                    naive_leaving = datetime.combine(today, route.leaving_time)
                    leaving_dt = timezone.make_aware(naive_leaving)
                    if leaving_dt < now:
                        leaving_dt = leaving_dt + timedelta(days=1)
                    # trigger in the 2 minute window before leaving
                    if now >= (leaving_dt - timedelta(minutes=2)) and now <= leaving_dt:
                        should_alert = True

                # update last_checked
                route.last_checked = now
                route.save(update_fields=['last_checked'])

                if should_alert:
                    profile = getattr(route.user, 'profile', None)
                    device = None
                    if profile:
                        device = UserFcmDevice.objects.filter(user_profile=profile).order_by('-updated_at').first()
                    if device and device.fcm_token:
                        # compute severity dynamically from live traffic API
                        try:
                            google_response = get_live_traffic(route.origin, route.destination)
                            normal = google_response.get('duration_seconds')
                            live = google_response.get('duration_in_traffic_seconds') or normal
                            if normal and live and normal > 0:
                                ratio = float(live) / float(normal)
                                if ratio >= 1.6:
                                    severity = 'Heavy congestion'
                                elif ratio >= 1.3:
                                    severity = 'Moderate traffic'
                                else:
                                    severity = 'Normal flow'
                            else:
                                severity = 'Normal flow'
                        except Exception:
                            severity = 'Normal flow'

                        ok = send_congestion_alert_for_route(route, severity)
                        if ok:
                            self.stdout.write(self.style.SUCCESS(f"Alert sent for route {route.route_id} to {route.user.username}"))
                            route.last_alert_sent = now
                            route.alert_status = 'sent'
                            route.save(update_fields=['last_alert_sent', 'alert_status'])
                        else:
                            self.stdout.write(self.style.WARNING(f"Failed to deliver alert for route {route.route_id} to {route.user.username}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"No FCM device for route {route.route_id} (user: {getattr(route.user, 'username', None)})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking route {route.route_id}: {e}"))

        self.stdout.write("check_routes run complete.")