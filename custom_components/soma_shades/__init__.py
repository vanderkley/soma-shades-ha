"""Soma Smart Shades over Bluetooth LE."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN
from .coordinator import ShadeCoordinator

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SENSOR, Platform.SWITCH]

type ShadeConfigEntry = ConfigEntry[ShadeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ShadeConfigEntry) -> bool:
    connect_semaphore = hass.data.setdefault(DOMAIN, asyncio.Semaphore(1))
    coordinator = ShadeCoordinator(hass, entry, connect_semaphore)
    entry.runtime_data = coordinator

    async def _stop(_event: Event) -> None:
        await coordinator.async_stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShadeConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
