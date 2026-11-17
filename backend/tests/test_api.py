"""End-to-end API tests. Run from the backend/ directory:

    DATABASE_URL=sqlite:///./test.db python -m pytest tests -q

No network is used: weather rules are tested as pure functions, and all other
tests hit the real FastAPI app + real TFLite model through TestClient.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="agrishield-test-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TMP/'test.db'}")
os.environ.setdefault("UPLOAD_DIR", str(TMP / "uploads"))
os.environ.setdefault("GRADCAM_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from app.main import app  # noqa: E402
from app.services.advisory import get_advisory_service  # noqa: E402
from app.services.weather import WeatherService  # noqa: E402

CLIENT = TestClient(app)
PHONE = "9876543210"


def leaf_jpeg() -> bytes:
    """A real JPEG (not a synthetic prediction source): green leaf-like shape."""
    img = Image.new("RGB", (320, 320), (30, 90, 35))
    draw = ImageDraw.Draw(img)
    draw.ellipse((40, 70, 280, 250), fill=(70, 140, 55))
    draw.line((160, 70, 160, 250), fill=(120, 180, 80), width=6)
    for x in range(70, 260, 24):
        draw.line((160, 160, x, 120), fill=(100, 160, 70), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture(scope="module")
def auth():
    with CLIENT:
        r = CLIENT.post(
            "/api/auth/register",
            json={"phone": PHONE, "name": "Ramesh", "password": "secret123", "language": "te"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        return {"Authorization": f"Bearer {data['access_token']}"}, data


def test_health():
    with CLIENT:
        r = CLIENT.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["advisory_diseases"] == 27
        if body["model_loaded"]:
            assert body["model_version"]


def test_register_duplicate_conflict(auth):
    r = CLIENT.post(
        "/api/auth/register",
        json={"phone": PHONE, "name": "Ramesh", "password": "secret123"},
    )
    assert r.status_code == 409


def test_login_and_me(auth):
    headers, user = auth
    r = CLIENT.post("/api/auth/login", json={"phone": PHONE, "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = CLIENT.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["name"] == "Ramesh"
    bad = CLIENT.post("/api/auth/login", json={"phone": PHONE, "password": "wrong-pass"})
    assert bad.status_code == 401


def test_prediction_requires_auth():
    r = CLIENT.post("/api/detection/predict", files={"file": ("leaf.jpg", leaf_jpeg(), "image/jpeg")})
    assert r.status_code == 401


def test_reject_non_image(auth):
    headers, _ = auth
    r = CLIENT.post(
        "/api/detection/predict",
        headers=headers,
        files={"file": ("notes.txt", b"hello, not an image", "text/plain")},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_image"


def test_predict_and_history(auth):
    headers, _ = auth
    health = CLIENT.get("/health").json()
    r = CLIENT.post(
        "/api/detection/predict",
        headers=headers,
        files={"file": ("leaf.jpg", leaf_jpeg(), "image/jpeg")},
        params={"lang": "te"},
    )
    if not health["model_loaded"]:
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "model_unavailable"
        pytest.skip("model artifacts unavailable in this environment")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["level"] in {"green", "yellow", "red"}
    assert body["status"] in {"diagnosed", "unclear"}
    assert len(body["top3"]) == 3
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["advisory"]["do_now"]
    assert body["disclaimer"]
    assert body["language"] == "te"

    hist = CLIENT.get("/api/detection/history", headers=headers)
    assert hist.status_code == 200
    assert hist.json()["total"] >= 1
    first = hist.json()["items"][0]
    detail = CLIENT.get(f"/api/detection/{first['id']}", headers=headers)
    assert detail.status_code == 200

    image = CLIENT.get(f"/api/detection/{first['id']}/image", headers=headers)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"

    # Another farmer can never read this diagnosis.
    other = CLIENT.post(
        "/api/auth/register",
        json={"phone": "9123456780", "name": "Sita", "password": "secret123", "language": "hi"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert CLIENT.get(f"/api/detection/{first['id']}", headers=other_headers).status_code == 404
    assert CLIENT.get(f"/api/detection/{first['id']}/image", headers=other_headers).status_code == 404


def test_advisory_localised(auth):
    r = CLIENT.get("/api/advisory/tomato_late_blight", params={"lang": "te"})
    assert r.status_code == 200
    body = r.json()
    assert body["crop"] == "tomato"
    assert "లేట్" in body["advisory"]["name"]
    assert body["advisory"]["do_now"]
    assert set(body["available_languages"]) == {"te", "hi", "en", "ta", "kn"}
    assert CLIENT.get("/api/advisory/not_a_disease").status_code == 404

    crops = CLIENT.get("/api/advisory/crops", params={"lang": "hi"}).json()["crops"]
    assert any(c["key"] == "potato" and c["name"] == "आलू" for c in crops)


def test_assistant_disease_and_fallback(auth):
    headers, _ = auth
    q = "టమాటా ఆకుకుళ్లు తెగులు ఏమిటి?"
    r = CLIENT.post(
        "/api/assistant/ask", headers=headers, json={"question": q, "language": "te"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["language"] == "te"
    assert body["sources"]
    assert len(body["follow_ups"]) >= 1
    assert body["disclaimer"]

    fallback = CLIENT.post(
        "/api/assistant/ask", headers=headers, json={"question": "zzzz unknown topic xyz"}
    )
    assert fallback.status_code == 200
    assert fallback.json()["answer"]


def test_profile_update(auth):
    headers, _ = auth
    r = CLIENT.put(
        "/api/user/profile",
        headers=headers,
        json={"language": "hi", "village": "Warangal", "name": "Ramesh Kumar"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "hi"
    assert body["village"] == "Warangal"
    assert body["name"] == "Ramesh Kumar"
    assert CLIENT.get("/api/user/profile", headers=headers).json()["language"] == "hi"


def test_weather_rules_are_pure():
    advisory = get_advisory_service()
    service = WeatherService(advisory)
    humid = {
        "temperature_2m": 24,
        "relative_humidity_2m": 92,
        "wind_speed_10m": 8,
        "precipitation": 0.2,
    }
    daily = {"precipitation_probability_max": [30, 85, 80, 60, 40, 20, 10]}
    rules = service._active_rules(humid, daily)
    assert "high_humidity" in rules and "rain_soon" in rules
    alert = service._rule_alert(rules[0], "te")
    assert alert["message"] and alert["level"] in {"green", "yellow", "red"}

    hot = {"temperature_2m": 41, "relative_humidity_2m": 40, "wind_speed_10m": 5}
    assert "heat_stress" in service._active_rules(hot, {"precipitation_probability_max": [0]})

    # Very little rain + low humidity is a dry-spell warning, not "good weather".
    dry = {"temperature_2m": 27, "relative_humidity_2m": 55, "wind_speed_10m": 6}
    assert service._active_rules(dry, {"precipitation_probability_max": [10, 10]}) == [
        "dry_spell"
    ]
    mild = {"temperature_2m": 27, "relative_humidity_2m": 65, "wind_speed_10m": 6}
    assert service._active_rules(mild, {"precipitation_probability_max": [30, 40]}) == [
        "good_weather"
    ]
