"""The Twist Local integration."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from homeassistant.components.cover import PLATFORM_SCHEMA, CoverEntity
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    STATE_CLOSED,
    STATE_OPEN,
)

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

from . import twist_local

_LOGGER = logging.getLogger(__name__)

# TOD List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twist Local from a config entry."""

    tw_l = twist_local.TwistLocal(entry.data["network"], hass)
    await tw_l.check_connection()

    hass.data[DOMAIN] = tw_l

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.pop(DOMAIN)

    return unload_ok
