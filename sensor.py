"""Platform for sensor integration."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import mqtt
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
    twist = config_entry.runtime_data

    # Get all sensor devices
    sensors = []
    for device in twist.devices:
        device_type = device.get("type", "")
        # For now, we don't create sensor entities as we don't have sensor-specific
        # device types in the mapping. Binary_Sensor will be handled by binary_sensor platform
        # This is a placeholder for future sensor types
        if device_type == "Sensor":
            sensors.append(TwistSensor(twist, device, config_entry))

    async_add_entities(sensors)


class TwistSensor(SensorEntity):
    """Representation of a Twist sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, twist, device_config: dict[str, Any], config_entry) -> None:
        """Initialize the sensor."""
        self._twist = twist
        self._device_config = device_config
        self._config_entry = config_entry

        self._device_id = device_config["device_id"]
        self._model_id = device_config["model_id"]
        self._device_name = device_config["name"]
        self._device_type = device_config["type"]

        self._current_value = None

        self._attr_unique_id = f"{self._device_id}_{self._model_id}"
        self._attr_name = self._device_name or f"{self._device_type} {self._model_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer="Twist Innovation",
            model=self._device_type,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events when added to hass."""
        await super().async_added_to_hass()

        # Subscribe to model context updates
        topic = f"{self._twist.installation_id}/send/{self._device_id}/model/context"

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                context = json.loads(msg.payload)
                if context.get("model_index") == self._model_id:
                    # Update value from context
                    context_data = context.get("context", [])
                    if context_data:
                        self._current_value = context_data[0].get("value")
                        self.async_write_ha_state()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        await mqtt.async_subscribe(self.hass, topic, message_received, 0)

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self._current_value
