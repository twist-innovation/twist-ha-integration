"""Config flow for Twist integration."""

from __future__ import annotations

import logging
from typing import Any


import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .twist_api import Twist

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required("installation_id"): str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    twist = Twist(data["installation_id"], hass)

    if not await twist.check_connection():
        raise GatewayNotFound

    await twist.configure()

    # Return info that you want to store in the config entry.
    return {"installation_id": "Twist"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                existing_entry = await self.async_set_unique_id(info["installation_id"])
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    # Reload the config entry otherwise devices will remain unavailable
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(existing_entry.entry_id)
                    )
                    return self.async_abort(reason="already exists")

                return self.async_create_entry(
                    title=info["installation_id"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class GatewayNotFound(HomeAssistantError):
    """Error to indicate the gateway is not found."""
