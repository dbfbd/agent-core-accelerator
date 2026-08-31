"""Tests for the package installation boundary."""

from importlib import import_module


def test_incident_agent_package_is_importable() -> None:
    module = import_module("incident_agent")

    assert module.__name__ == "incident_agent"
