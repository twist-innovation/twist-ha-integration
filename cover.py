"""Platform for cover integration."""

from __future__ import annotations

import logging
from typing import Any

from twist.TwistGarage import TwistGarage
from twist.TwistShutter import TwistShutter

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
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
    """Add cover for passed config_entry in HA."""
    twist_api = config_entry.runtime_data

    # Get models from the API and filter for cover types
    covers = []
    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue

            # Skip models that are not part of a product
            if not hasattr(model, "product_name"):
                continue

            if model.product_name is None:
                continue

            if isinstance(model, (TwistShutter, TwistGarage)):
                covers.append(TwistCover(model, config_entry))
    async_add_entities(covers)


class TwistCover(CoverEntity):
    """Representation of a Twist cover."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, model: TwistShutter | TwistGarage, config_entry) -> None:
        """Initialize the cover."""
        self._model = model
        self._config_entry = config_entry

        # Use device twist_id + model_id for truly unique ID
        device_id = self._model.parent_device.twist_id
        self._attr_unique_id = f"twist_{device_id}_{self._model.model_id}"
        self._attr_name = getattr(model, "name", f"Cover {self._model.model_id}")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._model.product_name)},
            name=self._model.product_name,
            manufacturer="Twist Innovation",
        )

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to hass."""
        await super().async_added_to_hass()
        self._model.register_update_cb(self._handle_update)

    async def _handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self._model.actual_state

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._model.actual_state == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._model.actual_state > self._model.requested_state

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._model.actual_state < self._model.requested_state

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._model.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._model.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        await self._model.set_value(kwargs[ATTR_POSITION])

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._model.stop()
