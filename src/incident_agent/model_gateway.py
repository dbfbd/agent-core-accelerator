"""Select a deterministic teaching model or a real OpenAI chat model."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from incident_agent.agent_loop import AsyncChatModel, ToolBindableModel
from incident_agent.settings import AppSettings


class RuleBasedDemoModel(ToolBindableModel, AsyncChatModel):
    """Exercise the real graph and RAG tool without an external API account."""

    def __init__(self) -> None:
        self._tool_names: set[str] = set()

    def bind_tools(
        self,
        tools: Sequence[dict[str, object]],
    ) -> AsyncChatModel:
        """Remember the schemas exactly as a real model binding step would."""

        self._tool_names = {str(tool["name"]) for tool in tools}
        return self

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        """Request runbook evidence, then turn its ToolMessage into an answer."""

        last_message = messages[-1]
        if isinstance(last_message, ToolMessage):
            if last_message.name == "restart_service":
                return AIMessage(
                    content=(
                        "The reviewed restart action returned this evidence: "
                        f"{last_message.content}"
                    )
                )
            return AIMessage(
                content=(
                    "Runbook retrieval completed. The following search_runbooks "
                    "evidence preserves its source fields for citation: "
                    f"{last_message.content}"
                )
            )
        if (
            isinstance(last_message, HumanMessage)
            and "search_runbooks" in self._tool_names
        ):
            query = (
                last_message.content
                if isinstance(last_message.content, str)
                else str(last_message.content)
            )
            if "restart" in query.lower() and "restart_service" in self._tool_names:
                return AIMessage(
                    content="A service restart needs explicit operator approval.",
                    tool_calls=[
                        {
                            "name": "restart_service",
                            "args": {
                                "service": "checkout-api",
                                "reason": query,
                            },
                            "id": "demo-restart-service",
                            "type": "tool_call",
                        }
                    ],
                )
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_runbooks",
                        "args": {"query": query, "top_k": 2},
                        "id": "demo-search-runbooks",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="The demo model found no runbook tool to call.")


def build_chat_model(settings: AppSettings) -> ToolBindableModel:
    """Build the configured model behind the shared tool-bindable interface."""

    if settings.model_provider == "demo":
        return RuleBasedDemoModel()
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required when model_provider=openai")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        use_responses_api=True,
        max_retries=2,
    )
