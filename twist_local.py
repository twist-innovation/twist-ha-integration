import asyncio
import json

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

        self.shutters = list()

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

    async def scan_for_devices(self):
        """scan for devices."""
        if self.connected:

            @callback
            def message_received(msg):
                """Handle new MQTT messages."""
                if "pong" in msg.topic:
                    tp_split = msg.topic.split("/")
                    device_id = tp_split[2]
                    existing_shutter = [
                        x for x in self.shutters if x.shutter_id == device_id
                    ]
                    if len(existing_shutter) == 0:
                        tb_shutter = TbShutter(device_id, device_id, self, self.hass)
                        self.shutters.append(tb_shutter)

            unsubscribe = await mqtt.async_subscribe(
                self.hass,
                f"{self.network_id}/receive/#",
                message_received,
                0,
            )

        timeout_cnt = 0
        while timeout_cnt < 2:
            await mqtt.async_publish(
                self.hass,
                f"{self.network_id}/send/gateway/4294967295/ping",
                "ping",
                0,
                False,
            )

            await asyncio.sleep(1)
            timeout_cnt += 1

        unsubscribe()


class TbShutter:
    """TB shutter model."""

    def __init__(
        self, shutter_id: str, name: str, twist_local: TwistLocal, hass
    ) -> None:
        """Init dummy roller."""
        self._id = shutter_id
        self.twist_local = twist_local
        self.name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self._current_position = 0
        self.moving = 0
        self.firmware_version = "1.3.0.1"
        self.model = "TB Shutter"
        self.hass = hass

    async def start_listening(self) -> None:
        """Start listening for state changes."""

        @callback
        async def message_received(msg):
            """Handle new MQTT messages."""

            payload = msg.payload

            context = json.loads(payload)

            if context["model_index"] == 0:
                self._current_position = context["context"][0]["value"] / 65535 * 100
                await self.publish_updates()

        self.unsubscribe = await mqtt.async_subscribe(
            self.hass,
            f"{self.twist_local.network_id}/receive/{self._id}/model/context",
            message_received,
            0,
        )

    def stop_listening(self) -> None:
        self.unsubscribe()

    @property
    def shutter_id(self) -> str:
        """Return ID for roller."""
        return self._id

    @property
    def position(self):
        """Return position for roller."""
        return self._current_position

    async def set_position(self, position: int) -> None:
        """Set requested position"""

        raw_position = int(position * 65535 / 100)

        data = {
            "model_index": 0,
            "event_id": 4,
            "data": [int(raw_position / 255), int(raw_position % 255)],
        }

        await mqtt.async_publish(
            self.hass,
            f"{self.twist_local.network_id}/send/{self._id}/model/activate_event",
            json.dumps(data),
            0,
            False,
        )

    async def stop_motor(self):
        """Stop motor."""
        data = {
            "model_index": 0,
            "event_id": 2,
            "data": [],
        }

        await mqtt.async_publish(
            self.hass,
            f"{self.twist_local.network_id}/send/{self._id}/model/activate_event",
            json.dumps(data),
            0,
            False,
        )

    @property
    def online(self) -> float:
        """Roller is online."""
        # The dummy roller is offline about 10% of the time. Returns True if online,
        # False if offline.
        return True

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
