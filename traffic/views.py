from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
import requests
from django.http import JsonResponse
from django.conf import settings
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt
import logging
from django.utils import timezone
from datetime import timedelta

from .models import (
    LoginActivity, UserProfile, Route, UserDevice,
    SavedRoute, DeviceToken, UserFcmDevice
)
from .serializers import (
    RouteSerializer, UserDeviceSerializer,
    SavedRouteSerializer, DeviceTokenSerializer, SyncRouteSerializer
)
from .serializers import TrafficAlertSerializer
from fcm_service import send_traffic_alert
from .notification_service import send_route_notification
from .utils.google_directions import get_live_traffic

logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

User = get_user_model()


# Alerts polling endpoint for clients (useful for emulators without FCM)
@api_view(['GET'])
@permission_classes([AllowAny])
def alerts(request):
    """
    GET /api/alerts/?username=<username>
    Returns a list of routes that currently require alerting (should_alert == true).
    This endpoint is intended for clients (emulator or apps) to poll and show
    a local notification when backend determines alerting is needed.
    """
    username = request.GET.get('username')
    if not username:
        return Response({"status": "error", "detail": "username is required"}, status=400)

    now = timezone.now()
    # SavedRoute stores leaving_time as a time of day; compute upcoming by matching user
    upcoming = SavedRoute.objects.filter(user__username=username).order_by('timestamp')
    alerts_list = []

    for route in upcoming:
        seed = (route.origin + route.destination + str(route.leaving_time)).__hash__()
        level = abs(seed) % 3
        traffic_map = {0: "LIGHT", 1: "MODERATE", 2: "HEAVY"}
        traffic = traffic_map[level]

        # compute leaving datetime for next occurrence
        try:
            lt = route.leaving_time
            # combine with today's date
            # build naive datetime then make it timezone-aware
            from datetime import datetime as _dt
            naive = _dt.combine(now.date(), lt)
            leaving_dt = timezone.make_aware(naive)
            if leaving_dt < now:
                leaving_dt = leaving_dt + timedelta(days=1)
        except Exception:
            leaving_dt = now

        # alert_time may be stored as minutes (int) or a time; try to derive minutes
        alert_minutes = 0
        try:
            at = route.alert_time
            if isinstance(at, int):
                alert_minutes = at
            else:
                # if time object, compute minutes difference between leaving_time and alert_time (today)
                if hasattr(at, 'hour'):
                    from datetime import datetime as _dt
                    naive_at = _dt.combine(now.date(), at)
                    at_dt = timezone.make_aware(naive_at)
                    alert_minutes = int((leaving_dt - at_dt).total_seconds() / 60)
        except Exception:
            alert_minutes = 0

        alert_delta = timedelta(minutes=alert_minutes)
        should_alert = False
        if now >= (leaving_dt - alert_delta) and now <= leaving_dt:
            should_alert = True

            # update last_checked for visibility
            route.last_checked = now
            route.save(update_fields=['last_checked'])

        if should_alert:
            alerts_list.append({
                "route_id": route.id,
                "origin": route.origin,
                "destination": route.destination,
                "leaving_time": route.leaving_time,
                "traffic": traffic,
                "should_alert": should_alert,
            })

    return Response({"alerts": alerts_list})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_alerts(request):
    """Return stored TrafficAlert objects for the authenticated user (JSON)."""
    try:
        from .models import TrafficAlert
        qs = TrafficAlert.objects.filter(user=request.user).order_by('-timestamp')
        out = []
        for a in qs:
            route_display = None
            try:
                if a.route:
                    route_display = f"{a.route.origin} → {a.route.destination}"
            except Exception:
                route_display = None
            out.append({
                'id': str(a.id),
                'title': a.title,
                'message': a.message,
                'severity': a.severity,
                'route': route_display,
                'timestamp': a.timestamp.isoformat(),
                'is_read': a.is_read,
            })
        return Response(out)
    except Exception as e:
        logger.exception('get_alerts error')
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_alert_read(request):
    """Mark a TrafficAlert as read for the authenticated user.

    Payload: {"alert_id": "<uuid>"}
    """
    try:
        alert_id = request.data.get('alert_id') or request.POST.get('alert_id')
        if not alert_id:
            return Response({'error': 'alert_id required'}, status=400)
        from .models import TrafficAlert
        a = TrafficAlert.objects.filter(id=alert_id, user=request.user).first()
        if not a:
            return Response({'error': 'not found'}, status=404)
        a.is_read = True
        a.save(update_fields=['is_read'])
        return Response({'status': 'ok'})
    except Exception as e:
        logger.exception('mark_alert_read error')
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_alert(request, alert_id):
    """Delete a TrafficAlert owned by the authenticated user.

    URL: DELETE /api/alerts/<uuid:alert_id>/
    Returns: {"message": "Deleted"} on success.
    """
    try:
        from .models import TrafficAlert
        a = TrafficAlert.objects.filter(id=alert_id, user=request.user).first()
        if not a:
            return Response({'error': 'not found'}, status=404)
        a.delete()
        return Response({'message': 'Deleted'}, status=200)
    except Exception as e:
        logger.exception('delete_alert error')
        return Response({'error': str(e)}, status=500)
# Signup API
@api_view(['POST'])
def signup(request):
    """
    POST /api/register/
    Creates a user and profile, returns auth token.
    Payload: {username, email, password, phone}
    """
    try:
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")
        phone = request.data.get("phone")

        if not username or not email or not password:
            return Response({"error": "username, email and password are required"}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=400)

        user = User.objects.create_user(username=username, email=email, password=password)
        # create profile
        try:
            UserProfile.objects.create(user=user, phone_number=phone)
        except Exception:
            pass

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"message": "User created successfully", "token": token.key}, status=201)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


# Login API
@api_view(['POST'])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    # get client IP
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    user_agent = request.META.get('HTTP_USER_AGENT', '')

    if user is not None:
        # create profile only on first successful login
        try:
            UserProfile.objects.get_or_create(user=user)
        except Exception:
            pass

        # record login activity (optional)
        try:
            LoginActivity.objects.create(user=user, ip_address=ip, user_agent=user_agent, success=True)
        except Exception:
            pass

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "message": "Login successful",
            "token": token.key,
            "user_id": user.id,
            "email": user.email
        })
    else:
        return Response({"error": "Invalid credentials"}, status=400)


# Routes list/create endpoint - authenticated users only
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def routes(request):
    """
    GET: list all routes belonging to request.user
    POST: create a new route for request.user (payload: start, destination, travel_time)
    """
    if request.method == 'GET':
        qs = Route.objects.filter(user=request.user).order_by('-created_at')
        serializer = RouteSerializer(qs, many=True)
        return Response(serializer.data)

    # POST
    serializer = RouteSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


# simple homepage showing project title
def home(request):
    context = {
        "title": "welcome to traffic congestion information and alert system database"
    }
    return render(request, "traffic/home.html", context)


def get_route(request):
    origin = request.GET.get("origin")
    destination = request.GET.get("destination")

    if not origin or not destination:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": settings.GOOGLE_MAPS_API_KEY
    }

    response = requests.get(url, params=params)
    return JsonResponse(response.json())


# New: return alerts for a given user id (authenticated). Caller must be same user.
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_alerts(request, user_id):
    # only allow users to fetch their own alerts
    if request.user.id != int(user_id):
        return Response({'error': 'forbidden'}, status=403)
    try:
        from .models import TrafficAlert
        qs = TrafficAlert.objects.filter(user_id=user_id).order_by('-timestamp')
        serializer = TrafficAlertSerializer(qs, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.exception('user_alerts error')
        return Response({'error': str(e)}, status=500)


# New: return full detail for a single alert (authenticated owner only)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_detail(request, alert_id):
    try:
        from .models import TrafficAlert
        a = TrafficAlert.objects.filter(id=alert_id, user=request.user).first()
        if not a:
            return Response({'error': 'not found'}, status=404)
        # return full description and metadata
        return Response({
            'id': str(a.id),
            'severity': a.severity,
            'description': a.description,
            'origin': a.origin,
            'destination': a.destination,
            'timestamp': a.timestamp.isoformat(),
        })
    except Exception as e:
        logger.exception('alert_detail error')
        return Response({'error': str(e)}, status=500)


# Save route endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def save_route(request):
    """
    POST /api/save_route/
    Accepts saved route payload from Flutter and stores it.
    """
    data = request.data.copy()
    # prefer provided username, else use authenticated username
    if not data.get('username') and request.user and request.user.is_authenticated:
        data['username'] = request.user.username

    serializer = SavedRouteSerializer(data=data)
    if serializer.is_valid():
        obj = serializer.save()
        return Response({"status": "success", "route_id": obj.id}, status=201)
    return Response({"status": "error", "errors": serializer.errors}, status=400)


# Check route status endpoint
@api_view(['GET'])
@permission_classes([AllowAny])
def check_route_status(request, username):
    """
    GET /api/check_route_status/<username>/
    Dummy traffic check for the user's most recent route(s).
    Returns JSON:
    {
      "route_id": 1,
      "traffic": "HEAVY",
      "should_alert": true
    }
    This endpoint also updates last_checked_at and will attempt to send FCM if should_alert.
    """
    now = timezone.now()
    # get the most recent future route for the user
    route = SavedRoute.objects.filter(username=username, leaving_time__gte=now).order_by('leaving_time').first()
    if not route:
        return Response({"status": "error", "detail": "no upcoming route found"}, status=404)

    # Dummy traffic logic: simple deterministic mapping
    seed = (route.origin + route.destination + str(route.leaving_time)).__hash__()  # deterministic
    level = abs(seed) % 3
    traffic_map = {0: "LIGHT", 1: "MODERATE", 2: "HEAVY"}
    traffic = traffic_map[level]

    # Determine alert time window
    alert_delta = timedelta(minutes=route.alert_time or 0)
    should_alert = False
    if now >= (route.leaving_time - alert_delta) and now <= route.leaving_time:
        should_alert = True

    # update last_checked
    route.last_checked = now
    route.save(update_fields=['last_checked'])

    # If should_alert, attempt to send FCM if DeviceToken exists
    if should_alert:
        try:
                dt = getattr(route.user, 'device_token', None)
                if dt and getattr(dt, 'token', None):
                    # Compose message
                    msg = f"Traffic {traffic} on {route.origin} -> {route.destination}"
                    try:
                        send_route_notification(dt.token, f"{route.origin} -> {route.destination}", msg)
                    except Exception:
                        # fallback to previous function
                        send_traffic_alert(dt.token, f"{route.origin} -> {route.destination}", msg)
        except Exception:
            # swallow exceptions to avoid breaking API
            pass

    return Response({
        "route_id": route.id,
        "traffic": traffic,
        "should_alert": should_alert
    })


# Save/update device token (stores one token per user)
@api_view(['POST'])
@permission_classes([AllowAny])
def save_token(request):
    """
    POST /api/save_token/
    Payload: {"username": "alice", "token": "<fcm_token>"}
    If username omitted and request.user authenticated, user's username is used.
    One token per username is maintained (create or update).
    """
    # legacy: allow unauthenticated POST with username, but prefer authenticated user
    token_value = request.data.get('fcm_token') or request.data.get('token')
    if not token_value:
        return Response({"status": "error", "detail": "fcm_token is required"}, status=400)

    if request.user and request.user.is_authenticated:
        try:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.fcm_token = token_value
            profile.save(update_fields=['fcm_token'])
            # create a new UserFcmDevice record for this token (allow multiple tokens per user)
            try:
                UserFcmDevice.objects.create(user_profile=profile, fcm_token=token_value)
            except Exception:
                # fallback to update_or_create if unique constraint exists
                UserFcmDevice.objects.update_or_create(user_profile=profile, defaults={'fcm_token': token_value})
            # also upsert into UserDevice table for backward compatibility
            try:
                UserDevice.objects.update_or_create(token=token_value, defaults={'user': request.user, 'device': ''})
            except Exception:
                logger.exception('Failed to upsert into UserDevice for user %s', request.user.username)

            logger.info('Saved FCM token for user=%s token=%s', request.user.username, token_value[:24])
            return Response({"message": "FCM token saved successfully"})
        except Exception as e:
            logger.exception('Error saving fcm token for authenticated user')
            return Response({"status": "error", "detail": str(e)}, status=500)

    # fallback: accept username in payload
    username = request.data.get('username')
    if not username:
        return Response({"status": "error", "detail": "username is required if unauthenticated"}, status=400)

    user = User.objects.filter(username=username).first()
    if not user:
        return Response({"status": "error", "detail": "user not found"}, status=404)

    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.fcm_token = token_value
        profile.save(update_fields=['fcm_token'])
        try:
            UserFcmDevice.objects.create(user_profile=profile, fcm_token=token_value)
        except Exception:
            UserFcmDevice.objects.update_or_create(user_profile=profile, defaults={'fcm_token': token_value})
        # upsert into UserDevice for backward compatibility
        try:
            UserDevice.objects.update_or_create(token=token_value, defaults={'user': user, 'device': ''})
        except Exception:
            logger.exception('Failed to upsert into UserDevice for username %s', username)
        logger.info('Saved FCM token for username=%s token=%s', username, token_value[:24])
        return Response({"message": "FCM token saved successfully"})
    except Exception as e:
        logger.exception('Error saving fcm token for username=%s', username)
        return Response({"status": "error", "detail": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def save_fcm_token(request):
    """
    POST /api/save_fcm_token/
    Payload: {"username": "alice", "token": "<fcm-token>"}

    Validates presence of username and token, ensures UserProfile exists,
    then creates or updates a UserFcmDevice for that profile.
    Returns {"status": "Token saved"} on success.
    """
    username = request.data.get('username')
    token_value = request.data.get('token')

    if not username or not token_value:
        return Response({"detail": "username and token are required"}, status=400)

    # find user
    user = User.objects.filter(username=username).first()
    if not user:
        return Response({"detail": "user not found"}, status=404)

    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        # update or create a single UserFcmDevice per profile
        # use update_or_create so we don't create duplicates
        UserFcmDevice.objects.update_or_create(
            user_profile=profile,
            defaults={"fcm_token": token_value}
        )
        # also update profile.fcm_token for backward compatibility
        profile.fcm_token = token_value
        profile.save(update_fields=['fcm_token'])

        logger.debug('Token stored for %s', username)
        print(f'Token stored for {username}')
        return Response({"status": "Token saved"})
    except Exception as e:
        logger.exception('Failed to save FCM token for %s', username)
        return Response({"detail": str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def save_route(request):
    """
    Accepts POST JSON from Flutter to save a route.
    Expected JSON fields (examples):
    {
      "username": "alice",
      "origin": "Point A",
      "destination": "Point B",
      "distance": "12 km",
      "duration": "15 mins",
      "alert_time": "10",        # minutes before leaving OR HH:mm
      "leaving_time": "2025-11-23T12:30:00Z"  # or "12:30"
    }

    Returns JSON {"message": "Saved", "id": <route_id>}
    """
    import json
    try:
        if request.content_type == 'application/json' or request.META.get('CONTENT_TYPE','').startswith('application/json'):
            payload = request.data if hasattr(request, 'data') and request.data else json.loads(request.body.decode('utf-8') or '{}')
        else:
            # fallback to POST form data
            payload = request.POST.dict()
    except Exception as e:
        return JsonResponse({'message': 'Invalid JSON', 'error': str(e)}, status=400)

    # map fields
    username = payload.get('username') or payload.get('user')
    origin = payload.get('origin')
    destination = payload.get('destination')
    distance = payload.get('distance')
    duration = payload.get('duration')
    alert_time = payload.get('alert_time')
    leaving_time = payload.get('leaving_time')

    if not username or not origin or not destination:
        return JsonResponse({'message': 'Missing required fields: username/origin/destination'}, status=400)

    try:
        # attempt to link to Django user if exists
        user = None
        try:
            user = User.objects.filter(username=username).first()
        except Exception:
            user = None
        # coerce distance/duration fields
        try:
            dist_val = float(distance) if distance is not None and distance != '' else None
        except Exception:
            dist_val = None

        # If authenticated, prefer request.user
        if request.user and getattr(request.user, 'is_authenticated', False):
            user = request.user

        route = SavedRoute.objects.create(
            username=username or (user.username if user else ''),
            user=user,
            origin=origin,
            destination=destination,
            distance_km=dist_val,
            duration_text=duration or '',
            alert_time=alert_time if alert_time is not None else None,
            leaving_time=leaving_time if leaving_time is not None else None,
        )
        logger.info('Saved route %s for user=%s origin=%s destination=%s', route.route_id, username or (user.username if user else 'anonymous'), origin, destination)
        return JsonResponse({'message': 'Saved', 'id': str(route.route_id)})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print('save_route error:', tb)
        return JsonResponse({'message': 'error', 'detail': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_route_view(request):
    """
    POST /api/sync_route/
    Accepts a single route JSON from Flutter and stores it under request.user.
    Requires TokenAuthentication (IsAuthenticated).
    """
    print("Received route for user:", getattr(request.user, 'username', None))
    print("Incoming JSON:", request.data)

    serializer = SyncRouteSerializer(data=request.data)
    if not serializer.is_valid():
        print('SyncRoute serializer errors:', serializer.errors)
        return Response({"error": "Invalid data", "details": serializer.errors}, status=400)

    try:
        # serializer.create expects model fields; ensure user is assigned after creation
        route = serializer.save()
        # associate with user if not set
        if getattr(route, 'user', None) is None:
            route.user = request.user
            route.username = request.user.username
            route.save(update_fields=['user', 'username'])

        return Response({"status": "success", "route_id": str(route.route_id)}, status=201)
    except Exception as e:
        import traceback
        print('sync_route error:', traceback.format_exc())
        return Response({"error": "Invalid data", "details": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_routes(request):
    """
    Accepts bulk routes from Flutter and upserts by route_id for the user.
    Payload: { "username": "...", "routes": [ {...} ] }
    """
    payload = request.data
    routes = payload.get('routes') or []
    user = request.user

    created = 0
    updated = 0
    errors = []

    for r in routes:
        route_uuid = r.get('route_id')
        data = {
            'user': user.id,
            'origin': r.get('origin'),
            'destination': r.get('destination'),
            'distance_km': r.get('distance_km'),
            'duration_text': r.get('duration_text'),
            'polyline_data': r.get('polyline'),
            'leaving_time': r.get('leaving_time'),
            'alert_time': r.get('alert_time'),
            'primary_route': r.get('primary_route'),
            'raw_selected_routes': r.get('selected_routes'),
            'alert_enabled': r.get('alert_enabled', True),
            'alternatives': r.get('alternatives', []),
        }

        if route_uuid:
            obj = SavedRoute.objects.filter(route_id=route_uuid, user=user).first()
            if obj:
                ser = SavedRouteSerializer(obj, data=data, partial=True)
                if ser.is_valid():
                    ser.save()
                    updated += 1
                else:
                    errors.append({'route_id': route_uuid, 'errors': ser.errors})
            else:
                # create new with provided UUID
                data['route_id'] = route_uuid
                data['user'] = user.id
                ser = SavedRouteSerializer(data=data)
                if ser.is_valid():
                    ser.save()
                    created += 1
                else:
                    errors.append({'route_id': route_uuid, 'errors': ser.errors})
        else:
            data['user'] = user.id
            ser = SavedRouteSerializer(data=data)
            if ser.is_valid():
                ser.save()
                created += 1
            else:
                errors.append({'route': data, 'errors': ser.errors})

    return Response({'status': 'ok', 'created': created, 'updated': updated, 'errors': errors})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_routes(request):
    """Return all saved routes for the authenticated user"""
    qs = SavedRoute.objects.filter(user=request.user).order_by('-created_at')
    serializer = SavedRouteSerializer(qs, many=True)
    return Response(serializer.data)