"""The connection between Home Assistant and a shade."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.event import async_call_later
from soma_shades import ConnectionConfig, ShadeClient, ShadeConnection

from .const import CONF_BLUETOOTH_ENABLED, CONF_SHOW_AS_TILT, CONF_TILT, SLOW_MOVE_TIMEOUT

CONNECTION_CONFIG = ConnectionConfig()

_LOGGER = logging.getLogger(__name__)


class ShadeCoordinator:
    """Connect a shade through the Bluetooth adapters of Home Assistant, and tell the entities about its changes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, connect_semaphore: asyncio.Semaphore) -> None:
        self.hass = hass
        self.entry = entry
        self.tilt: bool = entry.data[CONF_TILT]
        self.show_as_tilt = self.tilt and entry.options.get(CONF_SHOW_AS_TILT, True)
        self.shade = ShadeClient(
            mac=entry.data[CONF_ADDRESS],
            name=entry.data[CONF_NAME],
            bluetooth_enabled=entry.options.get(CONF_BLUETOOTH_ENABLED, True),
        )
        self.shade.on_update = self.async_update_listeners
        self.connection = ShadeConnection(
            self.shade,
            CONNECTION_CONFIG,
            connect_semaphore=connect_semaphore,
            find_device=self._find_device,
            on_availability=self._availability_changed,
            on_first_connection=self._update_device,
        )
        self._listeners: list[CALLBACK_TYPE] = []
        self._restore_speed: int | None = None  # the motor speed to set back after a slow move
        self._last_position: int | None = None
        self._cancel_restore_timeout: CALLBACK_TYPE | None = None
        entry.async_on_unload(self._clear_slow_move)

    @property
    def available(self) -> bool:
        return self.shade.bluetooth_enabled and self.connection.online

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_update_listeners(self) -> None:
        self._check_slow_move()
        for listener in self._listeners:
            listener()

    async def async_set_bluetooth_enabled(self, enabled: bool) -> None:
        """Turned off, the shade is free for e.g. the Soma app, also after a restart of Home Assistant."""
        self.shade.bluetooth_enabled = enabled
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, CONF_BLUETOOTH_ENABLED: enabled}
        )
        if enabled:
            self.connection.start()
            self.async_update_listeners()
        else:
            await self.connection.stop()

    async def async_set_motor_speed(self, speed: int) -> None:
        self._clear_slow_move()  # the new speed stays, also after a slow move
        await self.async_command(lambda: self.shade.set_motor_speed(speed))

    async def async_move_slowly(self, target: int, speed: int) -> None:
        """Move to a position (0 open, 100 closed) at a lower motor speed, as the morning mode of the Soma app.

        The motor speed is a setting of the shade, so it is set for the move and set back when the shade stops.
        """

        async def command() -> None:
            if self._restore_speed is None:
                saved_speed = self.shade.motor_speed
                if saved_speed is None:
                    saved_speed = await self.shade.get_motor_speed()
                if saved_speed is None:
                    raise ValueError("the motor speed is unknown, so it cannot be set back after the move")
                self._restore_speed = saved_speed
            await self.shade.set_motor_speed(speed)
            await self.shade.set_position(target)

        if target == self.shade.position:
            return  # the shade would not move and report a position, so the speed would not be set back
        self._last_position = self.shade.position
        try:
            await self.async_command(command)
        except Exception:
            self._restore_motor_speed()
            raise
        if self._restore_speed is not None:
            self._start_restore_timeout()

    async def async_cover_command(self, command: Callable[[], Awaitable[None]], *, stop: bool = False) -> None:
        """Run a cover command, and end a slow move: set the motor speed back before a move, or after a stop."""
        speed = self._restore_speed
        if speed is None:
            await self.async_command(command)
            return
        self._clear_slow_move()

        async def command_with_speed() -> None:
            if stop:
                await command()
                await self.shade.set_motor_speed(speed)
            else:
                await self.shade.set_motor_speed(speed)
                await command()

        await self.async_command(command_with_speed)

    @callback
    def _start_restore_timeout(self) -> None:
        if self._cancel_restore_timeout:
            self._cancel_restore_timeout()

        @callback
        def _timeout(_now: object) -> None:
            self._cancel_restore_timeout = None
            self._restore_motor_speed()

        self._cancel_restore_timeout = async_call_later(self.hass, SLOW_MOVE_TIMEOUT, _timeout)

    @callback
    def _check_slow_move(self) -> None:
        """Set the motor speed back once the shade reports a new position and is not moving.

        A shade only reports its position when it stops, and while it moves the read target position may not tell
        that it moves. A config write stops a moving shade, so wait for a new position.
        """
        position = self.shade.position
        if position == self._last_position:
            return
        self._last_position = position
        if self._restore_speed is not None and self.shade.cover_status not in ("opening", "closing"):
            self._restore_motor_speed()

    @callback
    def _restore_motor_speed(self) -> None:
        speed = self._restore_speed
        self._clear_slow_move()
        if speed is None:
            return

        async def restore() -> None:
            try:
                await self.connection.run_command(lambda: self.shade.set_motor_speed(speed))
            except Exception as err:
                _LOGGER.warning(
                    "Cannot set the motor speed of %s back to %s%%: %s", self.shade.display_name, speed, err
                )
            self.async_update_listeners()

        self.entry.async_create_background_task(
            self.hass, restore(), f"set the motor speed of {self.shade.display_name} back"
        )

    @callback
    def _clear_slow_move(self) -> None:
        self._restore_speed = None
        if self._cancel_restore_timeout:
            self._cancel_restore_timeout()
            self._cancel_restore_timeout = None

    async def async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        try:
            await self.connection.run_command(command)
        except Exception as err:
            raise HomeAssistantError(f"Cannot control {self.shade.display_name}: {err}") from err

    def _find_device(self, address: str) -> BLEDevice | None:
        # a shade only advertises while it has no connection, so this also finds the adapter that sees it best
        return bluetooth.async_ble_device_from_address(self.hass, address, connectable=True)

    async def _availability_changed(self, online: bool) -> None:
        self.async_update_listeners()
        if online:
            # the connection holds the lock of the shade while it reports the shade online, so read it afterwards
            self.entry.async_create_background_task(
                self.hass, self._read_motor_speed(), f"read the motor speed of {self.shade.display_name}"
            )

    async def _read_motor_speed(self) -> None:
        """Read the motor speed on every connection, it may have changed in the Soma app in the meantime."""
        try:
            await self.connection.run_command(self.shade.get_motor_speed)
        except Exception as err:
            _LOGGER.debug("Cannot read the motor speed of %s: %r", self.shade.display_name, err)
            return
        self.async_update_listeners()

    async def _update_device(self) -> None:
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(CONNECTION_BLUETOOTH, self.shade.mac)},
            manufacturer=self.shade.manufacturer,
            hw_version=self.shade.hardware_version,
            sw_version=self.shade.firmware_version,
        )
