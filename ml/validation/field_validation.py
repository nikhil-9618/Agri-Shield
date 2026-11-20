"""Measure the shipped model on real Indian farm photos.

Input: Digital Green Crop Disease Expert Annotations (CC-BY-4.0), 989 photos
taken by smallholder farmers and reviewed by agronomists.

    python -m ml.validation.field_validation --data /tmp/digigreen \
        --model mobile/assets/model/agrishield_model.tflite \
        --labels mobile/assets/model/class_names.json \
        --out docs/field_validation.json

This is not a leaderboard score: the labels are free-text agronomist
diagnoses, and many photos show crops or conditions PlantVillage does not
contain. The report separates what the model can be scored on from what it
should have refused.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

CROP_ALIASES = {
    "tomato": "tomato",
    "potato": "potato",
    "maize": "corn",
    "corn": "corn",
    "apple": "apple",
    "grape": "grape",
    "pepper": "pepper",
    "chilli": "pepper",
    "capsicum": "pepper",
    "peach": "peach",
    "cherry": "cherry",
    "strawberry": "strawberry",
    "squash": "squash",
    "pumpkin": "squash",
    "cucumber": "squash",
    "soybean": "soybean",
    "blueberry": "blueberry",
    "raspberry": "raspberry",
    "orange": "orange",
}

# (regex, crop filter or None, class key)
CONDITIONS = [
    (r"healthy|no disease|no symptom", None, "HEALTHY"),
    (r"late blight", "tomato", "tomato_late_blight"),
    (r"late blight", "potato", "potato_late_blight"),
    (r"early blight", "tomato", "tomato_early_blight"),
    (r"early blight", "potato", "potato_early_blight"),
    (r"leaf ?mold|leaf mould", "tomato", "tomato_leaf_mold"),
    (r"septoria|leaf spot", "tomato", "tomato_septoria_leaf_spot"),
    (r"bacterial (spot|leaf spot)", "tomato", "tomato_bacterial_spot"),
    (r"bacterial (spot|leaf spot)", "pepper", "pepper_bell_bacterial_spot"),
    (r"bacterial (spot|leaf spot)", "peach", "peach_bacterial_spot"),
    (r"target (spot|leaf spot)", "tomato", "tomato_target_spot"),
    (r"yellow leaf curl|leaf curl", "tomato", "tomato_tomato_yellow_leaf_curl_virus"),
    (r"mosaic", "tomato", "tomato_tomato_mosaic_virus"),
    (r"spider mite|mite", "tomato", "tomato_spider_mites_two_spotted_spider_mite"),
    (r"rust", "corn", "corn_maize_common_rust"),
    (r"northern leaf blight|leaf blight", "corn", "corn_maize_northern_leaf_blight"),
    (r"grey leaf spot|gray leaf spot|cercospora", "corn", "corn_maize_cercospora_leaf_spot_gray_leaf_spot"),
    (r"powdery mildew", "squash", "squash_powdery_mildew"),
    (r"powdery mildew", "cherry", "cherry_powdery_mildew"),
    (r"leaf scorch|scorch", "strawberry", "strawberry_leaf_scorch"),
    (r"black rot", "grape", "grape_black_rot"),
    (r"black rot", "apple", "apple_black_rot"),
    (r"apple scab|scab", "apple", "apple_apple_scab"),
    (r"cedar apple rust", "apple", "apple_cedar_apple_rust"),
    (r"greening|huanglongbing|hlb", "orange", "orange_haunglongbing_citrus_greening"),
    (r"esca|measles", "grape", "grape_esca_black_measles"),
    (r"isariopsis", "grape", "grape_leaf_blight_isariopsis_leaf_spot"),
]


def reference_key(crop: str, diagnosis: str, healthy_keys: dict[str, str]) -> str | None:
    """Best single PlantVillage class for a free-text agronomist diagnosis."""
    text = diagnosis.lower()
    for pattern, only_crop, key in CONDITIONS:
        if only_crop is not None and crop != only_crop:
            continue
        if re.search(pattern, text):
            if key == "HEALTHY":
                return healthy_keys.get(crop)
            return key
    if re.search(r"healthy|no disease|no symptom", text):
        return healthy_keys.get(crop)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/digigreen")
    ap.add_argument("--model", default="mobile/assets/model/agrishield_model.tflite")
    ap.add_argument("--labels", default="mobile/assets/model/class_names.json")
    ap.add_argument("--out", default="docs/field_validation.json")
    ap.add_argument("--min-confidence", type=float, default=0.55)
    args = ap.parse_args()

    from ai_edge_litert.interpreter import Interpreter

    labels = json.loads(Path(args.labels).read_text())
    healthy_keys = {c["crop"]: c["key"] for c in labels if c["is_healthy"]}
    key_of_index = {c["index"]: c["key"] for c in labels}
    crop_of_key = {c["key"]: c["crop"] for c in labels}

    it = Interpreter(model_path=args.model)
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    out = it.get_output_details()[0]
    size = int(inp["shape"][1])

    rows = list(csv.DictReader(open(Path(args.data) / "annotations.csv")))
    by_image: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_image[row["image_file"]].append(row)

    scored = correct1 = correct3 = 0
    covered = 0
    abstained = 0
    confident_wrong = 0
    per_crop: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "top1": 0})
    unsupported_confident = 0
    unsupported = 0
    skipped_crop = 0

    for image_file, anns in sorted(by_image.items()):
        crop_raw = anns[0]["crop"].strip().lower()
        crop = CROP_ALIASES.get(crop_raw)
        path = Path(args.data) / image_file
        if not path.exists():
            continue
        if crop is None:
            unsupported += 1
        arr = np.asarray(
            Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR),
            dtype=np.float32,
        )
        it.set_tensor(inp["index"], arr.reshape(1, size, size, 3))
        it.invoke()
        probs = it.get_tensor(out["index"])[0]
        order = np.argsort(probs)[::-1]
        top = key_of_index[int(order[0])]
        conf = float(probs[order[0]])
        top3 = [key_of_index[int(i)] for i in order[:3]]

        if crop is None:
            if conf >= args.min_confidence and crop_of_key.get(top) not in (None, crop):
                # Model answered confidently about a crop the farmer did not photograph.
                unsupported_confident += 1
            continue

        ref = None
        for ann in anns:
            ref = reference_key(crop, ann["diagnosis"], healthy_keys)
            if ref:
                break
        if not ref:
            skipped_crop += 1
            continue

        covered += 1
        per_crop[crop]["n"] += 1
        if conf < args.min_confidence:
            abstained += 1
        if top == ref:
            correct1 += 1
            per_crop[crop]["top1"] += 1
        elif conf >= 0.80:
            confident_wrong += 1
        if ref in top3:
            correct3 += 1

    report = {
        "dataset": "Digital Green Crop Disease Expert Annotations (CC-BY-4.0)",
        "images_in_dataset": len(by_image),
        "scored_images": covered,
        "out_of_scope_images": unsupported,
        "unmapped_label_images": skipped_crop,
        "top1_accuracy": round(correct1 / covered, 3) if covered else None,
        "top3_accuracy": round(correct3 / covered, 3) if covered else None,
        "abstention_rate": round(abstained / covered, 3) if covered else None,
        "confident_wrong_rate": round(confident_wrong / covered, 3) if covered else None,
        "unsupported_crop_confident_rate": round(unsupported_confident / unsupported, 3)
        if unsupported
        else None,
        "per_crop": {
            crop: {"n": v["n"], "top1": round(v["top1"] / v["n"], 3)}
            for crop, v in sorted(per_crop.items())
            if v["n"]
        },
        "notes": [
            "Reference labels are free-text agronomist diagnoses mapped by keyword, not a 1:1 class set.",
            "Photos are farmer field photos (soil, shadows, multiple leaves), unlike PlantVillage.",
            "unsupported_crop_confident_rate counts confident answers about crops not present in the photo.",
        ],
    }
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
