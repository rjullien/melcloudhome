"""Coordinator WebSocket/REST connection overlay reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.melcloudhome.coordinator import (
    MELCloudHomeCoordinator,
    _UnitCommOverlay,
)
from tests.integration.conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
)


def _coordinator() -> MELCloudHomeCoordinator:
    """Minimal coordinator instance without running HA update loops."""
    hass = MagicMock()
    client = MagicMock()
    # Bypass DataUpdateCoordinator.__init__ side effects where possible
    coord = object.__new__(MELCloudHomeCoordinator)
    coord.hass = hass
    coord.client = client
    coord._units = {}
    coord._atw_units = {}
    coord._unit_comm = {}
    coord.async_update_listeners = MagicMock()
    return coord


def test_effective_connection_prefers_ws_overlay_until_reconcile() -> None:
    coord = _coordinator()
    coord._unit_comm["u1"] = _UnitCommOverlay(ws_is_connected=False, disagree_polls=0)
    assert coord.effective_connection_is_on("u1", True) is False
    assert coord.effective_connection_is_on("u1", True) is False  # still overlay


def test_effective_connection_uses_rest_after_disagree_streak() -> None:
    coord = _coordinator()
    coord._unit_comm["u1"] = _UnitCommOverlay(ws_is_connected=False, disagree_polls=2)
    assert coord.effective_connection_is_on("u1", True) is True


def test_reconcile_logs_once_and_clears_overlay() -> None:
    coord = _coordinator()
    unit = create_mock_ata_unit(unit_id="u1", is_connected=True, name="Salon")
    context = create_mock_ata_user_context([create_mock_ata_building(units=[unit])])
    coord._unit_comm["u1"] = _UnitCommOverlay(ws_is_connected=False, disagree_polls=1)
    coord._reconcile_unit_communication(context)
    overlay = coord._unit_comm["u1"]
    assert overlay.disagree_polls == 2
    assert overlay.disagreement_logged is True
    assert overlay.ws_is_connected is None
    # Second reconcile with cleared overlay is a no-op
    coord._reconcile_unit_communication(context)
    assert overlay.disagree_polls == 2


@pytest.mark.asyncio
async def test_on_ws_communication_sets_timestamps() -> None:
    coord = _coordinator()
    unit = create_mock_ata_unit(unit_id="u1", name="Salon")
    coord._units["u1"] = unit
    ts = datetime(2026, 10, 5, 16, 32, 23, tzinfo=UTC)
    await coord._on_ws_communication("u1", False, ts)
    overlay = coord._unit_comm["u1"]
    assert overlay.ws_is_connected is False
    assert overlay.last_communication_lost == ts
    coord.async_update_listeners.assert_called()
    attrs = coord.connection_state_attributes(unit)
    assert attrs["last_communication_lost"] == ts.isoformat()
    assert attrs["is_multi_split_system"] is False
