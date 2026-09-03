"""Executable entry point for the complete incident-agent service."""

import uvicorn

from incident_agent.bootstrap import create_production_app
from incident_agent.settings import load_settings

settings = load_settings()
app = create_production_app(settings)


def main() -> None:
    """Run the configured ASGI application with Uvicorn."""

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
