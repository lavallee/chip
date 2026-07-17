"""Guarded jsonschema payload validation (skips when the extra is absent)."""

from __future__ import annotations

import pytest

from chip.errors import EnvelopeError
from chip.payloads import jsonschema_available, validate_payload

pytestmark = pytest.mark.skipif(
    not jsonschema_available(), reason="optional 'jsonschema' extra not installed"
)

_SCHEMA = {
    "type": "object",
    "properties": {"reportId": {"type": "string"}},
    "required": ["reportId"],
}


def test_valid_payload():
    validate_payload({"reportId": "r-1"}, _SCHEMA)


def test_invalid_payload_reports_path():
    with pytest.raises(EnvelopeError):
        validate_payload({"reportId": 3}, _SCHEMA)


def test_missing_required_field():
    with pytest.raises(EnvelopeError):
        validate_payload({}, _SCHEMA)
