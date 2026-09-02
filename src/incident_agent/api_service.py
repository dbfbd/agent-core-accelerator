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
)
from incident_agent.approval_gate import HumanDecision
from incident_agent.graph_state import AgentState
from incident_agent.streaming_agent import stream_compiled_graph
from incident_agent.thread_archive import (
    checkpoint_load_latest,
    checkpoint_load_pending_approval,
    thread_continue,
    thread_prepare_turn,
    thread_resume_approval,
)


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


class AgentHttpService:
    """Own one checkpoint-backed graph and expose HTTP-shaped operations."""

    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph

    async def _response_for_state(
        self,
        thread_id: str,
        state: AgentState,
    ) -> AgentRunResponse:
        """Build one public response from the newest graph state and interrupt."""

        approval = await checkpoint_load_pending_approval(self._graph, thread_id)
        return AgentRunResponse(
            status="approval_required" if approval is not None else "completed",
            thread_id=thread_id,
            answer=_latest_answer(state["messages"]),
            model_calls=state["model_calls"],
            approval=approval,
            messages=tuple(_public_message(message) for message in state["messages"]),
        )

    async def invoke(self, request: AgentInvokeRequest) -> AgentRunResponse:
        """Start or continue one thread and return its newest public state."""

        state = await thread_continue(
            self._graph,
            request.thread_id,
            request.user_input,
        )
        return await self._response_for_state(request.thread_id, state)

    async def resume(self, request: ApprovalResumeRequest) -> AgentRunResponse:
        """Resume one approval interrupt and return the resulting public state."""

        state = await thread_resume_approval(
            self._graph,
            request.thread_id,
            HumanDecision(
                approved=request.approved,
                operator=request.operator,
                note=request.note,
            ),
        )
        return await self._response_for_state(request.thread_id, state)

    async def history(self, thread_id: str) -> ThreadHistoryResponse | None:
        """Return the newest saved state for one thread, or none when unknown."""

        snapshot = await checkpoint_load_latest(self._graph, thread_id)
        if snapshot is None:
            return None

        state = cast(AgentState, snapshot.values)
        approval = await checkpoint_load_pending_approval(self._graph, thread_id)
        return ThreadHistoryResponse(
            thread_id=thread_id,
            model_calls=state["model_calls"],
            approval=approval,
            messages=tuple(_public_message(message) for message in state["messages"]),
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
        return stream_compiled_graph(
            self._graph,
            graph_input,
            user_input=request.user_input,
            config=thread_address,
        )
