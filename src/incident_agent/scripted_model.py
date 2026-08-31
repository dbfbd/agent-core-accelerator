"""Deterministic chat model used to test message and tool-call trajectories."""

from collections.abc import Sequence
from typing import Self

from langchain_core.messages import AIMessage, BaseMessage


class ScriptExhaustedError(RuntimeError):
    """Raised when a scripted model has no response left to return."""


class ScriptedModel:
    """Return predefined AI messages while recording every model input."""

    def __init__(self, responses: Sequence[AIMessage]) -> None:
        self._responses = list(responses)
        self._next_response_index = 0
        self.bound_tools: tuple[dict[str, object], ...] = ()
        self.calls: list[list[BaseMessage]] = []

    def bind_tools(
        self,
        tools: Sequence[dict[str, object]],
    ) -> Self:
        self.bound_tools = tuple(tools)
        return self

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.calls.append(list(messages))

        try:
            response = self._responses[self._next_response_index]
        except IndexError as error:
            raise ScriptExhaustedError("No scripted model response remains") from error

        self._next_response_index += 1
        return response
