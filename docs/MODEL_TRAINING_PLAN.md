# Model training plan

## Why retrain at all

The v1.3.0 model scored 88.4% once the double-preprocessing bug was removed
(`docs/MODEL_AUDIT.md`), but it still only knew 27 classes across 6 crops. This
plan widens coverage to all 38 PlantVillage classes / 14 crops and rebuilds the
pipeline so the same class of bug cannot ship again.

## Pipeline

```
dataset/download_plantvillage.py      -> /tmp/pv/*.parquet
ml/training/prepare_dataset.py        -> /tmp/agrishield_v2/{train,val,test}/<Class>/*.jpg
ml/training/retrain.py                -> ml/artifacts_v2/{agrishield_model.keras,class_names.json,training_report.json}
ml/export/export_tflite.py            -> mobile/assets/model/agrishield_model.tflite
ml/training/evaluate.py               -> confusion matrix, per-class metrics
ml/validation/field_validation.py     -> real-field behaviour report
```

Reproduce:

```bash
python dataset/download_plantvillage.py --out /tmp/pv
python -m ml.training.prepare_dataset \
    --parquet /tmp/pv/data/train-00000-of-00002.parquet /tmp/pv/data/train-00001-of-00002.parquet \
    --test-parquet /tmp/pv/data/test-00000-of-00001.parquet \
    --out /tmp/agrishield_v2 --max-per-class 400 --val-per-class 100 --test-per-class 200
python -m ml.training.retrain --data /tmp/agrishield_v2 --out ml/artifacts_v2 \
    --head-epochs 10 --finetune-epochs 0
python -m ml.export.export_tflite --model ml/artifacts_v2/agrishield_model.keras \
    --out mobile/assets/model/agrishield_model.tflite --quantize float16
```

Seeds: 1337 for splitting and shuffling. CPU-only, ~13 minutes for the frozen
phase on 8 cores.

## Architecture decision

MobileNetV2 128×128, ImageNet backbone **frozen**, head = GAP → Dropout(0.2) →
Dense(38, softmax). Input domain is raw 0–255; `preprocess_input` lives inside
the graph.

The previous design had a `Dense(256, relu)` bottleneck before the softmax
layer. It was replaced with a direct head: a ReLU bottleneck is one more place
for the head to die, and it gave no measurable benefit at this data scale.

### Why not EfficientNet / ConvNeXt

Not benchmarked in this session. Fine-tuning was tried and abandoned: two
epochs at 8e-5 dropped validation accuracy from 85.8% to 79.6% while training
accuracy rose to 91.3% — classic overfitting on 13.5k images. Unfreezing a
larger backbone on CPU without more data would make that worse, so the frozen
MobileNetV2 remains the honest choice for now. Benchmarking EfficientNetB0 and
MobileNetV3 is listed as future work, not claimed as done.

## Verification gates

`retrain.py` refuses to save when:

1. the model's output does not change between a noise image and a black image
   (a constant-output model);
2. held-out test accuracy is below 0.80.

It warns when the model is confident (>0.80) on blank or noise frames, because
a closed-set classifier has no "not a leaf" class; the app's leaf gate and the
low-confidence path handle that case.

`ml/tests/test_tflite_parity.py` requires ≥99% Keras/TFLite agreement and
asserts the class-index table matches the output tensor width.

## Status of each phase

| Phase | Status |
| --- | --- |
| Audit | done (`docs/PROJECT_AUDIT.md`, `docs/MODEL_AUDIT.md`) |
| Preprocessing fix | done, all five call sites |
| Dataset download + prep, 38 classes | done |
| Training | done (see `ml/artifacts_v2/training_report.json`) |
| Parity test | done |
| TFLite export + app integration | done |
| Field validation on DigiGreen | done (`docs/FIELD_VALIDATION.md`) |
| Calibration (temperature scaling) | **not done** |
| OOD detection | **not done** — leaf gate only |
| Multi-crop architecture benchmark | **not done** |
| pHash duplicate removal | **not done** |
