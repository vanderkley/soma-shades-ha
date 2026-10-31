"""The switch that leaves a shade free for e.g. the Soma app, a shade accepts a single connection."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShadeConfigEntry
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BluetoothConnectionSwitch(entry.runtime_data, "bluetooth_connection")])


class BluetoothConnectionSwitch(ShadeEntity, SwitchEntity):
    _attr_translation_key = "bluetooth_connection"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        return True  # it has to work while the shade is unavailable

    @property
    def is_on(self) -> bool:
        return self.shade.bluetooth_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_bluetooth_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_bluetooth_enabled(False)
