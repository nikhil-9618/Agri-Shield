"""Build one unified, de-duplicated dataset for AgriShield.

Sources (all CC-BY-4.0 or public):
  * PlantVillage lab images, already extracted under ``--lab`` as
    ``{train,val,test}/<filesystem class name>/``.
  * PlantDoc field images from the upstream classification repository
    (``--plantdoc``), 2,598 web-scraped photos of 13 crops.

What this script guarantees, and records in ``manifest.jsonl``:

  * corrupted/unreadable files are dropped, never silently
  * exact duplicates (md5) are collapsed to one copy
  * near-duplicates (64-bit dHash, Hamming <= 6, compared within a class) are
    grouped, so they cannot straddle splits
  * if any image in a group is in PlantVillage's training split, the rest of
    that group is removed from val/test (leak removal)
  * PlantDoc's held-out ``test`` folder is never used for training; it becomes
    the external field test set
  * PlantDoc train images are split by group (85/15) so near-duplicates of a
    validation photo cannot sit in training

PlantDoc labels are mapped class-by-class onto the PlantVillage taxonomy below.
Anything not in the mapping stays out; no two diseases are merged.

    python -m ml.datasets.build_unified --lab /tmp/agrishield_v2 \
        --plantdoc /tmp/plantdoc --out /tmp/agrishield_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[2]))

# PlantDoc folder name -> AgriShield class key. None = deliberately excluded.
PLANTDOC_MAP: dict[str, str | None] = {
    "Apple Scab Leaf": "apple_apple_scab",
    "Apple leaf": "apple_healthy",
    "Apple rust leaf": "apple_cedar_apple_rust",
    "Bell_pepper leaf": "pepper_bell_healthy",
    "Bell_pepper leaf spot": "pepper_bell_bacterial_spot",
    "Blueberry leaf": "blueberry_healthy",
    "Cherry leaf": "cherry_including_sour_healthy",
    "Corn Gray leaf spot": "corn_maize_cercospora_leaf_spot_gray_leaf_spot",
    "Corn leaf blight": "corn_maize_northern_leaf_blight",
    "Corn rust leaf": "corn_maize_common_rust",
    "Peach leaf": "peach_healthy",
    "Potato leaf early blight": "potato_early_blight",
    "Potato leaf late blight": "potato_late_blight",
    "Raspberry leaf": "raspberry_healthy",
    "Soyabean leaf": "soybean_healthy",
    "Squash Powdery mildew leaf": "squash_powdery_mildew",
    "Strawberry leaf": "strawberry_healthy",
    "Tomato Early blight leaf": "tomato_early_blight",
    "Tomato Septoria leaf spot": "tomato_septoria_leaf_spot",
    "Tomato leaf": "tomato_healthy",
    "Tomato leaf bacterial spot": "tomato_bacterial_spot",
    "Tomato leaf late blight": "tomato_late_blight",
    "Tomato leaf mosaic virus": "tomato_tomato_mosaic_virus",
    "Tomato leaf yellow virus": "tomato_tomato_yellow_leaf_curl_virus",
    "Tomato mold leaf": "tomato_leaf_mold",
    # Only 2 images upstream: too few to train or score a class on.
    "Tomato two spotted spider mites leaf": None,
    "grape leaf": "grape_healthy",
    "grape leaf black rot": "grape_black_rot",
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def dhash(path: Path, size: int = 8) -> int:
    """64-bit difference hash: robust to rescaling and mild compression."""
    with Image.open(path) as im:
        small = im.convert("L").resize((size + 1, size), Image.BILINEAR)
    pixels = np.asarray(small, dtype=np.int16)
    diff = pixels[:, 1:] > pixels[:, :-1]
    bits = 0
    for bit in diff.flatten():
        bits = (bits << 1) | int(bit)
    return bits


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def popcount64(values: np.ndarray) -> np.ndarray:
    return np.bitwise_count(values.astype(np.uint64))


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def scan_lab(root: Path, class_of_dir: dict[str, str]) -> list[dict]:
    rows = []
    for split in ("train", "val", "test"):
        split_dir = root / split
        if not split_dir.is_dir():
            continue
        for folder in sorted(split_dir.iterdir()):
            key = class_of_dir.get(folder.name)
            if key is None or not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    rows.append(
                        {"path": path, "source": "plantvillage", "split": split, "label": key}
                    )
    return rows


def scan_plantdoc(root: Path) -> list[dict]:
    rows = []
    for split in ("train", "test"):
        split_dir = root / split
        if not split_dir.is_dir():
            continue
        for folder in sorted(split_dir.iterdir()):
            if not folder.is_dir():
                continue
            key = PLANTDOC_MAP.get(folder.name)
            if key is None:
                continue
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    rows.append(
                        {"path": path, "source": "plantdoc", "split": split, "label": key}
                    )
    return rows


def build(lab: Path, plantdoc: Path, out: Path, min_group_val: float = 0.15) -> dict:
    from ml.training.labels import class_directory_name

    labels = json.loads(Path("ml/artifacts/class_names.json").read_text())
    keys = [c["key"] for c in sorted(labels, key=lambda c: c["index"])]
    class_of_dir = {class_directory_name(c["label"]): c["key"] for c in labels}

    rows = scan_lab(lab, class_of_dir) + scan_plantdoc(plantdoc)
    print(f"scanned {len(rows)} candidate images", flush=True)

    # ---- corruption + md5 dedupe -------------------------------------
    md5_seen: dict[str, dict] = {}
    clean: list[dict] = []
    corrupt = 0
    exact_dupes = 0
    for row in rows:
        try:
            with Image.open(row["path"]) as im:
                im.verify()
            with Image.open(row["path"]) as im:
                width, height = im.size
            digest = file_md5(row["path"])
        except Exception:
            corrupt += 1
            continue
        if digest in md5_seen:
            exact_dupes += 1
            continue
        md5_seen[digest] = row
        row["md5"], row["width"], row["height"] = digest, width, height
        clean.append(row)
    print(f"dropped {corrupt} corrupt, {exact_dupes} exact duplicates", flush=True)

    # ---- near-duplicate groups, compared inside each class ------------
    by_class: dict[str, list[dict]] = defaultdict(list)
    for row in clean:
        row["phash"] = dhash(row["path"])
        by_class[row["label"]].append(row)

    group_id = 0
    for key, items in sorted(by_class.items()):
        hashes = np.array([r["phash"] for r in items], dtype=np.uint64)
        uf = UnionFind(len(items))
        for i in range(len(items)):
            distances = popcount64(hashes[i] ^ hashes)
            for j in np.where(distances <= 6)[0]:
                if j > i:
                    uf.union(i, int(j))
        roots = {}
        for i, row in enumerate(items):
            root = uf.find(i)
            if root not in roots:
                roots[root] = f"g{group_id:06d}"
                group_id += 1
            row["group"] = roots[root]
    print(f"{group_id} near-duplicate groups across {len(by_class)} classes", flush=True)

    # ---- leak removal: a group may not straddle splits -----------------
    splits_of: dict[str, set[str]] = defaultdict(set)
    for row in clean:
        splits_of[row["group"]].add(f"{row['source']}:{row['split']}")
    train_sources = {row["source"] for row in clean if row["split"] == "train"}
    leaks = 0
    kept: list[dict] = []
    for row in clean:
        # PlantDoc test is external: it must never share a group with training.
        conflicts = any(
            s.split(":")[1] == "train" and s.split(":")[0] in train_sources
            for s in splits_of[row["group"]]
        )
        if row["split"] != "train" and conflicts:
            leaks += 1
            continue
        kept.append(row)
    print(f"removed {leaks} val/test images grouped with training images", flush=True)

    # ---- PlantDoc train -> group-aware train/val ----------------------
    final: list[dict] = []
    pd_train = [r for r in kept if r["source"] == "plantdoc" and r["split"] == "train"]
    pd_groups = sorted({r["group"] for r in pd_train})
    val_groups = {
        g for g in pd_groups if int(hashlib.md5(g.encode()).hexdigest()[:8], 16) % 100 < min_group_val * 100
    }
    for row in kept:
        if row["source"] == "plantdoc" and row["split"] == "train":
            row = dict(row)
            row["split"] = "val" if row["group"] in val_groups else "train"
        final.append(row)

    # ---- materialise ---------------------------------------------------
    if out.exists():
        shutil.rmtree(out)
    counts: Counter = Counter()
    for row in final:
        dest_dir = out / row["split"] / row["label"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{row['source']}_{row['md5'][:12]}{row['path'].suffix.lower()}"
        if not dest.exists():
            os.symlink(row["path"].resolve(), dest)
        row["dest"] = str(dest.relative_to(out))
        counts[(row["split"], row["source"])] += 1

    with (out / "manifest.jsonl").open("w") as fh:
        for row in final:
            fh.write(
                json.dumps(
                    {
                        "path": row["dest"],
                        "original_path": str(row["path"]),
                        "source": row["source"],
                        "split": row["split"],
                        "label": row["label"],
                        "group": row["group"],
                        "md5": row["md5"],
                        "phash": f"{row['phash']:016x}",
                        "width": row["width"],
                        "height": row["height"],
                    }
                )
                + "\n"
            )

    per_class = Counter((r["label"]) for r in final)
    stats = {
        "candidates": len(rows),
        "dropped_corrupt": corrupt,
        "dropped_exact_duplicates": exact_dupes,
        "removed_cross_split_leaks": leaks,
        "kept": len(final),
        "near_duplicate_groups": group_id,
        "counts": {f"{s}/{src}": n for (s, src), n in sorted(counts.items())},
        "classes": {
            k: dict(
                sorted(
                    Counter(r["split"] for r in final if r["label"] == k).items()
                )
            )
            for k in keys
        },
        "unmapped_plantdoc_classes": [
            name for name, key in PLANTDOC_MAP.items() if key is None
        ],
        "sources": {
            "plantvillage": "spMohanty/PlantVillage-Dataset (public, lab conditions)",
            "plantdoc": "pratikkayal/PlantDoc-Dataset (CC-BY-4.0, 2,598 field photos)",
        },
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2))
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", default="/tmp/agrishield_v2")
    ap.add_argument("--plantdoc", default="/tmp/plantdoc")
    ap.add_argument("--out", default="/tmp/agrishield_v3")
    args = ap.parse_args()
    stats = build(Path(args.lab), Path(args.plantdoc), Path(args.out))
    print(json.dumps({k: v for k, v in stats.items() if k != "classes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
