import os
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Use the configured path from settings (which loads from environment)
SERVICE_ACCOUNT_PATH = getattr(settings, 'FCM_SERVICE_ACCOUNT_PATH', None)


def _init_firebase():
    """Initialize Firebase Admin SDK with validation."""
    if not SERVICE_ACCOUNT_PATH:
        raise ValueError('FCM_SERVICE_ACCOUNT_PATH not configured in settings')
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(f'Firebase credentials not found: {SERVICE_ACCOUNT_PATH}')
    try:
        firebase_admin.get_app()
    except Exception:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)


def send_notification_to_token(token, title, body, data=None):
    """Send a notification to a single FCM registration token.

    Returns True on success, False on failure. Uses logging instead of prints.
    """
    try:
        _init_firebase()
    except Exception as e:
        logger.error('FCM init failed: %s', e)
        return False

    if not token:
        logger.error('send_notification_to_token: empty token')
        return False

    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
        data=(data or {})
    )

    try:
        resp = messaging.send(msg)
        logger.info('FCM sent to token=%s resp=%s', token[:24], resp)
        return True
    except Exception as e:
        # Log full exception traceback to help debugging (includes firebase_admin errors)
        logger.exception('FCM send error for token=%s', token[:24])
        # Also return False so callers can mark attempt as failed
        return False


def send_congestion_alert_for_route(saved_route, severity, description=None):
    """Send a congestion alert for a SavedRoute instance.

    This looks up the associated user's latest FCM token (via UserFcmDevice or UserProfile),
    sends a human-friendly notification and structured data payload, updates
    `last_alert_sent` and `alert_status` on the saved_route, and logs outcomes.
    Returns True on successful send, False otherwise.
    """
    try:
        from .models import UserFcmDevice, UserProfile
    except Exception:
        logger.exception('Failed to import models in notification_service')
        return False

    profile = None
    user = getattr(saved_route, 'user', None)
    if user:
        profile = getattr(user, 'profile', None)
    # fallback to username lookup
    if not profile and getattr(saved_route, 'username', None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.filter(username=saved_route.username).first()
        if u:
            profile = getattr(u, 'profile', None)

    # final fallback: no profile -> error
    if not profile:
        logger.warning('No UserProfile found for SavedRoute %s', saved_route.route_id)
        # still update status to 'no-profile'
        saved_route.alert_status = 'no_profile'
        try:
            saved_route.save(update_fields=['alert_status'])
        except Exception:
            logger.exception('Failed to update alert_status for %s', saved_route.route_id)
        return False

    # pick latest token from UserFcmDevice if present
    token = None
    try:
        device = UserFcmDevice.objects.filter(user_profile=profile).order_by('-updated_at').first()
        if device and device.fcm_token:
            token = device.fcm_token
        elif getattr(profile, 'fcm_token', None):
            token = profile.fcm_token
    except Exception:
        logger.exception('Error querying UserFcmDevice for profile %s', profile)
        token = getattr(profile, 'fcm_token', None)

    if not token:
        logger.info('No FCM token available for user %s (route %s)', profile.user.username, saved_route.route_id)
        saved_route.alert_status = 'no_token'
        try:
            saved_route.save(update_fields=['alert_status'])
        except Exception:
            logger.exception('Failed to update alert_status for %s', saved_route.route_id)
        return False

    # Helper: shorten a place string to its main name (first CSV segment, trimmed)
    import re

    def _clean_text_keep_alpha(s: str) -> str:
        if not s:
            return ''
        # remove parentheses content, digits, and non-letter characters
        try:
            s = s.split('(')[0]
            # replace digits and punctuation with spaces
            s = re.sub(r"\d+", "", s)
            s = re.sub(r"[^\w\s]", " ", s)
            # keep only ASCII letters and spaces
            s = re.sub(r"[^A-Za-z\s]", "", s)
            s = ' '.join(s.split())
            return s.strip()
        except Exception:
            return ''

    def _main_place(text: str) -> str:
        if not text:
            return ''
        try:
            cleaned = _clean_text_keep_alpha(text)
            if not cleaned:
                return ''
            parts = [p.strip() for p in cleaned.split(',') if p.strip()]
            main = parts[0] if parts else cleaned
            # limit to first 2 words to keep it very short
            words = main.split()
            if len(words) > 2:
                main = ' '.join(words[:2])
            return main.title()
        except Exception:
            return ''

    # Helper: build a short route name
    def _route_short_name(route) -> str:
        # prefer explicit name fields but clean them
        for attr in ('name', 'route_name', 'label'):
            v = getattr(route, attr, None)
            if v:
                vclean = _clean_text_keep_alpha(v)
                return ' '.join(vclean.split()[:3]).title() if vclean else 'Saved Route'
        o = _main_place(getattr(route, 'origin', '') or '')
        d = _main_place(getattr(route, 'destination', '') or '')
        # try to use first word of each side (alphabetic only)
        so = o.split()[0] if o else ''
        sd = d.split()[0] if d else ''
        if so and sd:
            return f"{so}→{sd}"
        if o or d:
            return f"{o}→{d}" if (o and d) else (o or d)
        return 'Saved Route'

    # Compose compact user-facing title and message
    origin_main = _main_place(getattr(saved_route, 'origin', ''))
    destination_main = _main_place(getattr(saved_route, 'destination', ''))
    route_short = _route_short_name(saved_route)

    # Compose payload according to new spec
    title = "Traffic Alert"
    sev = (severity or '').lower() if severity is not None else ''
    # If description not provided, build a short fallback based on severity
    if not description:
        if 'heavy' in sev:
            description = (
                "Severe congestion expected on this route. Traffic delays may be significant.\n"
                "Consider taking an alternate route to avoid long delays."
            )
        elif 'moderate' in sev:
            description = (
                "Moderate traffic on your route. Expect some delays above normal.\n"
                "You may want to check alternate timings or leave a bit earlier."
            )
        else:
            description = (
                "Light traffic currently on this route. Travel should proceed normally.\n"
                "No special action is required; monitor for changes."
            )

    body = description.split('\n')[0] if description else ''

    # structured data payload for the app (includes full description)
    data = {
        'route_id': str(saved_route.route_id),
        'title': title,
        'severity': severity,
        'description': description,
        'origin': saved_route.origin,
        'destination': saved_route.destination,
        'timestamp': timezone.now().isoformat(),
    }

    ok = send_notification_to_token(token, title, body, data)

    # update route metadata regardless of success to record attempt
    try:
        saved_route.last_alert_sent = timezone.now()
        saved_route.alert_status = 'sent' if ok else 'failed'
        saved_route.save(update_fields=['last_alert_sent', 'alert_status'])
    except Exception:
        logger.exception('Failed to update SavedRoute alert fields for %s', saved_route.route_id)

    if ok:
        logger.info('Sent congestion alert to %s for route %s severity=%s', profile.user.username, saved_route.route_id, severity)
        # Persist alert in DB
        try:
            from .models import TrafficAlert
            TrafficAlert.objects.create(
                user=profile.user,
                route=saved_route,
                title=title,
                message=body,
                severity=severity,
                description=description,
                origin=saved_route.origin,
                destination=saved_route.destination,
            )
        except Exception:
            logger.exception('Failed to persist TrafficAlert for %s', saved_route.route_id)
    else:
        logger.error('Failed to send congestion alert to %s for route %s', profile.user.username, saved_route.route_id)

    return ok


def send_route_notification(fcm_token, title, body, data=None):
    """Compatibility wrapper used by older code paths.

    Sends to a raw token. Returns True/False.
    """
    return send_notification_to_token(fcm_token, title, body, data)


def send_congestion_alert(user, title, message):
    """Compatibility wrapper matching older signature: send_congestion_alert(user, title, message).

    This will try to find the user's latest token (UserFcmDevice or UserProfile.fcm_token)
    and send a message. Returns True on success, False otherwise.
    """
    try:
        from .models import UserFcmDevice
    except Exception:
        logger.exception('Failed to import models in send_congestion_alert')
        return False

    profile = None
    # accept username or User instance
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if isinstance(user, str):
        u = User.objects.filter(username=user).first()
        if not u:
            logger.warning('send_congestion_alert: user not found %s', user)
            return False
        profile = getattr(u, 'profile', None)
    else:
        profile = getattr(user, 'profile', None)

    if not profile:
        logger.warning('send_congestion_alert: no profile for user %s', getattr(user, 'username', None))
        return False

    token = None
    try:
        device = UserFcmDevice.objects.filter(user_profile=profile).order_by('-updated_at').first()
        if device and device.fcm_token:
            token = device.fcm_token
        elif getattr(profile, 'fcm_token', None):
            token = profile.fcm_token
    except Exception:
        logger.exception('Error fetching UserFcmDevice for profile %s', profile)
        token = getattr(profile, 'fcm_token', None)

    if not token:
        logger.info('No token to send for user %s', getattr(profile.user, 'username', None))
        return False

    ok = send_notification_to_token(token, title, message, data=None)
    if ok:
        logger.info('send_congestion_alert: sent to %s', profile.user.username)
    else:
        logger.error('send_congestion_alert: failed to send to %s', profile.user.username)
    return ok


def save_fcm_token_for_profile(profile, token):
    """Save or update an FCM token for a given UserProfile instance.

    Returns True on success, False on failure.
    This writes both `UserFcmDevice` (latest device record) and the
    `UserProfile.fcm_token` field so older codepaths keep working.
    """
    try:
        from .models import UserFcmDevice
    except Exception:
        logger.exception('Failed to import UserFcmDevice in save_fcm_token_for_profile')
        return False

    if profile is None:
        logger.warning('save_fcm_token_for_profile called with no profile')
        return False

    try:
        obj, created = UserFcmDevice.objects.update_or_create(
            user_profile=profile,
            defaults={
                'fcm_token': token,
            }
        )
        # keep the legacy single-token field in sync
        profile.fcm_token = token
        profile.save(update_fields=['fcm_token'])
        logger.info('Saved FCM token for %s (created=%s)', profile.user.username, created)
        return True
    except Exception:
        logger.exception('Failed to save FCM token for profile %s', profile)
        return False


def save_fcm_token(user_or_username, token):
    """Accept either a username (str) or a Django User instance and save token.

    Example usages:
      - `save_fcm_token('alice', 'tokenstring')`
      - `save_fcm_token(user_instance, 'tokenstring')`

    Returns True on success, False otherwise.
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
    except Exception:
        logger.exception('Failed to import User model in save_fcm_token')
        return False

    profile = None
    if isinstance(user_or_username, str):
        u = User.objects.filter(username=user_or_username).first()
        if not u:
            logger.warning('save_fcm_token: user not found %s', user_or_username)
            return False
        profile = getattr(u, 'profile', None)
    else:
        profile = getattr(user_or_username, 'profile', None)

    if not profile:
        logger.warning('save_fcm_token: no profile for %s', getattr(user_or_username, 'username', user_or_username))
        return False

    return save_fcm_token_for_profile(profile, token)
