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
    (r"powdery mildew", "cherry", "cherry_including_sour_powdery_mildew"),
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


def summarise(rows: list[dict], threshold: float) -> dict:
    """Agronomist-agreement metrics for one confidence threshold."""
    covered = [r for r in rows if r["ref"]]
    unsupported = [r for r in rows if r["crop"] is None]

    correct1 = sum(r["top"] == r["ref"] for r in covered)
    correct3 = sum(r["ref"] in r["top3"] for r in covered)
    abstained = sum(r["conf"] < threshold for r in covered)
    accepted = [r for r in covered if r["conf"] >= threshold]
    # "Confident and wrong" is measured at the threshold that actually ships,
    # so it reflects what the farmer would have been told.
    confident_wrong = sum(
        r["top"] != r["ref"] and r["conf"] >= threshold for r in covered
    )
    # A confident answer about a crop the farmer did not photograph is the
    # clearest form of "guessing", so it is measured separately.
    unsupported_confident = sum(
        r["conf"] >= threshold and r["top_crop"] != r["crop"] for r in unsupported
    )

    return {
        "threshold": round(threshold, 4),
        "scored_images": len(covered),
        "top1_accuracy": round(correct1 / len(covered), 3) if covered else None,
        "top3_accuracy": round(correct3 / len(covered), 3) if covered else None,
        "coverage": round(len(accepted) / len(covered), 3) if covered else None,
        "accepted_top1_accuracy": round(
            sum(r["top"] == r["ref"] for r in accepted) / len(accepted), 3
        )
        if accepted
        else None,
        "abstention_rate": round(abstained / len(covered), 3) if covered else None,
        "confident_wrong_rate": round(confident_wrong / len(covered), 3)
        if covered
        else None,
        "out_of_scope_images": len(unsupported),
        "out_of_scope_confident_rate": round(
            unsupported_confident / len(unsupported), 3
        )
        if unsupported
        else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/digigreen")
    ap.add_argument("--model", default="mobile/assets/model/agrishield_model.tflite")
    ap.add_argument("--labels", default="mobile/assets/model/class_names.json")
    ap.add_argument("--calibration", default="ml/artifacts/calibration.json")
    ap.add_argument("--out", default="docs/field_validation.json")
    ap.add_argument(
        "--legacy-threshold",
        type=float,
        default=0.55,
        help="pre-calibration threshold, reported for comparison",
    )
    args = ap.parse_args()

    from ai_edge_litert.interpreter import Interpreter

    from ml.calibration.calibration import apply_temperature, load_calibration

    labels = json.loads(Path(args.labels).read_text())
    healthy_keys = {c["crop"]: c["key"] for c in labels if c["is_healthy"]}
    key_of_index = {c["index"]: c["key"] for c in labels}
    crop_of_key = {c["key"]: c["crop"] for c in labels}
    calibration = load_calibration(args.calibration)
    temperature = float(calibration["temperature"])
    fitted_threshold = float(calibration["min_confidence"])

    it = Interpreter(model_path=args.model)
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    out = it.get_output_details()[0]
    size = int(inp["shape"][1])

    rows = list(csv.DictReader(open(Path(args.data) / "annotations.csv")))
    by_image: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_image[row["image_file"]].append(row)

    records: list[dict] = []
    for image_file, anns in sorted(by_image.items()):
        path = Path(args.data) / image_file
        if not path.exists():
            continue
        crop = CROP_ALIASES.get(anns[0]["crop"].strip().lower())
        arr = np.asarray(
            Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR),
            dtype=np.float32,
        )
        it.set_tensor(inp["index"], arr.reshape(1, size, size, 3))
        it.invoke()
        probs = apply_temperature(
            np.asarray(it.get_tensor(out["index"]))[0], temperature
        )
        order = np.argsort(probs)[::-1]
        top = key_of_index[int(order[0])]

        ref = None
        if crop is not None:
            for ann in anns:
                ref = reference_key(crop, ann["diagnosis"], healthy_keys)
                if ref:
                    break

        records.append(
            {
                "crop": crop,
                "ref": ref,
                "conf": float(probs[order[0]]),
                "top": top,
                "top_crop": crop_of_key.get(top),
                "top3": [key_of_index[int(i)] for i in order[:3]],
            }
        )

    per_crop: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "top1": 0})
    for r in records:
        if r["crop"] and r["ref"]:
            per_crop[r["crop"]]["n"] += 1
            per_crop[r["crop"]]["top1"] += r["top"] == r["ref"]

    unmapped = sum(1 for r in records if r["crop"] is not None and not r["ref"])
    report = {
        "dataset": "Digital Green Crop Disease Expert Annotations (CC-BY-4.0)",
        "images_in_dataset": len(by_image),
        "scored_images": sum(1 for r in records if r["ref"]),
        "out_of_scope_images": sum(1 for r in records if r["crop"] is None),
        "unmapped_label_images": unmapped,
        "calibration": {
            "source": args.calibration if Path(args.calibration).exists() else "defaults",
            "temperature": temperature,
            "min_confidence": fitted_threshold,
            "healthy_confidence": float(calibration["healthy_confidence"]),
        },
        "uncalibrated": summarise(records, args.legacy_threshold),
        "calibrated": summarise(records, fitted_threshold),
        "per_crop": {
            crop: {"n": v["n"], "top1": round(v["top1"] / v["n"], 3)}
            for crop, v in sorted(per_crop.items())
            if v["n"]
        },
        "notes": [
            "Reference labels are free-text agronomist diagnoses mapped by keyword, not a 1:1 class set.",
            "Photos are farmer field photos (soil, shadows, multiple leaves), unlike PlantVillage.",
            "Top-1 accuracy does not improve with calibration: temperature scaling never changes the predicted class.",
            "What calibration changes is coverage: how often the app abstains instead of naming a disease.",
            "out_of_scope_confident_rate counts confident answers about crops absent from the model's class list.",
        ],
    }
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
