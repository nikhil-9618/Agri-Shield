# Architecture

```
┌──────────────────────────── Android phone ────────────────────────────┐
│ Flutter app (Riverpod + go_router)                                    │
│                                                                       │
│  screens/ ──► providers.dart (AppController) ──► ApiClient (HTTP)     │
│      │              │                                                 │
│      │              ├── LocalStore (SharedPreferences)                │
│      │              │     settings, token, saved diagnoses,           │
│      │              │     upload queue, weather cache                 │
│      │              └── SpeechService (flutter_tts / speech_to_text)  │
│      │                                                                │
│      └── assets/advisory/*.json  (27 advisories, 5 languages)         │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ HTTPS/HTTP (multipart + JSON)
┌───────────────────────────────▼───────────────────────────────────────┐
│ FastAPI                                                               │
│  api/auth, api/user      bcrypt + JWT                                 │
│  api/detection           upload → validate → TFLite predict →         │
│                          advisory lookup → Grad-CAM → SQL             │
│  api/weather             Open-Meteo + rule engine (10-min cache)      │
│  api/advisory            reads advisory/*.json                        │
│  api/assistant           retrieval over FAQ/advisories/weather        │
│                                                                       │
│  services/vision.py      TFLite interpreter (+ optional Keras)        │
│  services/advisory.py    language lookup, severity, messages          │
│  services/weather.py     WMO mapping, risk rules                      │
│  services/assistant.py   intent + retrieval + honest fallback         │
│                                                                       │
│  SQLAlchemy: users, detections (+ uploaded JPEGs on disk)             │
└───────────────────────────────────────────────────────────────────────┘
```

## Photo → result

1. `image_picker` captures a rear-camera photo (max 1600 px, quality 88).
2. The app copies it into its documents directory and shows the analysis screen.
3. `AppController.diagnose` makes sure the phone is registered (silently, with
   generated credentials) and POSTs the bytes to `/api/detection/predict`.
4. The server validates and resizes the image, strips EXIF/GPS, runs the
   float16 TFLite MobileNetV2 model (128×128), and optionally computes Grad-CAM
   with the Keras twin for the winning class.
5. It stores the detection with an advisory snapshot in the requested language,
   then returns the full result — including the three top predictions.
6. The app saves the response locally *with the photo path*, shows the
   green/yellow/red screen and automatically reads the result aloud.
7. If the bundled model cannot load on an old device, the photo goes to the API
   instead. If both are unavailable the photo is queued; the app never shows an
   invented result.

## Inference strategy

The same 5 MB float16 MobileNetV2 model is bundled in the APK and run by
`tflite_flutter` on the phone. Diagnosis therefore needs no connection, no
account and no server round trip. The on-device path uses the same 128×128
raw 0-255 preprocessing, the same temperature-scaled confidence and the same
thresholds from `calibration.json` as the API.

The FastAPI service remains the fallback for devices where the model cannot
load, and it serves Grad-CAM, weather, the voice assistant and cross-device
history. Keeping the thresholds and class metadata in one model artifact means
the two paths cannot drift apart.

Grad-CAM needs Keras and is server-only; on-device results show the photo and
top-3 predictions without a heat map.

## Offline strategy

| Data | Where | Behaviour offline |
| --- | --- | --- |
| Language, profile, token | SharedPreferences | read/write locally |
| Saved diagnoses | SharedPreferences (200 newest) | readable, with photo |
| Advisory text | bundled JSON assets | readable for any disease |
| Pending photos | app documents + queue | diagnosed locally by `syncQueue` |
| Weather | last snapshot in prefs | shown with fetch time |
| Voice answers | none | explicit "cannot reach server" message |

## Silent account

On first use the client generates a random 10-digit phone number and a random
20-character password, registers them, and stores both in SharedPreferences. If
the token expires, it logs in again with those credentials; if that fails it
registers a fresh account. The farmer never types, never sees an OTP, and each
phone's photos stay under its own account. The Profile screen exposes the server
address (for helpers) but not the password.

## Language handling

`advisory/` is the single source of truth. The backend localises advisories,
weather alerts, messages and assistant answers from it; the app bundles a copy
for offline reading (`scripts/sync_advisory_assets.sh` regenerates it). UI labels
live in `mobile/lib/core/strings.dart` for all five languages, with English
fallback. Speech uses `te-IN`, `hi-IN`, `en-IN`, `ta-IN`, `kn-IN` for TTS and the
underscore equivalents for recognition.

## Security and privacy

- Passwords are bcrypt-hashed; JWTs are signed with `SECRET_KEY` (must be
  changed in production), 30-day expiry by default.
- Every detection query filters by `user_id`; another account's id returns 404.
- Uploaded images are resized copies with EXIF/GPS removed.
- Rate limiting and security headers are middleware, so they apply to all routes.
- The development build allows cleartext HTTP so it can talk to a LAN server;
  production must use HTTPS and disable it (see `DEPLOYMENT.md`).
