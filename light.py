"""Platform for sensor integration."""

from __future__ import annotations

from typing import Any

import asyncio


from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    LightEntityFeature,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

from .twist_api import Twist
from twist import TwistLight

from importlib.metadata import version


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switch for passed config_entry in HA."""

    tw_l: Twist = hass.data[DOMAIN]

    async_add_entities(
        HATwistLight(light, config_entry.entry_id)
        for light in tw_l.get_devices(TwistLight.TwistLight)
    )


class HATwistLight(LightEntity):
    """Representation of a dummy Cover."""

    _attr_has_entity_name = True
    should_poll = False

    def __init__(self, light: TwistLight.TwistLight, entry_id: str) -> None:
        """Initialize the sensor."""
        self._twist_light = light
        self._entry_id = entry_id

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = (
            f"{self._twist_light.parent_device.twist_id}_{self._twist_light.model_id}"
        )

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"light {self._twist_light.model_id}"

        self.manufacturer = "Twist-Innovation"
        self.sw_version = None
        self._added_to_hass = False

        self._twist_light.register_update_cb(self.update_received)

        asyncio.create_task(self._set_version_async())  # set in background

    async def _set_version_async(self):
        self.sw_version = await asyncio.to_thread(version, "twist-innovation-api")

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._added_to_hass = True

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._added_to_hass = False

    async def update_received(self, model):
        if self._added_to_hass:
            self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._twist_light.parent_device.twist_id)},
            "name": f"{self._twist_light.parent_device.twist_id}",
            "sw_version": self.sw_version,
            "model": "Twist Mono Light",
            "manufacturer": self.manufacturer,
        }

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        return LightEntityFeature.TRANSITION

    @property
    def available(self) -> bool:
        """Return True if Roller and twist is available."""
        # return self._twist_light.online and self._twist_light.twist.connected
        return True

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._twist_light.actual_state != 0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._twist_light.actual_state * 2.55)

    @property
    def supported_color_modes(self):
        return {ColorMode.BRIGHTNESS}

    @property
    def color_mode(self):
        return ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        if ATTR_BRIGHTNESS in kwargs:
            if ATTR_TRANSITION in kwargs:
                return await self._twist_light.set_value(
                    round(kwargs[ATTR_BRIGHTNESS] / 2.55),
                    round(kwargs[ATTR_TRANSITION] * 1000.0),
                )

            return await self._twist_light.set_value(
                round(kwargs[ATTR_BRIGHTNESS] / 2.55)
            )

        await self._twist_light.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        if ATTR_TRANSITION in kwargs:
            return await self._twist_light.set_value(
                0,
                round(kwargs[ATTR_TRANSITION] * 1000.0),
            )
        await self._twist_light.set_value(0)

    # async def async_toggle(self, **kwargs: Any):
    #     """Toggle the entity."""
    #     return self._switch.toggle()
