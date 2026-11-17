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

`aapt dump badging` confirms package `org.agrishield.agrishield`, version 1.0.0,
minSdk 24, targetSdk 36, and the camera/microphone/location/internet
permissions. `apksigner verify` confirms the v2 signature with the generated
release key.

## Not tested (important)

- **No Android device or emulator was available**, so no screen was rendered or
  tapped. Layouts, TTS voices, camera permission dialogs, STT and GPS were not
  exercised at runtime.
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
