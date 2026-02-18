"""Platform for sensor integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from twist.TwistBinarySensor import TwistBinarySensor
from twist.TwistTemperature import TwistTemperature

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
            if isinstance(model, (TwistTemperature, TwistBinarySensor)):
                # Only create entities for models that are part of a product
                if not hasattr(model, "product_name") or model.product_name is None:
                    continue

                sensor_entity = TwistSensorEntity(model, config_entry)
                sensors.append(sensor_entity)
                # Register callback before adding entity to avoid race condition with MQTT
                await model.register_update_cb(sensor_entity.handle_update)

    async_add_entities(sensors)


class TwistSensorEntity(SensorEntity):
    """Representation of a Twist sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, model: TwistTemperature | TwistBinarySensor, config_entry
    ) -> None:
        """Initialize the sensor."""
        self._model = model
        self._config_entry = config_entry

        # Use device twist_id + model_id for truly unique ID
        device_id = self._model.parent_device.twist_id
        self._attr_unique_id = f"twist_{device_id}_{self._model.model_id}"
        self._attr_name = getattr(model, "name", f"Sensor {self._model.model_id}")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._model.product_name)},
            name=self._model.product_name,
            manufacturer="Twist Innovation",
        )

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to HA."""
        await super().async_added_to_hass()
        # Callback already registered in async_setup_entry before entity creation

    async def handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if isinstance(self._model, TwistTemperature):
            return self._model.actual_state
        if isinstance(self._model, TwistBinarySensor):
            # Binary sensor not fully implemented yet, but use actual_state when available
            return getattr(self._model, "actual_state", None)
        return None
