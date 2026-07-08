# Traffic Congestion & Alerts Backend

## Quick Start

### 1. Environment Setup

**IMPORTANT:** Configure environment variables before running the server.

See [SECURITY.md](SECURITY.md) for detailed setup instructions.

Quick setup:
```bash
# Copy example env file
cp .env.example API.env

# Generate Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Edit API.env and add:
# - DJANGO_SECRET_KEY (generated above)
# - GOOGLE_MAPS_API_KEY (from Google Cloud Console)
# - FCM_SERVICE_ACCOUNT_PATH (path to Firebase credentials JSON)
```

### 2. Install Dependencies

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 3. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Start Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

### 5. Run Traffic Checker (Optional)

```bash
python manage.py check_routes
```

## Security

- Never commit `API.env`, `.env`, or `*.json` files
- All secrets are loaded from environment variables
- See [SECURITY.md](SECURITY.md) for complete security setup

## API Endpoints

- `POST /api/sync_routes/` — bulk upsert saved routes from Flutter
- `GET /api/alerts/?username=<username>` — poll for alerts
- `GET /api/alerts/user/<user_id>/` — get user's traffic alerts (authenticated)
- `GET /api/alerts/<alert_id>/detail/` — get alert detail with description
- `DELETE /api/alerts/<alert_id>/` — delete an alert

## Flutter Integration

- From Android emulator use `http://10.0.2.2:8000` to reach host's localhost
- Include `Authorization: Token <token>` header for authenticated endpoints
- To receive push notifications call `/api/save_token/` to register FCM device token

## Background Tasks (Optional)

Configure Celery with Redis for periodic traffic checks:
```bash
celery -A traffic_backend worker -l info
celery -A traffic_backend beat -l info
```

