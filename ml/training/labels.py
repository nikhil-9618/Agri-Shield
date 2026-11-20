"""Canonical PlantVillage label metadata for AgriShield.

The 38 class names below are the *dataset's own* class labels (PlantVillage,
published by Hughes & Salathé, 2015). They are metadata only — no prediction is
ever hard-coded from this file. The trained model produces the predictions.
"""

from __future__ import annotations

import re

# Official PlantVillage class order (38 classes as published / as used by the
# Kaggle and Hugging Face mirrors).
CLASS_NAMES: list[str] = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

# Every crop PlantVillage covers. The app ships all 38 classes so a farmer is
# not told "unknown crop" when the leaf is cherry, peach, strawberry or citrus.
SUPPORTED_CROPS: list[str] = [
    "apple",
    "blueberry",
    "cherry",
    "corn",
    "grape",
    "orange",
    "peach",
    "pepper",
    "potato",
    "raspberry",
    "soybean",
    "squash",
    "strawberry",
    "tomato",
]

# Prefix -> crop slug. PlantVillage mixes "Apple___", "Apple__Apple_scab",
# "Pepper,_bell___", "Corn_(maize)___" spellings across mirrors.
_CROP_PREFIXES: dict[str, tuple[str, ...]] = {
    "apple": ("apple",),
    "blueberry": ("blueberry",),
    "cherry": ("cherry",),
    "corn": ("corn",),
    "grape": ("grape",),
    "orange": ("orange",),
    "peach": ("peach",),
    "pepper": ("pepper",),
    "potato": ("potato",),
    "raspberry": ("raspberry",),
    "soybean": ("soybean",),
    "squash": ("squash",),
    "strawberry": ("strawberry",),
    "tomato": ("tomato",),
}


def _clean(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()


def canonical_key(raw_label: str) -> str:
    """Stable identifier shared by model artifacts, API and advisory JSON.

    >>> canonical_key("Tomato___Late_blight")
    'tomato___late_blight'
    """
    return _clean(raw_label)


def split_label(raw_label: str) -> tuple[str, str]:
    """Return (crop_slug, disease_slug) for a PlantVillage class name."""
    head = re.split(r"_{2,}", raw_label, maxsplit=1)[0].lower()
    crop = "unknown"
    for slug, prefixes in _CROP_PREFIXES.items():
        if any(head.startswith(p) for p in prefixes):
            crop = slug
            break
    # Everything after the crop marker is the disease / condition name.
    parts = re.split(r"_{2,}", raw_label)
    if len(parts) > 1:
        disease_raw = parts[-1]
    else:  # mirror spelling "Apple__Apple_scab"
        disease_raw = raw_label.split("__", 1)[-1]
    disease = _clean(disease_raw)
    if disease in {"healthy", ""}:
        disease = "healthy"
    return crop, disease


def classify(raw_label: str) -> dict:
    crop, disease = split_label(raw_label)
    return {
        "label": raw_label,
        "key": canonical_key(raw_label),
        "crop": crop,
        "disease": disease,
        "is_healthy": disease == "healthy",
    }


def supported_class_indices() -> list[int]:
    """Indices (into CLASS_NAMES) of every crop the app ships with."""
    return [
        i for i, name in enumerate(CLASS_NAMES) if split_label(name)[0] in SUPPORTED_CROPS
    ]


def class_directory_name(raw_label: str) -> str:
    """Filesystem-safe, human-readable folder name for image_datasets."""
    return re.sub(r"[^A-Za-z0-9]+", "_", raw_label).strip("_")
