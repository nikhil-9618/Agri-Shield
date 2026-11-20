# Testing

## Automated checks (run in this repository)

### Model — 3 tests passing

```bash
python -m pytest ml/tests -q
# 3 passed
```

`ml/tests/test_tflite_parity.py` enforces the properties whose absence let the
v1.3.0 bug ship:

1. the TFLite model's output changes when the input changes (a constant-output
   model fails);
2. Keras and TFLite agree on at least 99% of sampled test images;
3. the class-index table matches the model's output width.

`ml/training/retrain.py` refuses to save a model below 0.80 test accuracy or
one that ignores its input.

### Backend — 16 tests passing

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
# 12 passed, 2 warnings in ~2 s
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

- `pytest` → **16 passed** in 2.1 s (same tests, real TFLite model, calibrated confidence);
- uvicorn started with `APP_ENV=production`, `GRADCAM_ENABLED=false`;
- `/health` returned `model_loaded: true`;
- a real PlantVillage test image was predicted as `corn_maize_common_rust`
  (0.712) with the Telugu advisory and no heat map, as designed;
- resident memory after a prediction: **~116 MB**, so a 512 MB Render instance
  has ample headroom.

### APK

```bash
./scripts/build_apk.sh
# Built build/app/outputs/flutter-apk/app-release.apk (59.5MB)
```

`aapt dump badging` confirms package `org.agrishield.agrishield`, version 1.4.1
(code 7), minSdk 24, targetSdk 34, native ABIs `arm64-v8a`, `armeabi-v7a` and
`x86_64`, and the camera/microphone/location/internet permissions.
`apksigner verify` confirms v2 and v3 signatures with the release key; ZIP
integrity and 16 KB alignment also pass.

### Emulator install and launch

A clean Android 7.0 (API 24) x86_64 emulator was booted with the SDK emulator
(software acceleration). `adb install` of the universal 1.3.0 APK returned
`Success` (exit 0), and the app launched without a native crash. The native
launch screen, animated splash, language picker, welcome screen, home header,
app drawer and About screen were captured and visually checked. This test also
caught an earlier packaging bug: an arm-only build exposed x86_64 TFLite
libraries but no x86_64 `libflutter.so`, causing a `MissingLibraryException`.
The final build includes all three ABIs.

### Leaf gate (1.3.0)

Before any disease inference, `LeafGuard` runs ML Kit's bundled image-labeling
model on-device. It rejects a person at confidence >= 0.50 and requires a
plant/leaf label at confidence >= 0.30. The decision logic has four unit tests
(`mobile/test/leaf_guard_test.dart`); all 8 Flutter tests pass.

The real model was also run on the API 24 emulator against two photos:

- a human portrait returned `leaf=false rejection=person`, with `smile 0.76`,
  `beard 0.66` and `moustache 0.64`; it never reached the disease model;
- a tomato late-blight leaf returned `leaf=true`, with `plant 0.63` and
  `twig 0.36`, so it proceeded to diagnosis.

## Not tested (important)

- **No physical Android phone was available**, so installation on the farmer's
  actual handset and a real-device camera/voice run were not performed. The APK
  was installed and launched on an API 24 emulator (see above).
- Camera capture, TTS voices, speech-to-text and GPS permission flows were not
  exercised end-to-end; the emulator has no camera/voice hardware configured.
  The leaf gate itself was run on-device with a portrait and a leaf photo, but
  the full gallery-picker -> result tap-through on the old emulator was not
  completed. Those paths are covered by code inspection and unit tests, not a
  real-device run.
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
