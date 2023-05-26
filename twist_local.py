import asyncio

from homeassistant.core import callback
from homeassistant.components import mqtt

from homeassistant.exceptions import HomeAssistantError

from collections.abc import (
    Callable,
)


class TwistLocal:
    """API wrapper for the Twist network."""

    def __init__(self, gateway_id, hass) -> None:
        self.gateway_id = gateway_id
        self.network_id = gateway_id
        self.hass = hass
        self.wait_for_answer = False
        self.valid = False
        self.connected = False

        self.manufacturer = "Ledsgo"

        self.shutters = [
            TbShutter("1147007262", "1147007262", self),
            TbShutter("1410948014", "1410948014", self),
        ]

    async def check_connection(self):
        """Check if we can connect to the gateway"""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise CannotConnect

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            self.wait_for_answer = True
            if "major" in msg.payload:
                self.valid = True

        unsubscribe = await mqtt.async_subscribe(
            self.hass, f"{self.network_id}/receive/gateway/version", message_received, 0
        )

        timeout_cnt = 0
        while not self.wait_for_answer:
            await mqtt.async_publish(
                self.hass,
                f"{self.network_id}/send/gateway/version",
                "version",
                0,
                False,
            )

            await asyncio.sleep(2)
            timeout_cnt += 1

            if timeout_cnt > 10:
                unsubscribe()
                return False

        unsubscribe()

        if not self.valid:
            return False

        self.connected = True

        return True

    async def scan_for_devices(self, cb: Callable[[], None]):
        """scan for devices."""
        if self.connected:

            @callback
            def message_received(msg):
                """Handle new MQTT messages."""
                # if "pong" in msg.topic:
                #     tp_split = msg.topic.split("/")
                #     device_id = tp_split[2]
                #     tb_shutter = TbShutter(device_id, device_id, self)
                #     cb(tb_shutter)

            await mqtt.async_subscribe(
                self.hass,
                f"{self.network_id}/receive/#",
                message_received,
                0,
            )

            await mqtt.async_publish(
                self.hass,
                f"{self.network_id}/send/gateway/4294967295/ping",
                "ping",
                0,
                False,
            )


class TbShutter:
    """TB shutter model."""

    def __init__(self, shutter_id: str, name: str, twist_local: TwistLocal) -> None:
        """Init dummy roller."""
        self._id = shutter_id
        self.twist_local = twist_local
        self.name = name
        self._loop = asyncio.get_event_loop()
        self._target_position = 100
        self._current_position = 100
        self.moving = 0
        self.firmware_version = "1.3.0.1"
        self.model = "TB Shutter"

    @property
    def shutter_id(self) -> str:
        """Return ID for roller."""
        return self._id

    @property
    def position(self):
        """Return position for roller."""
        return self._current_position

    async def set_position(self, position: int) -> None:
        """
        Set dummy cover to the given position.

        State is announced a random number of seconds later.
        """
        self._current_position = position

    @property
    def online(self) -> float:
        """Roller is online."""
        # The dummy roller is offline about 10% of the time. Returns True if online,
        # False if offline.
        return True


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
