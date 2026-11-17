#!/usr/bin/env python3
"""Download the PlantVillage parquet mirror used to train AgriShield.

The training images are NOT committed to this repository. This script fetches
the public Hugging Face mirror and leaves the parquet shards on disk; the next
step is `ml/training/prepare_dataset.py`, which extracts the 27 supported
classes into a train/val/test folder layout.

    python dataset/download_plantvillage.py --out /tmp/pv

    python -m ml.training.prepare_dataset \
        --parquet /tmp/pv/train_a.parquet /tmp/pv/train_b.parquet \
        --test-parquet /tmp/pv/test_full.parquet \
        --out /tmp/agrishield_dataset --max-per-class 400 --val-per-class 100

Dataset: Hughes & Salathé (2015), "An open access repository of images on plant
health to enable the development of mobile disease diagnostics". PlantVillage is
published for research use; cite the original paper in any publication.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ID = "BrandonFors/Plant-Diseases-PlantVillage-Dataset"
REPO_TYPE = "dataset"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="/tmp/pv", help="directory for the parquet shards")
    parser.add_argument("--repo", default=REPO_ID, help="Hugging Face dataset repo id")
    parser.add_argument(
        "--check",
        action="store_true",
        help="only list the parquet files and their sizes, do not download",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        print("Missing dependency. Run: pip install huggingface_hub", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    api = HfApi()
    try:
        files = api.list_repo_files(args.repo, repo_type=REPO_TYPE)
    except Exception as exc:  # offline machine or typo in repo id
        print(f"Could not list {args.repo}: {exc}", file=sys.stderr)
        return 1

    parquet = sorted(f for f in files if f.endswith(".parquet"))
    if not parquet:
        print(f"No parquet files found in {args.repo}", file=sys.stderr)
        return 1

    print(f"{args.repo}: {len(parquet)} parquet shard(s)")
    for name in parquet:
        print(f"  {name}")

    if args.check:
        return 0

    paths = []
    for name in parquet:
        target = out / Path(name).name
        print(f"downloading {name} -> {target}")
        downloaded = hf_hub_download(
            repo_id=args.repo,
            repo_type=REPO_TYPE,
            filename=name,
            local_dir=str(out),
        )
        paths.append(Path(downloaded))

    total = sum(p.stat().st_size for p in paths)
    print(f"done: {len(paths)} file(s), {total / 1024 / 1024:.1f} MiB in {out}")
    print("next: python -m ml.training.prepare_dataset --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
