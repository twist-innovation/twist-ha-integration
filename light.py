"""Platform for light integration."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
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
    twist = config_entry.runtime_data

    # Get all light devices (Light and RGB types)
    lights = []
    for device in twist.devices:
        device_type = device.get("type", "")
        if device_type in ("Light", "RGB"):
            lights.append(TwistLightEntity(twist, device, config_entry))

    async_add_entities(lights)


class TwistLightEntity(LightEntity):
    """Representation of a Twist light."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(self, twist, device_config: dict[str, Any], config_entry) -> None:
        """Initialize the light."""
        self._twist = twist
        self._device_config = device_config
        self._config_entry = config_entry

        self._device_id = device_config["device_id"]
        self._model_id = device_config["model_id"]
        self._device_name = device_config["name"]
        self._device_type = device_config["type"]

        self._brightness = 0
        self._hs_color = (0, 0)

        self._attr_unique_id = f"{self._device_id}_{self._model_id}"
        self._attr_name = self._device_name or f"{self._device_type} {self._model_id}"

        # Determine color mode based on device type
        if self._device_type == "RGB":
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

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
                    # Update brightness from context
                    context_data = context.get("context", [])
                    if context_data:
                        # Value is 0-100, convert to 0-255 for HA
                        brightness_pct = context_data[0].get("value", 0)
                        self._brightness = round(brightness_pct * 2.55)
                        self.async_write_ha_state()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        await mqtt.async_subscribe(self.hass, topic, message_received, 0)

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._brightness != 0

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._device_type == "RGB":
            return self._hs_color
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness_pct = 100
        transition_ms = 0

        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = round(kwargs[ATTR_BRIGHTNESS] / 2.55)
        elif self._brightness > 0:
            brightness_pct = round(self._brightness / 2.55)

        if ATTR_TRANSITION in kwargs:
            transition_ms = round(kwargs[ATTR_TRANSITION] * 1000.0)

        if ATTR_HS_COLOR in kwargs and self._device_type == "RGB":
            self._hs_color = kwargs[ATTR_HS_COLOR]
            # TODO: Send HS color command for RGB lights

        await self._set_brightness(brightness_pct, transition_ms)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition_ms = 0
        if ATTR_TRANSITION in kwargs:
            transition_ms = round(kwargs[ATTR_TRANSITION] * 1000.0)

        await self._set_brightness(0, transition_ms)

    async def _set_brightness(self, brightness_pct: int, transition_ms: int = 0) -> None:
        """Set the brightness value."""
        data = {
            "model_index": self._model_id,
            "event_id": 4,  # Set value
            "data": [brightness_pct],
        }

        if transition_ms > 0:
            data["transition"] = transition_ms

        json_data = json.dumps(data)
        topic = f"{self._twist.installation_id}/send/{self._device_id}/event"
        await mqtt.async_publish(self.hass, topic, json_data, 0, False)
