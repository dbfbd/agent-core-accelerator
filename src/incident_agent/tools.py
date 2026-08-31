"""Deterministic, read-only incident investigation tools."""

from datetime import datetime, timedelta

from incident_agent.fixtures import (
    DEPLOYMENTS_BY_SERVICE,
    KNOWN_SERVICES,
    LOGS_BY_SERVICE,
    METRICS_BY_SERVICE,
)
from incident_agent.models import (
    DeploymentQuery,
    DeploymentRecord,
    LogEntry,
    LogSearchQuery,
    LogSearchResult,
    MetricPoint,
    MetricsQuery,
    RecentDeployments,
    ServiceMetrics,
    ServiceWindowQuery,
)

MAX_QUERY_WINDOW = timedelta(hours=24)


class UnknownServiceError(LookupError):
    """Raised when the requested service does not exist in the fixture catalog."""


class QueryWindowTooLargeError(ValueError):
    """Raised when a query exceeds the supported local time window."""


def _validate_business_rules(query: ServiceWindowQuery) -> None:
    if query.service not in KNOWN_SERVICES:
        raise UnknownServiceError(f"Unknown service: {query.service!r}")

    if query.end - query.start > MAX_QUERY_WINDOW:
        raise QueryWindowTooLargeError("Query window cannot exceed 24 hours")


def _is_in_window(timestamp: datetime, query: ServiceWindowQuery) -> bool:
    return query.start <= timestamp <= query.end


async def get_service_metrics(query: MetricsQuery) -> ServiceMetrics:
    """Return metric samples for a service and inclusive time window."""

    _validate_business_rules(query)

    points: list[MetricPoint] = []
    for point in METRICS_BY_SERVICE[query.service]:
        if _is_in_window(point.timestamp, query):
            points.append(point)

    return ServiceMetrics(
        service=query.service,
        start=query.start,
        end=query.end,
        points=points,
    )


async def search_logs(query: LogSearchQuery) -> LogSearchResult:
    """Return case-insensitive message matches in chronological order."""

    _validate_business_rules(query)
    search_text = query.query.casefold()

    entries: list[LogEntry] = []
    for entry in LOGS_BY_SERVICE[query.service]:
        if not _is_in_window(entry.timestamp, query):
            continue
        if search_text not in entry.message.casefold():
            continue

        entries.append(entry)
        if len(entries) >= query.limit:
            break

    return LogSearchResult(
        service=query.service,
        query=query.query,
        entries=entries,
    )


async def get_recent_deployments(query: DeploymentQuery) -> RecentDeployments:
    """Return deployment records for a service and inclusive time window."""

    _validate_business_rules(query)

    deployments: list[DeploymentRecord] = []
    for deployment in DEPLOYMENTS_BY_SERVICE[query.service]:
        if _is_in_window(deployment.timestamp, query):
            deployments.append(deployment)

    return RecentDeployments(
        service=query.service,
        deployments=deployments,
    )
