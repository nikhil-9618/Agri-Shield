# Field validation report — v3 model

Raw output: `docs/field_validation.json`. Script: `ml/validation/field_validation.py`.

## Data

**Digital Green Crop Disease Expert Annotations** (CC BY 4.0,
`DigiGreen/Crop_Disease_Images`): 989 photographs taken by smallholder farmers in
India, reviewed by agronomists. Independent of PlantVillage and PlantDoc; never
used for training, validation or threshold fitting.

| Bucket | Images |
| --- | --- |
| Total | 989 |
| Out-of-scope crop (model has no class for it) | 626 |
| Supported crop, condition not mappable to a class | 245 |
| Scored (crop **and** condition mapped) | 118 |

The reference labels are free-text agronomist diagnoses (often multi-condition),
mapped by crop + first matching condition keyword. This is a keyword-mapped
reference, not a per-image clinical ground truth, and 118 scored photos is a
small sample.

## Results — same model, two thresholds

| Metric | Raw threshold 0.55 | Calibrated 0.8823 |
| --- | --- | --- |
| Top-1 agreement (118) | 0.110 | 0.110 |
| Top-3 agreement (118) | 0.203 | 0.203 |
| Coverage (answered) | 0.381 | **0.059** |
| Accuracy on answered photos | 0.133 | **0.429** |
| Abstention | 0.619 | **0.941** |
| Confident-but-wrong rate | 0.331 | **0.034** |
| Confident answer on an absent crop (626) | 0.468 | **0.118** |

Temperature scaling cannot change predictions, so top-1 is identical by
construction — that it is identical is a correctness check, not a result. What
changes is how often the app speaks: it now answers 7 of 118 field photos, and
3 of those 7 are right, instead of answering 45 and being right on 6.

## Per crop (scored photos, raw threshold)

| Crop | Images | Top-1 |
| --- | --- | --- |
| corn | 16 | 0.188 |
| pepper | 8 | 0.125 |
| potato | 48 | 0.021 |
| squash | 9 | 0.222 |
| tomato | 35 | 0.171 |
| soybean | 1 | 0.000 |
| strawberry | 1 | 0.000 |

## Interpretation

- **PlantVillage accuracy does not transfer to field photos.** 0.86 on lab images,
  0.11 on mapped real field photos.
- The calibrated gate converts most wrong answers into abstentions, which is
  safer but is not a fix: the model still cannot diagnose these images, it just
  no longer claims to.
- Potato is the worst crop (0.021 over 48 photos) despite potato classes scoring
  0.90+ macro F1 internally. That gap is the domain shift, not a class imbalance.
- The 626 out-of-scope photos are the strongest safety signal: 11.8% still get a
  confident answer about a crop that is not in the model's class list.

## What this means for the app

1. A result is never presented as a diagnosis; the copy says "possible problem"
   and offers the agriculture officer route.
2. Because 94% of real field photos are refused, the field experience is
   dominated by "could not decide — retake / ask an expert". That is the honest
   behaviour of this model, and it is why the next step is field training data,
   not more threshold tuning.
3. Any claim about Indian field accuracy beyond these numbers would be invented.

## Limitations of this validation

- Keyword-mapped labels, 118 scored photos, no per-image expert re-check.
- DigiGreen was collected for an advisory chat service; annotation consistency
  is unknown.
- No state-level or seasonal stratification.
- Severity is not annotated, so severity accuracy cannot be measured.
