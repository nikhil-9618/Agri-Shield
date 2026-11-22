"""The assistant must keep the crop the farmer named.

Earlier the matcher scored every disease name word across every crop, so
"tomato leaves with brown spots" was answered with a *corn* advisory (the word
"spot" appeared in a corn disease name). These tests pin the crop-aware
behaviour: named diseases resolve, a named crop restricts the answer, and a
vague question stays unanswered instead of guessing.
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.services.advisory import AdvisoryService
from app.services.assistant import AssistantService
from app.services.weather import WeatherService

ADVISORY = AdvisoryService(settings.advisory_path)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("tomato late blight", "tomato_late_blight"),
        ("late blight in potato", "potato_late_blight"),
        ("my corn has rust", "corn_maize_common_rust"),
        ("apple scab", "apple_apple_scab"),
        ("what is septoria leaf spot", "tomato_septoria_leaf_spot"),
        ("corn grey leaf spot", "corn_maize_cercospora_leaf_spot_gray_leaf_spot"),
        # Hindi / Telugu questions, even when the app language is different.
        ("टमाटर पर पछेती झुलसा", "tomato_late_blight"),
        ("టమాటా ఆకుకుళ్లు తెగులు ఏమిటి", "tomato_late_blight"),
    ],
)
def test_named_disease_is_matched(question: str, expected: str) -> None:
    assert ADVISORY.find_disease_in_text(question, "en") == expected


@pytest.mark.parametrize(
    "question",
    [
        "brown spots on tomato",  # several tomato diseases fit: do not guess
        "मेरे टमाटर के पत्तों पर भूरे धब्बे हैं",  # same question in Hindi
        "how do I water my tomato plants",  # general advice, not a disease
        "zzzz unknown topic xyz",
    ],
)
def test_vague_question_is_not_forced_into_a_disease(question: str) -> None:
    assert ADVISORY.find_disease_in_text(question, "en") is None


@pytest.mark.parametrize("lang", ["en", "hi", "te", "ta", "kn"])
def test_every_advisory_name_resolves_to_its_own_advisory(lang: str) -> None:
    """Crop + localised disease name must find that advisory, in every language."""
    misses = []
    for key, item in ADVISORY.diseases.items():
        if item.get("is_healthy"):
            continue
        block = item["l"].get(lang) or item["l"]["en"]
        question = f"{ADVISORY.crop_name(item['crop'], lang)} {block['name']}"
        if ADVISORY.find_disease_in_text(question, lang) != key:
            misses.append(question)
    assert misses == []


def test_crop_is_never_swapped() -> None:
    """A named crop restricts candidates, so no other crop's advisory leaks in."""
    assert ADVISORY.find_disease_in_text("tomato grey leaf spot", "en") is None
    assert ADVISORY.find_disease_in_text("potato common rust", "en") is None


def test_assistant_answers_disease_and_faq_separately() -> None:
    service = AssistantService(ADVISORY, WeatherService(ADVISORY))

    disease = asyncio.run(
        service.ask("my tomato has late blight", "en", None, None)
    )
    assert disease["sources"][0]["reference"] == "advisory/diseases/tomato_late_blight.json"
    assert "Tomato" in disease["answer"]

    faq = asyncio.run(service.ask("why are my leaves yellow", "en", None, None))
    assert faq["sources"][0]["reference"].startswith("advisory/assistant_faq.json#")

    vague = asyncio.run(service.ask("brown spots on tomato", "en", None, None))
    # Not enough to name one disease, so list the tomato possibilities instead.
    assert vague["answer"] != ADVISORY.faq["fallback"]["en"]
    assert vague["answer"].startswith(
        ADVISORY.t("disease_possibilities", "en", crop="Tomato", list="").split(":")[0]
    )
    assert "Early blight" in vague["answer"]
    assert "Corn" not in vague["answer"]
    assert {s["reference"] for s in vague["sources"]} <= {
        f"advisory/diseases/{key}.json"
        for key in ADVISORY.diseases
        if ADVISORY.crop_of(key) == "tomato"
    }

    unknown = asyncio.run(service.ask("zzzz unknown topic xyz", "en", None, None))
    assert unknown["sources"] == []
    assert unknown["answer"] == ADVISORY.faq["fallback"]["en"]


def test_candidates_stay_inside_the_named_crop() -> None:
    candidates = ADVISORY.candidate_diseases("brown spots on tomato", "en")
    assert candidates
    assert all(ADVISORY.crop_of(c["key"]) == "tomato" for c in candidates)
    assert len(candidates) <= 3
    # A question with no crop or no symptom words offers no candidates.
    assert ADVISORY.candidate_diseases("tell me about tomato", "en") == []
    assert ADVISORY.candidate_diseases("brown spots", "en") == []


def test_symptom_wording_is_not_mistaken_for_an_faq_keyword() -> None:
    """"Water-soaked patches" is a late-blight sign, not a watering question."""
    service = AssistantService(ADVISORY, WeatherService(ADVISORY))
    answer = asyncio.run(
        service.ask(
            "my potato leaves have large dark water-soaked patches", "en", None, None
        )
    )
    assert answer["sources"][0]["reference"] == (
        "advisory/diseases/potato_late_blight.json"
    )


def test_symptom_with_one_matching_advisory_is_answered() -> None:
    candidates = ADVISORY.candidate_diseases("whitefly on tomato", "en")
    assert [c["key"] for c in candidates] == ["tomato_tomato_yellow_leaf_curl_virus"]
    service = AssistantService(ADVISORY, WeatherService(ADVISORY))
    answer = asyncio.run(service.ask("whitefly on tomato", "en", None, None))
    assert answer["sources"][0]["reference"] == (
        "advisory/diseases/tomato_tomato_yellow_leaf_curl_virus.json"
    )
