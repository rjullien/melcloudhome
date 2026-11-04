"""Test WebSocket/REST connection reconciliation through Home Assistant."""

import json
from unittest.mock import MagicMock

import aiohttp
import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    TEST_ATA_UNIT_ID,
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
    wire_connected_ws,
)

CONNECTION_ENTITY = "binary_sensor.melcloudhome_a1b2_9abc_connection_state"
EVENT_TIME = "2026-10-05T16:32:23+00:00"


def _communication_frame(connected: bool) -> MagicMock:
    frame = MagicMock()
    frame.type = aiohttp.WSMsgType.TEXT
    frame.data = json.dumps(
        {
            "messageType": (
                "unitCommunicationRestored" if connected else "unitCommunicationLost"
            ),
            "Data": {"id": TEST_ATA_UNIT_ID, "timestamp": EVENT_TIME},
        }
    )
    return frame


@pytest.mark.asyncio
@pytest.mark.parametrize("connected", [False, True])
async def test_ws_communication_updates_connection_state_and_timestamp(
    hass: HomeAssistant, connected: bool
) -> None:
    unit = create_mock_ata_unit(is_connected=not connected)
    context = create_mock_ata_user_context([create_mock_ata_building(units=[unit])])
    await setup_ata_integration_custom(
        hass,
        context,
        configure_client=lambda client: wire_connected_ws(
            client, [_communication_frame(connected)]
        ),
    )

    state = hass.states.get(CONNECTION_ENTITY)
    assert state is not None
    assert state.state == (STATE_ON if connected else STATE_OFF)
    timestamp_key = (
        "last_communication_restored" if connected else "last_communication_lost"
    )
    assert state.attributes[timestamp_key] == EVENT_TIME
    assert state.attributes["is_connected"] is not connected
    assert state.attributes["is_multi_split_system"] is False


@pytest.mark.asyncio
async def test_rest_wins_after_two_disagreeing_refreshes_and_logs_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    unit = create_mock_ata_unit(is_connected=True)
    context = create_mock_ata_user_context([create_mock_ata_building(units=[unit])])
    await setup_ata_integration_custom(
        hass,
        context,
        configure_client=lambda client: wire_connected_ws(
            client, [_communication_frame(False)]
        ),
    )
    state = hass.states.get(CONNECTION_ENTITY)
    assert state is not None
    assert state.state == STATE_OFF

    for expected in (STATE_OFF, STATE_ON, STATE_ON):
        await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
        await hass.async_block_till_done()
        state = hass.states.get(CONNECTION_ENTITY)
        assert state is not None
        assert state.state == expected
        assert state.attributes["last_communication_lost"] == EVENT_TIME

    assert caplog.text.count("for more than one poll; using REST") == 1
