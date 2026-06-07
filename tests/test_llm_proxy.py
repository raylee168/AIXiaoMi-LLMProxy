import os

os.environ["DATABASE_URL"] = "sqlite:///./test_llm_proxy.db"
os.environ["MOCK_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_decision_contract():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model_type": "text_llm",
            "purpose": "moments_album_decision",
            "user_id": "u001",
            "session_id": "decision_s001",
            "request_id": "decision_r001",
            "messages": [
                {"role": "system", "content": "strict json"},
                {
                    "role": "user",
                    "content": '{"photo_count": 6, "usable_photo_count": 6, "photo_ids": ["p1","p2","p3","p4","p5","p6"]}',
                },
            ],
            "response_format": "json",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "decision_r001"
    assert payload["content"]["decision"] == "should_generate"
    assert payload["usage"]["total_tokens"] > 0
    assert payload["cost"]["charged_tokens"] > 0


def test_copywriting_contract():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model_type": "text_llm",
            "purpose": "moments_album_copywriting",
            "user_id": "u001",
            "session_id": "gen_s001",
            "request_id": "copy_r001",
            "messages": [{"role": "user", "content": "{}"}],
            "response_format": "json",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"]["title"]
    assert len(payload["content"]["copy_options"]) >= 3


def test_vision_contract():
    response = client.post(
        "/v1/vision/analyze",
        json={
            "model_type": "image_vlm",
            "purpose": "moments_album_image_review",
            "user_id": "u001",
            "summary": {},
            "images": [{"photo_id": "p1", "image_path": "/tmp/p1.jpg"}],
            "response_format": "json",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"]["suggested_main_photo_id"] == "p1"
    assert payload["usage"]["image_count"] == 1


def test_request_id_idempotency_and_session_billing():
    body = {
        "model_type": "text_llm",
        "purpose": "moments_album_copywriting",
        "user_id": "u002",
        "session_id": "gen_s002",
        "request_id": "copy_r002",
        "messages": [{"role": "user", "content": "{}"}],
        "response_format": "json",
    }
    first = client.post("/v1/chat/completions", json=body)
    second = client.post("/v1/chat/completions", json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cached"] is True

    billing = client.get("/v1/billing/sessions/gen_s002")
    assert billing.status_code == 200
    payload = billing.json()
    assert payload["request_count"] == 1
    assert payload["success_count"] == 1
    assert payload["cost"]["charged_tokens"] == first.json()["cost"]["charged_tokens"]

    request_billing = client.get("/v1/billing/requests/copy_r002")
    assert request_billing.status_code == 200
    assert request_billing.json()["request_id"] == "copy_r002"
