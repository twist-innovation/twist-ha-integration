"""Platform for switch integration."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
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
    """Add switch entities for passed config_entry in HA."""
    twist = config_entry.runtime_data

    # Get all relay (switch) devices
    switches = []
    for device in twist.devices:
        if device.get("type") == "Relay":
            switches.append(TwistSwitch(twist, device, config_entry))

    async_add_entities(switches)


class TwistSwitch(SwitchEntity):
    """Representation of a Twist switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, twist, device_config: dict[str, Any], config_entry) -> None:
        """Initialize the switch."""
        self._twist = twist
        self._device_config = device_config
        self._config_entry = config_entry

        self._device_id = device_config["device_id"]
        self._model_id = device_config["model_id"]
        self._device_name = device_config["name"]

        self._current_state = False

        self._attr_unique_id = f"{self._device_id}_{self._model_id}"
        self._attr_name = self._device_name or f"Relay {self._model_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer="Twist Innovation",
            model="Relay",
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
                    # Update state from context
                    context_data = context.get("context", [])
                    if context_data:
                        self._current_state = context_data[0].get("value") == 1
                        self.async_write_ha_state()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        await mqtt.async_subscribe(self.hass, topic, message_received, 0)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._current_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        data = {
            "model_index": self._model_id,
            "event_id": 0,  # Set
            "data": [],
        }
        await self._send_command(data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        data = {
            "model_index": self._model_id,
            "event_id": 1,  # Clear
            "data": [],
        }
        await self._send_command(data)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        if self._current_state:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def _send_command(self, data: dict) -> None:
        """Send command via MQTT."""
        json_data = json.dumps(data)
        topic = f"{self._twist.installation_id}/send/{self._device_id}/event"
        await mqtt.async_publish(self.hass, topic, json_data, 0, False)
