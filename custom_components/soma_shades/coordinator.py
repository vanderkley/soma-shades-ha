"""The connection between Home Assistant and a shade."""

import asyncio
from collections.abc import Awaitable, Callable

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from soma_shades import ConnectionConfig, ShadeClient, ShadeConnection

from .const import CONF_BLUETOOTH_ENABLED, CONF_SHOW_AS_TILT, CONF_TILT

CONNECTION_CONFIG = ConnectionConfig()


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

    @property
    def available(self) -> bool:
        return self.shade.bluetooth_enabled and self.connection.online

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_update_listeners(self) -> None:
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

    async def async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        try:
            await self.connection.run_command(command)
        except Exception as err:
            raise HomeAssistantError(f"Cannot control {self.shade.display_name}: {err}") from err

    def _find_device(self, address: str) -> BLEDevice | None:
        # a shade only advertises while it has no connection, so this also finds the adapter that sees it best
        return bluetooth.async_ble_device_from_address(self.hass, address, connectable=True)

    async def _availability_changed(self, _online: bool) -> None:
        self.async_update_listeners()

    async def _update_device(self) -> None:
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(CONNECTION_BLUETOOTH, self.shade.mac)},
            manufacturer=self.shade.manufacturer,
            hw_version=self.shade.hardware_version,
            sw_version=self.shade.firmware_version,
        )
