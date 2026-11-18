import asyncio
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from soma_shades import ConnectionConfig

pytestmark = pytest.mark.usefixtures("fake_bluetooth")

COVER = "cover.living_room"
SWITCH = "switch.living_room_bluetooth_connection"
MOTOR_SPEED = "number.living_room_motor_speed"


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


async def test_motor_speed(hass, entry):
    coordinator = await start(hass, entry)
    assert hass.states.get(MOTOR_SPEED).state == "60"  # read after connecting

    await service(hass, "number", "set_value", MOTOR_SPEED, value=35)
    assert hass.states.get(MOTOR_SPEED).state == "35"
    assert "motor speed 35" in coordinator.shade.commands
    await hass.config_entries.async_unload(entry.entry_id)


async def test_move_slowly(hass, entry):
    coordinator = await start(hass, entry)
    shade = coordinator.shade

    await service(hass, "soma_shades", "move_slowly", COVER, position=0)  # close at the default slow speed
    assert shade.commands[-2:] == ["motor speed 10", "position 100"]
    assert hass.states.get(COVER).state == "closing"

    shade.arrive()
    await hass.async_block_till_done()
    assert shade.commands[-1] == "motor speed 60"  # set back to the speed of the shade
    assert hass.states.get(MOTOR_SPEED).state == "60"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_move_slowly_stopped(hass, entry):
    coordinator = await start(hass, entry)
    shade = coordinator.shade

    await service(hass, "soma_shades", "move_slowly", COVER, position=100, speed=25)
    assert shade.commands[-2:] == ["motor speed 25", "position 0"]
    await service(hass, "cover", "stop_cover", COVER)
    assert shade.commands[-1] == "motor speed 60"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_move_during_a_slow_move_is_at_the_normal_speed(hass, entry):
    coordinator = await start(hass, entry)
    shade = coordinator.shade

    await service(hass, "soma_shades", "move_slowly", COVER, position=0)
    await service(hass, "cover", "open_cover", COVER)
    assert shade.commands[-2:] == ["motor speed 60", "up"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_no_config_write_while_the_shade_moves(hass, entry):
    """A read of the target position can make the shade look stopped, only a new position ends a slow move."""
    coordinator = await start(hass, entry)
    shade = coordinator.shade

    await service(hass, "soma_shades", "move_slowly", COVER, position=0)
    shade._target_position = shade.position  # e.g. read by the keepalive while the shade moves
    shade._notify_update()
    await hass.async_block_till_done()
    assert shade.commands[-1] == "position 100"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_motor_speed_set_during_a_slow_move_stays(hass, entry):
    coordinator = await start(hass, entry)
    shade = coordinator.shade

    await service(hass, "soma_shades", "move_slowly", COVER, position=0)
    await service(hass, "number", "set_value", MOTOR_SPEED, value=80)
    shade.arrive()
    await hass.async_block_till_done()
    assert shade.commands[-1] == "motor speed 80"
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
