"""The Twist integration."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from twist import TwistAPI


type TwistConfigEntry = ConfigEntry[TwistAPI]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: TwistConfigEntry) -> bool:
    """Set up Twist from a config entry."""
    try:
        # Initialize Twist API with backend configuration
        twist_api = TwistAPI(
            backend_url=entry.data["backend_url"],
            api_key=entry.data["api_key"],
            installation_uuid=entry.data["installation_uuid"],
        )

        # Fetch models from backend first (this sets installation_id and installation_name)
        models = await twist_api.get_models()

        # Update config entry title with installation name
        if twist_api.installation_name and entry.title != twist_api.installation_name:
            hass.config_entries.async_update_entry(
                entry, title=twist_api.installation_name
            )

        _LOGGER.info(
            "Loaded %d models from Twist installation '%s' (ID: %s)",
            len(models),
            twist_api.installation_name or entry.data["installation_uuid"],
            twist_api.installation_id,
        )

        # Set up MQTT publish/subscribe functions
        async def mqtt_publish(topic: str, payload: str) -> None:
            """Publish MQTT message."""
            await mqtt.async_publish(hass, topic, payload, 0, False)

        async def mqtt_subscribe(topic: str, callback) -> None:
            """Subscribe to MQTT topic."""

            # Wrap the callback to match HA MQTT signature
            async def wrapped_callback(msg):
                """Wrap callback to extract topic and payload from message."""
                # Payload is already a string in HA MQTT
                payload = (
                    msg.payload
                    if isinstance(msg.payload, str)
                    else msg.payload.decode()
                )
                await callback(msg.topic, payload)

            await mqtt.async_subscribe(hass, topic, wrapped_callback, 0)

        # Set up MQTT publish first so entities can send messages during registration
        twist_api.set_mqtt_publish(mqtt_publish)

    except Exception as ex:
        _LOGGER.exception("Failed to set up Twist integration")
        raise ConfigEntryNotReady(
            f"Unable to connect to Twist installation {entry.data.get('installation_uuid', 'unknown')}: {ex}"
        ) from ex

    entry.runtime_data = twist_api

    # Set up platforms - entities can now register callbacks and send messages
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Now set up MQTT subscribe to start receiving messages
    await twist_api.set_mqtt_subscribe(mqtt_subscribe)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TwistConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
