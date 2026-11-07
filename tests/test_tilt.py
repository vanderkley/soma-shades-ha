from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.soma_shades.const import CONF_BLUETOOTH_ENABLED, CONF_SHOW_AS_TILT, CONF_TILT, DOMAIN

from .conftest import MAC
from .test_config_flow import INFO, TILT_INFO
from .test_shade import COVER, service, start

pytestmark = pytest.mark.usefixtures("fake_bluetooth")


async def test_state(hass, tilt_entry):
    await start(hass, tilt_entry)

    cover = hass.states.get(COVER)
    assert cover.state == "open"
    assert cover.attributes["current_tilt_position"] == 70  # the Tilt is at 30, with 0 is closed upwards
    assert "current_position" not in cover.attributes
    assert cover.attributes["device_class"] == "blind"
    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), tilt_entry.entry_id)
    assert device.model == "Tilt 2"
    await hass.config_entries.async_unload(tilt_entry.entry_id)


async def test_commands(hass, tilt_entry):
    coordinator = await start(hass, tilt_entry)

    await service(hass, "cover", "open_cover_tilt", COVER)
    await service(hass, "cover", "close_cover_tilt", COVER)
    await service(hass, "cover", "stop_cover_tilt", COVER)
    await service(hass, "cover", "set_cover_tilt_position", COVER, tilt_position=100)
    await service(hass, "cover", "set_cover_tilt_position", COVER, tilt_position=25)

    commands = [command for command in coordinator.shade.commands if not command.startswith("notify")]
    assert commands == ["position 50", "position 100", "stop", "position 0", "position 75"]
    await hass.config_entries.async_unload(tilt_entry.entry_id)


def old_entry() -> MockConfigEntry:
    """An entry added before the Tilt support."""
    return MockConfigEntry(
        domain=DOMAIN, unique_id=MAC, title="Living Room", data={CONF_ADDRESS: MAC, CONF_NAME: "living_room"}
    )


@pytest.mark.parametrize(("info", "tilt"), [(INFO, False), (TILT_INFO, True)])
async def test_entry_without_the_tilt_flag(hass, info, tilt):
    entry = old_entry()
    with patch("homeassistant.components.bluetooth.async_last_service_info", return_value=info):
        await start(hass, entry)

    assert entry.data[CONF_TILT] is tilt
    assert ("current_tilt_position" in hass.states.get(COVER).attributes) is tilt
    await hass.config_entries.async_unload(entry.entry_id)


async def test_entry_without_the_tilt_flag_waits_for_an_advertisement(hass):
    entry = old_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.bluetooth.async_last_service_info", return_value=None):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert CONF_TILT not in entry.data


async def test_show_as_tilt_option(hass, tilt_entry):
    await start(hass, tilt_entry)
    await service(hass, "switch", "turn_off", "switch.living_room_bluetooth_connection")

    result = await hass.config_entries.options.async_init(tilt_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SHOW_AS_TILT: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # a cover with a position, with the same values, and the Bluetooth connection stays off
    assert tilt_entry.options == {CONF_BLUETOOTH_ENABLED: False, CONF_SHOW_AS_TILT: False}
    await service(hass, "switch", "turn_on", "switch.living_room_bluetooth_connection")
    cover = hass.states.get(COVER)
    assert cover.attributes["current_position"] == 70
    assert "current_tilt_position" not in cover.attributes
    await service(hass, "cover", "set_cover_position", COVER, position=25)
    assert tilt_entry.runtime_data.shade.commands[-1] == "position 75"
    await hass.config_entries.async_unload(tilt_entry.entry_id)


async def test_only_a_tilt_has_options(hass, entry, tilt_entry):
    assert not entry.supports_options
    assert tilt_entry.supports_options
