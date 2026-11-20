# Project audit

Scope: the AgriShield repository as it stood at `v1.3.0` (branch `main`,
commit `1263359`). Findings are from reading the code and running it, not from
the README.

## Components

| Layer | Location | Notes |
| --- | --- | --- |
| Flutter app | `mobile/` | Riverpod state, go_router, 5 languages, offline queue, bundled TFLite model, ML Kit leaf gate |
| FastAPI service | `backend/app/` | auth, detection, advisory, weather, assistant, SQLite via SQLAlchemy |
| Training | `ml/training/` | MobileNetV2 transfer learning, PlantVillage, 38-class label table with 6 supported |
| Export | `ml/export/` | Keras → TFLite float16/int8 |
| Grad-CAM | `ml/gradcam/` | Keras-only; disabled on Render (`GRADCAM_ENABLED=false`) |
| Content | `advisory/` → `mobile/assets/advisory/` | 5-language disease advisories, synced by `scripts/sync_advisory_assets.sh` |

## Inference paths (three of them)

1. **On device** — `OnDeviceClassifier.classify()` runs the bundled `.tflite`.
2. **Server** — `backend/app/services/vision.py::predict()` runs the same file.
3. **Export/eval tooling** — `ml/training/evaluate.py` and Grad-CAM.

All three must agree. Before this audit they agreed on being wrong: every path
applied `preprocess_input` to a graph that already does it. See
`docs/MODEL_AUDIT.md`.

## Diagnosis flow in the app

`CameraScreen` → `image_picker` → `/analysis` → `AppController.diagnose()`:

1. `LeafGuard` (ML Kit image labelling, bundled, offline) rejects people and
   non-plant photos. Fails closed.
2. `OnDeviceClassifier` runs the TFLite model, falls back to the API when the
   model cannot load.
3. Result screen renders top-3, advisory, severity and voice.

`syncQueue()` re-runs the same gate for queued uploads, so a queued image cannot
bypass the leaf check.

## Defects found and their status

| # | Defect | Impact | Status |
| --- | --- | --- | --- |
| 1 | Double preprocessing on device | every photo → common rust, 3.7% accuracy | fixed |
| 2 | Double preprocessing in API | same | fixed |
| 3 | Double preprocessing in Grad-CAM | wrong explanations | fixed |
| 4 | Double preprocessing in int8 calibration | bad quantisation if used | fixed |
| 5 | No parity test between Keras and TFLite | bug shipped unnoticed | test added |
| 6 | Only 6 of 14 PlantVillage crops shipped | "unknown crop" for cherry, peach, strawberry, citrus | fixed (38 classes) |
| 7 | Advisory fallback shows raw class keys | unreadable output for a missing advisory | mitigated (all 38 classes now have one) |
| 8 | No calibration | confidence was not a correctness probability; 0.55 was invented | fixed (`docs/CALIBRATION.md`) |
| 9 | No OOD score | 21% of field photos of unsupported crops still get a confident answer | open (entropy/margin measured as redundant) |

## Things that were already correct

- Class index mapping is consistent: `class_names.json` indices match the model
  output order, and `on_device_classifier` rejects a length mismatch at load.
- Softmax is applied once, inside the graph; no double softmax anywhere.
- The RGB path is correct — no BGR/RGB swap in the app or the API (`PIL`
  `convert("RGB")`, Flutter `rawRgba` read as `r,g,b`).
- Image resizing to 128×128 with bilinear filtering matches training.
- The API validates images, strips EXIF, and enforces size limits.
- The offline queue and history survive process death.

## Test coverage at audit time

- `mobile/test` — 8 unit tests (leaf gate decision logic, core).
- `backend/tests/test_api.py` — 10 tests.
- No test compared Keras against TFLite; none asserted predictions vary by image.
  Both gaps are now covered.
