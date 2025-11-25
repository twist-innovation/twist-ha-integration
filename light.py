"""Platform for light integration."""

from __future__ import annotations

from typing import Any

from twist.TwistLight import TwistLight
from twist.TwistRgb import TwistRgb

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
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
    """Add light entities for passed config_entry in HA."""
    twist_api = config_entry.runtime_data

    # Get models from the API and filter for light types
    lights = []
    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue
            if isinstance(model, (TwistLight, TwistRgb)):
                lights.append(TwistLightEntity(model, config_entry))

    async_add_entities(lights)


class TwistLightEntity(LightEntity):
    """Representation of a Twist light."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(self, model: TwistLight | TwistRgb, config_entry) -> None:
        """Initialize the light."""
        self._model = model
        self._config_entry = config_entry

        self._attr_unique_id = f"{self._model.parent_device.twist_id}_{self._model.model_id}"
        self._attr_name = getattr(model, 'name', f"Light {self._model.model_id}")

        # Determine color mode based on light type
        if isinstance(self._model, TwistRgb):
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._model.parent_device.twist_id))},
            name=str(self._model.parent_device.twist_id),
            manufacturer="Twist Innovation",
            model=getattr(model, 'device_type', 'Light'),
        )

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to hass."""
        await super().async_added_to_hass()
        self._model.register_update_cb(self._handle_update)

    async def _handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._model.actual_state != 0

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return round(self._model.actual_state * 2.55)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = round(kwargs[ATTR_BRIGHTNESS] / 2.55)
            if ATTR_TRANSITION in kwargs:
                transition_ms = round(kwargs[ATTR_TRANSITION] * 1000.0)
                await self._model.set_value(brightness_pct, transition_ms)
            else:
                await self._model.set_value(brightness_pct)
        else:
            await self._model.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs:
            transition_ms = round(kwargs[ATTR_TRANSITION] * 1000.0)
            await self._model.set_value(0, transition_ms)
        else:
            await self._model.set_value(0)
