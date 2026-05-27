import os
import requests
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__)

METRICS_URL = os.environ.get("METRICS_SERVICE_URL", "http://localhost:5001")
ALERT_URL = os.environ.get("ALERT_SERVICE_URL", "http://localhost:5002")
API_KEY = os.environ.get("API_KEY", "dev-key-change-in-production")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


def authenticate():
    return request.headers.get("X-API-Key") == API_KEY


def proxy_request(method, url, **kwargs):
    try:
        resp = requests.request(method, url, timeout=5, **kwargs)
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Upstream service unavailable"}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Upstream service timed out"}), 504


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "api-gateway"})


@app.route("/api/metrics", methods=["GET", "POST"])
def metrics():
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401

    if request.method == "POST":
        data = request.get_json()
        resp = requests.request("POST", f"{METRICS_URL}/metrics", json=data, timeout=5)
        if resp.status_code == 201:
            requests.request("POST", f"{ALERT_URL}/alerts/evaluate", json=data, timeout=5)
        return Response(resp.content, status=resp.status_code, content_type="application/json")

    qs = request.query_string.decode()
    return proxy_request("GET", f"{METRICS_URL}/metrics?{qs}")


@app.route("/api/metrics/services", methods=["GET"])
def metric_services():
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401
    return proxy_request("GET", f"{METRICS_URL}/metrics/services")


@app.route("/api/metrics/summary", methods=["GET"])
def metrics_summary():
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401
    return proxy_request("GET", f"{METRICS_URL}/metrics/summary")


@app.route("/api/rules", methods=["GET", "POST"])
def rules():
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401
    if request.method == "POST":
        return proxy_request("POST", f"{ALERT_URL}/rules", json=request.get_json())
    return proxy_request("GET", f"{ALERT_URL}/rules")


@app.route("/api/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401
    return proxy_request("DELETE", f"{ALERT_URL}/rules/{rule_id}")


@app.route("/api/alerts", methods=["GET"])
def alerts():
    if not authenticate():
        return jsonify({"error": "Unauthorized - provide a valid X-API-Key header"}), 401
    qs = request.query_string.decode()
    return proxy_request("GET", f"{ALERT_URL}/alerts?{qs}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
