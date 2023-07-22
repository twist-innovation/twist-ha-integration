import asyncio
import json
import enum

from homeassistant.core import callback
from homeassistant.components import mqtt
from homeassistant.exceptions import HomeAssistantError

from collections.abc import (
    Callable,
)


class TwistVariants(enum.Enum):
    """The twist variants"""

    NO_VARIANT = 0xFFFF
    LED_4_BUTTON_4 = 0x0000
    LED_1_BUTTON_1 = 0x0001
    MONO_LIGHT_32 = 0x0002
    MONO_LIGHT_4 = 0x0003
    MONO_LIGHT_2 = 0x0004
    TEMP_HUM_PIR_LUX_VOC = 0x0005
    MONO_LIGHT_1_BUTTON_1 = 0x0006
    SHUTTER_2_BATTERY_1 = 0x0007
    BUTTON_8_LED_4 = 0x0008
    MONO_LIGHT_2_LUX2BRIGHTNESS_1 = 0x0009
    SHUTTER_1_BATTERY_1 = 0x000A
    SHUTTER_1 = 0x000B
    RGBW_1 = 0x000C
    SHUTTER_1_TEMP_1 = 0x000D
    BUTTON_4 = 0x000E
    TUNABLE_WHITE_2 = 0x000F
    WIND_1_LUX_1_RAIN_1 = 0x0010
    BUTTON_1 = 0x0011
    PULSE_CONTACT_2 = 0x0012
    TBSHUTTER_1 = 0x0013
    REPEATER_1 = 0x0015
    REPEATER_1_LED_1 = 0x0016
    LED_12 = 0x0017
    BUTTON_12 = 0x0018
    FB_SHUTTER_1_VOLTAGE_1_CURRENT_1 = 0x0019
    TBSHUTTER_6 = 0x001A


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

        self.devices = []

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
            async def message_received(msg):
                """Handle new MQTT messages."""
                if not "gateway" in msg.topic:
                    tp_split = msg.topic.split("/")
                    device_id_str = tp_split[2]
                    if not device_id_str.isdigit():
                        return
                    device_id = int(device_id_str)
                    existing_device = [
                        x for x in self.devices if x.device_id == device_id
                    ]
                    if len(existing_device) > 0:
                        for device in existing_device:
                            await device.handle_message(msg.topic, msg.payload)
                    elif "variant" in msg.topic:
                        self.add_models_to_lists(device_id, msg.payload)

            await mqtt.async_subscribe(
                self.hass,
                f"{self.network_id}/receive/#",
                message_received,
                0,
            )

        timeout_cnt = 0
        while timeout_cnt < 2:
            await mqtt.async_publish(
                self.hass,
                f"{self.network_id}/send/4294967295/device/variant/get",
                "ping",
                0,
                False,
            )

            await asyncio.sleep(1)
            timeout_cnt += 1

    def add_models_to_lists(self, device_id: int, variant_message):
        """Add models to lists according to variant."""
        json_data = json.loads(variant_message)

        if json_data["variant_id"] == TwistVariants.MONO_LIGHT_32.value:
            for i in range(0, 32):
                self.devices.append(TwistMonoLight(device_id, i, self, self.hass))
        elif json_data["variant_id"] == TwistVariants.TBSHUTTER_1.value:
            self.devices.append(TwistTbShutter(device_id, 0, self, self.hass))
        elif json_data["variant_id"] == TwistVariants.LED_12.value:
            for i in range(0, 12):
                self.devices.append(TwistRelay(device_id, i, self, self.hass))
        elif json_data["variant_id"] == TwistVariants.BUTTON_12.value:
            for i in range(0, 12):
                self.devices.append(TwistButton(device_id, i, self, self.hass))
        elif json_data["variant_id"] == TwistVariants.TBSHUTTER_6.value:
            for i in range(0, 6):
                self.devices.append(TwistTbShutter(device_id, i, self, self.hass))

    def get_devices(self, class_type) -> list:
        """Get devices of a specific type."""
        return [x for x in self.devices if isinstance(x, class_type)]


class TwistDevice:
    """API wrapper for the Twist device."""

    def __init__(
        self, device_id: str, model_index: int, twist_local: TwistLocal, hass
    ) -> None:
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self.moving = 0
        self.firmware_version = "1.3.0.1"
        self.unsubscribe = None

        self.device_id = device_id
        self.twist_local = twist_local
        self.hass = hass
        self.model_index = model_index

    def received_event(self, context) -> None:
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

    async def activate_event(self, json_data) -> None:
        """Activate event."""
        await mqtt.async_publish(
            self.hass,
            f"{self.twist_local.network_id}/send/{self.device_id}/model/activate_event",
            json.dumps(json_data),
            0,
            False,
        )

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
            f"{self.twist_local.network_id}/send/{self.device_id}/config/parameters/set",
            json.dumps(json_data),
            0,
            False,
        )


class TwistTbShutter(TwistDevice):
    """TB shutter model."""

    def __init__(
        self, device_id: str, model_index: int, twist_local: TwistLocal, hass
    ) -> None:
        super().__init__(device_id, model_index, twist_local, hass)
        self.model = "tb_shutter"
        self._current_position = 0

    def received_event(self, context) -> None:
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


class TwistMonoLight(TwistDevice):
    """Twist Light model."""

    def __init__(
        self, device_id: str, model_index: int, twist_local: TwistLocal, hass
    ) -> None:
        super().__init__(device_id, model_index, twist_local, hass)
        self.model = "light"
        self._current_intensity = 0

    def received_event(self, context) -> None:
        self._current_intensity = context[0]["value"] / 65535 * 100

    @property
    def intensity(self):
        """Return intensity for light."""
        return self._current_intensity

    async def set_intensity(self, intensity: int) -> None:
        """Set requested intensity."""

        raw_intensity = int(intensity * 65535 / 100)

        data = {
            "model_index": self.model_index,
            "event_id": 2,  # Set value
            "data": [int(raw_intensity % 256), int(raw_intensity / 256)],
        }

        await self.activate_event(data)

    async def set_intensity_with_fade_time(
        self, intensity: int, fade_time: float
    ) -> None:
        """Set requested intensity."""

        raw_intensity = int(intensity * 65535 / 100)

        fade_time0 = int(fade_time) % 256
        fade_time1 = (int(fade_time) / 256) % 256
        fade_time2 = (int(fade_time) / 256 / 256) % 256
        fade_time3 = (int(fade_time) / 256 / 256 / 256) % 256

        data = {
            "model_index": self.model_index,
            "event_id": 4,  # Set value
            "data": [
                int(raw_intensity % 256),
                int(raw_intensity / 256),
                int(fade_time0),
                int(fade_time1),
                int(fade_time2),
                int(fade_time3),
            ],
        }

        await self.activate_event(data)


class TwistRelay(TwistDevice):
    """Twist Relay model."""

    def __init__(
        self, device_id: str, model_index: int, twist_local: TwistLocal, hass
    ) -> None:
        super().__init__(device_id, model_index, twist_local, hass)
        self.model = "relay"
        self._current_state = 0

    def received_event(self, context) -> None:
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

    def __init__(
        self, device_id: str, model_index: int, twist_local: TwistLocal, hass
    ) -> None:
        super().__init__(device_id, model_index, twist_local, hass)
        self.model = "button"
        self._current_state = "Released"

    def received_event(self, context) -> None:
        self._current_state = ButtonState(context[0]["value"]).name

    @property
    def state(self):
        """Return state of the Button."""
        return self._current_state


class ButtonState(enum.Enum):
    """Button states."""

    Pushed = 0
    Released = 1
    LongPushed = 2
    LongReleased = 3


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
