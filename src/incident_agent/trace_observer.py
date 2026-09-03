"""In-memory run tracing reconstructed from complete Agent message state."""

from datetime import UTC, datetime
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import BaseModel, ConfigDict

from incident_agent.graph_state import AgentState

type RunStatus = Literal["running", "waiting_approval", "completed", "failed"]


class TraceStep(BaseModel):
    """One ordered, public-safe step in an Agent run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int
    message_type: str
    detail: str
    tool_call_ids: tuple[str, ...] = ()


class RunTrace(BaseModel):
    """Complete observable summary for one Agent run ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    thread_id: str
    user_input: str
    status: RunStatus
    started_at: datetime
    updated_at: datetime
    error: str | None = None
    steps: tuple[TraceStep, ...] = ()


def _message_detail(message: BaseMessage) -> str:
    """Create a compact trace description without exposing hidden model internals."""

    if isinstance(message, AIMessage) and message.tool_calls:
        names = ", ".join(tool_call["name"] for tool_call in message.tool_calls)
        return f"model requested tools: {names}"
    if isinstance(message, ToolMessage):
        return f"tool {message.name or 'unknown'} returned status={message.status}"
    content = (
        message.content if isinstance(message.content, str) else str(message.content)
    )
    return content[:300]


def _trace_steps(messages: list[BaseMessage]) -> tuple[TraceStep, ...]:
    """Translate every saved message into one ordered trace step."""

    return tuple(
        TraceStep(
            sequence=position,
            message_type=type(message).__name__,
            detail=_message_detail(message),
            tool_call_ids=(
                tuple(tool_call["id"] for tool_call in message.tool_calls)
                if isinstance(message, AIMessage)
                else (
                    (message.tool_call_id,) if isinstance(message, ToolMessage) else ()
                )
            ),
        )
        for position, message in enumerate(messages, start=1)
    )


class TraceObserver:
    """Start, update, fail, and query Agent run traces."""

    def __init__(self) -> None:
        self._traces: dict[str, RunTrace] = {}

    def start_run(self, *, run_id: str, thread_id: str, user_input: str) -> None:
        """Create the initial running trace before graph execution."""

        now = datetime.now(UTC)
        self._traces[run_id] = RunTrace(
            run_id=run_id,
            thread_id=thread_id,
            user_input=user_input,
            status="running",
            started_at=now,
            updated_at=now,
        )

    def capture_state(
        self,
        *,
        thread_id: str,
        user_input: str,
        state: AgentState,
        status: RunStatus,
    ) -> RunTrace:
        """Replace a run trace with steps rebuilt from the newest complete state."""

        run_id = state["run_id"]
        previous = self._traces.get(run_id)
        trace = RunTrace(
            run_id=run_id,
            thread_id=thread_id,
            user_input=user_input,
            status=status,
            started_at=(previous.started_at if previous else datetime.now(UTC)),
            updated_at=datetime.now(UTC),
            steps=_trace_steps(state["messages"]),
        )
        self._traces[run_id] = trace
        return trace

    def fail_run(self, run_id: str, error: Exception) -> RunTrace:
        """Mark an already started run as failed with a readable reason."""

        previous = self._traces[run_id]
        trace = previous.model_copy(
            update={
                "status": "failed",
                "updated_at": datetime.now(UTC),
                "error": str(error),
            }
        )
        self._traces[run_id] = trace
        return trace

    def get(self, run_id: str) -> RunTrace | None:
        """Return one immutable run trace when known."""

        return self._traces.get(run_id)
