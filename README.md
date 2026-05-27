# CloudPulse

A cloud-native distributed metrics and alerting system built with a microservices architecture. CloudPulse collects real-time service metrics, evaluates them against configurable threshold rules, and surfaces triggered alerts through a unified REST API and web dashboard.

This project demonstrates full-stack development across distributed services, containerized deployments with Docker, automated CI/CD pipelines, and security-first API design.

---

## Architecture

```
                        +---------------------+
                        |     Web Browser     |
                        |   (Dashboard UI)    |
                        +----------+----------+
                                   |
                                   v
                        +----------+----------+
                        |     API Gateway     |  :5000
                        |  Auth + Routing +   |
                        |  Frontend Static    |
                        +----+----------+-----+
                             |          |
               +-------------+          +-------------+
               |                                      |
               v                                      v
  +------------+-----------+          +--------------+---------+
  |    Metrics Service     |          |      Alert Service     |
  |  Ingest + Query +      |  :5001   |  Rules + Evaluation +  |  :5002
  |  Aggregation API       |          |  Alert History API     |
  +------------------------+          +------------------------+
               |                                      |
               v                                      v
        [metrics.db]                           [alerts.db]
         (SQLite)                               (SQLite)
```

**Data flow:** A client POSTs a metric to the gateway. The gateway forwards it to the metrics service for storage and simultaneously triggers the alert service to evaluate the value against all matching rules. If a threshold is breached, an alert is persisted and returned in the response.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web Framework | Flask 3.x |
| Database | SQLite (per-service, isolated storage) |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Testing | pytest |
| Architecture | Microservices, REST, API Gateway pattern |

---

## Features

- **Microservices architecture** - three independently deployable services with clear separation of concerns
- **API Gateway** - single entry point for all clients, handles authentication and routes requests downstream
- **Real-time metric ingestion** - ingest CPU, memory, disk, latency, and error rate metrics per service
- **Threshold-based alerting** - configurable rules with operators (>, <, >=, <=) and severity levels (info, warning, critical)
- **Service-scoped rules** - rules can apply globally or target a specific service
- **Aggregation endpoint** - per-service averages, min, and max values across metric types
- **Security-first design** - all API endpoints protected by API key authentication
- **Graceful error handling** - 503 on upstream unavailability, 504 on timeout, input validation on all routes
- **Health checks** - all services expose a health endpoint used by Docker Compose readiness probes
- **Web dashboard** - live dashboard served by the gateway for submitting metrics and viewing alerts
- **Automated tests** - 30+ unit and integration tests across all three services
- **CI/CD pipeline** - GitHub Actions runs all test suites and builds Docker images on every push

---

## Getting Started

### Option 1: Docker Compose (recommended)

```bash
git clone https://github.com/your-username/cloudpulse.git
cd cloudpulse
docker compose up --build
```

The dashboard is available at `http://localhost:5000`.

Default API key: `dev-key-change-in-production`

To use a custom key, set the environment variable before starting:

```bash
API_KEY=your-secret-key docker compose up --build
```

### Option 2: Run services manually

You need Python 3.11 and pip. Open three terminals.

**Terminal 1 - Metrics Service**
```bash
cd metrics-service
pip install -r requirements.txt
python app.py
```

**Terminal 2 - Alert Service**
```bash
cd alert-service
pip install -r requirements.txt
python app.py
```

**Terminal 3 - API Gateway**
```bash
cd api-gateway
pip install -r requirements.txt
METRICS_SERVICE_URL=http://localhost:5001 ALERT_SERVICE_URL=http://localhost:5002 python app.py
```

---

## API Reference

All endpoints require the header `X-API-Key: <your-key>`.

### Metrics

| Method | Path | Description |
|---|---|---|
| POST | /api/metrics | Ingest a metric |
| GET | /api/metrics | List recent metrics (supports ?service, ?type, ?limit) |
| GET | /api/metrics/services | List all distinct service names |
| GET | /api/metrics/summary | Per-service aggregated stats (avg, min, max) |

**POST /api/metrics**
```json
{
  "service_name": "auth-api",
  "metric_type": "cpu",
  "value": 78.5
}
```

### Alert Rules

| Method | Path | Description |
|---|---|---|
| POST | /api/rules | Create a threshold rule |
| GET | /api/rules | List all rules |
| DELETE | /api/rules/{id} | Delete a rule |

**POST /api/rules**
```json
{
  "metric_type": "cpu",
  "operator": ">",
  "threshold": 80,
  "severity": "critical",
  "service_name": "auth-api"
}
```

Valid operators: `>`, `<`, `>=`, `<=`
Valid severities: `info`, `warning`, `critical`
`service_name` is optional - omitting it applies the rule to all services.

### Alerts

| Method | Path | Description |
|---|---|---|
| GET | /api/alerts | List triggered alerts (supports ?severity, ?service, ?limit) |

---

## Example Workflow

```bash
API_KEY="dev-key-change-in-production"

# 1. Create a rule: alert when CPU exceeds 80 percent
curl -X POST http://localhost:5000/api/rules \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"metric_type": "cpu", "threshold": 80, "operator": ">", "severity": "critical"}'

# 2. Send a metric that breaches the rule
curl -X POST http://localhost:5000/api/metrics \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"service_name": "auth-api", "metric_type": "cpu", "value": 95}'

# 3. Check triggered alerts
curl http://localhost:5000/api/alerts \
  -H "X-API-Key: $API_KEY"

# 4. View aggregated summary
curl http://localhost:5000/api/metrics/summary \
  -H "X-API-Key: $API_KEY"
```

---

## Running Tests

Each service has its own isolated test suite using pytest and an in-memory SQLite database. No running services are required.

```bash
# Metrics service tests
pip install -r metrics-service/requirements.txt
pytest metrics-service/tests/ -v

# Alert service tests
pip install -r alert-service/requirements.txt
pytest alert-service/tests/ -v

# API Gateway tests (uses mocks for upstream services)
pip install -r api-gateway/requirements.txt
pytest api-gateway/tests/ -v
```

---

## CI/CD Pipeline

GitHub Actions runs on every push and pull request to `main`.

```
push to main
    |
    +-- test-metrics-service   (pytest)
    +-- test-alert-service     (pytest)
    +-- test-api-gateway       (pytest with mocked upstreams)
    |
    +-- docker-build           (runs only after all tests pass)
```

The pipeline enforces that no Docker image is built unless all tests pass.

---

## Project Structure

```
cloudpulse/
├── .github/
│   └── workflows/
│       └── ci.yml
├── metrics-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       └── test_metrics.py
├── alert-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       └── test_alerts.py
├── api-gateway/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── frontend/
│   │   └── index.html
│   └── tests/
│       └── test_gateway.py
├── docker-compose.yml
└── README.md
```

---

## Design Decisions

**Why separate databases per service?**
Each service owns its own data store, following the database-per-service principle in distributed systems design. This ensures services are independently deployable and failures in one do not corrupt another.

**Why an API gateway?**
The gateway centralizes authentication and decouples clients from the internal service topology. Downstream services are not exposed directly and can be changed without affecting clients.

**Why SQLite?**
SQLite is sufficient for a demonstration of this scope and requires zero infrastructure setup. Replacing it with PostgreSQL or another database would require only changing the connection string in each service.

**Why synchronous alert evaluation on metric ingestion?**
For simplicity and clarity in a demo context. A production system would use a message queue (RabbitMQ, Kafka) to decouple ingestion from evaluation and support higher throughput.

---

## License

MIT
