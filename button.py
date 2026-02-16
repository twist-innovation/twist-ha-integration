"""Platform for button integration."""

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
                # Create device registry entry only if part of a product
                if hasattr(model, "product_name") and model.product_name is not None:
                    device_registry.async_get_or_create(
                        config_entry_id=config_entry.entry_id,
                        identifiers={(DOMAIN, model.product_name)},
                        manufacturer="Twist Innovation",
                        name=model.product_name,
                    )

                # Register callback to fire events for ALL buttons (even without product_name)
                @callback
                async def _fire_button_event(
                    btn_model,
                    btn_device_id=device.twist_id,
                    btn_model_id=model.model_id,
                ):
                    """Fire an event for button press."""
                    event_type: str | None = None
                    if hasattr(btn_model, "last_event") and btn_model.last_event is not None:
                        last_event = btn_model.last_event
                        event_type = getattr(last_event, "name", str(last_event)).lower()
                    elif hasattr(btn_model, "state") and btn_model.state is not None:
                        state = btn_model.state
                        event_type = getattr(state, "name", str(state)).lower()

                    if event_type not in BUTTON_EVENT_TYPES:
                        _LOGGER.debug(
                            "Ignoring unsupported button event '%s' for model_id=%s",
                            event_type,
                            btn_model_id,
                        )
                        return

                    event_data = {
                        "device_id": btn_device_id,
                        "model_id": btn_model_id,
                        "type": event_type,
                    }
                    # Fire single event type for device triggers
                    hass.bus.async_fire("twist_button_event", event_data)

                await model.register_update_cb(_fire_button_event)
