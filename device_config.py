"""Device configuration fetcher and parser for Twist integration.

This module handles fetching device configuration from the Twist server
and parsing it into a format usable by the integration.

When the server API format changes, only update the parsing functions in this file.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TwistDeviceConfig:
    """Fetches and parses device configuration from Twist server."""

    def __init__(self, server_url: str, api_key: str) -> None:
        """Initialize the device config fetcher.

        Args:
            server_url: Base URL of the Twist server (e.g., "http://192.168.1.248:8080")
            api_key: API key for authentication
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self._raw_config: dict[str, Any] | None = None

    async def fetch_devices(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        """Fetch device configuration from the server.

        Args:
            session: aiohttp ClientSession to use for the request

        Returns:
            Raw device configuration from the server

        Raises:
            aiohttp.ClientError: If the request fails
        """
        url = f"{self.server_url}/devices?api={self.api_key}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            self._raw_config = await response.json()
            _LOGGER.debug("Fetched device config: %s", self._raw_config)
            return self._raw_config

    def get_installation_id(self) -> str:
        """Get the installation ID from the configuration.

        Returns:
            Installation ID as string
        """
        if not self._raw_config:
            raise ValueError("No configuration loaded. Call fetch_devices() first.")

        # Current format: {"installation_id": 1808, ...}
        # If format changes, update this function only
        return str(self._raw_config.get("installation_id", ""))

    def parse_devices(self) -> list[dict[str, Any]]:
        """Parse the raw configuration into normalized device list.

        Returns:
            List of normalized device dictionaries with keys:
                - device_id: Device identifier
                - model_id: Model identifier
                - name: Device name
                - type: Device type (Button, Relay, Binary_Sensor, etc.)

        Note:
            When the server API format changes, update this method to transform
            the new format into the same normalized output format.
        """
        if not self._raw_config:
            raise ValueError("No configuration loaded. Call fetch_devices() first.")

        # Current format parsing
        # If the server returns a different structure in the future,
        # update this section while keeping the output format the same
        products = self._raw_config.get("products", [])

        devices = []
        for product in products:
            device = {
                "device_id": str(product.get("device", "")),
                "model_id": product.get("model", 0),
                "name": product.get("name", ""),
                "type": product.get("type", "Unknown"),
            }
            devices.append(device)

        _LOGGER.debug("Parsed %d devices", len(devices))
        return devices

    def get_devices_by_type(self, device_type: str) -> list[dict[str, Any]]:
        """Get all devices of a specific type.

        Args:
            device_type: Type of devices to filter (e.g., "Button", "Relay", "Binary_Sensor")

        Returns:
            List of devices matching the specified type
        """
        devices = self.parse_devices()
        return [d for d in devices if d["type"] == device_type]

    def get_devices_by_platform(self, platform: str) -> list[dict[str, Any]]:
        """Get all devices for a specific Home Assistant platform.

        Args:
            platform: Home Assistant platform name (e.g., "button", "switch", "cover")

        Returns:
            List of devices that should be created for this platform
        """
        devices = self.parse_devices()
        platform_devices = []

        for device in devices:
            normalized_type = self.normalize_type(device["type"])
            # Skip devices that should be ignored (Timer, etc.)
            if normalized_type is None:
                continue
            # Add device if it maps to this platform
            if normalized_type == platform:
                platform_devices.append(device)

        return platform_devices

    @staticmethod
    def normalize_type(device_type: str) -> str:
        """Normalize device type names to match Home Assistant platforms.

        Args:
            device_type: Raw device type from server

        Returns:
            Normalized type name, or None if device should be ignored

        Note:
            Update this mapping if new device types are added or naming changes.
        """
        # Map server types to Home Assistant platforms
        # None means the device type should be ignored
        type_mapping = {
            "Button": "button",
            "Relay": "switch",
            "Binary_Sensor": "binary_sensor",
            "Garage": "cover",
            "Timer": None,  # Ignore Timer devices
            "Louvre": "cover",
            "Light": "light",
            "RGB": "light",
        }
        return type_mapping.get(device_type, device_type.lower())
