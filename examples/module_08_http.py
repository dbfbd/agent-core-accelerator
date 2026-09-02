"""Run module 8 through a real local Uvicorn HTTP server."""

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn
from langchain_core.messages import AIMessage

from incident_agent.api_app import create_app
from incident_agent.scripted_model import ScriptedModel

HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"
DEMO_TOKEN = "course-token"


def _json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    """Send one synchronous JSON request to the local teaching server."""

    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _stream_request(
    path: str,
    *,
    token: str,
    payload: dict[str, object],
) -> tuple[int, str]:
    """Send one POST request and collect the real SSE wire text."""

    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return response.status, response.read().decode()


async def _wait_until_ready() -> None:
    """Wait until Uvicorn accepts a health request on the local port."""

    for _ in range(100):
        try:
            status_code, _ = await asyncio.to_thread(
                _json_request,
                "GET",
                "/health",
            )
            if status_code == 200:
                return
        except (URLError, TimeoutError):
            pass
        await asyncio.sleep(0.05)
    raise RuntimeError("The local HTTP server did not become ready")


def _demo_model() -> ScriptedModel:
    """Create the deterministic model replies consumed by the HTTP walkthrough."""

    return ScriptedModel(
        [
            AIMessage(content="checkout-api is ready for HTTP investigation."),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_service_metrics",
                        "args": {
                            "service": "checkout-api",
                            "start": "2026-08-20T10:00:00Z",
                            "end": "2026-08-20T10:11:00Z",
                        },
                        "id": "metrics-http-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Evidence: error rate rose from 1% to 21%."),
            AIMessage(
                content="I need approval before restarting checkout-api.",
                tool_calls=[
                    {
                        "name": "restart_service",
                        "args": {
                            "service": "checkout-api",
                            "reason": "error rate reached 38% after deployment",
                        },
                        "id": "restart-http-001",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The approved checkout-api restart completed."),
            AIMessage(
                content="I need approval before the streamed restart can continue.",
                tool_calls=[
                    {
                        "name": "restart_service",
                        "args": {
                            "service": "checkout-api",
                            "reason": "streamed high-risk action demonstration",
                        },
                        "id": "restart-stream-http-001",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )


async def main() -> None:
    """Exercise health, authentication, invoke, stream, history, and resume."""

    app = create_app(model=_demo_model(), api_token=DEMO_TOKEN)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="error",
            access_log=False,
        )
    )
    server_task = asyncio.create_task(server.serve())

    try:
        await _wait_until_ready()

        health_status, health_body = await asyncio.to_thread(
            _json_request,
            "GET",
            "/health",
        )
        print("\n=== GET /health ===")
        print(health_status, json.dumps(health_body, indent=2))

        unauthorized_status, unauthorized_body = await asyncio.to_thread(
            _json_request,
            "POST",
            "/invoke",
            payload={"thread_id": "no-token", "user_input": "investigate"},
        )
        print("\n=== POST /invoke without Bearer token ===")
        print(unauthorized_status, json.dumps(unauthorized_body, indent=2))

        invoke_status, invoke_body = await asyncio.to_thread(
            _json_request,
            "POST",
            "/invoke",
            token=DEMO_TOKEN,
            payload={
                "thread_id": "http-invoke",
                "user_input": "Investigate checkout-api through HTTP.",
            },
        )
        print("\n=== POST /invoke ===")
        print(invoke_status, json.dumps(invoke_body, indent=2))

        stream_status, stream_body = await asyncio.to_thread(
            _stream_request,
            "/stream",
            token=DEMO_TOKEN,
            payload={
                "thread_id": "http-stream",
                "user_input": "Stream checkout-api metric evidence.",
            },
        )
        print("\n=== POST /stream ===")
        print(stream_status)
        print(stream_body.strip())

        history_status, history_body = await asyncio.to_thread(
            _json_request,
            "GET",
            "/history/http-stream",
            token=DEMO_TOKEN,
        )
        print("\n=== GET /history/http-stream ===")
        print(history_status, json.dumps(history_body, indent=2))

        paused_status, paused_body = await asyncio.to_thread(
            _json_request,
            "POST",
            "/invoke",
            token=DEMO_TOKEN,
            payload={
                "thread_id": "http-approval",
                "user_input": "Restart checkout-api now.",
            },
        )
        print("\n=== POST /invoke: approval required ===")
        print(paused_status, json.dumps(paused_body, indent=2))

        resumed_status, resumed_body = await asyncio.to_thread(
            _json_request,
            "POST",
            "/resume",
            token=DEMO_TOKEN,
            payload={
                "thread_id": "http-approval",
                "approved": True,
                "operator": "on-call-engineer",
                "note": "Impact checked through the HTTP approval endpoint",
            },
        )
        print("\n=== POST /resume ===")
        print(resumed_status, json.dumps(resumed_body, indent=2))

        approval_stream_status, approval_stream_body = await asyncio.to_thread(
            _stream_request,
            "/stream",
            token=DEMO_TOKEN,
            payload={
                "thread_id": "http-stream-approval",
                "user_input": "Stream a restart request that needs approval.",
            },
        )
        print("\n=== POST /stream: approval required ===")
        print(approval_stream_status)
        print(approval_stream_body.strip())
    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(main())
