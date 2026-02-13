"""Platform for switch integration."""

from __future__ import annotations

from typing import Any

from twist.TwistRelay import TwistRelay

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
    twist_api = config_entry.runtime_data

    # Get models from the API and filter for switch types
    switches = []
    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue
            if isinstance(model, TwistRelay):
                # Only create entities for models that are part of a product
                if not hasattr(model, 'product_name') or model.product_name is None:
                    # Still register callback to avoid crashes, but don't create entity
                    async def _dummy_callback(m):
                        pass
                    await model.register_update_cb(_dummy_callback)
                    continue

                switch_entity = TwistSwitch(model, config_entry)
                switches.append(switch_entity)
                # Register callback before adding entity to avoid race condition with MQTT
                await model.register_update_cb(switch_entity._handle_update)

    async_add_entities(switches)


class TwistSwitch(SwitchEntity):
    """Representation of a Twist switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, model: TwistRelay, config_entry) -> None:
        """Initialize the switch."""
        self._model = model
        self._config_entry = config_entry

        # Use device twist_id + model_id for truly unique ID
        device_id = self._model.parent_device.twist_id
        self._attr_unique_id = f"twist_{device_id}_{self._model.model_id}"
        self._attr_name = getattr(model, 'name', f"Switch {self._model.model_id}")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._model.product_name)},
            name=self._model.product_name,
            manufacturer="Twist Innovation",
        )

    async def async_added_to_hass(self) -> None:
        """Run when this entity has been added to HA."""
        await super().async_added_to_hass()
        # Callback already registered in async_setup_entry before entity creation

    async def _handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._model.actual_state != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._model.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._model.turn_off()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        await self._model.toggle()
