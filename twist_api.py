import asyncio
import json
import enum

from homeassistant.core import callback
from homeassistant.components import mqtt
from homeassistant.exceptions import HomeAssistantError

from collections.abc import (
    Callable,
)

from twist import TwistAPI, TwistModel, TwistLight


class Twist:
    """API wrapper for the Twist network."""

    def __init__(self, installation_id, hass) -> None:
        self.installation_id = installation_id
        self.hass = hass
        self.wait_for_answer = True
        self.valid = True
        self.connected = False

        self.manufacturer = "Twist"

        self.devices = []
        self.twist_model_list = []

        self.twist = TwistAPI(self.installation_id)

        # Create a callback function
        self.callback_f: Callable[[str, str], None] | None = None

    async def configure(self):
        await self.twist.add_mqtt(self._mqtt_publish, self._mqtt_subscribe)

        # we need to sleep for 2s, so the async subscribe function should be configured
        await asyncio.sleep(2)

    async def _mqtt_publish(self, topic, payload):
        await mqtt.async_publish(
            self.hass,
            topic,
            payload,
            0,
            False,
        )

    async def _mqtt_subscribe(self, topic, callback_f):
        self.callback_f = callback_f
        await mqtt.async_subscribe(
            self.hass,
            topic,
            self._message_received,
            0,
        )

    async def _message_received(self, msg):
        if self.callback_f is not None:
            await self.callback_f(msg.topic, msg.payload)

    async def check_connection(self):
        """Check if we can connect to the gateway."""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise CannotConnect

        self.connected = True

        return True

    async def scan_for_devices(self):
        """Scan for devices."""
        self.twist_model_list = await self.twist.search_models()

    def get_devices(self, class_type) -> list:
        """Get devices of a specific type."""
        return [x for x in self.twist_model_list if isinstance(x, class_type)]


class TwistDevice:
    """API wrapper for the Twist device."""

    def __init__(self, model, twist: Twist, hass) -> None:
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self.moving = 0
        self.firmware_version = "1.3.0.1"
        self.unsubscribe = None

        self._model = model

        self.device_id = model.parent_device.twist_id
        self.twist = twist
        self.hass = hass
        self.model_index = model.model_id

    async def activate_event(self, json_data) -> None:
        # TODO This needs to be removed
        pass

    def get_model(self):
        return self._model

    async def received_event(self) -> None:
        """placeholder function that needs to be overridden."""
        pass

    async def handle_message(self, topic, payload) -> None:
        """Handle new MQTT messages."""
        if "model/context" in topic:
            context = json.loads(payload)

            if context["model_index"] == self.model_index:
                self.received_event(context["context"])
                await self.publish_updates()

    @property
    def twist_id(self) -> str:
        """Return ID for shutter."""
        return self.device_id

    @property
    def online(self) -> float:
        """Model is online."""
        # TODO: create an online mechanism
        return True

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    async def set_parameter(self, parameter_index: int, value: int) -> None:
        """set parameter."""

        data = {
            "model_index": self.model_index,
            "parameters": [{"index": parameter_index, "value": value}],
        }
        json_data = json.dumps(data)
        await mqtt.async_publish(
            self.hass,
            f"{self.twist.network_id}/send/{self.device_id}/config/parameters/set",
            json.dumps(json_data),
            0,
            False,
        )


class TwistTbShutter(TwistDevice):
    """TB shutter model."""

    def __init__(self, model, twist: Twist, hass) -> None:
        super().__init__(model, twist, hass)
        self.model_name = "tb_shutter"
        self._current_position = 0

    async def received_event(self) -> None:
        self._current_position = context[0]["value"] / 65535 * 100

    @property
    def position(self):
        """Return position for shutter."""
        return self._current_position

    async def set_position(self, position: int) -> None:
        """Set requested position"""

        raw_position = int(position * 65535 / 100)

        data = {
            "model_index": self.model_index,
            "event_id": 4,  # Set value
            "data": [int(raw_position / 256), int(raw_position % 256)],
        }

        await self.activate_event(data)

    async def stop_motor(self):
        """Stop motor."""
        data = {
            "model_index": self.model_index,
            "event_id": 1,  # Stop motor
            "data": [],
        }

        await self.activate_event(data)


class TwistRelay(TwistDevice):
    """Twist Relay model."""

    def __init__(self, model, twist: Twist, hass) -> None:
        super().__init__(model, twist, hass)
        self.model_name = "relay"
        self._current_state = 0

    async def received_event(self) -> None:
        self._current_state = context[0]["value"] == 1

    @property
    def state(self):
        """Return state of the Relay."""
        return self._current_state

    async def set(self) -> None:
        """Set requested state"""

        data = {
            "model_index": self.model_index,
            "event_id": 0,  # Set
            "data": [],
        }

        await self.activate_event(data)

    async def clear(self) -> None:
        """Clear requested state"""

        data = {
            "model_index": self.model_index,
            "event_id": 1,  # Clear
            "data": [],
        }

        await self.activate_event(data)

    async def toggle(self) -> None:
        """Toggle requested state"""
        if self._current_state == 0:
            await self.set()
        else:
            await self.clear()


class TwistButton(TwistDevice):
    """Twist Relay model."""

    def __init__(self, model, twist: Twist, hass) -> None:
        super().__init__(model, twist, hass)
        self.model_name = "button"
        self._current_state = "Released"

    async def received_event(self) -> None:
        self._current_state = ButtonState(context[0]["value"]).name

    @property
    def state(self):
        """Return state of the Button."""
        return self._current_state


class TwistGeneralSensor(TwistDevice):
    """Twist Sensor light."""

    def __init__(
        self,
        device_id: int,
        model_index: int,
        factor: float,
        offset: float,
        name: str,
        unit: str,
        twist: Twist,
        hass,
    ) -> None:
        super().__init__(model, twist, hass)
        self.model_name = "sensor"
        self._current_value = 0
        self.factor = factor
        self.offset = offset
        self.name = name
        self.unit = unit

    async def received_event(self) -> None:
        self._current_value = round(
            (context[0]["value"] * self.factor) + self.offset, 2
        )

    @property
    def value(self):
        """Return value of the sensor."""
        return self._current_value


class ButtonState(enum.Enum):
    """Button states."""

    Pushed = 0
    Released = 1
    LongPushed = 2
    LongReleased = 3


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
