"""Agricultural advisory knowledge base (crop/disease content in 5 languages).

Content lives in ``advisory/`` as version-controlled JSON authored from
extension-service guidance (see docs/ADVISORY_SOURCES.md). It contains
*no* pesticide brand names or doses on purpose: the app always directs farmers to
a qualified agriculture officer for chemical treatment.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

LANGUAGES = ("te", "hi", "en", "ta", "kn")
DEFAULT_LANGUAGE = "te"

# Words that carry no disease information on their own. Without this list a
# question about "brown spots" used to match whichever disease name contained
# "spot", regardless of the crop.
STOPWORDS = frozenset(
    {
        "about", "after", "again", "also", "because", "been", "before", "being",
        "both", "crop", "could", "disease", "does", "doing", "from", "have",
        "help", "into", "just", "leaf", "leaves", "like", "look", "looks",
        "more", "much", "plant", "plants", "please", "should", "some", "spots",
        "spot", "than", "that", "their", "them", "then", "there", "these",
        "they", "this", "very", "what", "when", "where", "which", "while",
        "with", "your",
    }
)

WORD_RE = re.compile(r"[0-9a-z\u0900-\u0d7f]+")


def _tokens(text: str) -> set[str]:
    """Words that can identify content.

    Latin words need four letters ("rust", "spot" are noise otherwise); Indic
    words are often short but meaningful (Kannada "ಆನೆ", "ರೋಗ").
    """
    tokens: set[str] = set()
    for word in WORD_RE.findall(text.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        if word.isascii() and len(word) <= 3:
            continue
        tokens.add(word)
    return tokens


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
        self._prepare_matching()

    # --------------------------------------------------------------- matching
    def _prepare_matching(self) -> None:
        """Pre-index the words used to rank a question against a disease.

        Terms are weighted by how many diseases use them, so "late" or
        "septoria" count for a lot and "blight" or "brown" count for little.
        ``spot``/``leaf`` are dropped through :data:`STOPWORDS`.
        """
        self._crop_words: dict[str, set[str]] = {}
        crop_words: set[str] = set()
        for crop, item in self.crops.items():
            names = {crop} | {
                str(v).lower() for v in item.get("names", {}).values() if v
            }
            self._crop_words[crop] = names
            crop_words |= names

        self._name_terms: dict[str, set[str]] = {}
        self._name_variants: dict[str, list[set[str]]] = {}
        self._sign_terms: dict[str, set[str]] = {}
        name_df: Counter[str] = Counter()
        sign_df: Counter[str] = Counter()
        for key, item in self.diseases.items():
            if item.get("is_healthy"):
                continue
            names: set[str] = set()
            signs: set[str] = set()
            variants: list[set[str]] = []
            for block in item.get("l", {}).values():
                names |= _tokens((block or {}).get("name", ""))
                signs |= _tokens((block or {}).get("signs", ""))
                signs |= _tokens((block or {}).get("do_now", ""))
                variant = _tokens((block or {}).get("name", "")) - crop_words
                if variant:
                    variants.append(variant)
            self._name_terms[key] = names - crop_words
            self._name_variants[key] = variants
            self._sign_terms[key] = signs - crop_words
            for term in self._name_terms[key]:
                name_df[term] += 1
            for term in self._sign_terms[key]:
                sign_df[term] += 1
        self._name_df = name_df
        self._sign_df = sign_df

    @staticmethod
    def _mentions(text: str, word: str) -> bool:
        """Whole-word match for Latin script, substring for Indic scripts."""
        if re.fullmatch(r"[a-z0-9 ]+", word):
            if len(word) < 4:
                return False
            return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None
        return len(word) >= 2 and word in text

    def crops_in_text(self, text: str) -> set[str]:
        """Crops the farmer actually named, in any of the five languages."""
        haystack = text.lower()
        found: set[str] = set()
        for crop, names in self._crop_words.items():
            if any(self._mentions(haystack, name) for name in names):
                found.add(crop)
        return found

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
    def _ranked_diseases(
        self, text: str
    ) -> list[tuple[float, float, str, list[str]]]:
        """Score every disease the question could be about, best first.

        Returns ``(name_score, sign_score, key, matched_sign_terms)`` for the
        crop named in the question (or for every crop when none is named).
        ``name_score`` comes from distinctive disease-name words and is the
        only evidence strong enough to name one disease outright.
        """
        haystack = text.lower()
        question_tokens = _tokens(text)
        crops_named = self.crops_in_text(text)
        ranked: list[tuple[float, float, str, list[str]]] = []
        for key, item in self.diseases.items():
            if item.get("is_healthy"):
                continue
            if crops_named and item.get("crop") not in crops_named:
                continue
            name_score = 0.0
            for term in self._name_terms.get(key, set()):
                if self._mentions(haystack, term):
                    name_score += 3.0 / self._name_df[term]
            # The farmer used this advisory's whole name. Without this, names
            # made only of common words ("Grape leaf blight", Telugu
            # "బంగాళదుంప ఆకు మచ్చల తెగులు") score too low to be recognised.
            if any(
                variant <= question_tokens
                for variant in self._name_variants.get(key, [])
            ):
                name_score += 3.0
            sign_score = 0.0
            sign_hits: list[str] = []
            for term in self._sign_terms.get(key, set()):
                if self._mentions(haystack, term):
                    sign_hits.append(term)
                    sign_score += 0.5 / self._sign_df[term]
            ranked.append((name_score, sign_score, key, sign_hits))
        ranked.sort(key=lambda row: row[0] + row[1], reverse=True)
        return ranked

    def candidate_diseases(
        self, text: str, lang: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Reviewed advisories that fit the signs in the question.

        Used when the signs could be more than one disease for the named crop:
        the assistant then lists the possibilities with their distinguishing
        signs instead of picking one at random.
        """
        if not self.crops_in_text(text):
            return []
        out: list[dict[str, Any]] = []
        for name_score, sign_score, key, sign_hits in self._ranked_diseases(text):
            if not sign_hits:
                continue
            block = self.localised(key, lang)
            out.append(
                {
                    "key": key,
                    "name": block["name"],
                    "signs": block["signs"],
                    "score": round(name_score + sign_score, 2),
                }
            )
            if len(out) >= limit:
                break
        return out

    def find_disease_in_text(self, text: str, lang: str) -> str | None:
        """Name the disease a farmer is asking about, or ``None`` if unsure.

        The question is ranked against every reviewed advisory:

        * a crop named in the question restricts the search to that crop, so a
          tomato question can never be answered with a corn advisory;
        * disease-name words are weighted by how distinctive they are ("late",
          "septoria", "rust" decide; "blight" barely counts);
        * wording from the reviewed symptom/advisory text adds a little weight.

        If no disease is distinctive enough the answer is ``None`` and the
        caller falls back to an FAQ answer or an honest "I do not know" rather
        than guessing a wrong disease.

        ``lang`` is kept for callers but is not needed: names, crops and signs
        are matched in all five languages, because farmers often type English
        while the app language is set to Telugu or Hindi.
        """
        ranked = self._ranked_diseases(text)
        if not ranked:
            return None
        name_score, _sign_score, key, _ = ranked[0]
        # Only disease-name words identify a disease outright; symptoms alone
        # go through candidate_diseases() so the answer can list them.
        return key if name_score >= 1.0 else None


@lru_cache
def get_advisory_service() -> AdvisoryService:
    from ..config import settings

    return AdvisoryService(settings.advisory_path)
