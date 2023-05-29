"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any


from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

from .twist_local import TwistLocal, TbShutter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover for passed config_entry in HA."""

    tw_l: TwistLocal = hass.data[DOMAIN]

    async_add_entities(
        TwistShutter(tbshutter, config_entry.entry_id)
        for tbshutter in tw_l.get_devices(TbShutter)
    )


class TwistShutter(CoverEntity):
    """Representation of a dummy Cover."""

    _attr_has_entity_name = True
    should_poll = False
    supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, shutter: TbShutter, entry_id: str) -> None:
        """Initialize the sensor."""
        self._shutter = shutter
        self._entry_id = entry_id

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._shutter.twist_id}_{self._shutter.model_index}"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"- {self._shutter.model_index}"

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._shutter.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._shutter.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._shutter.twist_id)},
            "name": self._shutter.twist_id,
            "sw_version": self._shutter.firmware_version,
            "model": self._shutter.model,
            "manufacturer": self._shutter.twist_local.manufacturer,
        }

    @property
    def available(self) -> bool:
        """Return True if Roller and twist_local is available."""
        return self._shutter.online and self._shutter.twist_local.connected

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._shutter.position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._shutter.position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._shutter.moving < 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._shutter.moving > 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._shutter.set_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._shutter.set_position(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._shutter.set_position(kwargs[ATTR_POSITION])

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._shutter.stop_motor()
