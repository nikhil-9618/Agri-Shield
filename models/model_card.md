# Model card — AgriShield `agri_shield_best` (v3)

| Field | Value |
| --- | --- |
| Artifact | `models/agri_shield_best.tflite` (float16), `models/agri_shield_best.keras` |
| Task | 38-class single-label leaf-condition classification |
| Crops | apple, blueberry, cherry, corn (maize), grape, orange, peach, bell pepper, potato, raspberry, soybean, squash, strawberry, tomato |
| Architecture | MobileNetV2 (ImageNet) → GAP → Dropout 0.2 → Dense(38, softmax) |
| Input | 128 × 128 RGB, **raw 0–255 float32** (preprocessing is inside the graph) |
| Output | 38 softmax probabilities; the app applies temperature 0.745 before thresholds |
| Size | TFLite 4,611,780 B (4.61 MB); Keras 10,224,702 B |
| Trained | 2026-11-20T11:36Z, 1,182.7 s on 8-core CPU, TensorFlow 2.21.0 |
| Training data | PlantVillage (lab) + PlantDoc (field, CC BY 4.0), 25,652 images after deduplication |
| Licence of weights | same as this repository (see `LICENSE`) |

## Metrics (measured, not estimated)

| Split | Images | Top-1 | Top-3 | Macro F1 |
| --- | --- | --- | --- | --- |
| Validation | 3,914 | 0.8229 | 0.9453 | 0.8251 |
| Test, Keras | 6,210 | 0.8491 | 0.9568 | 0.8473 |
| Test, TFLite float16 | 6,210 | 0.8622 | 0.9593 | 0.8585 |
| PlantDoc external field test | 236 | 0.3810 | — | 0.3300 |
| Digital Green field photos (scorable) | 118 | 0.1100 | 0.2030 | — |

Calibration (fitted on validation): temperature 0.745, `min_confidence` 0.8823,
ECE 0.0950 → 0.0180 on test, 98.28% precision at 62.64% coverage.
On the 118 Digital Green photos the calibrated gate abstains 94.1% of the time
and is right on 3 of the 7 it answers.

Keras ↔ TFLite top-1 agreement: **0.9975** on 400 images (1 mismatch), required
≥ 0.99. Single-image CPU latency 2.3 ms (desktop x86); on-device Android latency
is not measured in this repository.

## Intended use

- First-pass hint on a single leaf photo of one of the 14 supported crops, in
  good light, on a phone.
- Always paired with an abstention gate and an "ask an agriculture officer"
  route. The app never presents a result as a diagnosis.

## Not intended for

- Lab diagnosis, insurance, spraying decisions or pesticide dosage.
- Crops outside the 14, or conditions outside the 38 classes (closed set: the
  model must pick something; only the confidence gate can refuse).
- Whole-plant, aerial or multi-leaf photos.
- Any claim about accuracy in Indian fields beyond the measured numbers above,
  which are low.

## Limitations

- **Domain gap is measured, not hypothetical.** 0.86 on the internal test vs
  0.11 on real farmer photos with mapped labels.
- Tomato conditions are the weakest group (early blight recall 0.41, target spot
  0.55 on test).
- Fine-tuning did not help at this budget: phase 2 dropped validation macro F1
  from 0.8251 to 0.8133, so the shipped weights are the frozen-backbone epoch 10.
- No learned rejection class; abstention is a calibrated softmax threshold.
- Severity is not predicted. Multi-condition leaves are forced to one class.
- Potato field performance (0.021 over 48 photos) is far below its internal
  score, so per-crop field claims are unsafe.

## Provenance

Built by `ml/datasets/build_unified.py` → `ml/training/train_field.py` →
`scripts/finalize_model.py` → `ml/export/verify_tflite.py`. Reports:
`reports/dataset_report.md`, `reports/model_benchmark.json`,
`reports/training_report.md`, `reports/evaluation_report.md`,
`reports/keras_tflite_parity_report.md`, `reports/field_validation_report.md`.
Full model history and the v1 inference bug: `docs/MODEL_CARD.md`,
`docs/MODEL_AUDIT.md`.
