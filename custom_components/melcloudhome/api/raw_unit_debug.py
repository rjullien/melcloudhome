"""Diagnostic DEBUG dumps of raw ATA /context units and WebSocket frames.

Enable with::

    custom_components.melcloudhome.api.raw_unit_debug: debug

Logs once per unit (and channel) on first sighting, then again whenever the
redacted payload fingerprint changes. Intended to capture live Automatic
heat/cool sub-mode fields that our cassettes may never have recorded.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Last fingerprint per (channel, unit_id) so unchanged polls stay quiet.
_last_fingerprints: dict[tuple[str, str], str] = {}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_MAC_RE = re.compile(
    r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"
    r"|\b(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}\b"
)
# Long opaque tokens / hashes (Bearer material, WS hash, etc.).
# Hyphens excluded so UUIDs (systemId, unit id) stay readable for correlation.
_TOKENISH_RE = re.compile(r"\b[A-Za-z0-9_+/]{32,}={0,2}\b")
# Exact (normalised: lower-case, no "_"/"-") key names to redact. Exact match,
# not substring: substring matching redacted harmless capability flags such as
# hasHeatOperationMode / hasHalfDegreeIncrements ("has"+"h…" contains "hash").
_SENSITIVE_KEYS = frozenset(
    {
        "email",
        "token",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "password",
        "secret",
        "clientsecret",
        "authorization",
        "hash",
        "serial",
        "serialnumber",
        "mac",
        "macaddress",
        "ssid",
        "cookie",
        "bearer",
        "connectedinterfaceidentifier",
    }
)


def reset_raw_unit_debug_state() -> None:
    """Clear fingerprints (tests only)."""
    _last_fingerprints.clear()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _key_is_sensitive(key: str) -> bool:
    normalised = key.lower().replace("_", "").replace("-", "")
    return normalised in _SENSITIVE_KEYS


def _redact_string(value: str) -> str:
    text = _EMAIL_RE.sub("<redacted:email>", value)
    text = _MAC_RE.sub("<redacted:mac>", text)
    text = _TOKENISH_RE.sub("<redacted:token>", text)
    return text


def redact_for_debug(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-serialisable copy with emails/tokens/serials/MACs scrubbed."""
    if key is not None and _key_is_sensitive(key):
        if value is None or value == "":
            return value
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact_for_debug(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        # Settings arrays: redact each entry's value when name looks sensitive.
        out: list[Any] = []
        for item in value:
            if isinstance(item, dict) and "name" in item:
                name = str(item.get("name") or "")
                entry = {
                    k: (
                        redact_for_debug(v, key=name)
                        if k == "value"
                        else redact_for_debug(v, key=str(k))
                    )
                    for k, v in item.items()
                }
                out.append(entry)
            else:
                out.append(redact_for_debug(item))
        return out
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _redact_string(str(value))


def _fingerprint(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _should_log(channel: str, unit_id: str, payload: Any) -> bool:
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return False
    key = (channel, unit_id)
    digest = _fingerprint(payload)
    if _last_fingerprints.get(key) == digest:
        return False
    _last_fingerprints[key] = digest
    return True


def log_ata_context_unit(raw_unit: dict[str, Any]) -> None:
    """Dump a redacted /context airToAirUnits[] object when it changes."""
    unit_id = str(raw_unit.get("id") or "")
    if not unit_id:
        return
    settings = raw_unit.get("settings")
    top_level = {k: v for k, v in raw_unit.items() if k != "settings"}
    payload = {
        "source": "context",
        "captured_at": _now_iso(),
        "unit_id": unit_id,
        "givenDisplayName": raw_unit.get("givenDisplayName"),
        "settings": settings,
        "top_level": top_level,
    }
    redacted = redact_for_debug(payload)
    # Fingerprint without captured_at so an unchanged unit does not re-log
    # every 60 s poll.
    fingerprint_body = {
        "settings": redacted.get("settings"),
        "top_level": redacted.get("top_level"),
    }
    if not _should_log("context", unit_id, fingerprint_body):
        return
    _LOGGER.debug(
        "ATA raw /context unit dump unit_id=%s captured_at=%s payload=%s",
        unit_id,
        redacted.get("captured_at"),
        json.dumps(redacted, default=str, sort_keys=True),
    )


def log_ata_ws_state_changed(frame_item: dict[str, Any]) -> None:
    """Dump a redacted unitStateChanged frame when its Data payload changes."""
    data = frame_item.get("Data") or frame_item.get("data") or {}
    if not isinstance(data, dict):
        return
    unit_id = str(data.get("id") or "")
    if not unit_id:
        return
    # Prefer the frame's own timestamp when present (WS deltas sometimes omit it).
    frame_ts = data.get("timestamp") or data.get("Timestamp")
    payload = {
        "source": "websocket_unitStateChanged",
        "captured_at": _now_iso(),
        "frame_timestamp": frame_ts,
        "messageType": frame_item.get("messageType"),
        "unit_id": unit_id,
        "data": data,
    }
    redacted = redact_for_debug(payload)
    fingerprint_body = {
        "messageType": redacted.get("messageType"),
        "data": redacted.get("data"),
    }
    if not _should_log("ws_state", unit_id, fingerprint_body):
        return
    _LOGGER.debug(
        "ATA raw WebSocket unitStateChanged dump unit_id=%s captured_at=%s "
        "frame_timestamp=%s payload=%s",
        unit_id,
        redacted.get("captured_at"),
        redacted.get("frame_timestamp"),
        json.dumps(redacted, default=str, sort_keys=True),
    )
