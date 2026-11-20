# Model audit

Audit of the shipped classifier (`v1.3.0`, model built 2026-11-16), performed
before any retraining. Everything below was measured, not assumed.

## What is shipped

| Property | Value |
| --- | --- |
| Architecture | MobileNetV2 (ImageNet weights), frozen backbone, GAP → Dropout → Dense(27, softmax) |
| Input | `float32` NHWC `[1, 128, 128, 3]` |
| Output | `float32` `[1, 27]` (softmax applied inside the graph) |
| Quantisation | float16 weights (`Optimize.DEFAULT` + `float16`) |
| Size | 5,185,020 bytes |
| Classes | 27 (apple, corn, grape, pepper, potato, tomato) |
| Reported val accuracy | 0.8633, top-3 0.9781 (`ml/artifacts/training_report.json`) |

The exported graph already contains `mobilenet_v2.preprocess_input`, because the
Keras model applies it internally after augmentation:

```python
x = augment(inputs)
x = tf.keras.applications.mobilenet_v2.preprocess_input(x)   # inside the model
x = base(x)
```

So the model's real input domain is **raw 0–255 pixels**.

## Bug 1 (critical): double preprocessing

Both clients scaled pixels before feeding that graph:

- `mobile/lib/core/on_device_classifier.dart`: `input[p++] = r / 127.5 - 1.0`
- `backend/app/services/vision.py::_preprocess`: `arr = (arr / 127.5) - 1.0`
- `ml/gradcam/gradcam.py`: `preprocess_input(batch)` before the Keras model
- `ml/training/evaluate.py` TFLite loop: same
- `ml/export/export_tflite.py` int8 calibration: same

The model therefore received values in roughly [-1, 1] on a scale it expects as
0–255, i.e. almost-black input. Measured on 405 held-out PlantVillage test
images (15 per class):

| Input fed | Top-1 accuracy | Most common prediction |
| --- | --- | --- |
| raw 0–255 (correct) | **0.884** | varies per image |
| `x/127.5 - 1` (shipped behaviour) | **0.037** | `corn_maize_common_rust` for **all 405** images |

This is the whole explanation for "every photo says common rust". The model was
never broken; the app and API were.

Feature inspection rules out a dead network: `gap` activations differ between a
leaf, a face, black, white and noise (mean absolute distance 0.56–0.89), and the
head weights are non-degenerate.

## Bug 2: Grad-CAM used the wrong input domain

Same root cause. Grad-CAM images were computed from a [-1, 1] tensor, so any
heatmap produced against the shipped model highlighted the wrong evidence.
Fixed with the same raw-pixel change.

## Bug 3: no input-independence guard

Nothing in the pipeline could detect a constant-output model. `ml/training/retrain.py`
now refuses to save a model whose prediction does not change between a noise
image and a black image, and `ml/tests/test_tflite_parity.py` enforces it.

## What is *not* claimed

Fixing preprocessing does not "improve accuracy" — it restores the accuracy the
model always had (88.4% on this test split). Field performance on farmer photos
is lower than PlantVillage numbers and has not been measured; see
`docs/FIELD_VALIDATION.md`.

## Known limitations of this model generation

- Closed-set classifier: it has no "not a leaf" or "unknown disease" class. The
  app's on-device ML Kit leaf gate and the low-confidence path handle that, not
  the model.
- Trained only on PlantVillage (uniform lab-style backgrounds, single leaf per
  image). Field photos with soil, shadow, blur and multiple leaves are out of
  distribution.
- Confidence is raw softmax, not calibrated. It is not a probability of being
  correct.
- No abstention beyond a fixed 0.55 threshold; no OOD score.
