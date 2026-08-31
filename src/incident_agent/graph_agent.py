"""LangGraph version of the model-to-tool-to-model agent loop."""

from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from incident_agent.agent_loop import (
    SYSTEM_PROMPT,
    AgentStepLimitError,
    AsyncChatModel,
    ToolBindableModel,
)
from incident_agent.graph_state import AgentState, AgentStateUpdate
from incident_agent.tool_runtime import TOOL_SCHEMAS, execute_tool_call

type ModelNode = Callable[[AgentState], Awaitable[AgentStateUpdate]]
type NextNode = Literal["tools", "__end__"]


class UnexpectedGraphStateError(RuntimeError):
    """Raised when a graph node receives an impossible message sequence."""


def _make_model_node(
    model: AsyncChatModel,
    max_model_calls: int,
) -> ModelNode:
    """Create a graph node that calls one already tool-bound model."""

    async def call_model(state: AgentState) -> AgentStateUpdate:
        if state["model_calls"] >= max_model_calls:
            raise AgentStepLimitError(
                f"Model did not produce a final answer after {max_model_calls} calls"
            )

        ai_message = await model.ainvoke(state["messages"])
        return {
            "messages": [ai_message],
            "model_calls": state["model_calls"] + 1,
        }

    return call_model


def _last_ai_message(state: AgentState) -> AIMessage:
    """Return the last message after checking the graph's message contract."""

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        raise UnexpectedGraphStateError(
            "The model and tools nodes require the last message to be an AIMessage"
        )
    return last_message


def route_after_model(state: AgentState) -> NextNode:
    """Choose the tools node when the model requested tools, otherwise finish."""

    if _last_ai_message(state).tool_calls:
        return "tools"
    return END


async def execute_tools(state: AgentState) -> AgentStateUpdate:
    """Execute every tool call requested by the latest AI message."""

    ai_message = _last_ai_message(state)
    tool_messages = []
    for tool_call in ai_message.tool_calls:
        tool_messages.append(await execute_tool_call(tool_call))
    return {"messages": tool_messages}


def build_agent_graph(
    model: ToolBindableModel,
    max_model_calls: int = 4,
    *,
    checkpoint_saver: BaseCheckpointSaver | None = None,
    knowledge_store: BaseStore | None = None,
) -> CompiledStateGraph:
    """Define nodes and edges, then compile an executable agent graph."""

    bound_model = model.bind_tools(TOOL_SCHEMAS)
    builder = StateGraph(AgentState)

    builder.add_node("model", _make_model_node(bound_model, max_model_calls))
    builder.add_node("tools", execute_tools)

    builder.add_edge(START, "model")
    builder.add_conditional_edges(
        "model",
        route_after_model,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "model")

    return builder.compile(
        checkpointer=checkpoint_saver,
        store=knowledge_store,
    )


def create_initial_state(user_input: str) -> AgentState:
    """Create the shared starting state used by every graph run mode."""

    return {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_input),
        ],
        "model_calls": 0,
    }


async def run_graph_agent(
    model: ToolBindableModel,
    user_input: str,
    max_model_calls: int = 4,
) -> AgentState:
    """Build and run the graph from one user request."""

    graph = build_agent_graph(model, max_model_calls)
    return await graph.ainvoke(create_initial_state(user_input))
