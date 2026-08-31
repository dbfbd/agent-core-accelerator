"""Deterministic local evidence for the incident lab."""

from datetime import UTC, datetime

from incident_agent.models import DeploymentRecord, LogEntry, MetricPoint

KNOWN_SERVICES = frozenset({"checkout-api", "inventory-api"})

METRICS_BY_SERVICE: dict[str, tuple[MetricPoint, ...]] = {
    "checkout-api": (
        MetricPoint(
            evidence_id="metric-checkout-1000",
            timestamp=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
            request_count=1200,
            error_rate=0.01,
            p95_latency_ms=180,
        ),
        MetricPoint(
            evidence_id="metric-checkout-1005",
            timestamp=datetime(2026, 8, 20, 10, 5, tzinfo=UTC),
            request_count=1180,
            error_rate=0.18,
            p95_latency_ms=1250,
        ),
        MetricPoint(
            evidence_id="metric-checkout-1010",
            timestamp=datetime(2026, 8, 20, 10, 10, tzinfo=UTC),
            request_count=1110,
            error_rate=0.21,
            p95_latency_ms=1510,
        ),
    ),
    "inventory-api": (
        MetricPoint(
            evidence_id="metric-inventory-1005",
            timestamp=datetime(2026, 8, 20, 10, 5, tzinfo=UTC),
            request_count=640,
            error_rate=0.002,
            p95_latency_ms=95,
        ),
    ),
}

LOGS_BY_SERVICE: dict[str, tuple[LogEntry, ...]] = {
    "checkout-api": (
        LogEntry(
            evidence_id="log-checkout-1004",
            timestamp=datetime(2026, 8, 20, 10, 4, tzinfo=UTC),
            level="INFO",
            message="checkout request accepted",
        ),
        LogEntry(
            evidence_id="log-checkout-1006",
            timestamp=datetime(2026, 8, 20, 10, 6, tzinfo=UTC),
            level="ERROR",
            message="payment upstream timeout after 2.0s",
        ),
        LogEntry(
            evidence_id="log-checkout-1007",
            timestamp=datetime(2026, 8, 20, 10, 7, tzinfo=UTC),
            level="ERROR",
            message="payment upstream timeout after 2.0s",
        ),
        LogEntry(
            evidence_id="log-checkout-1008",
            timestamp=datetime(2026, 8, 20, 10, 8, tzinfo=UTC),
            level="WARNING",
            message="payment retry budget exhausted",
        ),
    ),
    "inventory-api": (),
}

DEPLOYMENTS_BY_SERVICE: dict[str, tuple[DeploymentRecord, ...]] = {
    "checkout-api": (
        DeploymentRecord(
            evidence_id="deploy-checkout-v240",
            timestamp=datetime(2026, 8, 20, 9, 50, tzinfo=UTC),
            version="2.4.0",
            commit_sha="a1b2c3d",
            status="succeeded",
        ),
        DeploymentRecord(
            evidence_id="deploy-checkout-v239",
            timestamp=datetime(2026, 8, 19, 16, 0, tzinfo=UTC),
            version="2.3.9",
            commit_sha="9f8e7d6",
            status="succeeded",
        ),
    ),
    "inventory-api": (),
}
