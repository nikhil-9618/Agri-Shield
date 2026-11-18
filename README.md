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
| APK | [agrishield-1.3.0-universal.apk](https://github.com/nikhil-9618/Agri-Shield/releases/download/v1.3.0/agrishield-1.3.0-universal.apk) (59.5 MB, release-signed, arm64 + armv7 + x86_64) |
| APK SHA-256 | `ca77157d1ac17d76fb460c71e89de78cf62788faf02af7c8c00c586a7b56a93c` |

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
# -> artifacts/agrishield-1.3.0-universal.apk
```

### Installing on a phone

Download the [universal 1.3.0 APK](https://github.com/nikhil-9618/Agri-Shield/releases/download/v1.3.0/agrishield-1.3.0-universal.apk)
(59,452,656 bytes; SHA-256
`ca77157d1ac17d76fb460c71e89de78cf62788faf02af7c8c00c586a7b56a93c`).
It requires **Android 7.0 or newer** and is universal: it contains arm64,
32-bit ARM and x86_64 native libraries.

Every photo is checked on the phone before diagnosis. ML Kit's bundled
image-labeling model rejects people, faces and images with no clear leaf
material; only then does the 27-class disease model run. This check is free,
offline and needs no API key or account, and no photo leaves the device for it. If an older AgriShield is already on the
phone and was signed with a different key, Android shows "App not installed as
package appears to be invalid". Uninstall the old copy first, then install this
APK. The release key is kept out of Git (`key.properties`, `*.jks` ignored).

The shield-and-leaf SVG (`assets/images/agrishield_logo.svg`) is the single brand
source. It appears on the native launch screen, animated splash, language and
welcome screens, home header, drawer, profile and About screen; the launcher icon
uses the icon-only mark with the Deep Navy brand background.

## The screens

Splash · Language · Welcome · Home · Camera · Analysis · Result · Voice Assistant ·
Weather · Alerts · Previous Diagnoses · Help · About · Profile/Settings.

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
| Release APK build | **succeeded**, 43.7 MB universal, signed (v2+v3), targetSdk 34 |
| APK install + launch | **passed** on Android 7.0 (API 24) x86_64 emulator: `adb install` Success, no crash, screens rendered |
| Model evaluation on held-out test set | **84.78%** top-1, 97.25% top-3 |
| Render runtime (no TensorFlow, LiteRT) | **10 tests passed**, model loads, ~116 MB RSS |
| Docker image build / live Render deploy | **not performed** (no Docker daemon or Render account here) |
| Physical phone interaction | **not performed** (no physical device available) |

Details: [docs/TESTING.md](docs/TESTING.md).
