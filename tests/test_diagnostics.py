"""Tests for the minimal asynchronous diagnostic flow."""

from inspect import iscoroutine
from unittest.mock import AsyncMock

import pytest

from incident_agent.diagnostics import (
    EvidenceUnavailableError,
    PreparedIncident,
    prepare_incident,
    stream_preparation_events,
)
from incident_agent.models import IncidentRequest


@pytest.mark.asyncio
async def test_prepare_incident_awaits_loader_and_returns_result() -> None:
    request = IncidentRequest(
        service="checkout-api",
        question="Why are requests failing?",
    )
    status_loader = AsyncMock(return_value="degraded")

    operation = prepare_incident(request, status_loader)
    assert iscoroutine(operation)

    result = await operation

    assert result == PreparedIncident(
        service="checkout-api",
        question="Why are requests failing?",
        status="degraded",
    )
    status_loader.assert_awaited_once_with("checkout-api")


@pytest.mark.asyncio
async def test_prepare_incident_raises_when_evidence_is_unavailable() -> None:
    request = IncidentRequest(
        service="checkout-api",
        question="Why are requests failing?",
    )
    status_loader = AsyncMock(return_value=None)

    with pytest.raises(EvidenceUnavailableError, match="checkout-api"):
        await prepare_incident(request, status_loader)


@pytest.mark.asyncio
async def test_stream_preparation_events_yields_events_in_order() -> None:
    request = IncidentRequest(
        service="checkout-api",
        question="Why are requests failing?",
    )
    status_loader = AsyncMock(return_value="degraded")

    events = [
        event async for event in stream_preparation_events(request, status_loader)
    ]

    assert events == [
        "status_loading:checkout-api",
        "status_loaded:degraded",
    ]
