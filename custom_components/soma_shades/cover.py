"""The shade as a cover."""

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShadeConfigEntry
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    cover = TiltCover if coordinator.tilt else ShadeCover
    async_add_entities([cover(coordinator, "cover")])


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


class TiltCover(ShadeEntity, CoverEntity):
    """A Tilt turns the slats, it is closed upwards at 0, open at 50 and closed downwards at 100.

    As in the Soma integration of Home Assistant, the tilt position is closed downwards at 0, open at 50 and closed
    upwards at 100.
    """

    _attr_name = None
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )
    CLOSED_DOWN_THRESHOLD = 20
    CLOSED_UP_THRESHOLD = 80

    @property
    def current_cover_tilt_position(self) -> int | None:
        position = self.shade.position
        return None if position is None else 100 - position

    @property
    def is_closed(self) -> bool | None:
        tilt = self.current_cover_tilt_position
        return None if tilt is None else not self.CLOSED_DOWN_THRESHOLD <= tilt <= self.CLOSED_UP_THRESHOLD

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(lambda: self.shade.set_position(50))

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(lambda: self.shade.set_position(100))

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.shade.stop)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        target = 100 - kwargs[ATTR_TILT_POSITION]
        await self.coordinator.async_command(lambda: self.shade.set_position(target))
