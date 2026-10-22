"""Unit tests for HVACActionDeterminer (ATA climate hvac_action)."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import HVACAction

from custom_components.melcloudhome.climate_helpers import HVACActionDeterminer
from tests.integration.conftest import create_mock_ata_unit


@pytest.fixture
def determiner() -> HVACActionDeterminer:
    return HVACActionDeterminer()


class TestHVACActionDeterminer:
    def test_off_when_powered_off(self, determiner: HVACActionDeterminer) -> None:
        unit = create_mock_ata_unit(power=False, operation_mode="Heat")
        assert determiner.determine_action(unit) == HVACAction.OFF

    def test_heat_below_target_is_heating(
        self, determiner: HVACActionDeterminer
    ) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Heat", set_temperature=21.0, room_temperature=19.0
        )
        assert determiner.determine_action(unit) == HVACAction.HEATING

    def test_cool_above_target_is_cooling(
        self, determiner: HVACActionDeterminer
    ) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Cool", set_temperature=20.0, room_temperature=22.0
        )
        assert determiner.determine_action(unit) == HVACAction.COOLING

    def test_auto_standby_is_preheating_not_cooling(
        self, determiner: HVACActionDeterminer
    ) -> None:
        """René bug: Auto + attente chauffage must not report cooling."""
        unit = create_mock_ata_unit(
            operation_mode="Automatic",
            set_temperature=21.0,
            room_temperature=23.0,  # would have been COOLING under the old heuristic
            in_standby_mode=True,
        )
        assert determiner.determine_action(unit) == HVACAction.PREHEATING

    def test_auto_without_standby_is_idle_even_when_temps_suggest_heating(
        self, determiner: HVACActionDeterminer
    ) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Automatic",
            set_temperature=21.0,
            room_temperature=19.0,
            in_standby_mode=False,
        )
        assert determiner.determine_action(unit) == HVACAction.IDLE

    def test_auto_without_standby_is_idle_even_when_temps_suggest_cooling(
        self, determiner: HVACActionDeterminer
    ) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Automatic",
            set_temperature=21.0,
            room_temperature=23.0,
            in_standby_mode=False,
        )
        assert determiner.determine_action(unit) == HVACAction.IDLE

    def test_heat_standby_is_preheating(self, determiner: HVACActionDeterminer) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Heat",
            set_temperature=21.0,
            room_temperature=19.0,
            in_standby_mode=True,
        )
        assert determiner.determine_action(unit) == HVACAction.PREHEATING

    def test_cool_standby_is_idle(self, determiner: HVACActionDeterminer) -> None:
        unit = create_mock_ata_unit(
            operation_mode="Cool",
            set_temperature=20.0,
            room_temperature=22.0,
            in_standby_mode=True,
        )
        assert determiner.determine_action(unit) == HVACAction.IDLE
