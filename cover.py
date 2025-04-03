"""Platform for sensor integration."""

from __future__ import annotations

from typing import Any
import asyncio

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

from .twist_api import Twist
from twist import TwistLouvre

from importlib.metadata import version


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover for passed config_entry in HA."""

    tw_l: Twist = hass.data[DOMAIN]

    async_add_entities(
        HATwistShutter(shutter, config_entry.entry_id)
        for shutter in tw_l.get_devices(TwistLouvre.TwistLouvre)
    )


class HATwistShutter(CoverEntity):
    """Representation of a dummy Cover."""

    _attr_has_entity_name = True
    should_poll = False
    supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, shutter: TwistLouvre.TwistLouvre, entry_id: str) -> None:
        """Initialize the sensor."""
        self._twist_shutter = shutter
        self._entry_id = entry_id

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._twist_shutter.parent_device.twist_id}_{self._twist_shutter.model_id}"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"shutter {self._twist_shutter.model_id}"

        self.manufacturer = "Twist-Innovation"
        self.sw_version = None
        self._added_to_hass = False

        self._twist_shutter.register_update_cb(self.update_received)

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
            "identifiers": {(DOMAIN, self._twist_shutter.parent_device.twist_id)},
            "name": f"{self._twist_shutter.parent_device.twist_id}",
            "sw_version": self.sw_version,
            "model": "Twist Shutter",  # Todo: check the type of the shutter and use that name.
            "manufacturer": self.manufacturer,
        }

    @property
    def available(self) -> bool:
        """Return True if Roller and twist is available."""
        return True

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._twist_shutter.actual_state

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._twist_shutter.actual_state == self._twist_shutter.requested_state

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._twist_shutter.actual_state < self._twist_shutter.requested_state

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._twist_shutter.actual_state > self._twist_shutter.requested_state

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._twist_shutter.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._twist_shutter.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._twist_shutter.set_value(kwargs[ATTR_POSITION])

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._twist_shutter.stop()
