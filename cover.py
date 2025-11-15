"""Platform for cover integration."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import mqtt
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
    twist = config_entry.runtime_data

    # Get all cover devices (Garage and Louvre types)
    covers = []
    for device in twist.devices:
        device_type = device.get("type", "")
        if device_type in ("Garage", "Louvre"):
            covers.append(TwistCover(twist, device, config_entry))

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

    def __init__(self, twist, device_config: dict[str, Any], config_entry) -> None:
        """Initialize the cover."""
        self._twist = twist
        self._device_config = device_config
        self._config_entry = config_entry

        self._device_id = device_config["device_id"]
        self._model_id = device_config["model_id"]
        self._device_name = device_config["name"]
        self._device_type = device_config["type"]

        self._current_position = 0
        self._requested_position = 0

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
                    # Update position from context
                    context_data = context.get("context", [])
                    if context_data:
                        raw_value = context_data[0].get("value", 0)
                        self._current_position = int(raw_value / 65535 * 100)
                        self.async_write_ha_state()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        await mqtt.async_subscribe(self.hass, topic, message_received, 0)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self._current_position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._current_position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._current_position > self._requested_position

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._current_position < self._requested_position

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._set_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._set_position(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        position = kwargs[ATTR_POSITION]
        await self._set_position(position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        data = {
            "model_index": self._model_id,
            "event_id": 1,  # Stop motor
            "data": [],
        }
        await self._send_command(data)

    async def _set_position(self, position: int) -> None:
        """Set the requested position."""
        self._requested_position = position
        raw_position = int(position * 65535 / 100)

        data = {
            "model_index": self._model_id,
            "event_id": 4,  # Set value
            "data": [int(raw_position / 256), int(raw_position % 256)],
        }

        await self._send_command(data)

    async def _send_command(self, data: dict) -> None:
        """Send command via MQTT."""
        json_data = json.dumps(data)
        topic = f"{self._twist.installation_id}/send/{self._device_id}/event"
        await mqtt.async_publish(self.hass, topic, json_data, 0, False)
