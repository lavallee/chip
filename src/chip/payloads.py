"""Optional JSON Schema validation of port payload documents.

The chip contract is stdlib-only at runtime; validating a *port payload* against
its declared JSON Schema is the one place a richer validator helps, so
``jsonschema`` is an optional, guarded dependency (``pip install chipspec[jsonschema]``).
When it is not installed, :func:`validate_payload` raises a clear
:class:`EnvelopeError` telling the caller how to enable it rather than importing
at module load and breaking the zero-dependency core.
"""

from __future__ import annotations

from typing import Any

from chip.errors import EnvelopeError


def jsonschema_available() -> bool:
    """Return whether the optional ``jsonschema`` dependency is importable."""
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return False
    return True


def validate_payload(document: Any, schema: dict[str, Any]) -> None:
    """Validate a port payload ``document`` against a JSON ``schema`` dict.

    Requires the optional ``jsonschema`` extra. Raises :class:`EnvelopeError`
    when the extra is missing, when ``schema`` is not a schema object, or when
    the document does not conform (the message carries the offending path).
    """
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise EnvelopeError(
            "validate_payload requires the optional 'jsonschema' extra; "
            "install with: pip install chipspec[jsonschema]"
        ) from exc
    if not isinstance(schema, dict):
        raise EnvelopeError(f"schema must be a JSON object, got {type(schema).__name__}")
    try:
        jsonschema.validate(instance=document, schema=schema)
    except jsonschema.ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise EnvelopeError(f"payload invalid at {path}: {exc.message}") from exc
    except jsonschema.SchemaError as exc:
        raise EnvelopeError(f"invalid JSON schema: {exc.message}") from exc
