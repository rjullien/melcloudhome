"""Tests for ATA raw /context and WebSocket diagnostic DEBUG dumps."""

from __future__ import annotations

import json
import logging

import pytest

from custom_components.melcloudhome.api.raw_unit_debug import (
    log_ata_context_unit,
    log_ata_ws_state_changed,
    redact_for_debug,
    reset_raw_unit_debug_state,
)

LOGGER_NAME = "custom_components.melcloudhome.api.raw_unit_debug"


def setup_function() -> None:
    reset_raw_unit_debug_state()


def test_redact_email_mac_token_and_sensitive_keys() -> None:
    raw = {
        "email": "user@example.com",
        "connectedInterfaceIdentifier": "AA:BB:CC:DD:EE:FF",
        "notes": "contact me@test.org or MAC aa:bb:cc:dd:ee:ff",
        "token": "abcdefghijklmnopqrstuvwxyz012345",
        "settings": [
            {"name": "Power", "value": "True"},
            {"name": "SerialNumber", "value": "ABC123456789"},
        ],
    }
    out = redact_for_debug(raw)
    assert out["email"] == "<redacted>"
    assert out["connectedInterfaceIdentifier"] == "<redacted>"
    assert "<redacted:email>" in out["notes"]
    assert "<redacted:mac>" in out["notes"]
    assert out["token"] == "<redacted>"
    assert out["settings"][0]["value"] == "True"
    assert out["settings"][1]["value"] == "<redacted>"


def test_context_dump_logs_once_then_on_change(
    caplog: pytest.LogCaptureFixture,
) -> None:
    unit = {
        "id": "unit-1",
        "givenDisplayName": "Salon",
        "settings": [
            {"name": "OperationMode", "value": "Automatic"},
            {"name": "InStandbyMode", "value": "False"},
        ],
        "isConnected": True,
        "systemId": "LLLLLLLL-LLLL-LLLL-LLLL-LLLLLLLLLLLL",
    }
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        log_ata_context_unit(unit)
        log_ata_context_unit(unit)  # unchanged — silent
        unit["settings"][1]["value"] = "True"
        log_ata_context_unit(unit)

    messages = [
        r.getMessage()
        for r in caplog.records
        if r.name == LOGGER_NAME and "raw /context" in r.getMessage()
    ]
    assert len(messages) == 2
    assert "captured_at=" in messages[0]
    assert "InStandbyMode" in messages[0]
    assert "True" in messages[1]


def test_ws_dump_includes_timestamps(caplog: pytest.LogCaptureFixture) -> None:
    frame = {
        "messageType": "unitStateChanged",
        "Data": {
            "id": "unit-2",
            "timestamp": "2026-10-22T21:15:00.000+02:00",
            "settings": [
                {"name": "InStandbyMode", "value": True},
                {"name": "OperationMode", "value": 8},
            ],
        },
    }
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        log_ata_ws_state_changed(frame)

    messages = [r.getMessage() for r in caplog.records if r.name == LOGGER_NAME]
    assert len(messages) == 1
    assert "unitStateChanged" in messages[0]
    assert "frame_timestamp=" in messages[0]
    assert "2026-10-22T21:15:00.000+02:00" in messages[0]
    payload_json = messages[0].split("payload=", 1)[1]
    parsed = json.loads(payload_json)
    assert parsed["source"] == "websocket_unitStateChanged"
    assert parsed["captured_at"]
    assert parsed["frame_timestamp"] == "2026-10-22T21:15:00.000+02:00"


def test_silent_when_debug_disabled(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_ata_context_unit(
            {
                "id": "unit-3",
                "settings": [{"name": "Power", "value": "True"}],
            }
        )
    assert not any(r.name == LOGGER_NAME for r in caplog.records)


def test_from_dict_triggers_context_dump(caplog: pytest.LogCaptureFixture) -> None:
    from custom_components.melcloudhome.api.models_ata import AirToAirUnit

    reset_raw_unit_debug_state()
    data = {
        "id": "unit-from-dict",
        "givenDisplayName": "Salon",
        "settings": [
            {"name": "Power", "value": "True"},
            {"name": "OperationMode", "value": "Automatic"},
            {"name": "InStandbyMode", "value": "True"},
        ],
        "capabilities": {},
        "schedule": [],
    }
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        unit = AirToAirUnit.from_dict(data)
    assert unit.in_standby_mode is True
    assert any("raw /context" in r.getMessage() for r in caplog.records)
