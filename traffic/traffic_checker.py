import traceback
from datetime import datetime, timedelta, time as dtime
import threading
import traceback
import logging

from django.utils import timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .models import SavedRoute
from .utils.google_directions import get_live_traffic
from .notification_service import send_congestion_alert_for_route

logger = logging.getLogger(__name__)

_scheduler = None


def _should_check_route(route, now):
    """Return True if we should perform a live traffic check for this route now."""
    if not route.alert_enabled:
        return False
    if not route.alert_time:
        return False

    # combine today's date with route.alert_time
    tz = timezone.get_current_timezone()
    today = timezone.localtime(now).date()
    alert_dt = datetime.combine(today, route.alert_time)
    alert_dt = tz.localize(alert_dt) if getattr(tz, 'localize', None) else alert_dt.replace(tzinfo=tz)

    # If the alert time for today already passed and we already sent an alert for today, skip
    if route.last_alert_sent:
        # If last_alert_sent is later than today's alert time, we've already alerted
        if route.last_alert_sent >= alert_dt:
            return False

    # Trigger check if now >= alert_dt - 2 minutes and now <= alert_dt + 10 minutes
    window_start = alert_dt - timedelta(minutes=2)
    window_end = alert_dt + timedelta(minutes=10)
    return now >= window_start and now <= window_end


def _mark_passed(route):
    route.alert_status = 'passed'
    route.save(update_fields=['alert_status'])


def check_all_routes():
    """
    Iterate over saved routes and perform live traffic checks when appropriate.
    Returns summary dict.
    """
    now = timezone.now()
    logger.info('Traffic checker running at %s', now.isoformat())
    checked = 0
    alerts_sent = 0

    qs = SavedRoute.objects.filter(alert_enabled=True)
    for route in qs:
        try:
            checked += 1
            logger.info('Checking traffic for route: %s', route.route_id)

            # perform live traffic check if scheduled window or always check recent routes
            google_response = get_live_traffic(route.origin, route.destination)
            logger.info('API response for %s: %s', route.route_id, google_response)

            if 'error' in google_response or ('api_raw' in google_response and not google_response.get('duration_seconds')):
                logger.warning('Skipping route %s due to API error or missing data', route.route_id)
                continue

            normal = google_response.get('duration_seconds')
            live = google_response.get('duration_in_traffic_seconds') or normal

            route.last_checked = now
            route.last_checked_duration = live
            try:
                route.save(update_fields=['last_checked', 'last_checked_duration'])
            except Exception:
                logger.exception('Failed to update last_checked for %s', route.route_id)

            # compute severity dynamically using ratio = live / normal
            try:
                severity = 'Normal '
                if normal and live and normal > 0:
                    ratio = float(live) / float(normal)
                    if ratio >= 1.7:
                        severity = 'Heavy '
                    elif ratio >= 1.2:
                        severity = 'Moderate '
                    else:
                        severity = 'Normal '
                else:
                    severity = 'Normal '
            except Exception:
                logger.exception('Error computing severity for %s', route.route_id)
                severity = 'Normal '

            # Only send an alert if the route's saved alert_time matches current server time (HH:MM)
            try:
                current_time = datetime.now().strftime("%H:%M")
                route_alert_time = route.alert_time or ""
                # route.alert_time may be a time object or a string; normalize to HH:MM
                try:
                    # dtime was imported as alias for datetime.time
                    if isinstance(route_alert_time, dtime):
                        route_alert_time = route_alert_time.strftime("%H:%M")
                    else:
                        route_alert_time = str(route_alert_time).strip()
                except Exception:
                    route_alert_time = str(route_alert_time)

                if route_alert_time != current_time:
                    logger.debug('Skipping alert for %s: alert_time=%s current_time=%s', route.route_id, route_alert_time, current_time)
                    continue

                # Generate a short 2-line description based on severity
                sev_low = (severity or '').lower()
                if 'heavy' in sev_low:
                    description = (
                        "Severe congestion expected on this route. Traffic delays may be significant.\n"
                        "Consider taking an alternate route to avoid long delays."
                    )
                elif 'moderate' in sev_low:
                    description = (
                        "Moderate traffic on your route. Expect some delays above normal.\n"
                        "You may want to check alternate timings or leave a bit earlier."
                    )
                else:
                    description = (
                        "Light traffic currently on this route. Travel should proceed normally.\n"
                        "No special action is required; monitor for changes."
                    )

                ok = send_congestion_alert_for_route(route, severity, description)
                if ok:
                    alerts_sent += 1
                    logger.info('Alert send OK for %s severity=%s', route.route_id, severity)
                else:
                    logger.warning('Alert send failed for %s severity=%s', route.route_id, severity)
            except Exception:
                logger.exception('Exception while sending alert for %s', route.route_id)

        except Exception:
            print('Error checking route', route.route_id)
            traceback.print_exc()

    return {'checked': checked, 'alerts_sent': alerts_sent}


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=timezone.get_current_timezone())
    # run check_all_routes every 1 minute
    _scheduler.add_job(check_all_routes, 'interval', minutes=1, id='traffic_check_job', replace_existing=True)
    # start in separate thread to avoid blocking
    t = threading.Thread(target=_scheduler.start, daemon=True)
    t.start()
    print('Traffic checker scheduler started')
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
