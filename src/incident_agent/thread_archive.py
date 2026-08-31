"""Thread addresses and checkpoint-backed conversation continuation."""

from collections.abc import Sequence

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from incident_agent.agent_loop import ToolBindableModel
from incident_agent.graph_agent import build_agent_graph, create_initial_state
from incident_agent.graph_state import AgentState, AgentStateUpdate

type ThreadAddress = RunnableConfig


def thread_make_address(thread_id: str) -> ThreadAddress:
    """Wrap one thread ID in the config shape required by LangGraph."""

    return {"configurable": {"thread_id": thread_id}}


def checkpoint_build_resumable_agent(
    model: ToolBindableModel,
    max_model_calls: int = 4,
) -> CompiledStateGraph:
    """Compile an agent with an in-memory checkpoint saver."""

    return build_agent_graph(
        model,
        max_model_calls,
        checkpoint_saver=InMemorySaver(),
    )


async def thread_continue(
    graph: CompiledStateGraph,
    thread_id: str,
    user_input: str,
    *,
    context_messages: Sequence[BaseMessage] = (),
) -> AgentState:
    """Continue one saved conversation or start it when no checkpoint exists."""

    thread_address = thread_make_address(thread_id)
    saved_checkpoint = await graph.aget_state(thread_address)

    if saved_checkpoint.values:
        next_input: AgentStateUpdate = {
            "messages": [
                *context_messages,
                HumanMessage(content=user_input),
            ],
            "model_calls": 0,
        }
    else:
        initial_state = create_initial_state(user_input)
        next_input = {
            "messages": [
                initial_state["messages"][0],
                *context_messages,
                initial_state["messages"][1],
            ],
            "model_calls": 0,
        }

    return await graph.ainvoke(next_input, thread_address)


async def checkpoint_load_latest(
    graph: CompiledStateGraph,
    thread_id: str,
) -> StateSnapshot | None:
    """Load the newest saved graph-state snapshot for one thread."""

    snapshot = await graph.aget_state(thread_make_address(thread_id))
    if not snapshot.values:
        return None
    return snapshot
