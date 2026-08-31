"""Minimal asynchronous incident preparation flow."""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from incident_agent.models import IncidentRequest

type StatusLoader = Callable[[str], Awaitable[str | None]]


class EvidenceUnavailableError(RuntimeError):
    """Raised when no status evidence is available for a service."""


@dataclass(frozen=True, slots=True)
class PreparedIncident:
    """Validated request combined with asynchronously loaded status evidence."""

    service: str
    question: str
    status: str


async def prepare_incident(
    request: IncidentRequest,
    status_loader: StatusLoader,
) -> PreparedIncident:
    """Load service status and prepare the first internal incident object."""

    status = await status_loader(request.service)
    if status is None:
        raise EvidenceUnavailableError(
            f"No status evidence is available for service {request.service!r}"
        )

    return PreparedIncident(
        service=request.service,
        question=request.question,
        status=status,
    )


async def stream_preparation_events(
    request: IncidentRequest,
    status_loader: StatusLoader,
) -> AsyncIterator[str]:
    """Yield minimal progress events around incident preparation."""

    yield f"status_loading:{request.service}"
    prepared = await prepare_incident(request, status_loader)
    yield f"status_loaded:{prepared.status}"
