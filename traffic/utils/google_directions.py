import time
import requests
import os
from django.conf import settings

# Try to obtain the API key from Django settings or environment.
GOOGLE_MAPS_KEY = (
    getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
    or os.getenv('GOOGLE_MAPS_API_KEY')
    or os.getenv('GOOGLE_MAPS_KEY')
    or os.getenv('GOOGLE_API_KEY')
)

if not GOOGLE_MAPS_KEY:
    # Attempt to load dotenv if available and a known env path exists in settings
    try:
        from dotenv import load_dotenv
        env_path = None
        # settings may expose ENV_PATH_RESOLVED or BASE_DIR
        env_path = getattr(settings, 'ENV_PATH_RESOLVED', None)
        if not env_path and getattr(settings, 'BASE_DIR', None):
            # assume API.env is stored one level above backend
            env_path = str(getattr(settings, 'BASE_DIR').parent / 'API.env')
        if env_path and os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
            # check multiple possible names
            GOOGLE_MAPS_KEY = (
                os.getenv('GOOGLE_MAPS_API_KEY')
                or os.getenv('GOOGLE_MAPS_KEY')
                or os.getenv('GOOGLE_API_KEY')
            )
            # also print what the env file contains for google keys (masked)
            try:
                if os.path.exists(env_path):
                    with open(env_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    found = []
                    for ln in lines:
                        if '=' in ln:
                            k, v = ln.split('=', 1)
                            k = k.strip()
                            if k.upper().startswith('GOOGLE'):
                                val = v.strip().strip('"').strip("'")
                                masked = val[:6] + '*****' if val and len(val) > 6 else ('(empty)' if not val else '*****')
                                found.append((k, masked))
                    if found:
                        print('🔍 google_directions: Found Google-related keys in env file:')
                        for k, m in found:
                            print(f" - {k} = {m}")
            except Exception:
                pass
    except Exception:
        # ignore failures here; we'll raise below with a clear message
        pass

if GOOGLE_MAPS_KEY:
    try:
        preview = GOOGLE_MAPS_KEY[:6] + "*****"
    except Exception:
        preview = '*****'
    print("🔑 Loaded Google API key:", preview)
else:
    print("🔑 Google Maps API key not found in settings or environment")


def get_live_traffic(origin, destination, api_key=None, retries=2, backoff=1.0):
    """
    Query Google Directions API (or Routes) to get live traffic info.
    Returns dict: { distance_meters, duration_seconds, duration_in_traffic_seconds, polyline, summary, api_raw }
    """
    key = api_key or GOOGLE_MAPS_KEY or os.getenv('GOOGLE_MAPS_API_KEY')
    if not key:
        raise RuntimeError(
            'Google Maps API key not configured. Set GOOGLE_MAPS_API_KEY in your API.env or environment.'
        )

    url = 'https://maps.googleapis.com/maps/api/directions/json'
    params = {
        'origin': origin,
        'destination': destination,
        'key': key,
        'departure_time': 'now',
        'traffic_model': 'best_guess',
    }

    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            # parse first route/leg
            routes = data.get('routes') or []
            if not routes:
                return {'api_raw': data}

            route0 = routes[0]
            leg0 = route0.get('legs', [])[0]
            distance_meters = leg0.get('distance', {}).get('value')
            duration_seconds = leg0.get('duration', {}).get('value')
            duration_in_traffic = leg0.get('duration_in_traffic', {}).get('value') if leg0.get('duration_in_traffic') else duration_seconds
            polyline = route0.get('overview_polyline', {}).get('points')
            summary = route0.get('summary')
            return {
                'distance_meters': distance_meters,
                'duration_seconds': duration_seconds,
                'duration_in_traffic_seconds': duration_in_traffic,
                'polyline': polyline,
                'summary': summary,
                'api_raw': data,
            }
        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            return {'error': str(e)}
