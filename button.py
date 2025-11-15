"""Platform for button integration."""

from __future__ import annotations

import json

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TwistConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwistConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for passed config_entry in HA."""
    twist = config_entry.runtime_data

    # Create device registry entries for buttons and register event callbacks
    device_registry = dr.async_get(hass)

    for device in twist.devices:
        if device.get("type") != "Button":
            continue

        device_id = device["device_id"]
        model_id = device["model_id"]
        device_name = device["name"]

        # Create device registry entry
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            manufacturer="Twist Innovation",
            name=device_name or device_id,
            model="Button",
        )

        # Subscribe to button events
        topic = f"{twist.installation_id}/send/{device_id}/model/context"

        @callback
        def message_received(msg, dev_id=device_id, mod_id=model_id):
            """Handle new MQTT messages."""
            try:
                context = json.loads(msg.payload)
                if context.get("model_index") == mod_id:
                    # Fire button event
                    context_data = context.get("context", [])
                    if context_data:
                        button_state = context_data[0].get("value", 0)
                        # Map button state: 0=Pushed, 1=Released, 2=LongPushed, 3=LongReleased
                        state_names = ["Pushed", "Released", "LongPushed", "LongReleased"]
                        state_name = state_names[button_state] if button_state < 4 else "Unknown"

                        event_data = {
                            "type": state_name,
                            "device_id": dev_id,
                            "model_id": mod_id,
                        }
                        hass.bus.async_fire(
                            f"twist.button_{dev_id}_{mod_id}",
                            event_data,
                        )
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        await mqtt.async_subscribe(hass, topic, message_received, 0)
