"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

# These constants are relevant to the type of entity we are using.
# See below for how they are used.


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


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cover for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    tw_l: TwistLocal = hass.data[DOMAIN]

    # @callback
    # def new_device(tbshutter):
    #     # Add all entities to HA
    #     async_add_entities([TwistShutter(tbshutter, config_entry.entry_id)], True)

    # await tw_l.scan_for_devices(new_device)

    async_add_entities(
        TwistShutter(tbshutter, config_entry.entry_id)
        for tbshutter in tw_l.get_devices(TbShutter)
    )


# This entire class could be written to extend a base class to ensure common attributes
# are kept identical/in sync. It's broken apart here between the Cover and Sensors to
# be explicit about what is returned, and the comments outline where the overlap is.
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
        # Usual setup is done here. Callbacks are added in async_added_to_hass.
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
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        self._shutter.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._shutter.remove_callback(self.async_write_ha_state)

    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._shutter.twist_id)},
            # If desired, the name for the device could be different to the entity
            "name": self._shutter.twist_id,
            "sw_version": self._shutter.firmware_version,
            "model": self._shutter.model,
            "manufacturer": self._shutter.twist_local.manufacturer,
        }

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if Roller and twist_local is available."""
        return self._shutter.online and self._shutter.twist_local.connected

    # The following properties are how HA knows the current state of the device.
    # These must return a value from memory, not make a live query to the device/hub
    # etc when called (hence they are properties). For a push based integration,
    # HA is notified of changes via the async_write_ha_state call. See the __init__
    # method for hos this is implemented in this example.
    # The properties that are expected for a cover are based on the supported_features
    # property of the object. In the case of a cover, see the following for more
    # details: https://developers.home-assistant.io/docs/core/entity/cover/
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

    # These methods allow HA to tell the actual device what to do. In this case, move
    # the cover to the desired position, or open and close it all the way.
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
