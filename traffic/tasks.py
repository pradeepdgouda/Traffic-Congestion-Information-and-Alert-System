from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
from .models import SavedRoute, TrafficCheckLog
from .utils.google_directions import get_live_traffic
from .notification_service import send_route_notification


def should_send_alert(old_duration, new_duration):
    if old_duration is None:
        return False
    diff = new_duration - old_duration
    if diff <= 0:
        return False
    # threshold: 10 minutes (600s) or 15% of old_duration
    threshold = max(600, int(old_duration * 0.15))
    return diff >= threshold


def check_all_saved_routes():
    now = timezone.now()
    # look for routes that are alert_enabled
    routes = SavedRoute.objects.filter(alert_enabled=True)
    results = {'checked': 0, 'alerts_sent': 0}

    for r in routes:
        results['checked'] += 1
        # compute next leaving datetime from r.leaving_time
        try:
            naive_leaving = datetime.combine(now.date(), r.leaving_time)
            leaving_dt = timezone.make_aware(naive_leaving)
            if leaving_dt < now:
                leaving_dt = leaving_dt + timedelta(days=1)
        except Exception:
            leaving_dt = now

        # only check routes within next 24 hours
        if leaving_dt < now or leaving_dt > now + timedelta(days=1):
            continue

        res = get_live_traffic(r.origin, r.destination)
        if 'duration_in_traffic_seconds' not in res:
            # log failure
            TrafficCheckLog.objects.create(saved_route=r, api_response_snippet=str(res))
            continue

        new_duration = int(res['duration_in_traffic_seconds'] or 0)
        old_duration = r.last_checked_duration or 0

        diff = new_duration - old_duration
        flag = should_send_alert(old_duration, new_duration)

        TrafficCheckLog.objects.create(
            saved_route=r,
            old_duration=old_duration,
            new_duration=new_duration,
            diff_seconds=diff,
            congestion_flag=flag,
            api_response_snippet=str(res.get('api_raw'))[:2000]
        )

        # update saved route
        r.last_checked = now
        r.last_checked_duration = new_duration
        r.save(update_fields=['last_checked', 'last_checked_duration'])

        if flag:
            # send notification if user has device token
            dt = getattr(r.user, 'device_token', None)
            if dt and getattr(dt, 'token', None):
                try:
                    send_route_notification(dt.token, f"Traffic Alert: {r.origin} -> {r.destination}",
                                            f"Travel time increased by {diff//60} minutes.")
                    results['alerts_sent'] += 1
                except Exception:
                    pass

    return results


@shared_task
def check_all_saved_routes_task():
    return check_all_saved_routes()
