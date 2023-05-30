"""The Twist Local integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

from . import twist_local

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twist Local from a config entry."""

    tw_l = twist_local.TwistLocal(entry.data["network"], hass)
    await tw_l.check_connection()
    await tw_l.scan_for_devices()

    hass.data[DOMAIN] = tw_l

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_parameter(call):
        """Handle the service call."""
        device_id = call.data.get("device_id", None)
        parameter_index = call.data.get("parameter_index", None)
        value = call.data.get("value", None)
        model_index = call.data.get("model_index", None)

        if (
            device_id is not None
            and parameter_index is not None
            and value is not None
            and model_index is not None
        ):
            devs = [
                x
                for x in tw_l.devices
                if (x.twist_id == device_id and x.model_index == model_index)
            ]

            for dev in devs:
                await dev.set_parameter(parameter_index, value)

    hass.services.async_register(DOMAIN, "set_parameter", handle_parameter)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN)

    return unload_ok
