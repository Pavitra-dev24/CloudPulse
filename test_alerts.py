import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    os.environ["DB_PATH"] = str(tmp_path / "test_alerts.db")
    init_db()
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_rule_success(client):
    resp = client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"})
    assert resp.status_code == 201
    assert "id" in resp.get_json()


def test_create_rule_missing_fields(client):
    resp = client.post("/rules", json={"metric_type": "cpu"})
    assert resp.status_code == 400


def test_create_rule_invalid_operator(client):
    resp = client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": "==", "severity": "warning"})
    assert resp.status_code == 400


def test_create_rule_invalid_severity(client):
    resp = client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "extreme"})
    assert resp.status_code == 400


def test_list_rules(client):
    client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"})
    resp = client.get("/rules")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_delete_rule(client):
    create_resp = client.post("/rules", json={"metric_type": "mem", "threshold": 90, "operator": ">", "severity": "warning"})
    rule_id = create_resp.get_json()["id"]
    del_resp = client.delete(f"/rules/{rule_id}")
    assert del_resp.status_code == 200
    assert len(client.get("/rules").get_json()) == 0


def test_delete_nonexistent_rule(client):
    resp = client.delete("/rules/999")
    assert resp.status_code == 404


def test_evaluate_triggers_alert(client):
    client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"})
    resp = client.post("/alerts/evaluate", json={"service_name": "api", "metric_type": "cpu", "value": 95})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["triggered"][0]["severity"] == "critical"


def test_evaluate_does_not_trigger_below_threshold(client):
    client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"})
    resp = client.post("/alerts/evaluate", json={"service_name": "api", "metric_type": "cpu", "value": 50})
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0


def test_evaluate_less_than_operator(client):
    client.post("/rules", json={"metric_type": "disk", "threshold": 10, "operator": "<", "severity": "warning"})
    resp = client.post("/alerts/evaluate", json={"service_name": "db", "metric_type": "disk", "value": 5})
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 1


def test_evaluate_service_specific_rule(client):
    client.post("/rules", json={"service_name": "payment-svc", "metric_type": "latency", "threshold": 200, "operator": ">", "severity": "warning"})
    triggered = client.post("/alerts/evaluate", json={"service_name": "payment-svc", "metric_type": "latency", "value": 300})
    not_triggered = client.post("/alerts/evaluate", json={"service_name": "other-svc", "metric_type": "latency", "value": 300})
    assert triggered.get_json()["count"] == 1
    assert not_triggered.get_json()["count"] == 0


def test_list_alerts_after_trigger(client):
    client.post("/rules", json={"metric_type": "mem", "threshold": 70, "operator": ">", "severity": "warning"})
    client.post("/alerts/evaluate", json={"service_name": "db", "metric_type": "mem", "value": 85})
    resp = client.get("/alerts")
    assert resp.status_code == 200
    alerts = resp.get_json()
    assert len(alerts) == 1
    assert alerts[0]["service_name"] == "db"


def test_filter_alerts_by_severity(client):
    client.post("/rules", json={"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"})
    client.post("/rules", json={"metric_type": "cpu", "threshold": 50, "operator": ">", "severity": "warning"})
    client.post("/alerts/evaluate", json={"service_name": "api", "metric_type": "cpu", "value": 90})
    resp = client.get("/alerts?severity=critical")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(a["severity"] == "critical" for a in data)
