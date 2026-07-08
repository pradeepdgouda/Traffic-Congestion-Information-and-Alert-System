"""
Django settings for traffic_backend project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# BASE DIR
BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------
# ✅ Correct ENV File Path (one level above backend folder)
# -----------------------------------------
ENV_PATH = BASE_DIR.parent / "API.env"

# Resolve to absolute string (ensures consistent Windows path formatting)
ENV_PATH_RESOLVED = str(ENV_PATH.resolve())
print(f"🔍 Loading environment from: {ENV_PATH_RESOLVED}")

# Load .env correctly using resolved path
load_dotenv(dotenv_path=ENV_PATH_RESOLVED)


# -----------------------------------------
# Security & Debug
# -----------------------------------------
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        'DJANGO_SECRET_KEY not found in environment. '
        'Set it in your API.env file or environment variables.'
    )
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['10.0.2.2', '127.0.0.1', 'localhost']


# -----------------------------------------
# Installed Apps
# -----------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    'traffic',
]


# -----------------------------------------
# Middleware
# -----------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    'corsheaders.middleware.CorsMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True
# Explicitly allow common HTTP methods including DELETE for CORS preflight
from corsheaders.defaults import default_methods
CORS_ALLOW_METHODS = list(default_methods) + ["DELETE"]

ROOT_URLCONF = 'traffic_backend.urls'


# -----------------------------------------
# Templates
# -----------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'traffic_backend.wsgi.application'


# -----------------------------------------
# Database
# -----------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# -----------------------------------------
# Authentication
# -----------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# -----------------------------------------
# Internationalization
# -----------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# -----------------------------------------
# Static Files
# -----------------------------------------
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# -----------------------------------------
# Environment Variables (Loaded Correctly)
# -----------------------------------------
# Accept several possible variable names in case the env uses a different one.
GOOGLE_MAPS_API_KEY = (
    os.getenv("GOOGLE_MAPS_API_KEY")
    or os.getenv("GOOGLE_MAPS_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

# If key still missing, inspect the env file (masked) to help debugging.
if not GOOGLE_MAPS_API_KEY:
    try:
        if os.path.exists(ENV_PATH_RESOLVED):
            with open(ENV_PATH_RESOLVED, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            found = []
            for ln in lines:
                if '=' in ln:
                    k, v = ln.split('=', 1)
                    k = k.strip()
                    if k.upper().startswith('GOOGLE'):
                        val = v.strip().strip('"').strip("'")
                        if val:
                            masked = val[:6] + '*****' if len(val) > 6 else '*****'
                        else:
                            masked = '(empty)'
                        found.append((k, masked))
            if found:
                print('🔍 Found Google-related keys in env file:')
                for k, m in found:
                    print(f" - {k} = {m}")
            else:
                print('🔍 No Google-related keys found in env file.')
        else:
            print(f"🔍 Env file not found at: {ENV_PATH_RESOLVED}")
    except Exception as e:
        print('🔍 Error while inspecting env file:', repr(e))

print(f"🔑 Loaded Google Maps Key: {GOOGLE_MAPS_API_KEY}")

FCM_SERVICE_ACCOUNT_PATH = os.getenv('FCM_SERVICE_ACCOUNT_PATH')
if not FCM_SERVICE_ACCOUNT_PATH:
    # Try default location as last resort
    default_path = BASE_DIR / 'firebase-credentials.json'
    if default_path.exists():
        FCM_SERVICE_ACCOUNT_PATH = str(default_path)
        print(f'⚠️  Using default Firebase credentials: {default_path.name}')
    else:
        print('⚠️  FCM_SERVICE_ACCOUNT_PATH not set. Push notifications will not work.')
        print('   Set FCM_SERVICE_ACCOUNT_PATH in API.env to enable Firebase messaging.')
        FCM_SERVICE_ACCOUNT_PATH = None
else:
    # Verify the file exists
    from pathlib import Path as EnvPath
    fcm_path = EnvPath(FCM_SERVICE_ACCOUNT_PATH)
    if fcm_path.exists():
        print(f'✅ Firebase credentials loaded: {fcm_path.name}')
    else:
        print(f'⚠️  Firebase credentials file not found: {FCM_SERVICE_ACCOUNT_PATH}')

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', '')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}
