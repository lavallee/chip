"""State contract and cursor semantics (§9).

State is part of the public contract, not an implementation accident. This
module models the declared state contract and the cursor discipline. The
admitted scope is ``installation`` and the admitted concurrency strategies are
``single-flight`` and — as of spec 0.5.0 — ``partitioned(<keyField>)`` (§9).
``cas`` remains a deferred hypothesis; it parses but is rejected.

``partitioned(<keyField>)`` (0.5.0) lets runs overlap across distinct partition
keys with single-flight *per key* — admitted for cache/map-class "delegation
profile" chips keyed by a stable resource (e.g. one repository per partition).
Cursor-bearing *attention* chips still MUST use ``single-flight`` (§9): a
``cursor: required`` chip may not partition. The ``keyField`` names a signal
envelope field (§8.1); the manifest loader checks that membership.

Single-flight (and per-key single-flight) is *declared* here but *enforced* by
the host: one installation — or one partition — has at most one live lease. The
library records the declaration and checks cursor monotonicity; it does not
itself hold leases or run anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chip.errors import StateError

# Admitted normative vocabulary (§9). ``partitioned`` joined in spec 0.5.0.
_ADMITTED_SCOPES = ("installation",)
_ADMITTED_CONCURRENCY = ("single-flight", "partitioned")
# Wider vocabulary the spec names but still defers — parsed for clear errors.
_KNOWN_SCOPES = ("run", "binding", "installation", "project", "shared")
_KNOWN_CONCURRENCY = ("single-flight", "cas", "partitioned")
_CURSOR_MODES = ("required", "optional", "none")


def _parse_concurrency(ctx: str, concurrency: str) -> tuple[str, str | None]:
    """Return ``(base, partition_key)`` for a concurrency declaration (§9).

    ``"single-flight"`` -> ``("single-flight", None)``; ``"partitioned(repo)"``
    -> ``("partitioned", "repo")``. Raises on an unknown base, on ``partitioned``
    without a ``(key)``, or on a stray ``(key)`` on a non-partitioned base.
    """
    base = concurrency.split("(", 1)[0].strip()
    if base not in _KNOWN_CONCURRENCY:
        allowed = ", ".join(_KNOWN_CONCURRENCY)
        raise StateError(f"{ctx}: unknown concurrency {concurrency!r}; expected one of: {allowed}")
    has_parens = "(" in concurrency
    if base == "partitioned":
        if not (has_parens and concurrency.rstrip().endswith(")")):
            raise StateError(
                f"{ctx}: partitioned concurrency MUST name a key field as "
                f"'partitioned(<keyField>)', got {concurrency!r} (§9)"
            )
        key = concurrency[concurrency.index("(") + 1 : concurrency.rstrip().rindex(")")].strip()
        if not key:
            raise StateError(f"{ctx}: partitioned concurrency has an empty key field (§9)")
        return base, key
    if has_parens:
        raise StateError(f"{ctx}: concurrency {concurrency!r} does not take a key field (§9)")
    return base, None


@dataclass(frozen=True, slots=True)
class StateContract:
    """A chip's declared state contract (manifest ``state`` block, §9).

    Constructed via :meth:`from_dict`, which enforces that scope is
    ``installation`` and concurrency is either ``single-flight`` or
    ``partitioned(<keyField>)`` (0.5.0). A cursor-bearing chip MUST use
    single-flight (§9); this is validated. When concurrency is partitioned,
    :attr:`partition_key` holds the declared key field (else ``None``); the
    manifest loader additionally checks it names a signal envelope field (§8.1).
    """

    schema: str
    scope: str
    retention: str
    cursor: str  # "required" | "optional" | "none"
    concurrency: str
    migration: str | None = None
    reset_behavior: str | None = None
    sensitive: bool = False
    partition_key: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateContract:
        ctx = "state contract"
        schema = data.get("schema")
        if not schema:
            raise StateError(f"{ctx}: missing required field 'schema'")
        scope = data.get("scope", "installation")
        if scope not in _KNOWN_SCOPES:
            allowed = ", ".join(_KNOWN_SCOPES)
            raise StateError(f"{ctx}: unknown scope {scope!r}; expected one of: {allowed}")
        if scope not in _ADMITTED_SCOPES:
            raise StateError(
                f"{ctx}: scope {scope!r} is deferred; only 'installation' is valid (§3.1)"
            )
        concurrency = data.get("concurrency", "single-flight")
        base_concurrency, partition_key = _parse_concurrency(ctx, concurrency)
        if base_concurrency not in _ADMITTED_CONCURRENCY:
            raise StateError(
                f"{ctx}: concurrency {concurrency!r} is deferred; only 'single-flight' and "
                "'partitioned(<keyField>)' are admitted (§9)"
            )
        cursor = data.get("cursor", "none")
        if cursor not in _CURSOR_MODES:
            allowed = ", ".join(_CURSOR_MODES)
            raise StateError(f"{ctx}: unknown cursor mode {cursor!r}; expected one of: {allowed}")
        retention = data.get("retention")
        if not retention:
            raise StateError(f"{ctx}: missing required field 'retention'")
        if cursor == "required" and base_concurrency != "single-flight":
            raise StateError(
                f"{ctx}: cursor-bearing chips MUST use single-flight concurrency, not "
                f"{concurrency!r} — partitioned is for delegation-profile chips only (§9)"
            )
        return cls(
            schema=schema,
            scope=scope,
            retention=retention,
            cursor=cursor,
            concurrency=concurrency,
            migration=data.get("migration"),
            reset_behavior=data.get("resetBehavior"),
            sensitive=bool(data.get("sensitive", False)),
            partition_key=partition_key,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "scope": self.scope,
            "retention": self.retention,
            "cursor": self.cursor,
            "concurrency": self.concurrency,
            "sensitive": self.sensitive,
        }
        if self.migration is not None:
            out["migration"] = self.migration
        if self.reset_behavior is not None:
            out["resetBehavior"] = self.reset_behavior
        return out


@dataclass(frozen=True, slots=True)
class Cursor:
    """A monotonic attention cursor with lineage (§9, §10.1).

    ``value`` is an opaque, orderable cursor position (e.g. an ISO timestamp or
    a monotonically increasing sequence). ``lineage`` records the cursor's
    identity chain so a migration can preserve it. :meth:`advance` returns a new
    cursor and enforces monotonicity — a retry or migration attempting to move
    the cursor backwards raises :class:`StateError`, which is how the spec
    prevents "reset a cursor and emit an old effect again" (§21).
    """

    value: str
    lineage: str

    def advance(self, new_value: str) -> Cursor:
        """Return a new cursor at ``new_value``, asserting it does not regress.

        Monotonicity is checked with a plain string comparison, so callers
        should use lexically-orderable cursor values (ISO-8601 timestamps or
        zero-padded sequence numbers). Equal values are rejected — an advance
        must make progress.
        """
        if not new_value:
            raise StateError("cursor advance requires a non-empty value")
        if new_value <= self.value:
            raise StateError(
                f"cursor may not regress: {new_value!r} is not after current {self.value!r}"
            )
        return Cursor(value=new_value, lineage=self.lineage)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "lineage": self.lineage}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cursor:
        if "value" not in data or "lineage" not in data:
            raise StateError("cursor: requires 'value' and 'lineage' fields")
        return cls(value=data["value"], lineage=data["lineage"])
