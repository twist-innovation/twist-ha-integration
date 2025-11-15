"""The Twist integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .device_config import TwistDeviceConfig
from .twist_api import Twist

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigType

type TwistConfigEntry = ConfigEntry[Twist]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Twist component."""

    async def handle_set_parameter(call: ServiceCall) -> None:
        """Handle the set_parameter service call."""
        device_id = call.data.get("device_id")
        parameter_index = call.data.get("parameter_index")
        value = call.data.get("value")
        model_index = call.data.get("model_index")

        if (
            device_id is None
            or parameter_index is None
            or value is None
            or model_index is None
        ):
            _LOGGER.error("Missing required parameters for set_parameter service")
            return

        # Find matching config entries and devices
        for entry in hass.config_entries.async_entries(DOMAIN):
            if not isinstance(entry, ConfigEntry):
                continue
            twist: Twist = entry.runtime_data
            devs = [
                x
                for x in twist.devices
                if (x.twist_id == device_id and x.model_index == model_index)
            ]

            for dev in devs:
                await dev.set_parameter(parameter_index, value)

    hass.services.async_register(DOMAIN, "set_parameter", handle_set_parameter)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TwistConfigEntry) -> bool:
    """Set up Twist from a config entry."""
    try:
        # Fetch device configuration from server
        session = async_get_clientsession(hass)
        device_config = TwistDeviceConfig(
            entry.data["server_url"], entry.data["api_key"]
        )
        await device_config.fetch_devices(session)
        installation_id = device_config.get_installation_id()

        # Initialize Twist API with MQTT
        twist = Twist(installation_id, hass)
        await twist.check_connection()
        await twist.configure()

        # Load devices from server config instead of MQTT scanning
        devices = device_config.parse_devices()
        await twist.load_devices_from_config(devices)

    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Twist installation {entry.data.get('installation_id', 'unknown')}"
        ) from ex

    entry.runtime_data = twist

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TwistConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
