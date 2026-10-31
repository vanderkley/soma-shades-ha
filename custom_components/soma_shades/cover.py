"""The shade as a cover."""

from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShadeConfigEntry
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ShadeCover(entry.runtime_data, "cover")])


class ShadeCover(ShadeEntity, CoverEntity):
    """In Home Assistant 100 is open, a shade is open at 0."""

    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int | None:
        position = self.shade.position
        return None if position is None else 100 - position

    @property
    def is_closed(self) -> bool | None:
        position = self.shade.position
        return None if position is None else position == 100

    @property
    def is_opening(self) -> bool:
        return self.shade.cover_status == "opening"

    @property
    def is_closing(self) -> bool:
        return self.shade.cover_status == "closing"

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.shade.move_up)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.shade.move_down)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.shade.stop)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = 100 - kwargs[ATTR_POSITION]
        await self.coordinator.async_command(lambda: self.shade.set_position(target))
