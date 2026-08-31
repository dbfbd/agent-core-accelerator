"""Explicit model-to-tool-to-model loop without LangGraph automation."""

from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from incident_agent.tool_runtime import TOOL_SCHEMAS, execute_tool_call

SYSTEM_PROMPT = """You investigate service incidents with tools.
Separate tool evidence from inference and state what remains unknown.
Never claim that a tool was executed until its ToolMessage is present."""


class AsyncChatModel(Protocol):
    """Minimum interface required after tools have been bound."""

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage: ...


class ToolBindableModel(Protocol):
    """Minimum interface required to provide tool schemas to a model."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, object]],
    ) -> AsyncChatModel: ...


class AgentStepLimitError(RuntimeError):
    """Raised when the model does not produce a final answer in time."""


async def run_agent(
    model: ToolBindableModel,
    user_input: str,
    max_model_calls: int = 4,
) -> list[BaseMessage]:
    """Run a visible, manual tool-calling loop and return its transcript."""

    bound_model = model.bind_tools(TOOL_SCHEMAS)
    messages: list[BaseMessage] = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]

    for _ in range(max_model_calls):
        ai_message = await bound_model.ainvoke(messages)
        messages.append(ai_message)

        if not ai_message.tool_calls:
            return messages

        for tool_call in ai_message.tool_calls:
            tool_message = await execute_tool_call(tool_call)
            messages.append(tool_message)

    raise AgentStepLimitError(
        f"Model did not produce a final answer after {max_model_calls} calls"
    )
