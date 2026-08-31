"""Tests for deterministic, read-only incident tools."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from incident_agent.models import DeploymentQuery, LogSearchQuery, MetricsQuery
from incident_agent.tools import (
    QueryWindowTooLargeError,
    UnknownServiceError,
    get_recent_deployments,
    get_service_metrics,
    search_logs,
)


@pytest.mark.asyncio
async def test_get_service_metrics_filters_by_time_window() -> None:
    query = MetricsQuery(
        service="checkout-api",
        start=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 20, 10, 5, tzinfo=UTC),
    )

    result = await get_service_metrics(query)

    assert [point.evidence_id for point in result.points] == [
        "metric-checkout-1000",
        "metric-checkout-1005",
    ]


@pytest.mark.asyncio
async def test_get_service_metrics_returns_empty_result() -> None:
    query = MetricsQuery(
        service="checkout-api",
        start=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
        end=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )

    result = await get_service_metrics(query)

    assert result.points == []


@pytest.mark.asyncio
async def test_search_logs_is_case_insensitive_and_honors_limit() -> None:
    query = LogSearchQuery(
        service="checkout-api",
        start=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 20, 10, 10, tzinfo=UTC),
        query="PAYMENT UPSTREAM",
        limit=1,
    )

    result = await search_logs(query)

    assert [entry.evidence_id for entry in result.entries] == ["log-checkout-1006"]


@pytest.mark.asyncio
async def test_search_logs_returns_empty_result() -> None:
    query = LogSearchQuery(
        service="inventory-api",
        start=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
        query="timeout",
    )

    result = await search_logs(query)

    assert result.entries == []


@pytest.mark.asyncio
async def test_get_recent_deployments_filters_by_time_window() -> None:
    query = DeploymentQuery(
        service="checkout-api",
        start=datetime(2026, 8, 20, 9, 45, tzinfo=UTC),
        end=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
    )

    result = await get_recent_deployments(query)

    assert [deployment.evidence_id for deployment in result.deployments] == [
        "deploy-checkout-v240"
    ]


@pytest.mark.asyncio
async def test_tool_rejects_unknown_service() -> None:
    query = MetricsQuery(
        service="ghost-api",
        start=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        end=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
    )

    with pytest.raises(UnknownServiceError, match="ghost-api"):
        await get_service_metrics(query)


@pytest.mark.asyncio
async def test_tool_rejects_query_window_larger_than_24_hours() -> None:
    start = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)
    query = DeploymentQuery(
        service="checkout-api",
        start=start,
        end=start + timedelta(hours=25),
    )

    with pytest.raises(QueryWindowTooLargeError, match="24 hours"):
        await get_recent_deployments(query)


def test_query_model_rejects_reversed_time_window() -> None:
    with pytest.raises(ValidationError, match="end must be later than start"):
        MetricsQuery(
            service="checkout-api",
            start=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
            end=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        )
