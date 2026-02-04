"""Platform for button integration."""

from __future__ import annotations

from twist.TwistButton import TwistButton

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
                    event_data = {
                        "type": btn_model.state
                        if hasattr(btn_model, "state")
                        else "pressed",
                        "device_id": btn_device_id,
                        "model_id": btn_model_id,
                    }
                    hass.bus.async_fire(
                        f"twist.button_{btn_device_id}_{btn_model_id}",
                        event_data,
                    )

                await model.register_update_cb(_fire_button_event)
