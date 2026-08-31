"""Run module 7's complete pause, review, and resume business flow."""

import asyncio
import json

from langchain_core.messages import AIMessage

from incident_agent.approval_gate import HumanDecision
from incident_agent.scripted_model import ScriptedModel
from incident_agent.thread_archive import (
    checkpoint_build_resumable_agent,
    checkpoint_load_pending_approval,
    thread_continue,
    thread_resume_approval,
)


async def run_scenario(*, thread_id: str, approved: bool) -> None:
    """Run one approval or rejection scenario and print its complete state."""

    verdict = "approved" if approved else "rejected"
    model = ScriptedModel(
        [
            AIMessage(
                content="I need approval before restarting checkout-api.",
                tool_calls=[
                    {
                        "name": "restart_service",
                        "args": {
                            "service": "checkout-api",
                            "reason": "error rate reached 38% after deployment",
                        },
                        "id": f"restart-{verdict}-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content=(
                    "The approved checkout-api restart completed."
                    if approved
                    else "The checkout-api restart was rejected and was not executed."
                )
            ),
        ]
    )
    graph = checkpoint_build_resumable_agent(model)

    paused_state = await thread_continue(
        graph,
        thread_id,
        "checkout-api errors jumped after deployment; restart it now",
    )
    ticket = await checkpoint_load_pending_approval(graph, thread_id)

    print(f"\n=== {verdict.upper()}: PAUSED ===")
    print(json.dumps(ticket.model_dump(mode="json"), indent=2))
    print("messages before human decision:")
    for message in paused_state["messages"]:
        print(json.dumps(message.model_dump(mode="json"), indent=2))

    final_state = await thread_resume_approval(
        graph,
        thread_id,
        HumanDecision(
            approved=approved,
            operator="on-call-engineer",
            note="Impact checked against the incident timeline",
        ),
    )

    print(f"=== {verdict.upper()}: RESUMED ===")
    print("messages after human decision:")
    for message in final_state["messages"]:
        print(json.dumps(message.model_dump(mode="json"), indent=2))
    print(f"model_calls={final_state['model_calls']}")
    print(f"approval={final_state['approval']}")


async def main() -> None:
    """Demonstrate that approval executes and rejection blocks the same action."""

    await run_scenario(thread_id="incident-approved", approved=True)
    await run_scenario(thread_id="incident-rejected", approved=False)


if __name__ == "__main__":
    asyncio.run(main())
