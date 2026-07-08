# QUICKSTART - Environment Setup

⚠️ **REQUIRED BEFORE FIRST RUN** ⚠️

## 1. Copy Environment Template
```bash
cp .env.example API.env
```

## 2. Generate Secret Key
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copy the output!

## 3. Edit API.env
Open `API.env` and replace placeholders:

```env
DJANGO_SECRET_KEY=<paste-generated-key-from-step-2>
DJANGO_DEBUG=True
GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
FCM_SERVICE_ACCOUNT_PATH=<absolute-path-to-firebase-json>
```

## 4. Get Firebase Credentials
1. Go to https://console.firebase.google.com/
2. Select your project → Settings → Service Accounts
3. Click "Generate New Private Key"
4. Save JSON file (don't commit it!)
5. Update path in `API.env`

## 5. Run Server
```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Expected Output
```
🔍 Loading environment from: ...\API.env
🔑 Loaded Google Maps Key: AIzaSy*****
✅ Firebase credentials loaded: your-file.json
✅ Firebase initialized successfully
```

## Troubleshooting

### "DJANGO_SECRET_KEY not found"
→ Make sure you added it to `API.env` (step 2-3)

### "Firebase credentials file not found"
→ Use absolute path in `FCM_SERVICE_ACCOUNT_PATH`
→ Example: `C:\path\to\firebase-creds.json`

### "Google Maps API key not found"
→ Add `GOOGLE_MAPS_API_KEY=your-key` to `API.env`

---

📖 Full documentation: See [SECURITY.md](SECURITY.md)
