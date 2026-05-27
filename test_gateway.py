import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

os.environ["API_KEY"] = "test-api-key"
os.environ["METRICS_SERVICE_URL"] = "http://mock-metrics"
os.environ["ALERT_SERVICE_URL"] = "http://mock-alerts"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


def make_mock_response(status_code, body):
    m = MagicMock()
    m.status_code = status_code
    m.content = json.dumps(body).encode()
    m.headers = {"Content-Type": "application/json"}
    return m


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_unauthenticated_metrics_get(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 401


def test_unauthenticated_metrics_post(client):
    resp = client.post("/api/metrics", json={"service_name": "api", "metric_type": "cpu", "value": 50})
    assert resp.status_code == 401


def test_unauthenticated_rules(client):
    resp = client.get("/api/rules")
    assert resp.status_code == 401


def test_unauthenticated_alerts(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 401


def test_authenticated_get_metrics(client):
    mock = make_mock_response(200, [])
    with patch("requests.request", return_value=mock):
        resp = client.get("/api/metrics", headers={"X-API-Key": "test-api-key"})
    assert resp.status_code == 200


def test_authenticated_get_rules(client):
    mock = make_mock_response(200, [])
    with patch("requests.request", return_value=mock):
        resp = client.get("/api/rules", headers={"X-API-Key": "test-api-key"})
    assert resp.status_code == 200


def test_post_metric_triggers_alert_evaluation(client):
    metrics_resp = make_mock_response(201, {"message": "Metric recorded"})
    eval_resp = make_mock_response(200, {"triggered": [], "count": 0})
    call_count = {"n": 0}

    def side_effect(method, url, **kwargs):
        call_count["n"] += 1
        if "metrics" in url:
            return metrics_resp
        return eval_resp

    with patch("requests.request", side_effect=side_effect):
        resp = client.post(
            "/api/metrics",
            json={"service_name": "api", "metric_type": "cpu", "value": 90},
            headers={"X-API-Key": "test-api-key"},
        )
    assert resp.status_code == 201
    assert call_count["n"] == 2


def test_upstream_unavailable_returns_503(client):
    with patch("requests.request", side_effect=__import__("requests").exceptions.ConnectionError):
        resp = client.get("/api/metrics", headers={"X-API-Key": "test-api-key"})
    assert resp.status_code == 503


def test_get_metrics_summary(client):
    mock = make_mock_response(200, [])
    with patch("requests.request", return_value=mock):
        resp = client.get("/api/metrics/summary", headers={"X-API-Key": "test-api-key"})
    assert resp.status_code == 200


def test_delete_rule(client):
    mock = make_mock_response(200, {"message": "Rule deleted"})
    with patch("requests.request", return_value=mock):
        resp = client.delete("/api/rules/1", headers={"X-API-Key": "test-api-key"})
    assert resp.status_code == 200
