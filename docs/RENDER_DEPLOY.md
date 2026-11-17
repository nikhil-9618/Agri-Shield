# Deploy AgriShield on Render

This repository is ready for Render:

- `Dockerfile` — small production image (Python 3.12 + LiteRT, no TensorFlow)
- `render.yaml` — Blueprint for the web service + Postgres
- `backend/requirements-render.txt` — runtime without TensorFlow
- `backend/requirements-gradcam.txt` — full runtime if you want heat maps
- `backend/app/services/vision.py` — runs the same TFLite model with
  `ai-edge-litert` when TensorFlow is absent
- `backend/app/config.py` — accepts Render's `postgres://` URL

I could not create the Render service from this environment (no Render account
token, no Git remote, and no Docker daemon access), so the two account-bound
steps below are yours.

The exact runtime used by the image (`backend/requirements-render.txt`, no
TensorFlow) was verified locally: 10/10 backend tests passed, `/health` reported
`model_loaded: true`, a real leaf photo produced the correct Telugu result, and
the process used about 116 MB of RAM. The Docker build itself was not run here
because this environment has no Docker daemon access.

## Option A — Blueprint (recommended)

1. Push this project to a GitHub or GitLab repository Render can access.
2. In Render: **New → Blueprint**, choose the repository, apply. `render.yaml`
   is detected automatically.
3. Render creates:
   - `agrishield-api` (Docker web service, free plan)
   - `agrishield-db` (free Postgres) with `DATABASE_URL` wired in
   - a generated `SECRET_KEY`
4. Wait for the first build (about 3–6 minutes; the image is ~200 MB).
5. Open `https://agrishield-api.onrender.com/health`. It must show:

```json
{ "status": "ok", "model_loaded": true, "gradcam_enabled": false, ... }
```

If the name is already taken Render picks a suffix; use the URL from the
dashboard.

## Option B — Manual service

Render → **New → Web Service** → connect the repo → Runtime **Docker**:

| Setting | Value |
| --- | --- |
| Dockerfile path | `./Dockerfile` |
| Docker build context | `.` |
| Health check path | `/health` |
| Plan | Free (pilot) or Starter |

Environment variables:

| Key | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `SECRET_KEY` | generate a 48-byte random string (Render can generate it) |
| `DATABASE_URL` | your Render Postgres **internal** connection string |
| `GRADCAM_ENABLED` | `false` |
| `UPLOAD_DIR` | `/tmp/agrishield-uploads` |
| `CORS_ORIGINS` | `*` (the mobile app sends no Origin header) |
| `MAX_UPLOAD_MB` | `8` |
| `RATE_LIMIT_PER_MINUTE` | `60` |

Add a Postgres instance separately (**New → Postgres**) if you use this option.

## Verify the deployment

```bash
BASE=https://agrishield-api.onrender.com

curl -s $BASE/health
curl -s $BASE/api/meta?lang=te | head -c 400

# register, then predict with a leaf photo
TOKEN=$(curl -s -X POST $BASE/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"phone":"9000000001","name":"Test Farmer","password":"testpass123","language":"te"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s -X POST "$BASE/api/detection/predict?lang=te" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/leaf.jpg" | head -c 600
```

The prediction must contain `level`, `top3`, `advisory` and a Telugu `message`.
If `/health` reports `model_loaded: false`, the TFLite/class-name paths in the
image are wrong — check the deploy logs.

## Point the app at Render

```bash
AGRI_API_BASE_URL=https://agrishield-api.onrender.com ./scripts/build_apk.sh
```

This bakes the HTTPS URL into `artifacts/agrishield-1.0.0-release.apk`. For a
quick test you can instead open **Profile → Server address** on the phone and
enter the Render URL, but ship the rebuilt APK to farmers.

HTTPS means you can also turn off cleartext traffic in
`mobile/android/app/src/main/AndroidManifest.xml`
(`android:usesCleartextTraffic="false"`).

## Free-plan limits that matter

| Limit | Effect | Fix |
| --- | --- | --- |
| Web service sleeps after 15 min idle | first request takes ~1 min; the app's 20 s timeout treats it as offline and queues the photo | upgrade to Starter, or warm `/health` before a demo |
| Free Postgres expires after 30 days | all accounts and diagnoses are lost when it expires | upgrade the database before expiry |
| Ephemeral filesystem | detection rows survive, but stored JPEGs (history image endpoint) disappear on redeploy | attach a Render disk (paid) and set `UPLOAD_DIR=/var/data/uploads` |
| 512 MB RAM | TensorFlow would not fit — that is why the image omits it | keep the slim image; use a 2 GB plan for Grad-CAM |
| Single instance | in-memory rate limit and uploaded files are per instance | one instance is fine for a pilot; add a shared store before scaling |

## Grad-CAM heat maps (optional)

The slim image disables Grad-CAM, so results have no heat map and the app hides
that button. To enable explanations:

1. In `Dockerfile`, install `backend/requirements-gradcam.txt` instead of
   `backend/requirements-render.txt`. This adds TensorFlow (~600 MB RSS) and
   OpenCV.
2. Use a plan with at least 2 GB RAM.
3. Set `GRADCAM_ENABLED=true`.
4. Redeploy and check `/health` shows `"gradcam_enabled": true`. Take a new
   photo; the result screen now offers the heat-map toggle.

## Updating

`autoDeployTrigger: commit` means pushing to the connected branch rebuilds and
redeploys. Database tables are created at startup if missing, so no migration
step is needed for the current schema. Changing `SECRET_KEY` signs everyone out
(tokens become invalid); the app silently logs in again with its stored phone
and password.

## Troubleshooting

- **Build fails on `ai-edge-litert`**: keep Python 3.12 (the Docker image is
  pinned) and check the pip output in Render logs.
- **`model_loaded: false`**: confirm `ml/artifacts/agrishield_model.tflite` and
  `class_names.json` were copied into the image; `MODEL_PATH` is relative to the
  repository root (`/app`).
- **`OperationalError` connecting to Postgres**: use the internal database URL
  (not the external one), and make sure the database and service are in the same
  region.
- **First photo fails after idle**: expected on free; retry, or warm the service.
  The app queues the photo instead of inventing a result.
