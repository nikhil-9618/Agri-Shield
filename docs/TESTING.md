# Testing

## Automated checks (run in this repository)

### Backend — 10 tests passing

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
# 10 passed, 2 warnings in ~10 s
```

`backend/tests/test_api.py` covers:

1. health endpoint reports the model as loaded;
2. registration returns a token and user;
3. duplicate phone is rejected;
4. login works and a wrong password is rejected;
5. `/api/auth/me` requires and accepts the token;
6. prediction on a synthetic leaf image returns the full structure (level,
   status, top-3, advisory, disclaimer);
7. a second account cannot read the first account's detection (404, not 403
   leakage);
8. advisory is served in Telugu for a known disease;
9. assistant answers a known question and includes sources;
10. weather rule output is localised and shaped correctly (Open-Meteo mocked).

Tests set `DATABASE_URL` to a temporary SQLite file, load the real TFLite model
during app lifespan, and never touch the network.

### Flutter — analysis and unit tests

```bash
cd mobile
flutter analyze     # No issues found!
flutter test        # 4 tests passed
```

- `test/core_test.dart` checks that all five languages contain the core farmer
  strings, that missing translations fall back, that a `Diagnosis` survives an
  offline JSON round trip (including advisory and image path), and that language
  codes are canonicalised.
- `flutter analyze` runs with the project lints and reports zero issues.
- Android Lint is disabled in the Gradle build: the lint bundled with AGP 9
  crashes on JDK 17's javadoc parser while checking Flutter plugin modules
  (`NoSuchMethodError` in `JavaDocParser`). It does not affect the APK; Dart
  analysis covers the app code.

### Model

```bash
python -m ml.training.evaluate \
  --data /tmp/agrishield_dataset --split test \
  --model ml/artifacts/agrishield_model.keras \
  --tflite ml/artifacts/agrishield_model.tflite
```

Produced `ml/artifacts/evaluation/metrics_test.json`:

- accuracy 0.8478, top-3 0.9725, macro F1 0.8437 on 4,581 held-out images;
- confusion matrix CSV/PNG written alongside.

### Production stack without TensorFlow (Render image)

The Docker image installs `backend/requirements-render.txt`, where
`ai-edge-litert` replaces TensorFlow. Verified in a clean virtualenv:

- `pytest` → **10 passed** in 2.1 s (same tests, real TFLite model);
- uvicorn started with `APP_ENV=production`, `GRADCAM_ENABLED=false`;
- `/health` returned `model_loaded: true`;
- a real PlantVillage test image was predicted as `corn_maize_common_rust`
  (0.712) with the Telugu advisory and no heat map, as designed;
- resident memory after a prediction: **~116 MB**, so a 512 MB Render instance
  has ample headroom.

### APK

```bash
./scripts/build_apk.sh
# Built build/app/outputs/flutter-apk/app-release.apk (57.6MB)
```

`aapt dump badging` confirms package `org.agrishield.agrishield`, version 1.2.0
(code 6), minSdk 24, targetSdk 34, native ABIs `arm64-v8a`, `armeabi-v7a` and
`x86_64`, and the camera/microphone/location/internet permissions.
`apksigner verify` confirms v2 and v3 signatures with the release key; ZIP
integrity and 16 KB alignment also pass.

### Emulator install and launch

A clean Android 7.0 (API 24) x86_64 emulator was booted with the SDK emulator
(software acceleration). `adb install` of the universal 1.2.0 APK returned
`Success` (exit 0), and the app launched without a native crash. The native
launch screen, animated splash, language picker, welcome screen, home header,
app drawer and About screen were captured and visually checked. This test also
caught an earlier packaging bug: an arm-only build exposed x86_64 TFLite
libraries but no x86_64 `libflutter.so`, causing a `MissingLibraryException`.
The final build includes all three ABIs.

## Not tested (important)

- **No physical Android phone was available**, so installation on the farmer's
  actual handset and a real-device camera/voice run were not performed. The APK
  was installed and launched on an API 24 emulator (see above).
- Camera capture, gallery picker, TTS voices, speech-to-text and GPS permission
  flows were not exercised end-to-end; the emulator has no camera/voice hardware
  configured. Those paths are covered by code inspection and the backend tests,
  not a real-device run.
- No instrumented (`integration_test`) or widget smoke test of the navigation
  flow.
- No live Open-Meteo call in tests (deliberately mocked); the production request
  shape follows the documented API but weather numbers were not compared against
  the website.
- No real farmer usability or accessibility audit (see `ACCESSIBILITY.md`).
- The Docker image was not built here (no Docker daemon access in this
  environment), and no live Render deployment was performed — there are no
  Render credentials and no Git remote. The exact runtime dependency set and
  start command were tested directly instead; see `RENDER_DEPLOY.md`.

## Manual smoke test on a phone

1. Install the APK, open it, choose తెలుగు — the sample should be spoken.
2. Continue through the welcome guide; check that every speaker button speaks.
3. On Home, tap **నా పంటను పరీక్షించు**, allow camera, photograph a leaf.
4. Confirm the result banner colour, confidence, top-3 and that the advisory is
   read aloud; tap the heat-map button if shown.
5. Turn on airplane mode, take another photo: it should be queued, not guessed.
6. Re-enable data, return Home: the queue banner offers **ఇప్పుడు పంపండి**.
7. Open Weather, allow location: current conditions, warnings and 7 days appear;
   kill the network and reopen to see the cached snapshot with its time.
8. Voice: allow microphone, ask a suggestion, hear the answer; deny microphone
   and confirm prepared questions still work.
9. History: open a saved result with no network — advisory should still render.
10. Help: tap the call button and confirm the dialer opens with 1800-180-1551.
11. Profile: change language and village, save, reopen the app to confirm they
    persist.

Record device model, Android version and any TTS/STT language-pack prompts.
