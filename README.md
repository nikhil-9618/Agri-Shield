# AgriShield

A farmer-first Android app for crop disease checks, spoken advice and weather
warnings, built for rural India where typing, English and steady internet are
not guaranteed.

Telugu is the default; Hindi, English, Tamil and Kannada are fully translated.
Every important screen has a large speaker button, and the result is a single
colour — green, yellow or red — with a plain-language explanation.

| | |
| --- | --- |
| App | Flutter (Android), package `org.agrishield.agrishield` |
| API | FastAPI + SQLAlchemy, SQLite by default / PostgreSQL supported |
| Model | MobileNetV2 transfer learning on real PlantVillage images, 27 classes, 6 crops |
| Test accuracy | **84.8%** top-1, **97.3%** top-3 on 4,581 held-out images |
| APK | `artifacts/agrishield-1.1.1-arm-release.apk` (35.1 MB, release-signed, arm64 + 32-bit) |

## What a farmer does

1. Opens the app, taps their language (each card speaks its name).
2. Sees a three-picture explanation; taps the big green **Start**.
3. Taps **Check my crop**, points the camera at a leaf, and takes one photo.
4. Sees a big green/yellow/red result and presses the speaker to hear what to do.

No form filling, no OTP, no password. The trained model ships inside the app,
so a photo is diagnosed on the phone even with no internet. An account is
created silently only for the optional server features (weather, voice).

## Repository layout

```
advisory/            farmer-facing content in 5 languages (source of truth)
  diseases/*.json    27 per-disease advisories: signs, do now, avoid, prevent, expert
  crops|messages|weather_rules|assistant_faq.json
backend/             FastAPI service, TFLite inference, Grad-CAM, tests
ml/                  real training/evaluation/export pipeline + artifacts
  artifacts/         agrishield_model.tflite, .keras, class_names.json, metrics
dataset/             dataset docs + reproducible downloader
database/            PostgreSQL schema + init script
mobile/              Flutter app (12 screens), bundled advisory assets
docs/       API, architecture, accessibility, model card, testing, deployment
scripts/             toolchain setup, advisory asset sync, APK build
artifacts/           built release APK
```

## Quick start (from a clean checkout)

```bash
# 1. Backend (creates .venv, installs deps, starts on :8000)
./backend/run.sh

# 2. App against an Android emulator (10.0.2.2 = host machine)
cd mobile
flutter pub get
flutter run --dart-define=AGRI_API_BASE_URL=http://10.0.2.2:8000
```

On a physical phone use your computer's LAN IP, e.g.
`--dart-define=AGRI_API_BASE_URL=http://192.168.1.20:8000`. The URL is also
editable at runtime in **Profile → Server address** for field helpers.

Build the signed APK:

```bash
./scripts/build_apk.sh
# -> artifacts/agrishield-1.1.1-arm-release.apk
```

## The 12 screens

Language · Welcome · Home · Camera · Analysis · Result · Voice Assistant ·
Weather · Alerts · Previous Diagnoses · Help · Profile/Settings.

Offline behaviour is explicit rather than fake: a photo taken without internet
is stored and queued, saved results stay readable with bundled advisories, the
last weather snapshot is cached with its timestamp, and unknown voice questions
get an honest "I don't know, ask the agriculture officer" instead of a made-up
answer.

## API surface

`/health` plus:

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET|PUT /api/user/profile`
- `POST /api/detection/predict`, `GET /api/detection/history`,
  `GET /api/detection/{id}`, `GET /api/detection/{id}/image`
- `GET /api/weather/current|forecast|risk`
- `GET /api/advisory/crops`, `GET /api/advisory`, `GET /api/advisory/{disease}`
- `POST /api/assistant/ask`

Full request/response documentation: [docs/API.md](docs/API.md).

## Deploy

The API deploys to Render with the included `render.yaml` Blueprint and
`Dockerfile` (no TensorFlow needed at runtime; see
[docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md)). Build the APK
against the deployed URL with
`AGRI_API_BASE_URL=https://<service>.onrender.com ./scripts/build_apk.sh`.

## Honesty notes

- The model is trained on **PlantVillage**, a controlled-background research
  dataset. Field accuracy will be lower; the app therefore shows low-confidence
  results as "unclear" and never presents a prediction as a lab diagnosis.
- Advisories deliberately contain **no pesticide brand names or doses**. They
  describe cultural steps and say when to involve an agriculture officer.
- The voice assistant is **retrieval-based**, not a free-form chatbot: it matches
  the question to the bundled FAQ/disease advisory and weather data, cites its
  source, and admits when it does not know.
- Inference runs on the phone with the bundled 5 MB TFLite model, so diagnosis
  works offline. The FastAPI service is the fallback on devices where the model
  cannot load, and provides weather, voice and cross-device history.

## Verification status

| Check | Result |
| --- | --- |
| Backend tests (`pytest`, 10 tests) | **10 passed** |
| `flutter analyze` | **0 issues** |
| `flutter test` (translations, offline JSON) | **4 passed** |
| Release APK build | **succeeded**, 35.1 MB, signed (v2+v3), targetSdk 34, model and logo bundled |
| Model evaluation on held-out test set | **84.78%** top-1, 97.25% top-3 |
| Render runtime (no TensorFlow, LiteRT) | **10 tests passed**, model loads, ~116 MB RSS |
| Docker image build / live Render deploy | **not performed** (no Docker daemon or Render account here) |
| Real phone / emulator interaction | **not performed** (no device in build environment) |

Details: [docs/TESTING.md](docs/TESTING.md).
