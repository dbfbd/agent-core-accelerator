"""Run the complete service twice and prove SQLite thread persistence."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn
from pydantic import SecretStr

from incident_agent.bootstrap import create_production_app
from incident_agent.settings import AppSettings

HOST = "127.0.0.1"
PORT = 8766
BASE_URL = f"http://{HOST}:{PORT}"
DEMO_TOKEN = "final-module-token"


def _json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    """Send one authenticated JSON request to the running final service."""

    body = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {DEMO_TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


async def _wait_until_ready() -> None:
    """Wait until the current Uvicorn instance accepts requests."""

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
    raise RuntimeError("The final service did not become ready")


async def _start_server(settings: AppSettings) -> tuple[uvicorn.Server, asyncio.Task]:
    """Start one real HTTP process lifecycle over the supplied SQLite file."""

    server = uvicorn.Server(
        uvicorn.Config(
            create_production_app(settings),
            host=HOST,
            port=PORT,
            log_level="error",
            access_log=False,
        )
    )
    task = asyncio.create_task(server.serve())
    await _wait_until_ready()
    return server, task


async def _stop_server(server: uvicorn.Server, task: asyncio.Task) -> None:
    """Stop Uvicorn and wait for SQLite and other resources to close."""

    server.should_exit = True
    await task


async def main() -> None:
    """Invoke, inspect quality data, restart, and reload the same thread."""

    with TemporaryDirectory(prefix="incident-agent-module-13-") as temporary_dir:
        settings = AppSettings(
            api_token=SecretStr(DEMO_TOKEN),
            model_provider="demo",
            checkpoint_path=Path(temporary_dir) / "checkpoints.sqlite",
            runbook_dir=Path("knowledge/runbooks").resolve(),
        )

        first_server, first_task = await _start_server(settings)
        try:
            invoke_status, invoke_body = await asyncio.to_thread(
                _json_request,
                "POST",
                "/invoke",
                payload={
                    "thread_id": "persistent-checkout",
                    "user_input": "Find the checkout upstream timeout safe response.",
                },
            )
            run_id = str(invoke_body["run_id"])
            trace_status, trace_body = await asyncio.to_thread(
                _json_request,
                "GET",
                f"/trace/{run_id}",
            )
            audit_status, audit_body = await asyncio.to_thread(
                _json_request,
                "GET",
                f"/audit/{run_id}",
            )
            approval_status, approval_body = await asyncio.to_thread(
                _json_request,
                "POST",
                "/invoke",
                payload={
                    "thread_id": "persistent-restart",
                    "user_input": "Restart checkout-api after reviewing the incident.",
                },
            )
            approval_run_id = str(approval_body["run_id"])
            print("\n=== First process: POST /invoke ===")
            print(invoke_status, json.dumps(invoke_body, ensure_ascii=False, indent=2))
            print("\n=== First process: trace and audit ===")
            print(trace_status, json.dumps(trace_body, ensure_ascii=False, indent=2))
            print(audit_status, json.dumps(audit_body, ensure_ascii=False, indent=2))
            print("\n=== First process: approval interrupt saved to SQLite ===")
            print(
                approval_status,
                json.dumps(approval_body, ensure_ascii=False, indent=2),
            )
            if approval_body["status"] != "approval_required":
                raise RuntimeError("The protected action did not pause for approval")
        finally:
            await _stop_server(first_server, first_task)

        second_server, second_task = await _start_server(settings)
        try:
            history_status, history_body = await asyncio.to_thread(
                _json_request,
                "GET",
                "/history/persistent-checkout",
            )
            print("\n=== Second process: SQLite-restored GET /history ===")
            print(
                history_status, json.dumps(history_body, ensure_ascii=False, indent=2)
            )
            if history_status != 200 or history_body["run_id"] != run_id:
                raise RuntimeError("SQLite did not restore the original Agent run")

            resume_status, resume_body = await asyncio.to_thread(
                _json_request,
                "POST",
                "/resume",
                payload={
                    "thread_id": "persistent-restart",
                    "approved": True,
                    "operator": "module-13-reviewer",
                    "note": "Approved after the service process restarted",
                },
            )
            print("\n=== Second process: SQLite-restored approval /resume ===")
            print(
                resume_status,
                json.dumps(resume_body, ensure_ascii=False, indent=2),
            )
            if (
                resume_status != 200
                or resume_body["status"] != "completed"
                or resume_body["run_id"] != approval_run_id
            ):
                raise RuntimeError("The saved approval interrupt did not resume")
        finally:
            await _stop_server(second_server, second_task)


if __name__ == "__main__":
    asyncio.run(main())
