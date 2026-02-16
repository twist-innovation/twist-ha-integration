"""Provides device triggers for Twist buttons."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import BUTTON_EVENT_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Button event types - map internal event types to display names
# Custom components must use display names directly since translation system
# doesn't work reliably for device automations in custom components
TRIGGER_TYPE_SCHEMA = {
    "push": "Pushed",
    "release": "Released",
    "long_push": "Long pressed",
    "long_release": "Long press released",
    "double_push": "Double clicked",
    "double_release": "Double click released",
    "double_long_push": "Double long pressed",
    "double_long_release": "Double long press released",
}

TRIGGER_TYPES = set(BUTTON_EVENT_TYPES)

# Additional config for button subtype (model_id)
CONF_SUBTYPE = "subtype"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),  # Validate against keys
        vol.Required(CONF_SUBTYPE): vol.Coerce(int),
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    return TRIGGER_SCHEMA(config)


def _get_button_subtypes_by_device_id(
    hass: HomeAssistant, device_id: str
) -> dict[int, str]:
    """Return button model IDs and names for a Home Assistant device."""
    from homeassistant.helpers import device_registry as dr
    from twist.TwistButton import TwistButton

    config_entries = hass.config_entries.async_entries(DOMAIN)
    device_registry = dr.async_get(hass)
    subtypes: dict[int, str] = {}

    for entry in config_entries:
        if not hasattr(entry, "runtime_data"):
            continue

        twist_api = entry.runtime_data

        for twist_device in twist_api.device_list:
            for model in twist_device.model_list:
                if model is None or not isinstance(model, TwistButton):
                    continue

                if not hasattr(model, "product_name") or model.product_name is None:
                    continue

                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, model.product_name)}
                )

                if device_entry and device_entry.id == device_id:
                    subtypes[model.model_id] = getattr(
                        model, "name", f"Button {model.model_id}"
                    )

    return subtypes


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Twist button devices."""
    subtypes = _get_button_subtypes_by_device_id(hass, device_id)
    if not subtypes:
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: event_type,
            CONF_SUBTYPE: model_id,
        }
        for model_id in sorted(subtypes)
        for event_type in TRIGGER_TYPE_SCHEMA
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: event_trigger.TriggerActionType,
    trigger_info: event_trigger.TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    # config[CONF_TYPE] is already the event type key (e.g., "push", "release")
    event_type = config[CONF_TYPE]

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: "twist_button_event",
            event_trigger.CONF_EVENT_DATA: {
                "model_id": config[CONF_SUBTYPE],
                "type": event_type,
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    device_id = config[CONF_DEVICE_ID]
    _LOGGER.debug("Getting trigger capabilities for device_id: %s", device_id)
    subtype_names = _get_button_subtypes_by_device_id(hass, device_id)

    # Return the subtype mapping for the UI
    _LOGGER.debug(
        "Found %s buttons for device %s: %s",
        len(subtype_names),
        device_id,
        subtype_names,
    )
    return {
        "extra_fields": vol.Schema({vol.Required(CONF_SUBTYPE): vol.In(subtype_names)})
    }
