# Security & Environment Setup

This Django backend uses environment variables for all sensitive configuration. **Never commit secrets to git.**

## Quick Setup

### 1. Copy the example environment file

```bash
cp .env.example API.env
```

### 2. Generate a secure Django secret key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it into `API.env` as `DJANGO_SECRET_KEY`.

### 3. Add your API credentials to API.env

```env
DJANGO_SECRET_KEY=your-generated-secret-key-here
DJANGO_DEBUG=True
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
FCM_SERVICE_ACCOUNT_PATH=/absolute/path/to/firebase-credentials.json
```

### 4. Download Firebase credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings → Service Accounts
4. Click "Generate New Private Key"
5. Save the JSON file **outside your git repository** or in the project root (it's gitignored)
6. Update `FCM_SERVICE_ACCOUNT_PATH` in `API.env` with the absolute path

### 5. Verify setup

```bash
python manage.py check
```

You should see:
- ✅ Google Maps API key loaded (masked preview)
- ✅ Firebase credentials loaded (filename only)
- ✅ Environment loaded successfully

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Yes | Django secret key for cryptographic signing | (50+ random chars) |
| `DJANGO_DEBUG` | No | Enable debug mode (default: True) | `True` or `False` |
| `GOOGLE_MAPS_API_KEY` | Yes | Google Maps/Directions API key | `AIza...` |
| `FCM_SERVICE_ACCOUNT_PATH` | Yes* | Path to Firebase Admin SDK JSON | `/path/to/creds.json` |
| `CELERY_BROKER_URL` | No | Celery broker for background tasks | `redis://localhost:6379/0` |

\* Required only if you want push notifications

## Security Checklist

- [ ] `.gitignore` includes `.env`, `API.env`, and `*.json`
- [ ] No hard-coded secrets in any `.py` files
- [ ] `API.env` exists locally but is **never committed**
- [ ] Firebase credentials JSON is **never committed**
- [ ] Production uses unique `DJANGO_SECRET_KEY` (not the example)
- [ ] Production sets `DJANGO_DEBUG=False`

## Troubleshooting

### "DJANGO_SECRET_KEY not found"
Generate a new key and add it to `API.env`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### "Firebase credentials file not found"
- Verify `FCM_SERVICE_ACCOUNT_PATH` points to the correct file
- Use absolute path (e.g., `C:\path\to\file.json` on Windows)
- Ensure the file was downloaded from Firebase Console

### "Google Maps API key not found"
- Verify `GOOGLE_MAPS_API_KEY` is set in `API.env`
- Check that `API.env` is in `traffic_backend/` directory (one level above `settings.py`)
- Restart the development server after changing `API.env`

## Production Deployment

1. Set environment variables on your hosting platform (Heroku, Railway, AWS, etc.)
2. Use secrets management (AWS Secrets Manager, Google Cloud Secret Manager, etc.)
3. Set `DJANGO_DEBUG=False`
4. Use a strong, unique `DJANGO_SECRET_KEY`
5. Restrict `ALLOWED_HOSTS` to your domain(s)
6. Enable HTTPS only
7. Keep Firebase credentials secure and restrict API permissions

## Files Protected by .gitignore

- `API.env` - Your local environment variables
- `.env` - Alternative env file location
- `*.json` - All JSON files (includes Firebase credentials)
- `db.sqlite3` - Local database (use managed DB in production)

**Never commit these files to version control!**
