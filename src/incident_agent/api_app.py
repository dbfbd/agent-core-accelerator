"""FastAPI routes that expose the checkpoint-backed incident agent."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.sse import EventSourceResponse, ServerSentEvent

from incident_agent.agent_events import AgentStreamEvent
from incident_agent.agent_loop import AgentStepLimitError, ToolBindableModel
from incident_agent.api_models import (
    AgentInvokeRequest,
    AgentRunResponse,
    ApprovalResumeRequest,
    HealthResponse,
    ThreadHistoryResponse,
    ToolAuditResponse,
)
from incident_agent.api_service import AgentHttpService
from incident_agent.streaming_agent import UnexpectedStreamUpdateError
from incident_agent.thread_archive import (
    NoPendingApprovalError,
    PendingApprovalError,
    checkpoint_build_resumable_agent,
)
from incident_agent.tool_runtime import ToolRuntime, build_default_tool_runtime
from incident_agent.trace_observer import RunTrace, TraceObserver

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)
type AgentServiceContextFactory = Callable[
    [], AbstractAsyncContextManager[AgentHttpService]
]


@asynccontextmanager
async def _default_service_context(
    app: FastAPI,
) -> AsyncIterator[AgentHttpService]:
    """Build the original in-memory service used by focused module examples."""

    graph = checkpoint_build_resumable_agent(
        app.state.agent_model,
        tool_runtime=app.state.tool_runtime,
    )
    yield AgentHttpService(
        graph,
        trace=app.state.trace_observer,
        audit=app.state.tool_runtime.audit,
    )


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open one service context and release all owned resources at shutdown."""

    factory: AgentServiceContextFactory | None = app.state.service_context_factory
    context = factory() if factory is not None else _default_service_context(app)
    async with context as service:
        app.state.agent_service = service
        try:
            yield
        finally:
            del app.state.agent_service


def get_agent_service(request: Request) -> AgentHttpService:
    """Read the application service created by the lifespan startup step."""

    return request.app.state.agent_service


def require_bearer(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> str:
    """Reject requests whose Bearer token does not match the configured secret."""

    if credentials is None or not compare_digest(
        credentials.credentials,
        request.app.state.api_token,
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


AgentServiceDependency = Annotated[AgentHttpService, Depends(get_agent_service)]
AuthenticatedCaller = Annotated[str, Depends(require_bearer)]
ThreadIdPath = Annotated[
    str,
    Path(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
RunIdPath = Annotated[
    str,
    Path(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the HTTP process is alive without invoking the agent."""

    return HealthResponse()


@router.post("/invoke", response_model=AgentRunResponse)
async def invoke_agent(
    payload: AgentInvokeRequest,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> AgentRunResponse:
    """Run one complete agent turn and return JSON or an approval request."""

    try:
        return await service.invoke(payload)
    except PendingApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/resume", response_model=AgentRunResponse)
async def resume_agent(
    payload: ApprovalResumeRequest,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> AgentRunResponse:
    """Resume one paused approval thread with a validated human decision."""

    try:
        return await service.resume(payload)
    except NoPendingApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/history/{thread_id}", response_model=ThreadHistoryResponse)
async def history(
    thread_id: ThreadIdPath,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> ThreadHistoryResponse:
    """Return the newest saved messages and pending approval for one thread."""

    response = await service.history(thread_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Unknown thread_id")
    return response


@router.get("/trace/{run_id}", response_model=RunTrace)
async def trace(
    run_id: RunIdPath,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> RunTrace:
    """Return the reconstructed message trace for one Agent run."""

    response = service.trace(run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return response


@router.get("/audit/{run_id}", response_model=ToolAuditResponse)
async def audit(
    run_id: RunIdPath,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> ToolAuditResponse:
    """Return every recorded tool attempt for one Agent run."""

    if service.trace(run_id) is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return service.audit(run_id)


async def _sse_events(
    events: AsyncIterator[AgentStreamEvent],
) -> AsyncIterator[ServerSentEvent]:
    """Convert public agent events into named Server-Sent Events."""

    try:
        async for event in events:
            yield ServerSentEvent(data=event, event=event.event)
    except (
        AgentStepLimitError,
        LookupError,
        PermissionError,
        UnexpectedStreamUpdateError,
        ValueError,
    ) as error:
        yield ServerSentEvent(
            data={"error": str(error)},
            event="error",
        )


@router.post("/stream", response_class=EventSourceResponse)
async def stream_agent(
    payload: AgentInvokeRequest,
    service: AgentServiceDependency,
    _caller: AuthenticatedCaller,
) -> AsyncIterator[ServerSentEvent]:
    """Open one SSE response that emits each agent business event in order."""

    try:
        events = await service.open_stream(payload)
    except PendingApprovalError as error:
        yield ServerSentEvent(data={"error": str(error)}, event="error")
        return

    async for event in _sse_events(events):
        yield event


def create_app(
    *,
    model: ToolBindableModel | None = None,
    api_token: str,
    tool_runtime: ToolRuntime | None = None,
    trace_observer: TraceObserver | None = None,
    service_context_factory: AgentServiceContextFactory | None = None,
) -> FastAPI:
    """Create FastAPI around either focused parts or a complete service context."""

    if not api_token.strip():
        raise ValueError("api_token must not be empty")
    if model is None and service_context_factory is None:
        raise ValueError("model or service_context_factory must be supplied")

    app = FastAPI(
        title="Reliable DevOps Incident Agent",
        version="0.1.0",
        lifespan=app_lifespan,
    )
    app.state.agent_model = model
    app.state.api_token = api_token
    app.state.tool_runtime = tool_runtime or build_default_tool_runtime()
    app.state.trace_observer = trace_observer or TraceObserver()
    app.state.service_context_factory = service_context_factory
    app.include_router(router)
    return app
