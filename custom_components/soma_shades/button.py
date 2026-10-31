"""The buttons of a shade."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShadeConfigEntry
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([IdentifyButton(coordinator, "identify"), SyncTimeButton(coordinator, "sync_time")])


class IdentifyButton(ShadeEntity, ButtonEntity):
    """Beep to find out which shade this is."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.shade.identify)


class SyncTimeButton(ShadeEntity, ButtonEntity):
    """Set the clock of the shade, which the schedules of the Soma app use."""

    _attr_translation_key = "sync_time"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.shade.sync_time)
