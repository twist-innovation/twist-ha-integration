"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any


from homeassistant.components.sensor import SensorEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

from .twist_local import TwistLocal, TwistGeneralSensor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensor for passed config_entry in HA."""

    tw_l: TwistLocal = hass.data[DOMAIN]

    async_add_entities(
        TwistSensor(sensor, config_entry.entry_id)
        for sensor in tw_l.get_devices(TwistGeneralSensor)
    )


class TwistSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    should_poll = False

    def __init__(self, sensor: TwistGeneralSensor, entry_id: str) -> None:
        """Initialize the sensor."""
        self._sensor = sensor
        self._entry_id = entry_id

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._sensor.twist_id}_{self._sensor.model_index}"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"{self._sensor.name}"

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._sensor.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._sensor.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._sensor.twist_id)},
            "name": f"{self._sensor.twist_id}",
            "sw_version": self._sensor.firmware_version,
            "model": self._sensor.model,
            "manufacturer": self._sensor.twist_local.manufacturer,
        }

    @property
    def available(self) -> bool:
        """Return True if Roller and twist_local is available."""
        return self._sensor.online and self._sensor.twist_local.connected

    @property
    def native_value(self):
        """Return the state of the sensor."""

        return self._sensor.value

    @property
    def native_unit_of_measurement(self):
        return self._sensor.unit
