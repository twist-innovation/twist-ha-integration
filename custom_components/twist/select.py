"""Platform for select integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from twist.TwistModel import TwistModel

from . import TwistConfigEntry
from .const import DOMAIN, MAX_CHANNELS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwistConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add channel select entities for passed config_entry in HA."""
    twist_api = config_entry.runtime_data

    # Every model supports switching between channels
    selects = []
    for device in twist_api.device_list:
        for model in device.model_list:
            if model is None:
                continue
            # Only create entities for models that are part of a product
            if not hasattr(model, "product_name") or model.product_name is None:
                continue

            select_entity = TwistChannelSelect(model, config_entry)
            selects.append(select_entity)
            # Register callback before adding entity to avoid race condition with MQTT
            await model.register_update_cb(select_entity.handle_update)

    async_add_entities(selects)


class TwistChannelSelect(SelectEntity):
    """Select for the active channel of a Twist model.

    Options are 1-based, the firmware channel index is 0-based.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, model: TwistModel, config_entry) -> None:
        """Initialize the select."""
        self._model = model
        self._config_entry = config_entry

        # Use device twist_id + model_id for truly unique ID
        device_id = self._model.parent_device.twist_id
        self._attr_unique_id = f"twist_{device_id}_{self._model.model_id}_channel"
        name = getattr(model, "name", f"Model {self._model.model_id}")
        self._attr_name = f"{name} channel"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._model.product_name)},
            name=self._model.product_name,
            manufacturer="Twist Innovation",
        )

    async def handle_update(self, model: Any) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def options(self) -> list[str]:
        """Return the available channels."""
        highest = self._model.highest_channel
        if highest is None or highest >= MAX_CHANNELS:
            count = MAX_CHANNELS
        else:
            count = highest + 1
        return [str(channel + 1) for channel in range(count)]

    @property
    def current_option(self) -> str | None:
        """Return the active channel."""
        active = self._model.active_channel
        # The firmware reports 255 while a channel is being loaded
        if active is None or active >= MAX_CHANNELS:
            return None
        return str(active + 1)

    async def async_select_option(self, option: str) -> None:
        """Change the active channel."""
        await self._model.set_channel(int(option) - 1)
