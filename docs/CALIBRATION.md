# Confidence calibration and abstention

## Why this exists

The v1.4.0 model reported a softmax score, and the app treated `0.55` as the
line between "diagnosed" and "unclear". That number was invented, not measured.
A softmax output from a frozen-backbone transfer model is an ordering score, not
the probability that the answer is right, and nothing in the pipeline checked
that `0.55` meant anything.

Two consequences were measured earlier (see `docs/FIELD_VALIDATION.md`): the
model was confidently wrong on 19.5% of real field photos, and it gave a
confident answer on a crop that was not even in the photo 55% of the time. A
threshold nobody validated cannot fix that; a threshold fitted on data can at
least stop the worst answers.

## Method

**Temperature scaling** (`ml/calibration/calibration.py`):

- The exported graph ends in softmax, so the logits are recovered as
  `log(p)` up to an additive constant, which cancels inside the softmax.
- `T` is fitted on the **validation split only** by minimising negative
  log-likelihood: `q = softmax(log(p) / T)`.
- Argmax is invariant, so temperature scaling cannot change a prediction.
  `ml/calibration/run_calibration.py` asserts that accuracy is bit-identical
  before and after; the test suite checks it again.

Fitted value on the shipped 38-class model:

| Quantity | Value |
| --- | --- |
| Temperature `T` | **0.745** |
| Validation accuracy (unchanged) | 0.8306 |
| Test accuracy (unchanged) | 0.8622 |
| ECE before → after (validation) | 0.0786 → **0.0128** |
| ECE before → after (test) | 0.0950 → **0.0180** |
| NLL before → after (test) | 0.5214 → **0.4672** |

`T < 1` means the raw model is *over*-confident, which is what the v3 model
(field-augmented training) turned out to be: its raw ECE was 0.095 on test, five
times the v2 value, and temperature scaling brings it to 0.018. The effect on the
farm-facing numbers is direct: at the raw confidences the uncalibrated gate
accepted 47% of test images for 99.3% precision, and the calibrated gate accepts
63% for 98.3% precision — the same safety target, more answered photos.

## Abstention thresholds

The app needs one question answered: *when it does not say "unclear", how often
is it right?* So the threshold is the **lowest confidence that held
accepted-set precision at the target on validation**, which maximises how many
farmers still get an answer.

- Target: **98% precision when naming a disease**, with coverage not below 60%.
- A 90% target was rejected deliberately: it accepted 97.8% of photos and
  almost never abstained, which is the behaviour this step is meant to replace.
- Search is over measured confidence values from low to high, so the shipped
  threshold is an operating point that was actually observed, not interpolated.

| Setting | Value | Validation | Test |
| --- | --- | --- | --- |
| `min_confidence` | **0.8823** | coverage 0.6045, precision 0.9789, recall 0.7124 | coverage 0.6264, precision 0.9828 |
| `healthy_confidence` | **0.8823** | 68.1% of healthy claims kept, precision 0.9863 | — |

The healthy rule is fitted separately because a false "healthy" verdict stops
treatment: it requires 95% precision among photos the model calls healthy. On
validation that was satisfied at 68.1% of healthy claims with 98.6% precision, so
the healthy threshold coincides with the abstention threshold rather than being
raised above it.

The abstention search targets 98% precision with at least 60% coverage. On the
v3 validation split the lowest threshold reaching the target is 0.8823, and the
result is reported as-is: 97.89%, i.e. `"target_met": false` by 0.11 percentage
points. The threshold is not nudged to make that flag green.

## What this does and does not fix on field photos

Re-running `ml/validation/field_validation.py` with the calibration file:

| Metric (118 scored field photos) | Threshold 0.55 (before) | Calibrated 0.8823 |
| --- | --- | --- |
| Abstained | 0.619 | **0.941** |
| Answered and wrong | 0.331 | **0.034** |
| Top-1 agreement | 0.110 | 0.110 |
| Confident answer on an absent crop (626 photos) | 0.468 | **0.118** |

Read this honestly:

- The gate removes most harmful answers: it refuses 94% of field photos and cuts
  confident answers about absent crops by three quarters.
- It does **not** make field photos diagnosable. It answers 7 of 118 field
  photos, and 3 of those 7 match the mapped label. Top-1 agreement is unchanged
  at 0.110, exactly as expected, because temperature scaling cannot change
  predictions.
- So the app is now mostly silent on field photos instead of confidently wrong.
  That is safer, not solved. The remaining fix is training on field imagery, not
  more threshold tuning.

## Out-of-distribution scoring: measured, not shipped

Before adding an OOD gate, three candidate signals were measured on 500
DigiGreen photos of crops the model has no class for, against the PlantVillage
validation split (500 vs 3,800):

| Signal | AUROC (in-distribution vs OOD) |
| --- | --- |
| max softmax probability | 0.818 |
| top-1 minus top-2 margin | 0.806 |
| negative entropy | 0.831 |

At a cutoff that keeps 95% of validation photos, the entropy gate rejected
79.4% of out-of-scope photos — **exactly the same 79.4% the plain confidence
threshold already rejects**, and it cost zero correct validation answers either
way. It is redundant, so it was not added. A second check that duplicates the
first would only make the pipeline look safer than it is.

A real OOD detector needs images the model should refuse (whole plants, other
crops, non-leaf scenes) in training or in a fitted one-class model. That data is
not in this repository, so that work stays open and documented rather than
faked with a heuristic.

## Where the numbers live

| File | Role |
| --- | --- |
| `ml/artifacts/calibration.json` | source of truth: temperature, thresholds, measured metrics |
| `mobile/assets/model/calibration.json` | identical copy bundled with the app |
| `backend/app/services/vision.py` | loads it, applies `T`, exposes thresholds |
| `mobile/lib/core/on_device_classifier.dart` | loads it, applies `T`, uses thresholds |
| `backend/app/api/detection.py` | abstains using the thresholds the service reports |

The API and the app both fall back to `0.55` / `0.60` if the file is missing, so
an old bundle still runs — it just loses the fitted thresholds.

## Reproduce

```bash
python -m ml.calibration.run_calibration --data /tmp/agrishield_v3 \
    --out ml/artifacts/calibration.json
cp ml/artifacts/calibration.json mobile/assets/model/calibration.json
python -m ml.validation.field_validation --data /tmp/digigreen \
    --calibration ml/artifacts/calibration.json --out docs/field_validation.json
python -m pytest ml/tests -q
```

A refit on a new model must regenerate the file; the tests fail if the mobile
copy, the model's class count and the API's temperature drift apart.
