"""Agricultural advisory knowledge base (crop/disease content in 5 languages).

Content lives in ``advisory/`` as version-controlled JSON authored from
extension-service guidance (see docs/ADVISORY_SOURCES.md). It contains
*no* pesticide brand names or doses on purpose: the app always directs farmers to
a qualified agriculture officer for chemical treatment.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LANGUAGES = ("te", "hi", "en", "ta", "kn")
DEFAULT_LANGUAGE = "te"


class AdvisoryService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.crops: dict[str, Any] = json.loads((root / "crops.json").read_text("utf-8"))
        self.diseases: dict[str, Any] = {}
        for path in sorted((root / "diseases").glob("*.json")):
            item = json.loads(path.read_text("utf-8"))
            self.diseases[item["key"]] = item
        self.messages: dict[str, Any] = json.loads((root / "messages.json").read_text("utf-8"))
        self.weather_rules: dict[str, Any] = json.loads(
            (root / "weather_rules.json").read_text("utf-8")
        )
        self.faq: dict[str, Any] = json.loads(
            (root / "assistant_faq.json").read_text("utf-8")
        )

    # ------------------------------------------------------------------ utils
    @staticmethod
    def normalize_language(lang: str | None) -> str:
        return lang if lang in LANGUAGES else DEFAULT_LANGUAGE

    def t(self, key: str, lang: str, **fmt: Any) -> str:
        """Localised server message (falls back to English, then key)."""
        entry = self.messages.get(key, {})
        text = entry.get(lang) or entry.get("en") or key
        return text.format(**fmt) if fmt else text

    def crop_name(self, crop: str, lang: str) -> str:
        names = self.crops.get(crop, {}).get("names", {})
        return names.get(lang) or names.get("en") or crop

    def disease_name(self, key: str, lang: str) -> str:
        item = self.diseases.get(key, {})
        return (item.get("l", {}).get(lang) or item.get("l", {}).get("en") or {}).get(
            "name", key
        )

    def localised(self, key: str, lang: str) -> dict[str, str]:
        item = self.diseases.get(key, {})
        blocks = item.get("l", {})
        block = blocks.get(lang) or blocks.get("en") or {}
        fields = ("name", "signs", "do_now", "avoid", "prevention", "expert")
        return {f: block.get(f, "") for f in fields}

    def block(self, key: str, lang: str) -> dict[str, str]:
        return self.localised(key, lang)

    def severity(self, key: str) -> str:
        return self.diseases.get(key, {}).get("severity", "yellow")

    def is_healthy(self, key: str) -> bool:
        return bool(self.diseases.get(key, {}).get("is_healthy", False))

    def icon(self, key: str) -> str:
        return self.diseases.get(key, {}).get("icon", "spot")

    def crop_of(self, key: str) -> str:
        return self.diseases.get(key, {}).get("crop", "unknown")

    # ----------------------------------------------------------------- catalogue
    def list_crops(self, lang: str) -> list[dict[str, str]]:
        return [
            {"key": k, "name": self.crop_name(k, lang), "icon": v.get("icon", "leaf")}
            for k, v in self.crops.items()
        ]

    def list_diseases(self, lang: str, crop: str | None = None) -> list[dict[str, Any]]:
        out = []
        for key, item in self.diseases.items():
            if crop and item.get("crop") != crop:
                continue
            block = self.localised(key, lang)
            out.append(
                {
                    "key": key,
                    "crop": item.get("crop"),
                    "crop_name": self.crop_name(item.get("crop", ""), lang),
                    "name": block["name"],
                    "severity": item.get("severity"),
                    "is_healthy": item.get("is_healthy", False),
                    "icon": item.get("icon", "spot"),
                }
            )
        return sorted(out, key=lambda d: (d["crop_name"], d["name"]))

    # ------------------------------------------------------------------- search
    def find_disease_in_text(self, text: str, lang: str) -> str | None:
        """Match a disease/crop name inside a farmer's question (any language)."""
        haystack = text.lower()
        best: tuple[int, str] | None = None
        for key, item in self.diseases.items():
            if item.get("is_healthy"):
                continue
            for code, block in item.get("l", {}).items():
                name = (block or {}).get("name", "").lower()
                if not name:
                    continue
                tokens = [t for t in name.replace("(", " ").replace(")", " ").split() if len(t) > 3]
                hits = sum(1 for tok in tokens if tok in haystack)
                if hits and (best is None or hits > best[0]):
                    best = (hits, key)
            crop = self.crop_name(item.get("crop", ""), lang).lower()
            if crop and crop in haystack and not best:
                best = (1, key)
        return best[1] if best else None


@lru_cache
def get_advisory_service() -> AdvisoryService:
    from ..config import settings

    return AdvisoryService(settings.advisory_path)
