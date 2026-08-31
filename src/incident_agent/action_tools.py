"""High-risk service actions that must run behind human approval."""

from typing import Literal

from pydantic import BaseModel, Field


class RestartInput(BaseModel):
    """Validated input for one service restart action."""

    service: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RestartReceipt(BaseModel):
    """Structured evidence returned after the local restart simulation runs."""

    service: str
    outcome: Literal["restart_completed"] = "restart_completed"
    reason: str
    simulated: bool = True


async def restart_service(restart_input: RestartInput) -> RestartReceipt:
    """Simulate one approved restart and return its execution receipt."""

    return RestartReceipt(
        service=restart_input.service,
        reason=restart_input.reason,
    )
