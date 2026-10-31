"""The battery, charging and connection sensors of a shade."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from soma_shades import ShadeClient

from . import ShadeConfigEntry
from .coordinator import ShadeCoordinator
from .entity import ShadeEntity


@dataclass(frozen=True, kw_only=True)
class ShadeSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ShadeClient], int | datetime | None]


SENSORS = (
    ShadeSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda shade: shade.battery_level,
    ),
    ShadeSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda shade: shade.battery_voltage,
    ),
    ShadeSensorDescription(
        key="input_voltage",
        translation_key="input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda shade: shade.input_voltage,
    ),
    ShadeSensorDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,  # the unit is not certain
        value_fn=lambda shade: shade.charging_current,
    ),
    ShadeSensorDescription(
        key="connected_since",
        translation_key="connected_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda shade: shade.last_connect_time.astimezone() if shade.last_connect_time else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShadeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ShadeSensor(entry.runtime_data, description) for description in SENSORS)


class ShadeSensor(ShadeEntity, SensorEntity):
    entity_description: ShadeSensorDescription

    def __init__(self, coordinator: ShadeCoordinator, description: ShadeSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | datetime | None:
        return self.entity_description.value_fn(self.shade)
