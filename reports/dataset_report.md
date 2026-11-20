# Dataset report

Built by `ml/datasets/build_unified.py`. Sources are public and CC-BY-4.0 or
equivalent; attribution is preserved in the manifest.

## Sources

| Dataset | What it is | Licence | Used for |
| --- | --- | --- | --- |
| PlantVillage (spMohanty) | lab images, uniform background, 38 classes / 14 crops | public research dataset | training, validation, internal test |
| PlantDoc (pratikkayal) | 2,598 web-scraped field photos, 13 crops, 28 classes | CC-BY-4.0 | training + validation (mapped), held-out field test |
| Digital Green Crop Disease Images | 989 Indian farmer photos with agronomist notes | CC-BY-4.0 | external field validation only (never trained) |

## Cleaning

- candidates scanned: **26302**
- unreadable/corrupt dropped: **0**
- exact duplicates (md5) dropped: **17**
- images removed because their near-duplicate group also appeared in training: **633**
- near-duplicate groups (64-bit dHash, Hamming <= 6, within class): **24925**
- kept: **25652**

## Split composition

| Split | Source | Images |
| --- | --- | --- |
| test | plantdoc | 219 |
| test | plantvillage | 5991 |
| train | plantdoc | 1993 |
| train | plantvillage | 13535 |
| val | plantdoc | 346 |
| val | plantvillage | 3568 |

## Classes (train / val / test)

| Class | train | val | test |
| --- | --- | --- | --- |
| `apple_apple_scab` | 473 | 109 | 131 |
| `apple_black_rot` | 397 | 99 | 121 |
| `apple_cedar_apple_rust` | 183 | 115 | 64 |
| `apple_healthy` | 476 | 102 | 199 |
| `blueberry_healthy` | 489 | 107 | 188 |
| `cherry_including_sour_powdery_mildew` | 400 | 93 | 184 |
| `cherry_including_sour_healthy` | 437 | 98 | 155 |
| `corn_maize_cercospora_leaf_spot_gray_leaf_spot` | 368 | 106 | 96 |
| `corn_maize_common_rust` | 490 | 76 | 134 |
| `corn_maize_northern_leaf_blight` | 559 | 119 | 203 |
| `corn_maize_healthy` | 400 | 96 | 192 |
| `grape_black_rot` | 445 | 97 | 191 |
| `grape_esca_black_measles` | 400 | 95 | 181 |
| `grape_leaf_blight_isariopsis_leaf_spot` | 400 | 91 | 189 |
| `grape_healthy` | 291 | 90 | 90 |
| `orange_haunglongbing_citrus_greening` | 400 | 96 | 186 |
| `peach_bacterial_spot` | 400 | 98 | 193 |
| `peach_healthy` | 274 | 94 | 67 |
| `pepper_bell_bacterial_spot` | 456 | 105 | 204 |
| `pepper_bell_healthy` | 450 | 100 | 198 |
| `potato_early_blight` | 492 | 117 | 207 |
| `potato_late_blight` | 481 | 114 | 204 |
| `potato_healthy` | 22 | 100 | 30 |
| `raspberry_healthy` | 288 | 106 | 66 |
| `soybean_healthy` | 451 | 101 | 204 |
| `squash_powdery_mildew` | 497 | 127 | 205 |
| `strawberry_leaf_scorch` | 400 | 99 | 197 |
| `strawberry_healthy` | 342 | 107 | 97 |
| `tomato_bacterial_spot` | 485 | 97 | 174 |
| `tomato_early_blight` | 472 | 107 | 203 |
| `tomato_late_blight` | 485 | 115 | 201 |
| `tomato_leaf_mold` | 470 | 112 | 187 |
| `tomato_septoria_leaf_spot` | 508 | 131 | 210 |
| `tomato_spider_mites_two_spotted_spider_mite` | 400 | 91 | 184 |
| `tomato_target_spot` | 400 | 98 | 196 |
| `tomato_tomato_yellow_leaf_curl_virus` | 458 | 106 | 196 |
| `tomato_tomato_mosaic_virus` | 239 | 97 | 79 |
| `tomato_healthy` | 450 | 103 | 204 |

## Label limitations

- PlantDoc is mapped onto PlantVillage class names; ambiguous PlantDoc folders were excluded, never merged.
- Excluded PlantDoc classes: Tomato two spotted spider mites leaf (2 images upstream — too few to learn or score).
- PlantDoc has no per-plant grouping metadata, so grouping uses image near-duplicates only.
- PlantVillage images come from controlled lab sessions; their split cannot be group-aware by plant, which is why near-duplicate leak removal matters here.
- DigiGreen labels are free-text agronomist diagnoses, not a 1:1 class set; it is scored by keyword mapping in `ml/validation/field_validation.py`.
## Datasets researched but not used

These were checked rather than assumed; none were silently skipped.

| Dataset | Status | Reason |
| --- | --- | --- |
| ICAR crop disease and insect pest images for rice and maize (AIKOSH, IndiaAI) | **not downloaded** | The portal requires an account and dataset acceptance; there are no credentials in this environment and no bypass was attempted. Setup: create an IndiaAI/AIKOSH account, accept the dataset terms, download, then pass the folder with `--rice-maize PATH` once a mapping exists. |
| Indian Rice Disease Dataset (IEEE DataPort, DOI 10.21227/4rmf-gd63) | **not downloaded** | IEEE DataPort requires an IEEE account; the DOI resolves to a gated page. |
| Plant Pathology 2020 FGVC7 (Kaggle) | **not downloaded** | Needs a Kaggle account and acceptance of competition rules; `kaggle.json` credentials are absent. It is also a multi-label apple-only task, so it would need a different head. |
| ARTEN enhanced multi-crop dataset (Mendeley Data, DOI 10.17632/s2sxywhtx5.1) | **not used** | Public listing, but its five crops are banana, chilli, groundnut, cauliflower and radish — only chilli overlaps the 38-class taxonomy, and the images are ARTEN-enhanced rather than native camera output, which changes the pixel distribution the phone produces. Including it would train on a different image formation process. |
| Agri-Foundation-145k (Zenodo 18214758) | **not used** | Open, but it re-aggregates PlantVillage, PlantDoc and PlantWild among others. Pulling it would duplicate sources already here and risk the same photo entering train and test under different names — the exact leakage this pipeline is built to remove. PlantWild remains the best future addition for field images. |

## What would improve the field numbers

1. A labelled Indian field set with per-plant grouping (the ICAR/AIKOSH set above is the obvious candidate) so training and validation can be split by plant and session.
2. PlantWild (in-the-wild plant disease images) for backgrounds and camera variation.
3. Expert-verified severity labels if severity is ever displayed.
