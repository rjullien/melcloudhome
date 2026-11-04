"""Test ATA HVAC actions through Home Assistant climate state."""

from typing import Any

import pytest
from homeassistant.components.climate import HVACAction
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"power": False}, HVACAction.OFF),
        (
            {"operation_mode": "Heat", "room_temperature": 19.0},
            HVACAction.HEATING,
        ),
        (
            {
                "operation_mode": "Cool",
                "set_temperature": 20.0,
                "room_temperature": 22.0,
            },
            HVACAction.COOLING,
        ),
        (
            {
                "operation_mode": "Automatic",
                "room_temperature": 23.0,
                "in_standby_mode": True,
            },
            HVACAction.PREHEATING,
        ),
        (
            {"operation_mode": "Automatic", "room_temperature": 19.0},
            HVACAction.IDLE,
        ),
        (
            {"operation_mode": "Automatic", "room_temperature": 23.0},
            HVACAction.IDLE,
        ),
        (
            {"operation_mode": "Heat", "in_standby_mode": True},
            HVACAction.PREHEATING,
        ),
        (
            {
                "operation_mode": "Cool",
                "set_temperature": 20.0,
                "room_temperature": 22.0,
                "in_standby_mode": True,
            },
            HVACAction.IDLE,
        ),
    ],
)
async def test_climate_hvac_action(
    hass: HomeAssistant, settings: dict[str, Any], expected: HVACAction
) -> None:
    unit = create_mock_ata_unit(**settings)
    context = create_mock_ata_user_context([create_mock_ata_building(units=[unit])])
    await setup_ata_integration_custom(hass, context)

    state = hass.states.get("climate.melcloudhome_a1b2_9abc_climate")
    assert state is not None
    assert state.attributes["hvac_action"] == expected
