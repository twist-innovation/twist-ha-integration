"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any


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

from .twist_local import TwistLocal, TwistMonoLight


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switch for passed config_entry in HA."""

    tw_l: TwistLocal = hass.data[DOMAIN]

    async_add_entities(
        TwistLight(light, config_entry.entry_id)
        for light in tw_l.get_devices(TwistMonoLight)
    )


class TwistLight(LightEntity):
    """Representation of a dummy Cover."""

    _attr_has_entity_name = True
    should_poll = False

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, light: TwistMonoLight, entry_id: str) -> None:
        """Initialize the sensor."""
        self._light = light
        self._entry_id = entry_id

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._light.twist_id}_{self._light.model_index}"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"light {self._light.model_index}"

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._light.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._light.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._light.twist_id)},
            "name": f"{self._light.twist_id}",
            "sw_version": self._light.firmware_version,
            "model": self._light.model,
            "manufacturer": self._light.twist_local.manufacturer,
        }

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        return LightEntityFeature.TRANSITION

    @property
    def available(self) -> bool:
        """Return True if Roller and twist_local is available."""
        return self._light.online and self._light.twist_local.connected

    @property
    def is_on(self) -> bool:
        """Return if the cover is opening or not."""
        return self._light.intensity != 0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._light.intensity * 255 / 100)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        if ATTR_BRIGHTNESS in kwargs:
            if ATTR_TRANSITION in kwargs:
                return await self._light.set_intensity_with_fade_time(
                    round(kwargs[ATTR_BRIGHTNESS] / 2.55),
                    round(kwargs[ATTR_TRANSITION] * 1000.0),
                )

            return await self._light.set_intensity(
                round(kwargs[ATTR_BRIGHTNESS] / 2.55)
            )

        await self._light.set_intensity(100)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        if ATTR_TRANSITION in kwargs:
            return await self._light.set_intensity_with_fade_time(
                0,
                round(kwargs[ATTR_TRANSITION] * 1000.0),
            )
        await self._light.set_intensity(0)

    # async def async_toggle(self, **kwargs: Any):
    #     """Toggle the entity."""
    #     return self._switch.toggle()
