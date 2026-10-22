"""Tests for MELCloud Home ATW binary sensor entities.

Tests cover ATW-specific binary sensors including forced DHW mode.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)


@pytest.mark.asyncio
async def test_atw_error_state_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW error state binary sensor is created."""
    mock_unit = create_mock_atw_unit(is_in_error=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
    assert state is not None
    assert state.state == STATE_OFF  # No error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_connected", "interface_type", "expected_state"),
    [
        pytest.param(True, "melCloudWiFi", STATE_ON, id="connected"),
        pytest.param(False, "fourthGenWifi", STATE_OFF, id="disconnected"),
        pytest.param(None, None, STATE_ON, id="missing_treated_as_connected"),
    ],
)
async def test_atw_connection_state_reflects_unit_is_connected(
    hass: HomeAssistant,
    is_connected: bool | None,
    interface_type: str | None,
    expected_state: str,
) -> None:
    """ATW connection state follows per-unit isConnected from /context."""
    mock_unit = create_mock_atw_unit(
        is_connected=is_connected,
        connected_interface_type=interface_type,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_connection_state")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["is_connected"] is is_connected
    assert state.attributes["connected_interface_type"] == interface_type


@pytest.mark.asyncio
async def test_atw_connection_state_updates_when_unit_disconnects(
    hass: HomeAssistant,
) -> None:
    """ATW connection state flips off when /context reports isConnected=false."""
    mock_unit = create_mock_atw_unit(
        is_connected=True, connected_interface_type="melCloudWiFi"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)

    connection_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_connection_state"
    assert hass.states.get(connection_sensor_id).state == STATE_ON

    disconnected = create_mock_atw_unit(
        is_connected=False, connected_interface_type="melCloudWiFi"
    )
    mock_client.get_user_context = AsyncMock(
        return_value=create_mock_atw_user_context(
            [create_mock_atw_building(units=[disconnected])]
        )
    )

    from custom_components.melcloudhome.const import DOMAIN

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get(connection_sensor_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["is_connected"] is False


@pytest.mark.asyncio
async def test_atw_forced_dhw_active_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW forced DHW active binary sensor is created (ATW-specific)."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_forced_dhw_active")
    assert state is not None
    assert state.state == STATE_ON  # Forced DHW is active


@pytest.mark.asyncio
async def test_atw_error_state_on_when_device_in_error(hass: HomeAssistant) -> None:
    """Test error state sensor is ON when device in error."""
    mock_unit = create_mock_atw_unit(is_in_error=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
    assert state is not None
    assert state.state == STATE_ON  # Device in error


@pytest.mark.asyncio
async def test_atw_error_state_exposes_error_code(hass: HomeAssistant) -> None:
    """Test error state sensor exposes the device error code as attribute."""
    mock_unit = create_mock_atw_unit(is_in_error=True, error_code="E4")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
    assert state.state == STATE_ON
    assert state.attributes["error_code"] == "E4"


@pytest.mark.asyncio
async def test_atw_error_code_none_when_no_error(hass: HomeAssistant) -> None:
    """Test error code attribute is None when device has no error."""
    mock_unit = create_mock_atw_unit(is_in_error=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
    assert state.state == STATE_OFF
    assert state.attributes["error_code"] is None


@pytest.mark.asyncio
async def test_atw_forced_dhw_reflects_device_mode(hass: HomeAssistant) -> None:
    """Test forced DHW sensor reflects device forced_hot_water_mode."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_forced_dhw_active")
    assert state is not None
    assert state.state == STATE_OFF  # Forced DHW not active


@pytest.mark.asyncio
async def test_atw_connection_always_available(hass: HomeAssistant) -> None:
    """Test ATW connection sensor is always available (reports connection status)."""
    mock_unit = create_mock_atw_unit(is_connected=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_connection_state")
    assert state is not None
    assert state.state == STATE_OFF
    # available=True even when the unit reports disconnected
    assert state.state != "unavailable"
