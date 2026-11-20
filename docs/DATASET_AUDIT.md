# Dataset audit

Only datasets that were actually accessed are described as used. Everything
else is listed with its status, so nothing here implies access we do not have.

## Used for training

### PlantVillage

| Field | Value |
| --- | --- |
| Publisher | Hughes, D. P. & Salathé, M. (2015), arXiv:1511.08060 |
| Mirror used | `BrandonFors/Plant-Diseases-PlantVillage-Dataset` (Hugging Face) |
| Download | `python dataset/download_plantvillage.py --out /tmp/pv` (3 parquet shards, 812.6 MiB) |
| Licence | Released for research use; **not** a commercial-use grant. Cite the paper and check PlantVillage terms before shipping commercially. |
| Images | 54,305 in total |
| Classes | 38 in the official label set |
| Crops | 14 (apple, blueberry, cherry, corn, grape, orange, peach, pepper, potato, raspberry, soybean, squash, strawberry, tomato) |
| Conditions | Lab-style: single leaf, uniform background, even light |
| Annotation | Gardener/expert-labelled during collection, not field-verified per image |

Splits used for this retrain (seed 1337, deterministic, taken from the mirror's
own train/test shards so no test image is trained on):

| Split | Images |
| --- | --- |
| train | 13,538 |
| val | 3,800 |
| test | 6,388 |

Per-class caps: 400 train / 100 val / 200 test.

## Used for independent field validation

### Digital Green — Crop Disease Expert Annotations

| Field | Value |
| --- | --- |
| Publisher | Digital Green (`DigiGreen/Crop_Disease_Images` on Hugging Face) |
| Licence | CC-BY-4.0 |
| Contents | 1,026 expert annotations over 989 photographs, 74 crop types |
| Origin | India — photos taken by smallholder farmers on their own plots and sent to Farmer.Chat |
| Annotation | Reviewed by agronomists on Digital Green's platform |
| Why it matters | Real field photos (soil, shadows, blur, whole plants), independent of PlantVillage |

The labels are free-text agronomist diagnoses and do not map one-to-one onto
PlantVillage's 38 classes, so this is used to measure **behaviour on real field
photos** (does the model produce a sane, useful answer, or confidently wrong
one), not as a drop-in accuracy figure. See `docs/FIELD_VALIDATION.md`.

## Researched, not used

| Dataset | Status | Reason |
| --- | --- | --- |
| PlantDoc (`pratikkayal/PlantDoc-Dataset`) | Public, CC-BY-4.0, 2,598 points, 13 species | Not downloaded in this session; candidate field dataset |
| Plant Pathology 2020 FGVC7 (Kaggle) | 823.79 MB, 3,645 files, apple only, 4 labels; data under Apache-2.0 subject to competition rules | Needs a Kaggle account and rule acceptance — not bypassed |
| DigiGreen (see above) | Downloaded, CC-BY-4.0 | Used for field validation |
| ICAR / IndiaAI rice and maize dataset | Not accessed | Requires registration on indiaai.gov.in; no credentials available, no bypass attempted |
| Indian Rice Disease Dataset (IEEE DataPort, doi:10.21227/4rmf-gd63) | Not accessed | DOI resolves through IEEE DataPort, which requires an account |
| ARTEN multi-crop dataset (Sci Data) | Not accessed | Not retrieved in this session; no licence verified |

No download link, size or licence in this table is invented; unverified entries
say so explicitly.

## Data risks recorded

- **Near-duplicate leakage**: PlantVillage has many frames of the same leaf per
  class. The mirror's train/test shards are respected, but perceptual-hash
  de-duplication across splits was **not** run, so reported test accuracy may be
  optimistic. A pHash/embedding de-duplication pass is the next dataset task.
- **Domain gap**: training images are lab-style; DigiGreen photos are not.
- **Label noise**: PlantVillage labels are per-image collection labels, not
  per-image expert re-review.
- **No multi-label support**: a leaf with two conditions is forced to one class.
