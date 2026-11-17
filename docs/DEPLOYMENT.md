# Deployment

For a managed deployment, see [RENDER_DEPLOY.md](RENDER_DEPLOY.md): the repo
ships a Render Blueprint, a small Docker image and a TensorFlow-free runtime.

## 1. Backend

### Requirements

- Python 3.11+ (3.12 used here)
- 1 GB RAM minimum (TensorFlow loads for Grad-CAM; the TFLite model alone is
  small)
- Disk for uploaded leaf photos and the SQLite/PostgreSQL database

### Configuration

Copy `backend/.env.example` to `backend/.env` and set at least:

```ini
APP_ENV=production
SECRET_KEY=<48+ random bytes>          # python -c "import secrets;print(secrets.token_urlsafe(48))"
DATABASE_URL=postgresql+psycopg://agrishield:...@db:5432/agrishield
CORS_ORIGINS=https://your-app-origin   # not *
MODEL_PATH=ml/artifacts/agrishield_model.tflite
KERAS_MODEL_PATH=ml/artifacts/agrishield_model.keras
GRADCAM_ENABLED=true
MAX_UPLOAD_MB=8
MIN_CONFIDENCE=0.55
HEALTHY_CONFIDENCE=0.60
```

Relative model/advisory paths resolve from the repository root, so start the
process from the repo (or keep `backend/` as the working directory and use
absolute paths).

### Database

```bash
pip install -r backend/requirements.txt
pip install "psycopg[binary]"
createdb agrishield
psql -d agrishield -f database/schema.sql   # or: python database/init_db.py
```

`database/schema.sql` is the reviewable PostgreSQL schema. SQLite works with no
setup for a pilot (`DATABASE_URL=sqlite:///./agrishield.db`).

### Process

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

Put nginx/Caddy in front for TLS. Example nginx location:

```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    client_max_body_size 10m;
}
```

Health check: `GET /health` must return `"status":"ok"` and
`"model_loaded":true`. Start-up fails loudly in the logs if the TFLite model or
advisory set is missing.

Operational notes:

- Keep `backend/uploads/` on a persistent volume; it holds the per-user leaf
  photos referenced by history.
- Rate limit is per IP (`RATE_LIMIT_PER_MINUTE=60`). Behind a proxy, make sure
  the real client IP is forwarded, or all users share one bucket.
- Weather calls are cached 10 minutes per rounded coordinate; no API key is
  needed for Open-Meteo, but respect its usage policy at scale.
- Logs contain request paths and status codes, not image bytes or passwords.

## 2. Android APK

### Build

```bash
AGRI_API_BASE_URL=https://api.example.org ./scripts/build_apk.sh
```

The script uses JDK 17, Flutter stable and Android SDK 36 from
`~/toolchain` (override with `JAVA_HOME` / `ANDROID_SDK_ROOT`), runs
`flutter analyze`, builds the release APK, and copies it to
`artifacts/agrishield-1.0.0-release.apk`.

`AGRI_API_BASE_URL` is baked into the build as the default server address. It can
still be changed at runtime in **Profile → Server address** for testing, but a
production APK should ship with the real HTTPS URL.

### Signing

If `mobile/android/key.properties` is absent, the build script generates a
keystore (`mobile/android/app/agrishield-release.jks`) and a matching
`key.properties`. Both are git-ignored.

**Back these up.** Android only accepts updates signed with the same key; losing
it means publishing under a new application id. For a real release, generate the
keystore once, store it in a secret manager, and pass the four values through
`android/key.properties` in CI.

### HTTPS and cleartext

`AndroidManifest.xml` currently sets `android:usesCleartextTraffic="true"` so a
pilot APK can reach a LAN server over HTTP. Before public distribution:

1. Serve the API over HTTPS.
2. Set `android:usesCleartextTraffic="false"`.
3. Optionally add a `networkSecurityConfig` that pins the production domain.

### Phone prerequisites

- Android 7.0+ (minSdk 24), camera, ~60 MB free.
- Google TTS voice for the chosen language (Android usually prompts to install
  it). Without it, all text is still visible.
- Google speech recognition service for voice questions; prepared question
  buttons work without it.
- Location permission for weather; the app explains and offers a retry button if
  denied.

### Distribution

For a pilot, sideload the APK or use a managed Play Console internal-testing
track. Google Play requires a privacy policy; the app stores phone numbers,
village names and leaf photos, so state retention and deletion clearly. Deleting
the account/data is currently a server-side operation — add a self-service
delete endpoint before a public launch.

## 3. Advisory content updates

Farmer-facing text lives in `advisory/` (not in the app code). After editing:

```bash
python -m json.tool advisory/diseases/<file>.json >/dev/null   # syntax check
./scripts/sync_advisory_assets.sh                              # copies into mobile/assets
cd backend && ../.venv/bin/python -m pytest tests -q           # key/coverage checks
./scripts/build_apk.sh                                         # if the change must work offline
```

The backend picks up new text on restart; the app needs a rebuild only because
the offline copy is bundled. Model class keys must keep matching
`ml/artifacts/class_names.json` — the backend validator refuses to start
otherwise.
