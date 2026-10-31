import asyncio
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from soma_shades import ConnectionConfig

pytestmark = pytest.mark.usefixtures("fake_bluetooth")

COVER = "cover.living_room"
SWITCH = "switch.living_room_bluetooth_connection"


async def start(hass, entry):
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def service(hass, domain, name, target, **data):
    await hass.services.async_call(domain, name, {"entity_id": target, **data}, blocking=True)
    await hass.async_block_till_done()


async def test_state_after_connecting(hass, entry):
    await start(hass, entry)

    cover = hass.states.get(COVER)
    assert cover.state == "open"
    assert cover.attributes["current_position"] == 70  # the shade is at 30, with 0 is open
    assert hass.states.get("sensor.living_room_battery").state == "84"
    assert hass.states.get("sensor.living_room_battery_voltage").state == "4100"
    assert hass.states.get("sensor.living_room_input_voltage").state == "604"
    assert hass.states.get("sensor.living_room_charging_current") is None  # disabled by default
    assert hass.states.get("sensor.living_room_connected_since").state not in ("unknown", "unavailable")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_commands(hass, entry):
    coordinator = await start(hass, entry)

    await service(hass, "cover", "open_cover", COVER)
    await service(hass, "cover", "close_cover", COVER)
    await service(hass, "cover", "stop_cover", COVER)
    await service(hass, "cover", "set_cover_position", COVER, position=75)
    await service(hass, "button", "press", "button.living_room_sync_time")
    await service(hass, "button", "press", "button.living_room_identify")

    commands = [command for command in coordinator.shade.commands if not command.startswith("notify")]
    assert commands == ["up", "down", "stop", "position 25", "sync time", "identify"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_command_error(hass, entry):
    coordinator = await start(hass, entry)
    coordinator.shade.lose_connection()
    await hass.async_block_till_done()
    coordinator.shade.fail_connect = True

    with pytest.raises(HomeAssistantError):
        await service(hass, "cover", "open_cover", COVER)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_short_connection_drop_keeps_the_shade_available(hass, entry):
    config = ConnectionConfig(offline_grace_period=0.05)
    with patch("custom_components.soma_shades.coordinator.CONNECTION_CONFIG", config):
        coordinator = await start(hass, entry)
    coordinator.shade.fail_connect = True

    coordinator.shade.lose_connection()
    await hass.async_block_till_done()
    assert hass.states.get(COVER).state != "unavailable"

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    assert hass.states.get(COVER).state == "unavailable"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_bluetooth_connection_switch(hass, entry):
    coordinator = await start(hass, entry)

    await service(hass, "switch", "turn_off", SWITCH)
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get(COVER).state == "unavailable"
    assert not coordinator.shade.connected
    with pytest.raises(HomeAssistantError):
        await coordinator.async_command(coordinator.shade.move_up)

    # it stays off after a restart
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"
    assert not entry.runtime_data.shade.connected

    await service(hass, "switch", "turn_on", SWITCH)
    assert entry.runtime_data.shade.connected
    assert hass.states.get(COVER).state == "open"
    await hass.config_entries.async_unload(entry.entry_id)
