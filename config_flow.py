"""Config flow for Twist integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .device_config import TwistDeviceConfig
from .twist_api import Twist

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("server_url", default="http://192.168.1.248:8080"): str,
    vol.Required("api_key"): str,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Get aiohttp session
    session = async_get_clientsession(hass)

    # Create device config fetcher
    device_config = TwistDeviceConfig(data["server_url"], data["api_key"])

    try:
        # Try to fetch devices to validate connection
        await device_config.fetch_devices(session)
        installation_id = device_config.get_installation_id()
    except aiohttp.ClientError as err:
        _LOGGER.error("Failed to connect to server: %s", err)
        raise CannotConnect from err
    except (KeyError, ValueError) as err:
        _LOGGER.error("Invalid response from server: %s", err)
        raise InvalidResponse from err

    # Also check MQTT connection
    twist = Twist(installation_id, hass)
    if not await twist.check_connection():
        raise CannotConnect

    # Return info that you want to store in the config entry
    return {
        "installation_id": installation_id,
        "server_url": data["server_url"],
        "api_key": data["api_key"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twist."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["installation_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Twist {info['installation_id']}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidResponse(HomeAssistantError):
    """Error to indicate invalid response from server."""
