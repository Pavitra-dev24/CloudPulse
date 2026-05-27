import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    os.environ["DB_PATH"] = str(tmp_path / "test_metrics.db")
    init_db()
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_ingest_metric_success(client):
    resp = client.post("/metrics", json={"service_name": "auth-api", "metric_type": "cpu", "value": 72.5})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["value"] == 72.5


def test_ingest_metric_missing_fields(client):
    resp = client.post("/metrics", json={"service_name": "auth-api"})
    assert resp.status_code == 400


def test_ingest_metric_invalid_value(client):
    resp = client.post("/metrics", json={"service_name": "auth-api", "metric_type": "cpu", "value": "not-a-number"})
    assert resp.status_code == 400


def test_list_metrics_empty(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_metrics_returns_data(client):
    client.post("/metrics", json={"service_name": "api", "metric_type": "cpu", "value": 55})
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_filter_metrics_by_service(client):
    client.post("/metrics", json={"service_name": "svc-a", "metric_type": "mem", "value": 40})
    client.post("/metrics", json={"service_name": "svc-b", "metric_type": "mem", "value": 60})
    resp = client.get("/metrics?service=svc-a")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["service_name"] == "svc-a"


def test_filter_metrics_by_type(client):
    client.post("/metrics", json={"service_name": "api", "metric_type": "cpu", "value": 30})
    client.post("/metrics", json={"service_name": "api", "metric_type": "mem", "value": 80})
    resp = client.get("/metrics?type=cpu")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(m["metric_type"] == "cpu" for m in data)


def test_list_services(client):
    client.post("/metrics", json={"service_name": "svc-x", "metric_type": "cpu", "value": 30})
    client.post("/metrics", json={"service_name": "svc-y", "metric_type": "cpu", "value": 50})
    resp = client.get("/metrics/services")
    assert resp.status_code == 200
    services = resp.get_json()
    assert "svc-x" in services
    assert "svc-y" in services


def test_summary_endpoint(client):
    client.post("/metrics", json={"service_name": "api", "metric_type": "cpu", "value": 40})
    client.post("/metrics", json={"service_name": "api", "metric_type": "cpu", "value": 60})
    resp = client.get("/metrics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["avg_value"] == 50.0
    assert data[0]["total"] == 2


def test_limit_parameter(client):
    for i in range(10):
        client.post("/metrics", json={"service_name": "api", "metric_type": "cpu", "value": i})
    resp = client.get("/metrics?limit=3")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 3
