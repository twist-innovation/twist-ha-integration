"""Platform for button integration.

ID terminology:
- twist_id: The hardware device ID from the Twist API (int)
- device_id: The Home Assistant device registry UUID (str)
- model_id: The model index within a Twist device (int)
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from twist.TwistButton import TwistButton

from . import TwistConfigEntry
from .const import BUTTON_EVENT_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwistConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for passed config_entry in HA."""
    twist_api = config_entry.runtime_data

    # Create device registry entries for buttons and register event callbacks
    device_registry = dr.async_get(hass)

    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue
            if isinstance(model, TwistButton):
                # Only create entries for models that are part of a product
                if not hasattr(model, "product_name") or model.product_name is None:
                    continue

                device_registry.async_get_or_create(
                    config_entry_id=config_entry.entry_id,
                    identifiers={(DOMAIN, model.product_name)},
                    manufacturer="Twist Innovation",
                    name=model.product_name,
                )

                @callback
                async def _fire_button_event(
                    btn_model,
                    btn_twist_id=device.twist_id,
                    btn_model_id=model.model_id,
                ):
                    """Fire an event for button press."""
                    if btn_model.last_event is None:
                        return
                    event_type = btn_model.last_event.name.lower()

                    if event_type not in BUTTON_EVENT_TYPES:
                        _LOGGER.debug(
                            "Ignoring unsupported button event '%s' for model_id=%s",
                            event_type,
                            btn_model_id,
                        )
                        return

                    event_data = {
                        "twist_id": btn_twist_id,
                        "model_id": btn_model_id,
                        "type": event_type,
                    }
                    hass.bus.async_fire("twist_button_event", event_data)

                await model.register_update_cb(_fire_button_event)
