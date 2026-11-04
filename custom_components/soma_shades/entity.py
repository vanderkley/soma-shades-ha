"""The base of the entities of a shade."""

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .coordinator import ShadeCoordinator


class ShadeEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: ShadeCoordinator, key: str) -> None:
        self.coordinator = coordinator
        self.shade = coordinator.shade
        self._attr_unique_id = f"{self.shade.mac}_{key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self.shade.mac)},
            name=self.shade.display_name,
            model="Tilt 2" if coordinator.tilt else "Smart Shades 2",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
