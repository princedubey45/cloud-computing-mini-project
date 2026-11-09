import os
import pytest
from fastapi.testclient import TestClient
from app import app, is_model_ready, validate_schema

client = TestClient(app)


def test_healthz_endpoint():
    """Test 1: Liveness probe must return 200."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "OK"


def test_readyz_endpoint():
    """Test 2: Readiness probe returns 200 when initialized."""
    with TestClient(app) as test_client:
        response = test_client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_parse_valid_command():
    """Test 3: POST /parse returns 200, 4 keys, and headers."""
    with TestClient(app) as test_client:
        payload = {"text": "set an alarm for seven am tomorrow"}
        response = test_client.post("/parse", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"intent", "date", "time", "place"}
        assert data["intent"] == "alarm_set"
        assert "X-Model-Version" in response.headers
        assert "X-Served-By" in response.headers


def test_fault_injection():
    """Test 4: FAULT_INJECT=1 returns HTTP 500 with exact error body."""
    os.environ["FAULT_INJECT"] = "1"
    try:
        with TestClient(app) as test_client:
            payload = {"text": "what is the weather in london"}
            response = test_client.post("/parse", json=payload)
            assert response.status_code == 500
            assert response.json() == {"error": "invalid_model_output"}
    finally:
        os.environ["FAULT_INJECT"] = "0"


def test_schema_validator():
    """Test 5: validate_schema correctly checks keys and intents."""
    valid_obj = {"intent": "weather_query", "date": None, "time": None, "place": "london"}
    assert validate_schema(valid_obj) is True

    extra_key_obj = {"intent": "weather_query", "date": None, "time": None, "place": "london", "extra": 1}
    assert validate_schema(extra_key_obj) is False

    invalid_intent_obj = {"intent": "unknown_intent", "date": None, "time": None, "place": None}
    assert validate_schema(invalid_intent_obj) is False
