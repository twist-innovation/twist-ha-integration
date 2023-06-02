from homeassistant.helpers import device_registry as dr

from homeassistant.helpers.entity import Entity
from .twist_local import TwistLocal, TwistButton

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switch for passed config_entry in HA."""

    tw_l: TwistLocal = hass.data[DOMAIN]

    for button in tw_l.get_devices(TwistButton):
        HomeassistantButton(button, config_entry.entry_id, hass)


class HomeassistantButton:
    """Representation of a homeassistant button."""

    def __init__(self, button: TwistButton, entry_id: str, hass: HomeAssistant) -> None:
        """Initialize the sensor."""
        self._button = button
        self._entry_id = entry_id
        self._hass = hass

        device_registry = dr.async_get(self._hass)

        device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, self._button.twist_id)},
            manufacturer=self._button.twist_local.manufacturer,
            name=self._button.model,
            model=self._button.model,
            # sw_version=config.swversion,
            # hw_version=config.hwversion,
        )

        self._button.register_callback(self.fire_event)

    def fire_event(self) -> None:
        """Fire an event."""
        event_data = {
            "type": self._button.state,
        }
        self._hass.bus.async_fire(
            f"twist_local.button_{self._button.twist_id}_{self._button.model_index}",
            event_data,
        )
