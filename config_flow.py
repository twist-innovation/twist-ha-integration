"""Config flow for Twist integration."""

from __future__ import annotations

import logging
from typing import Any

from twist import TwistAPI

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("backend_url", default="https://backbone-dev.twist-innovation.com"): str,
    vol.Required("api_key"): str,
    vol.Required("installation_uuid", default="900a2051-3dad-4ab6-ba13-f13c6ecc4e2a"): str,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Initialize Twist API
    twist_api = TwistAPI(
        backend_url=data["backend_url"],
        api_key=data["api_key"],
        installation_uuid=data["installation_uuid"],
    )

    try:
        # Try to fetch models to validate connection
        # This will validate backend connection and fetch installation_id
        models = await twist_api.get_models()

        if not models:
            raise NoDevicesFound

        installation_id = twist_api.installation_id

        _LOGGER.info("Successfully validated Twist connection, found %d models", len(models))

    except Exception as err:
        _LOGGER.error("Failed to connect to Twist backend: %s", err)
        raise CannotConnect from err

    # Return info that you want to store in the config entry
    return {
        "installation_id": installation_id,
        "installation_uuid": data["installation_uuid"],
        "backend_url": data["backend_url"],
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
            except NoDevicesFound:
                errors["base"] = "no_devices"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(info["installation_id"]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Twist {info['installation_uuid']}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NoDevicesFound(HomeAssistantError):
    """Error to indicate no devices were found."""
