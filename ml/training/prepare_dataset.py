"""Build the AgriShield training set from PlantVillage parquet mirrors.

The dataset is *not* committed to this repository (it is ~850 MB of images).
This script turns any of the public parquet mirrors into a deterministic
image-folder layout that `train.py` consumes:

    dataset/processed/
        train/<Class>/xxxx.jpg
        val/<Class>/xxxx.jpg
        test/<Class>/xxxx.jpg
        dataset_manifest.json

Examples
--------
    # 1) download the mirror used for the shipped model (see dataset/README.md)
    python dataset/download_plantvillage.py --out /tmp/pv

    # 2) extract the 27 classes of the six supported crops
    python -m ml.training.prepare_dataset \
        --parquet /tmp/pv/train_a.parquet /tmp/pv/train_b.parquet \
        --test-parquet /tmp/pv/test_full.parquet \
        --out /tmp/agrishield_dataset --max-per-class 400 --val-per-class 100
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.training.labels import (  # noqa: E402
    CLASS_NAMES,
    class_directory_name,
    classify,
    supported_class_indices,
)

DATASET_CARD = "BrandonFors/Plant-Diseases-PlantVillage-Dataset"


def _iter_rows(paths: list[Path], target: dict[int, str], limit_per_class: int, seed: int):
    """Yield (class_name, image_bytes) capped per class, in a shuffled order."""
    rng = random.Random(seed)
    per_class: dict[int, int] = defaultdict(int)
    wanted = [i for i in sorted(target) if target[i] is not None]
    skipped = 0
    for path in paths:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=256, columns=["image", "label"]):
            images = batch.column("image")
            labels = batch.column("label").to_pylist()
            paths_col = images.field("path").to_pylist()
            bytes_col = images.field("bytes")
            for idx, (name, blob) in enumerate(zip(paths_col, bytes_col)):
                label = labels[idx]
                if label not in wanted:
                    skipped += 1
                    continue
                if per_class[label] >= limit_per_class:
                    skipped += 1
                    continue
                per_class[label] += 1
                yield label, name, blob.as_py()
    if skipped:
        print(f"  skipped {skipped} rows outside the cap / crop filter")


def _resize(blob: bytes, size: int) -> bytes:
    img = Image.open(io.BytesIO(blob)).convert("RGB")
    img = img.resize((size, size), Image.BILINEAR)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def extract(
    out_root: Path,
    train_parquets: list[Path],
    test_parquet: Path,
    max_per_class: int,
    val_per_class: int,
    test_per_class: int,
    size: int,
    seed: int,
) -> dict:
    targets = {i: class_directory_name(CLASS_NAMES[i]) for i in supported_class_indices()}
    print(f"extracting {len(targets)} classes -> {out_root}")

    # ---- test split (held-out, never used for training) -------------------
    test_counts: Counter[str] = Counter()
    for label, _name, blob in _iter_rows([test_parquet], targets, test_per_class, seed + 7):
        cls = targets[label]
        dest = out_root / "test" / cls
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{test_counts[cls]:05d}.jpg").write_bytes(_resize(blob, size))
        test_counts[cls] += 1

    # ---- train/val split ------------------------------------------------
    # Keep val_per_class images aside from the same train parquet, so the
    # evaluation split stays untouched.
    train_counts: Counter[str] = Counter()
    val_counts: Counter[str] = Counter()
    for label, _name, blob in _iter_rows(
        train_parquets, targets, max_per_class + val_per_class, seed
    ):
        cls = targets[label]
        if val_counts[cls] < val_per_class:
            split, counter = "val", val_counts
        else:
            split, counter = "train", train_counts
        dest = out_root / split / cls
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{counter[cls]:05d}.jpg").write_bytes(_resize(blob, size))
        counter[cls] += 1

    manifest = {
        "dataset": "PlantVillage (Hughes & Salathé 2015)",
        "source_mirror": DATASET_CARD,
        "license_note": "PlantVillage is published for research use; cite the original paper.",
        "image_size": size,
        "seed": seed,
        "classes": [
            {
                **classify(CLASS_NAMES[i]),
                "directory": targets[i],
                "train": train_counts[targets[i]],
                "val": val_counts[targets[i]],
                "test": test_counts[targets[i]],
            }
            for i in sorted(targets)
        ],
        "totals": {
            "train": sum(train_counts.values()),
            "val": sum(val_counts.values()),
            "test": sum(test_counts.values()),
        },
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", nargs="+", required=True, help="train parquet file(s)")
    ap.add_argument("--test-parquet", required=True, help="held-out test parquet")
    ap.add_argument("--out", default="dataset/processed")
    ap.add_argument("--max-per-class", type=int, default=400)
    ap.add_argument("--val-per-class", type=int, default=100)
    ap.add_argument("--test-per-class", type=int, default=200)
    ap.add_argument("--size", type=int, default=192)
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    manifest = extract(
        Path(args.out),
        [Path(p) for p in args.parquet],
        Path(args.test_parquet),
        args.max_per_class,
        args.val_per_class,
        args.test_per_class,
        args.size,
        args.seed,
    )
    print(json.dumps(manifest["totals"], indent=2))
    for row in manifest["classes"]:
        print(f"  {row['label']:52s} train={row['train']:4d} val={row['val']:3d} test={row['test']:3d}")
    print(f"manifest: {Path(args.out) / 'dataset_manifest.json'}")


if __name__ == "__main__":
    main()
