import os
import time
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)


def get_db_path():
    return os.environ.get("DB_PATH", "metrics.db")


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value REAL NOT NULL,
            timestamp INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "metrics-service"})


@app.route("/metrics", methods=["POST"])
def ingest_metric():
    data = request.get_json()
    if not data or not all(k in data for k in ["service_name", "metric_type", "value"]):
        return jsonify({"error": "Missing required fields: service_name, metric_type, value"}), 400

    try:
        value = float(data["value"])
    except (ValueError, TypeError):
        return jsonify({"error": "value must be a number"}), 400

    service_name = str(data["service_name"]).strip()
    metric_type = str(data["metric_type"]).strip()

    if not service_name or not metric_type:
        return jsonify({"error": "service_name and metric_type must not be empty"}), 400

    timestamp = int(data.get("timestamp", time.time()))

    conn = get_db()
    conn.execute(
        "INSERT INTO metrics (service_name, metric_type, value, timestamp) VALUES (?, ?, ?, ?)",
        (service_name, metric_type, value, timestamp),
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Metric recorded", "service_name": service_name, "metric_type": metric_type, "value": value}), 201


@app.route("/metrics", methods=["GET"])
def list_metrics():
    service = request.args.get("service")
    metric_type = request.args.get("type")
    try:
        limit = min(int(request.args.get("limit", 100)), 1000)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    query = "SELECT * FROM metrics WHERE 1=1"
    params = []

    if service:
        query += " AND service_name = ?"
        params.append(service)
    if metric_type:
        query += " AND metric_type = ?"
        params.append(metric_type)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@app.route("/metrics/services", methods=["GET"])
def list_services():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT service_name FROM metrics ORDER BY service_name").fetchall()
    conn.close()
    return jsonify([r["service_name"] for r in rows])


@app.route("/metrics/summary", methods=["GET"])
def summary():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT service_name, metric_type,
               ROUND(AVG(value), 2) AS avg_value,
               ROUND(MIN(value), 2) AS min_value,
               ROUND(MAX(value), 2) AS max_value,
               COUNT(*) AS total
        FROM metrics
        GROUP BY service_name, metric_type
        ORDER BY service_name, metric_type
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001)
