"""Constants for the Twist integration."""

DOMAIN = "twist"

# Maximum number of channels per model (TWIST_TYPES__MAX_CHANNELS in firmware)
MAX_CHANNELS = 8

BUTTON_EVENT_TYPES = (
    "push",
    "release",
    "long_push",
    "long_release",
    "double_push",
    "double_release",
    "double_long_push",
    "double_long_release",
)
