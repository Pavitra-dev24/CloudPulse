import os
import time
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

VALID_OPERATORS = [">", "<", ">=", "<="]
VALID_SEVERITIES = ["info", "warning", "critical"]


def get_db_path():
    return os.environ.get("DB_PATH", "alerts.db")


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT,
            metric_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            operator TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER,
            service_name TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value REAL NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "alert-service"})


@app.route("/rules", methods=["POST"])
def create_rule():
    data = request.get_json()
    required = ["metric_type", "threshold", "operator", "severity"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Missing required fields: metric_type, threshold, operator, severity"}), 400

    if data["operator"] not in VALID_OPERATORS:
        return jsonify({"error": "operator must be one of: >, <, >=, <="}), 400

    if data["severity"] not in VALID_SEVERITIES:
        return jsonify({"error": "severity must be one of: info, warning, critical"}), 400

    try:
        threshold = float(data["threshold"])
    except (ValueError, TypeError):
        return jsonify({"error": "threshold must be a number"}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO rules (service_name, metric_type, threshold, operator, severity) VALUES (?, ?, ?, ?, ?)",
        (data.get("service_name"), data["metric_type"], threshold, data["operator"], data["severity"]),
    )
    conn.commit()
    rule_id = cur.lastrowid
    conn.close()

    return jsonify({"id": rule_id, "message": "Rule created"}), 201


@app.route("/rules", methods=["GET"])
def list_rules():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rules ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    conn = get_db()
    result = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify({"message": "Rule deleted"})


@app.route("/alerts/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json()
    if not data or not all(k in data for k in ["service_name", "metric_type", "value"]):
        return jsonify({"error": "Missing required fields: service_name, metric_type, value"}), 400

    try:
        value = float(data["value"])
    except (ValueError, TypeError):
        return jsonify({"error": "value must be a number"}), 400

    service_name = str(data["service_name"])
    metric_type = str(data["metric_type"])

    conn = get_db()
    rules = conn.execute(
        "SELECT * FROM rules WHERE metric_type = ? AND (service_name IS NULL OR service_name = ?)",
        (metric_type, service_name),
    ).fetchall()

    triggered = []
    ts = int(time.time())

    for rule in rules:
        rule = dict(rule)
        op = rule["operator"]
        threshold = rule["threshold"]
        matched = (
            (op == ">" and value > threshold)
            or (op == "<" and value < threshold)
            or (op == ">=" and value >= threshold)
            or (op == "<=" and value <= threshold)
        )
        if matched:
            msg = f"{service_name}: {metric_type} is {value} ({op} {threshold} threshold breached)"
            conn.execute(
                "INSERT INTO alerts (rule_id, service_name, metric_type, value, severity, message, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rule["id"], service_name, metric_type, value, rule["severity"], msg, ts),
            )
            triggered.append({"rule_id": rule["id"], "severity": rule["severity"], "message": msg})

    conn.commit()
    conn.close()

    return jsonify({"triggered": triggered, "count": len(triggered)})


@app.route("/alerts", methods=["GET"])
def list_alerts():
    severity = request.args.get("severity")
    service = request.args.get("service")
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if service:
        query += " AND service_name = ?"
        params.append(service)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5002)
