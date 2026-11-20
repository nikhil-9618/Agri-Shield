# Field validation

## What was measured

The model was run on the **Digital Green Crop Disease Expert Annotations**
dataset: 989 photographs taken by smallholder farmers in India on their own
plots, each reviewed by an agronomist (CC-BY-4.0, `DigiGreen/Crop_Disease_Images`
on Hugging Face). These images are independent of PlantVillage and were never
used for training.

Script: `ml/validation/field_validation.py`. Raw output:
`docs/field_validation.json`.

## How labels were compared

The dataset's annotations are free-text agronomist diagnoses (often
multi-condition, e.g. "Pod Borer; Boron Deficiency") across 74 crops. They do
not map 1:1 onto PlantVillage's 38 classes, so keyword mapping was used:

- crop name → one of our 14 crops (626 photos were out-of-scope crops and were
  not scored for accuracy),
- first matching condition keyword → one of our class keys,
- 245 photos had a crop we support but a condition we could not map and were
  left unscored.

118 photos produced a scored comparison. That is a small sample and it is a
keyword-mapped reference, not a per-image clinical ground truth.

## Results

| Metric | Value | n |
| --- | --- | --- |
| Top-1 agreement with mapped label | **0.008** | 118 |
| Top-3 agreement | 0.102 | 118 |
| Abstention (confidence < 0.55) | 0.466 | 118 |
| Confidently wrong (confidence ≥ 0.80) | 0.195 | 118 |
| Confident answer on an out-of-scope crop | 0.55 | 626 |

Per crop (scored photos): corn 16, potato 48, tomato 35, squash 9, pepper 8,
soybean 1, strawberry 1. Top-1 was 0 for every crop except squash (1/9).

## Interpretation

**PlantVillage accuracy does not transfer to field photographs.** The 87.3%
held-out test number describes lab-style single-leaf images with uniform
backgrounds. Real farmer photos contain soil, shadows, multiple leaves, whole
plants, blur and varieties the model has never seen, and the model mostly gets
them wrong.

Two things make this less bad than it looks, and neither makes it good enough:

1. Nearly half of the scored photos were abstentions rather than wrong answers,
   and the app shows "could not decide" for those.
2. Part of the disagreement is label-mapping error: a photo labelled "early
   blight" on a whole plant is not the same task as a cropped single leaf.

But 19.5% confidently wrong and 55% confident on crops that are not even in the
photo are not acceptable for a diagnosis claim. Two actions follow:

- The app must not describe a result as a diagnosis. It says "possible problem"
  and offers the agriculture officer.
- The next model generation must be trained on field photography with
  crop-aware and abstention-aware objectives before any accuracy claim is made
  about Indian fields.

## What this dataset cannot tell us

- It cannot give a state-level or national accuracy figure.
- It has no Telangana/Andhra-specific seasonal coverage guaranteed; states vary.
- It cannot measure severity accuracy — severity is not annotated at a level
  that supports it.
- Expert labels were produced for an advisory chat service, not for benchmark
  evaluation, so annotation consistency is unknown.

## Reproduce

```bash
python -c "from huggingface_hub import snapshot_download as s; s('DigiGreen/Crop_Disease_Images', repo_type='dataset', local_dir='/tmp/digigreen')"
python -m ml.validation.field_validation --data /tmp/digigreen \
    --model mobile/assets/model/agrishield_model.tflite \
    --labels mobile/assets/model/class_names.json \
    --out docs/field_validation.json
```
