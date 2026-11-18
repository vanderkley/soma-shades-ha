"""The motor speed of a shade."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShadeConfigEntry
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([MotorSpeedNumber(entry.runtime_data, "motor_speed")])


class MotorSpeedNumber(ShadeEntity, NumberEntity):
    """The speed of the motor, which the shade keeps, e.g. lower for a quieter shade in the bedroom."""

    _attr_translation_key = "motor_speed"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> int | None:
        return self.shade.motor_speed

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_motor_speed(int(value))
        self.async_write_ha_state()
