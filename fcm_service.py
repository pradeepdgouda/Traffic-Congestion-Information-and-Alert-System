import os
import firebase_admin
from firebase_admin import credentials, messaging

# Load service account path from environment
SERVICE_ACCOUNT_PATH = os.getenv('FCM_SERVICE_ACCOUNT_PATH')

def _init_firebase():
    """Initialize Firebase Admin SDK if credentials are available."""
    if not SERVICE_ACCOUNT_PATH:
        raise ValueError(
            'FCM_SERVICE_ACCOUNT_PATH not set. Cannot initialize Firebase. '
            'Set this environment variable to enable push notifications.'
        )
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(
            f'Firebase credentials file not found: {SERVICE_ACCOUNT_PATH}'
        )
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)

# initialize on import
try:
    _init_firebase()
    print(f'✅ Firebase initialized successfully')
except Exception as e:
    # If initialization fails, we don't crash; send_traffic_alert will handle it.
    print(f'⚠️  Firebase initialization failed: {e}')
    print('   Push notifications will not work until FCM_SERVICE_ACCOUNT_PATH is configured.')

def send_traffic_alert(token, route_name, message):
    """
    Sends a FCM notification to `token` with a simple notification payload.
    token: FCM device token (string)
    route_name: short route name (string)
    message: message body (string)
    """
    try:
        _init_firebase()
        msg = messaging.Message(
            notification=messaging.Notification(
                title=f"Traffic Alert - {route_name}",
                body=message
            ),
            token=token
        )
        resp = messaging.send(msg)
        # Print acknowledgement when message successfully sent
        try:
            print(f"FCM: message sent to token={token}, response={resp}")
        except Exception:
            # ensure printing does not raise
            pass
        return resp
    except Exception as e:
        # Print failure for debugging, then return None
        try:
            print(f"FCM: failed to send to token={token}, error={e}")
        except Exception:
            pass
        return None
