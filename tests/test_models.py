"""Tests for validated incident request input."""

import pytest
from pydantic import ValidationError

from incident_agent.models import IncidentRequest


def test_incident_request_validates_and_normalizes_input() -> None:
    request = IncidentRequest.model_validate(
        {
            "service": " checkout-api ",
            "question": " Why are requests failing? ",
        }
    )

    assert request.service == "checkout-api"
    assert request.question == "Why are requests failing?"


def test_incident_request_rejects_empty_service() -> None:
    with pytest.raises(ValidationError) as error:
        IncidentRequest.model_validate(
            {"service": "   ", "question": "Why are requests failing?"}
        )

    assert error.value.errors()[0]["loc"] == ("service",)
    assert error.value.errors()[0]["type"] == "string_too_short"


def test_incident_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        IncidentRequest.model_validate(
            {
                "service": "checkout-api",
                "question": "Why are requests failing?",
                "priority": "high",
            }
        )

    assert error.value.errors()[0]["loc"] == ("priority",)
    assert error.value.errors()[0]["type"] == "extra_forbidden"
