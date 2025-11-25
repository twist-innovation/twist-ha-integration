"""Platform for sensor integration."""

from __future__ import annotations

from typing import Any

from twist.TwistBinarySensor import TwistBinarySensor
from twist.TwistSensor import TwistSensor

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TwistConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwistConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensor for passed config_entry in HA."""
    twist_api = config_entry.runtime_data

    # Get models from the API and filter for sensor types
    sensors = []
    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue
            if isinstance(model, (TwistSensor, TwistBinarySensor)):
                sensors.append(TwistSensorEntity(model, config_entry))

    async_add_entities(sensors)


class TwistSensorEntity(SensorEntity):
    """Representation of a Twist sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, model: TwistSensor | TwistBinarySensor, config_entry) -> None:
        """Initialize the sensor."""
        self._model = model
        self._config_entry = config_entry

        self._attr_unique_id = f"{self._model.parent_device.twist_id}_{self._model.model_id}"
        self._attr_name = getattr(model, 'name', f"Sensor {self._model.model_id}")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._model.parent_device.twist_id))},
            name=str(self._model.parent_device.twist_id),
            manufacturer="Twist Innovation",
            model=getattr(model, 'device_type', 'Sensor'),
        )

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to HA."""
        await super().async_added_to_hass()
        self._model.register_update_cb(self._handle_update)

    async def _handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return getattr(self._model, 'value', None)
