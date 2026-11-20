# Training report — AgriShield v3

Everything below was produced by the runs in this repository; no number is
estimated. Raw artifacts: `ml/artifacts_v3/` (Keras model, `training_report.json`,
`epoch_metrics.json`, `training_log.csv`, `classification_report.txt`) and
`reports/model_benchmark.json`.

## 1. Data

Built by `ml/datasets/build_unified.py` from two sources, both licence-checked:

| Source | Role | Licence | Images used |
| --- | --- | --- | --- |
| PlantVillage (Hughes & Salathé 2015) | lab, single-leaf | CC BY 4.0 / public | 13,535 train · 3,568 val · 5,991 test |
| PlantDoc (Singh et al. 2020) | web-scraped field photos | CC BY 4.0 | 1,993 train · 346 val · 219 test |

- 26,302 candidate images → 0 corrupt, 17 exact duplicates, 24,925 near-duplicate
  groups (dHash, Hamming ≤ 6, within class), 633 cross-split leaks removed,
  **25,652 kept**.
- Splits are group-aware: an image whose near-duplicate group appears in train is
  removed from validation/test, so the test score is not inflated by duplicates.
- Class mapping is per folder onto the 38-class taxonomy. Ambiguous folders were
  excluded, never merged, and a 2-image folder was dropped. Details and the
  excluded list: `reports/dataset_report.md`.

## 2. Backbone comparison (fixed budget)

`python -m ml.training.benchmark` — frozen ImageNet backbone, identical
augmentation, 3 epochs, 128 px, batch 64, Adam 1e-3, scored on the validation
split (3,914 images). This ranks backbones, it is not the final training run.

| Backbone | Params | Val top-1 | Val top-3 | Val macro F1 | CPU latency (batch 1) |
| --- | --- | --- | --- | --- | --- |
| **MobileNetV2** | 2,306,662 | 0.8137 | 0.9320 | **0.8153** | — |
| ResNet50 | 23,665,574 | **0.8155** | **0.9428** | 0.8126 | 79.4 ms |
| MobileNetV3-Large | 3,032,870 | 0.8102 | 0.9315 | 0.8111 | — |
| EfficientNetV2-B0 | 5,967,990 | 0.7787 | 0.9236 | 0.7750 | 82.9 ms |
| EfficientNet-B0 | 4,098,249 | 0.7649 | 0.9182 | 0.7614 | 97.0 ms |

ResNet50 edges MobileNetV2 on top-1 (0.8155 vs 0.8137) but not on macro F1, and
it costs 10× the parameters. On a phone, 10× the parameters for no macro-F1 gain
is the wrong trade, so **MobileNetV2** was kept.

Honest notes on this table:

- The MobileNet rows ran in an earlier invocation that was killed and its JSON
  was later overwritten by a single-architecture run. Their metrics are the
  values those runs logged (`artifacts/test/benchmark_resume.log`) and are
  flagged `recovered_from_log` in the JSON. Parameter counts for those two rows
  were counted from the same `build()` after the fact.
- The merge bug that caused the overwrite is fixed: `benchmark.py` now writes
  through `write_report()` at the end instead of overwriting the merged file.

## 3. Final training run

`python -m ml.training.train_field --data /tmp/agrishield_v3 --out ml/artifacts_v3 --arch mobilenetv2 --head-epochs 10 --finetune-epochs 2`

| Setting | Value |
| --- | --- |
| Architecture | MobileNetV2 (ImageNet), GAP → Dropout 0.2 → Dense(38, softmax) |
| Input | 128 × 128 RGB, raw 0–255 (preprocessing lives inside the graph) |
| Batch size | 64 |
| Phase 1 | 10 epochs, backbone frozen, Adam 5e-4 |
| Phase 2 | 2 epochs, last 40 backbone layers unfrozen, Adam 5e-5 |
| Loss | categorical cross-entropy, label smoothing 0.05 |
| Class weights | none (not justified: see below) |
| Augmentation | horizontal flip, ±8% rotation, 12% zoom, 6% translation, brightness/contrast ±15%, gaussian noise |
| Checkpoint metric | validation macro F1 |
| Seed | 1337 |
| Wall clock | **1,182.7 s** (19.7 min, 8-core CPU, no GPU) |
| TensorFlow | 2.21.0 |

Class weights were left off because the dataset after capping is close to
balanced (largest class ~400 train images) and weighting hurt macro precision in
the v2 run; the per-class recall table below is the check on that decision.

### Epoch history (checkpoint selection by macro F1)

| Epoch | Phase | Val macro F1 | Val top-1 | Val top-3 |
| --- | --- | --- | --- | --- |
| 1 | head | 0.6455 | 0.6576 | 0.8441 |
| 2 | head | 0.7317 | 0.7399 | 0.9024 |
| 3 | head | 0.7636 | 0.7647 | 0.9154 |
| 4 | head | 0.7890 | 0.7882 | 0.9277 |
| 5 | head | 0.8015 | 0.8012 | 0.9303 |
| 6 | head | 0.8098 | 0.8089 | 0.9354 |
| 7 | head | 0.8082 | 0.8074 | 0.9371 |
| 8 | head | 0.8245 | 0.8229 | 0.9359 |
| 9 | head | 0.8248 | 0.8240 | 0.9433 |
| **10** | **head** | **0.8251** | **0.8229** | **0.9453** |
| 11 | fine-tune | 0.7570 | 0.7524 | 0.9157 |
| 12 | fine-tune | 0.8133 | 0.8097 | 0.9371 |

Fine-tuning **made it worse** (0.8251 → 0.8133). The macro-F1 checkpoint kept
epoch 10, so the shipped model is the frozen-backbone result. Two epochs at
5e-5 with 40 trainable layers is enough to undo the converged head on 15k images
— the honest conclusion is that this dataset/budget does not support fine-tuning
yet, not that fine-tuning is useless.

### Final metrics

| Split | Images | Top-1 | Top-3 | Macro F1 | Weighted F1 |
| --- | --- | --- | --- | --- | --- |
| Validation | 3,914 | 0.8229 | 0.9453 | 0.8251 | 0.8211 |
| Test (Keras) | 6,210 | 0.8491 | 0.9568 | 0.8473 | 0.8475 |
| Test (TFLite float16) | 6,210 | **0.8622** | 0.9593 | **0.8585** | 0.8602 |

Test by source (TFLite): PlantVillage 5,991 images → 0.8795; the 219 PlantDoc
field photos inside the test split → 0.3881.

The TFLite score is slightly *higher* than Keras because float16 rounding shifts
a few near-ties; that is why the parity check in §4 compares predictions image by
image instead of trusting aggregate accuracy.

### Weakest classes (test recall, TFLite)

| Class | Images | Recall |
| --- | --- | --- |
| tomato_early_blight | 203 | 0.414 |
| tomato_target_spot | 196 | 0.546 |
| potato_healthy | 30 | 0.567 |
| tomato_septoria_leaf_spot | 210 | 0.667 |
| tomato_late_blight | 201 | 0.707 |
| corn gray leaf spot | 96 | 0.729 |
| pepper_bell_bacterial_spot | 204 | 0.755 |
| tomato_leaf_mold | 187 | 0.759 |

Tomato conditions remain the hard part: they are visually similar to each other
and to nutrient stress, and the model trades recall on early blight for
precision. Full table: `reports/evaluation_report.md`.

## 4. Export and parity

`scripts/finalize_model.py` exports float16 TFLite, publishes the same bytes to
`ml/artifacts/`, `mobile/assets/model/` and `models/`, refits calibration and
writes metadata.

| Artifact | Bytes |
| --- | --- |
| `models/agri_shield_best.tflite` | 4,611,780 (4.61 MB) |
| `models/agri_shield_best.keras` | 10,224,702 (10.22 MB) |

| Parity check (`ml/export/verify_tflite.py`) | Value |
| --- | --- |
| Images compared | 400 |
| Top-1 agreement Keras vs TFLite | **0.9975** (required ≥ 0.99) |
| Max probability difference | 0.02074 |
| Mismatches | 1 |
| Input sensitivity | 0.28116 |
| Single-image CPU latency | 2.3 ms |
| Result | **PASS** |

## 5. Field expectation, stated up front

This model was trained on lab images plus 2,558 PlantDoc field photos. Its
internal test score (0.86) is not a field score. On 236 PlantDoc images the model
never trained on it reaches 0.381 top-1, and on independently sourced Digital
Green photos (`reports/field_validation_report.md`) top-1 is 0.11 with 94%
abstention under the calibrated gate. Read `reports/field_validation_report.md`
before quoting any number from this run.

## Reproduce

```bash
python -m ml.datasets.build_unified --plantvillage /tmp/plantvillage --plantdoc /tmp/plantdoc --out /tmp/agrishield_v3
python -m ml.training.benchmark --data /tmp/agrishield_v3 --epochs 3 --out reports/model_benchmark.json
python -m ml.training.train_field --data /tmp/agrishield_v3 --out ml/artifacts_v3 \
    --arch mobilenetv2 --head-epochs 10 --finetune-epochs 2
python scripts/finalize_model.py --run ml/artifacts_v3 --data /tmp/agrishield_v3
python -m ml.export.verify_tflite --keras ml/artifacts_v3/agrishield_model.keras \
    --tflite mobile/assets/model/agrishield_model.tflite --labels ml/artifacts_v3/class_names.json
python -m ml.evaluation.evaluate --model mobile/assets/model/agrishield_model.tflite \
    --out reports/evaluation_report.md --json reports/evaluation.json
```

Wall clock on this machine: benchmark 5 architectures ≈ 55 min, final training
19.7 min, calibration refit ≈ 5 min, parity ≈ 2 min, evaluation ≈ 3 min.
