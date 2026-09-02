"""Translate LangGraph state updates into stable application events."""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from incident_agent.agent_events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    AgentStreamEvent,
    ApprovalRequiredEvent,
    ToolCompletedEvent,
    ToolRequest,
    ToolsRequestedEvent,
)
from incident_agent.agent_loop import ToolBindableModel
from incident_agent.approval_gate import ApprovalTicket
from incident_agent.graph_agent import build_agent_graph, create_initial_state
from incident_agent.graph_state import AgentState, AgentStateUpdate


class UnexpectedStreamUpdateError(RuntimeError):
    """Raised when an internal graph update breaks the event contract."""


def _message_text(content: str | list[str | dict[str, object]]) -> str:
    """Keep text content readable in the public teaching event model."""

    if isinstance(content, str):
        return content
    return str(content)


async def stream_compiled_graph(
    graph: CompiledStateGraph,
    graph_input: AgentState | AgentStateUpdate,
    *,
    user_input: str,
    config: RunnableConfig | None = None,
) -> AsyncIterator[AgentStreamEvent]:
    """Translate one compiled graph run into stable public business events."""

    yield AgentStartedEvent(user_input=user_input)
    final_answer: str | None = None
    final_model_calls = 0

    async for part in graph.astream(
        graph_input,
        config,
        stream_mode="updates",
        version="v2",
    ):
        for node_name, update in part["data"].items():
            if node_name == "__interrupt__":
                interruption = update[0]
                yield ApprovalRequiredEvent(
                    ticket=ApprovalTicket.model_validate(interruption.value)
                )
                return

            messages = update.get("messages", [])

            if node_name == "model":
                ai_message = messages[-1]
                if not isinstance(ai_message, AIMessage):
                    raise UnexpectedStreamUpdateError(
                        "The model update must contain an AIMessage"
                    )

                model_call = update["model_calls"]
                if ai_message.tool_calls:
                    yield ToolsRequestedEvent(
                        model_call=model_call,
                        requests=tuple(
                            ToolRequest(
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                            for tool_call in ai_message.tool_calls
                        ),
                    )
                else:
                    final_model_calls = model_call
                    final_answer = _message_text(ai_message.content)

            elif node_name == "tools":
                for message in messages:
                    if not isinstance(message, ToolMessage):
                        raise UnexpectedStreamUpdateError(
                            "The tools update must contain only ToolMessage objects"
                        )
                    yield ToolCompletedEvent(
                        name=message.name or "unknown",
                        tool_call_id=message.tool_call_id,
                        content=_message_text(message.content),
                    )

    if final_answer is None:
        raise UnexpectedStreamUpdateError(
            "The graph ended without a final AIMessage answer"
        )
    yield AgentCompletedEvent(
        model_calls=final_model_calls,
        answer=final_answer,
    )


async def stream_graph_agent(
    model: ToolBindableModel,
    user_input: str,
    max_model_calls: int = 4,
) -> AsyncIterator[AgentStreamEvent]:
    """Build one temporary graph and yield its public business events."""

    graph = build_agent_graph(model, max_model_calls)
    async for event in stream_compiled_graph(
        graph,
        create_initial_state(user_input),
        user_input=user_input,
    ):
        yield event
