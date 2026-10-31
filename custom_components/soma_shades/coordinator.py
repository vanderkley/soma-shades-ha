"""The Bluetooth connection with a shade."""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.event import async_call_later
from soma_shades import ShadeClient, ShadeConnectionError

from .const import (
    CONF_BLUETOOTH_ENABLED,
    CONNECT_TIMEOUT,
    DOMAIN,
    KEEPALIVE_INTERVAL,
    OFFLINE_GRACE_PERIOD,
    RECONNECT_BACKOFF_MAX,
    RECONNECT_BACKOFF_MIN,
    REFRESH_INTERVAL,
    STABLE_CONNECTION_TIME,
)

_LOGGER = logging.getLogger(__name__)


class ShadeCoordinator:
    """Keep the connection with a shade alive, and tell the entities about its changes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, connect_semaphore: asyncio.Semaphore) -> None:
        self.hass = hass
        self.entry = entry
        self.shade = ShadeClient(
            mac=entry.data[CONF_ADDRESS],
            name=entry.data[CONF_NAME],
            bluetooth_enabled=entry.options.get(CONF_BLUETOOTH_ENABLED, True),
        )
        self.shade.on_update = self.async_update_listeners
        self.online = False
        # the next shade connects after the initialization, the Bluetooth adapter of e.g. a Raspberry Pi fails the
        # service discovery and the reads (ATT error 0x0e) when a connection is set up at the same time
        self._connect_semaphore = connect_semaphore
        self._listeners: list[CALLBACK_TYPE] = []
        self._task: asyncio.Task[None] | None = None
        self._cancel_offline_timer: CALLBACK_TYPE | None = None

    @property
    def available(self) -> bool:
        return self.shade.bluetooth_enabled and self.online

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_update_listeners(self) -> None:
        for listener in self._listeners:
            listener()

    @callback
    def async_start(self) -> None:
        """Start the connection task, unless the Bluetooth connection is switched off."""
        if self.shade.bluetooth_enabled and self._task is None:
            self._task = self.entry.async_create_background_task(
                self.hass, self._maintain_connection(), name=f"{DOMAIN} connection {self.shade.name}"
            )

    async def async_stop(self) -> None:
        """Stop the connection task and disconnect the shade."""
        self._cancel_offline()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        async with self.shade.lock:
            await self.shade.disconnect()
        self.online = False
        self.async_update_listeners()

    async def async_set_bluetooth_enabled(self, enabled: bool) -> None:
        """Turned off, the shade is free for e.g. the Soma app, also after a restart of Home Assistant."""
        self.shade.bluetooth_enabled = enabled
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, CONF_BLUETOOTH_ENABLED: enabled}
        )
        if enabled:
            self.async_start()
            self.async_update_listeners()
        else:
            await self.async_stop()

    async def async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        """Run a command on the shade, connect first when the connection is lost."""
        if not self.shade.bluetooth_enabled:
            raise HomeAssistantError(f"The Bluetooth connection of {self.shade.display_name} is switched off")
        try:
            async with self.shade.lock:
                await self._connect()
                await command()
        except Exception as err:
            raise HomeAssistantError(f"Cannot control {self.shade.display_name}: {err}") from err

    async def _maintain_connection(self) -> None:
        """Keep the connection alive, reconnect with an exponential backoff."""
        backoff: float = RECONNECT_BACKOFF_MIN
        self._start_offline_timer()
        while True:
            try:
                async with self.shade.lock:
                    await self._connect()
            except Exception as err:
                _LOGGER.debug("Cannot connect to %s, retry in %s seconds: %s", self.shade.name, backoff, err)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)
                continue

            connected_since = time.monotonic()
            await self._keep_connection_alive()
            self._start_offline_timer()
            self.async_update_listeners()
            if time.monotonic() - connected_since >= STABLE_CONNECTION_TIME:
                backoff = RECONNECT_BACKOFF_MIN
            else:
                # the shade drops the connection right away, don't hammer it with reconnects
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    async def _connect(self) -> None:
        """Connect to the shade and initialize it, the caller must hold the shade lock."""
        shade = self.shade
        if shade.is_connected():
            return

        # a shade only advertises while it has no connection, so this also finds the adapter that sees it best
        shade.ble_device = bluetooth.async_ble_device_from_address(self.hass, shade.mac, connectable=True)
        if shade.ble_device is None:
            raise ShadeConnectionError(f"No connectable Bluetooth adapter sees {shade.name!r}")

        async with self._connect_semaphore:
            await shade.connect(timeout=CONNECT_TIMEOUT)
            try:
                if not shade.manufacturer:
                    await shade.get_info()
                    self._update_device()
                await shade.get_position()
                await shade.get_battery_level()
                await shade.start_notify("position")
                await shade.start_notify("battery_level")
            except Exception:
                # without notifications the state would go stale, so start over on the next attempt
                await shade.disconnect()
                raise
            await self._read_diagnostics()

        self._cancel_offline()
        self.online = True
        self.async_update_listeners()

    async def _keep_connection_alive(self) -> None:
        """Wait until the shade disconnects, set the clock every interval because reads do not count as activity."""
        last_refresh = time.monotonic()
        while True:
            try:
                async with asyncio.timeout(KEEPALIVE_INTERVAL):
                    await self.shade.wait_until_disconnected()
                return
            except TimeoutError:
                pass
            try:
                async with self.shade.lock:
                    if not self.shade.is_connected():
                        continue
                    await self.shade.keepalive()
                    if time.monotonic() - last_refresh >= REFRESH_INTERVAL:
                        last_refresh = time.monotonic()
                        await self.shade.get_position()
                        await self.shade.get_battery_level()
                        await self._read_diagnostics()
            except Exception as err:
                _LOGGER.warning("Keepalive of %s failed: %r", self.shade.name, err)

    async def _read_diagnostics(self) -> None:
        """Read the battery voltage and the charging input, which not every firmware may support."""
        for read in (self.shade.get_battery_voltage, self.shade.get_charging):
            try:
                await read()
            except Exception as err:
                _LOGGER.debug("Cannot read the diagnostics of %s: %r", self.shade.name, err)

    def _update_device(self) -> None:
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(CONNECTION_BLUETOOTH, self.shade.mac)},
            manufacturer=self.shade.manufacturer,
            hw_version=self.shade.hardware_version,
            sw_version=self.shade.firmware_version,
        )

    @callback
    def _start_offline_timer(self) -> None:
        """Report the shade unavailable when it is not connected again within the grace period."""

        @callback
        def report_offline(_now: object) -> None:
            self._cancel_offline_timer = None
            if not self.shade.is_connected():
                self.online = False
                self.async_update_listeners()

        self._cancel_offline()
        self._cancel_offline_timer = async_call_later(self.hass, OFFLINE_GRACE_PERIOD, report_offline)

    @callback
    def _cancel_offline(self) -> None:
        if self._cancel_offline_timer:
            self._cancel_offline_timer()
            self._cancel_offline_timer = None
