# Model card — AgriShield leaf disease classifier

## Overview

| Field | Value |
| --- | --- |
| Version | `agrishield-mobilenetv2-v2` (app 1.4.0) |
| Task | 38-class single-label classification of leaf photos (27 classes in v1) |
| Crops | apple, blueberry, cherry, corn (maize), grape, orange, peach, bell pepper, potato, raspberry, soybean, squash, strawberry, tomato |
| Architecture | MobileNetV2 (ImageNet weights) + global average pooling + dropout + dense softmax head |
| Input | 128 × 128 RGB, resized from the source images (192 px stored) |
| Training | transfer learning: 5 epochs frozen backbone, then 3 epochs fine-tuning the last 24 layers |
| Optimiser | Adam, 1e-3 head / 1e-4 fine-tune |
| Regularisation | dropout 0.25, L2 1e-4 |
| Artifacts | `agrishield_model.keras` (Grad-CAM), `agrishield_model.tflite` (5.18 MB, float16), `class_names.json` |
| Training time | 391 s (CPU) |
| Framework | TensorFlow 2.21.0 / NumPy 2.5.5 |

The TFLite file is what the API serves and what the app bundles for on-device inference; the Keras file is kept only to compute
Grad-CAM heat maps for the winning class.

## Data

- **PlantVillage** (Hughes & Salathé, 2015), via the
  `BrandonFors/Plant-Diseases-PlantVillage-Dataset` Hugging Face mirror.
- Only the 6 supported crops / 27 classes are used; everything else is dropped.
- Deterministic seed 1337. Images come from the mirror's own train/test shards,
  so no test image was used for training or validation.

| Split | Images |
| --- | --- |
| Train | 9,688 |
| Validation | 2,700 (100 per class) |
| Test | 4,581 |

Per-class training images are capped at 400 (some rare classes have fewer, e.g.
Potato healthy 22, Apple cedar apple rust 120, Tomato mosaic virus 199).

## Metrics (held-out test set, 4,581 images)

| Metric | Value |
| --- | --- |
| Top-1 accuracy | **0.8478** |
| Top-3 accuracy | **0.9725** |
| Macro precision | 0.8615 |
| Macro recall | 0.8574 |
| Macro F1 | 0.8437 |
| Weighted F1 | 0.8478 |

Validation accuracy after the last epoch: **0.8633**; validation top-3:
**0.9781**.

### Weakest classes (recall)

| Class | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Tomato early blight | 0.939 | 0.465 | 0.622 |
| Tomato target spot | 0.760 | 0.555 | 0.642 |
| Tomato leaf mold | 0.924 | 0.642 | 0.758 |
| Tomato bacterial spot | 0.910 | 0.655 | 0.762 |

Early blight is mostly confused with other tomato leaf conditions; its high
precision / low recall means the model is conservative — it misses cases rather
than naming the wrong disease. This is why the app shows top-3 guesses and tells
the farmer to retake the photo when confidence is low.

Best classes include Grape healthy (F1 0.977), Pepper healthy (0.903) and Apple
cedar apple rust (0.853 at 100% recall).

Full per-class results: `ml/artifacts/evaluation/metrics_test.json` and
`confusion_matrix_test.png`.

## Intended use

- A first-pass, on-demand check of a single leaf, as a prompt to look closer or
  contact an agriculture officer.
- Any of the 27 classes, photographed against a plain-ish background in good
  light.
- Telugu, Hindi, English, Tamil or Kannada advisory output.

## Not intended for

- A laboratory or official diagnosis, insurance claims, or pesticide
  prescription.
- Whole-field, aerial or multi-leaf photos.
- Crops outside the six supported ones.
- Diseases not in the 27 classes (the model still picks the closest class; the
  confidence gate is the only guard).
- Other geographies where the same visual symptoms have different causes.

## Limitations and biases

- **Domain gap:** PlantVillage images are studio-like (single leaf, uniform
  background, controlled light). Field photos include soil, shadows, blur,
  insects and multiple leaves. Real-world accuracy will be lower than 84.8%.
- **Tomato over-representation:** 10 of 27 classes are tomato, so tomato
  confusions dominate errors.
- **No severity or yield estimate:** the model classifies, it does not measure
  how advanced the infection is.
- **No abstain class:** the "unclear" state is a confidence threshold, not a
  learned rejection.
- **Language:** class names/advisories are translated; the model itself has no
  language input.

## Ethical and safety notes

- Advisories are deliberately free of pesticide brand names and doses.
- Every result screen carries a disclaimer and an "ask the agriculture officer"
  button; the expert section says when a visit is needed.
- Photos are stored per account, EXIF/GPS stripped, and never shared.
- The model was not trained on farmers' images and no farmer data was used.

## Reproduce

```bash
python dataset/download_plantvillage.py --out /tmp/pv
python -m ml.training.prepare_dataset --parquet /tmp/pv/*.parquet \
    --out /tmp/agrishield_dataset --max-per-class 400 --val-per-class 100
python -m ml.training.train --data /tmp/agrishield_dataset --out ml/artifacts
python -m ml.training.evaluate --data /tmp/agrishield_dataset --model ml/artifacts/agrishield_model.keras
python -m ml.export.export_tflite --model ml/artifacts/agrishield_model.keras --out ml/artifacts/agrishield_model.tflite
```

## v2 (app 1.4.0) — what changed

**The v1 inference pipeline was wrong, not the v1 model.** The exported graph
contains `preprocess_input`, but the app, the API, Grad-CAM and evaluation all
scaled pixels to [-1, 1] first. On 405 held-out images the model scored 88.4%
with raw 0–255 input and 3.7% with the shipped normalisation — returning
`corn_maize_common_rust` for every single photo. All five call sites now feed
raw pixels. Details: `docs/MODEL_AUDIT.md`.

v2 also widens coverage from 6 crops / 27 classes to 14 crops / 38 classes and
replaces the `Dense(256, relu)` bottleneck with a direct softmax head.

### Held-out PlantVillage test (6,388 images, never used for training)

| Metric | v2 | v1 (reported) |
| --- | --- | --- |
| Top-1 accuracy | **0.873** | 0.863 (27 classes) |
| Top-3 accuracy | **0.972** | 0.978 |
| Mean confidence | 0.855 | — |
| Keras↔TFLite top-1 agreement | ≥ 99% (test) | not tested |

Model size: 4.61 MB float16, 128×128 input, `[1, 38]` output.

### Real-field performance — the important number

Measured on the Digital Green expert-annotated set (989 Indian farmer photos,
agronomist labels, CC-BY-4.0). Of 118 photos whose crop and condition map onto
our classes:

| Metric | Value |
| --- | --- |
| Top-1 agreement with mapped reference label | **0.008** |
| Top-3 agreement | 0.102 |
| Abstained (confidence < 0.55) | 0.466 |
| Confidently wrong (confidence ≥ 0.80, wrong) | 0.195 |
| Confident answer on out-of-scope crops | 0.55 |

PlantVillage accuracy does **not** transfer to field photos. The model was
trained on lab-style single-leaf images and has not learned field backgrounds,
whole-plant framing or Indian crop varieties. Treat it as a decision-support
hint that must abstain, never as a diagnosis. See `docs/FIELD_VALIDATION.md`
for method and caveats.

### Known limitations (v2)

- No calibration: softmax confidence is not a probability of correctness.
- No OOD score; the ML Kit leaf gate is the only "not a leaf" filter.
- Closed set: anything outside the 38 classes is forced into one of them.
- No pHash de-duplication across splits; PlantVillage test accuracy is
  probably optimistic.
- Multi-label leaves are forced to one class.

### Reproduce v2

```bash
python dataset/download_plantvillage.py --out /tmp/pv
python -m ml.training.prepare_dataset \
    --parquet /tmp/pv/data/*.parquet --test-parquet /tmp/pv/data/test-00000-of-00001.parquet \
    --out /tmp/agrishield_v2 --max-per-class 400 --val-per-class 100 --test-per-class 200
python -m ml.training.retrain --data /tmp/agrishield_v2 --out ml/artifacts_v2 \
    --head-epochs 10 --finetune-epochs 0
python -m ml.export.export_tflite --model ml/artifacts_v2/agrishield_model.keras \
    --out mobile/assets/model/agrishield_model.tflite --quantize float16
python -m pytest ml/tests -q
python -m ml.validation.field_validation
```

## Citation

Hughes, D. P., & Salathé, M. (2015). *An open access repository of images on
plant health to enable the development of mobile disease diagnostics.*
arXiv:1511.08060.
