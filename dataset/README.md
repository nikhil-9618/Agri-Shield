# Dataset

AgriShield is trained on **PlantVillage** — 54,305 leaf images of healthy and
diseased plants, captured under controlled conditions and released for research.

- Source: Hughes, D. P., & Salathé, M. (2015). *An open access repository of
  images on plant health to enable the development of mobile disease
  diagnostics.* arXiv:1511.08060.
- Mirror used for training: [`BrandonFors/Plant-Diseases-PlantVillage-Dataset`](https://huggingface.co/datasets/BrandonFors/Plant-Diseases-PlantVillage-Dataset)
- License: PlantVillage is released for research use. It is **not** a
  commercial-use grant; cite the paper and check the PlantVillage terms before
  shipping a product trained on it.

## What is used

Only six crops and 27 label classes are in scope. The rest of PlantVillage
(other crops, background images) is discarded.

| Crop | Classes |
| --- | --- |
| Apple | apple scab, black rot, cedar apple rust, healthy |
| Corn (maize) | Cercospora/gray leaf spot, common rust, northern leaf blight, healthy |
| Grape | black rot, Esca (black measles), leaf blight (Isariopsis), healthy |
| Pepper (bell) | bacterial spot, healthy |
| Potato | early blight, late blight, healthy |
| Tomato | bacterial spot, early blight, late blight, leaf mold, Septoria leaf spot, spider mites, target spot, yellow leaf curl virus, mosaic virus, healthy |

## Reproduce the dataset

The images are not committed (about 850 MB of parquet). From the repo root:

```bash
python dataset/download_plantvillage.py --out /tmp/pv
python -m ml.training.prepare_dataset \
    --parquet /tmp/pv/train_a.parquet /tmp/pv/train_b.parquet \
    --test-parquet /tmp/pv/test_full.parquet \
    --out /tmp/agrishield_dataset \
    --max-per-class 400 --val-per-class 100 --test-per-class 200
```

`prepare_dataset.py` writes `train/`, `val/`, `test/` folders plus
`dataset_manifest.json`, keeping class folders in the exact order the model
expects. Splits are deterministic (seed 1337) and are taken from the mirror's
own train/test shards so no test image is ever used for training.

Split sizes used for the shipped model: **9,688 train / 2,700 validation /
4,581 test** images, 27 classes, images resized to 192 px on extraction and to
128 px for training.

## Limitations

PlantVillage images are photographed on plain backgrounds in even light. Field
photos have soil, shadows, multiple leaves and blur, so accuracy in the field is
lower than the test numbers. The app never presents a prediction as a
laboratory diagnosis and always tells the farmer when confidence is low.
