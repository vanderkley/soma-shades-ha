"""Soma Smart Shades over Bluetooth LE."""

import asyncio

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from soma_shades import is_tilt

from .const import CONF_TILT, DOMAIN
from .coordinator import ShadeCoordinator

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SENSOR, Platform.SWITCH]

type ShadeConfigEntry = ConfigEntry[ShadeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ShadeConfigEntry) -> bool:
    if CONF_TILT not in entry.data:
        # added before the Tilt support, the advertisement tells whether it is a Tilt
        info = bluetooth.async_last_service_info(hass, entry.data[CONF_ADDRESS], connectable=True)
        if info is None:
            raise ConfigEntryNotReady(f"Waiting for an advertisement of {entry.title}")
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_TILT: is_tilt(info.manufacturer_data)})

    connect_semaphore = hass.data.setdefault(DOMAIN, asyncio.Semaphore(1))
    coordinator = ShadeCoordinator(hass, entry, connect_semaphore)
    entry.runtime_data = coordinator

    async def _stop(_event: Event) -> None:
        await coordinator.connection.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.connection.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShadeConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.connection.stop()
    return unloaded
