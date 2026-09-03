"""Application service that connects HTTP contracts to the saved agent graph."""

from collections.abc import AsyncIterator
from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from incident_agent.agent_events import AgentStreamEvent
from incident_agent.api_models import (
    AgentInvokeRequest,
    AgentRunResponse,
    ApprovalResumeRequest,
    PublicMessage,
    PublicToolCall,
    ThreadHistoryResponse,
    ToolAuditResponse,
)
from incident_agent.approval_gate import HumanDecision
from incident_agent.graph_state import AgentState
from incident_agent.streaming_agent import stream_compiled_graph
from incident_agent.thread_archive import (
    checkpoint_load_latest,
    checkpoint_load_pending_approval,
    thread_prepare_turn,
    thread_resume_approval,
)
from incident_agent.tool_audit import ToolAuditLog
from incident_agent.trace_observer import RunTrace, TraceObserver


def _content_text(content: str | list[str | dict[str, object]]) -> str:
    """Convert one message's supported content shape into readable text."""

    if isinstance(content, str):
        return content
    return str(content)


def _public_message(message: BaseMessage) -> PublicMessage:
    """Translate one internal LangChain message into the stable HTTP view."""

    tool_calls: tuple[PublicToolCall, ...] = ()
    if isinstance(message, AIMessage):
        tool_calls = tuple(
            PublicToolCall(
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
                arguments=dict(tool_call["args"]),
            )
            for tool_call in message.tool_calls
        )

    return PublicMessage(
        message_type=message.type,
        content=message.content,
        tool_calls=tool_calls,
        tool_call_id=(
            message.tool_call_id if isinstance(message, ToolMessage) else None
        ),
        tool_name=(message.name if isinstance(message, ToolMessage) else None),
        tool_status=(message.status if isinstance(message, ToolMessage) else None),
    )


def _latest_answer(messages: list[BaseMessage]) -> str | None:
    """Find the newest final AI answer that contains no tool request."""

    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return _content_text(message.content)
    return None


def _latest_human_input(messages: list[BaseMessage]) -> str:
    """Find the newest human text used to label a trace."""

    for message in reversed(messages):
        if message.type == "human":
            return _content_text(message.content)
    return "unknown"


class AgentHttpService:
    """Own one checkpoint-backed graph and expose HTTP-shaped operations."""

    def __init__(
        self,
        graph: CompiledStateGraph,
        *,
        trace: TraceObserver | None = None,
        audit: ToolAuditLog | None = None,
    ) -> None:
        self._graph = graph
        self._trace = trace or TraceObserver()
        self._audit = audit or ToolAuditLog()

    async def _response_for_state(
        self,
        thread_id: str,
        state: AgentState,
    ) -> AgentRunResponse:
        """Build one public response from the newest graph state and interrupt."""

        approval = await checkpoint_load_pending_approval(self._graph, thread_id)
        return AgentRunResponse(
            status="approval_required" if approval is not None else "completed",
            run_id=state["run_id"],
            thread_id=thread_id,
            answer=_latest_answer(state["messages"]),
            model_calls=state["model_calls"],
            approval=approval,
            messages=tuple(_public_message(message) for message in state["messages"]),
        )

    async def invoke(self, request: AgentInvokeRequest) -> AgentRunResponse:
        """Start or continue one thread and return its newest public state."""

        graph_input, thread_address = await thread_prepare_turn(
            self._graph,
            request.thread_id,
            request.user_input,
        )
        run_id = graph_input["run_id"]
        self._trace.start_run(
            run_id=run_id,
            thread_id=request.thread_id,
            user_input=request.user_input,
        )
        try:
            state = await self._graph.ainvoke(graph_input, thread_address)
            response = await self._response_for_state(request.thread_id, state)
        except Exception as error:
            self._trace.fail_run(run_id, error)
            raise
        self._trace.capture_state(
            thread_id=request.thread_id,
            user_input=request.user_input,
            state=state,
            status=(
                "waiting_approval"
                if response.status == "approval_required"
                else "completed"
            ),
        )
        return response

    async def resume(self, request: ApprovalResumeRequest) -> AgentRunResponse:
        """Resume one approval interrupt and return the resulting public state."""

        previous = await checkpoint_load_latest(self._graph, request.thread_id)
        previous_state = (
            cast(AgentState, previous.values) if previous is not None else None
        )
        user_input = (
            _latest_human_input(previous_state["messages"])
            if previous_state is not None
            else "approval resume"
        )
        try:
            state = await thread_resume_approval(
                self._graph,
                request.thread_id,
                HumanDecision(
                    approved=request.approved,
                    operator=request.operator,
                    note=request.note,
                ),
            )
        except Exception as error:
            if (
                previous_state is not None
                and self._trace.get(previous_state["run_id"]) is not None
            ):
                self._trace.fail_run(previous_state["run_id"], error)
            raise
        response = await self._response_for_state(request.thread_id, state)
        self._trace.capture_state(
            thread_id=request.thread_id,
            user_input=user_input,
            state=state,
            status="completed",
        )
        return response

    async def history(self, thread_id: str) -> ThreadHistoryResponse | None:
        """Return the newest saved state for one thread, or none when unknown."""

        snapshot = await checkpoint_load_latest(self._graph, thread_id)
        if snapshot is None:
            return None

        state = cast(AgentState, snapshot.values)
        approval = await checkpoint_load_pending_approval(self._graph, thread_id)
        return ThreadHistoryResponse(
            run_id=state["run_id"],
            thread_id=thread_id,
            model_calls=state["model_calls"],
            approval=approval,
            messages=tuple(_public_message(message) for message in state["messages"]),
        )

    def trace(self, run_id: str) -> RunTrace | None:
        """Return one observed run trace without reading graph internals."""

        return self._trace.get(run_id)

    def audit(self, run_id: str) -> ToolAuditResponse:
        """Return tool attempts grouped by the run ID carried in graph state."""

        return ToolAuditResponse(
            run_id=run_id,
            records=self._audit.list_records(run_id=run_id),
        )

    async def _observe_stream(
        self,
        events: AsyncIterator[AgentStreamEvent],
        *,
        thread_id: str,
        user_input: str,
        run_id: str,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Forward events and capture the saved state after streaming stops."""

        try:
            async for event in events:
                yield event
        except Exception as error:
            self._trace.fail_run(run_id, error)
            raise

        snapshot = await checkpoint_load_latest(self._graph, thread_id)
        if snapshot is None:
            return
        state = cast(AgentState, snapshot.values)
        approval = await checkpoint_load_pending_approval(self._graph, thread_id)
        self._trace.capture_state(
            thread_id=thread_id,
            user_input=user_input,
            state=state,
            status="waiting_approval" if approval is not None else "completed",
        )

    async def open_stream(
        self,
        request: AgentInvokeRequest,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Prepare one thread turn before HTTP headers and return its event stream."""

        graph_input, thread_address = await thread_prepare_turn(
            self._graph,
            request.thread_id,
            request.user_input,
        )
        run_id = graph_input["run_id"]
        self._trace.start_run(
            run_id=run_id,
            thread_id=request.thread_id,
            user_input=request.user_input,
        )
        events = stream_compiled_graph(
            self._graph,
            graph_input,
            user_input=request.user_input,
            config=thread_address,
        )
        return self._observe_stream(
            events,
            thread_id=request.thread_id,
            user_input=request.user_input,
            run_id=run_id,
        )
