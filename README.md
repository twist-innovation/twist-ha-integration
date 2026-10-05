# Twist for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/twist-innovation/twist-ha-integration)

Home Assistant integration for [Twist Innovation](https://twist-innovation.com) home automation installations. Connects to your Twist backend over MQTT and exposes your shutters, lights, switches, buttons, and sensors as native Home Assistant entities.

## Features

- **Covers** — roller shutters and garage doors, with open/close/stop and (for shutters) precise position control.
- **Lights** — dimmers and RGB fixtures, with brightness and HS color support.
- **Switches** — generic on/off outputs.
- **Sensors** — device telemetry reported by your installation (e.g. temperature, current).
- **Buttons & device triggers** — physical Twist push-buttons are exposed as HA button events (`push`, `release`, `long_push`, `long_release`, `double_push`, `double_release`, `double_long_push`, `double_long_release`) so you can build automations directly off a wall switch.
- Devices are grouped by product, and entities update in real time over MQTT (`local_push`) rather than polling.

## Requirements

- A configured [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) in Home Assistant, connected to the same broker your Twist installation publishes to.
- A Twist backend API key and installation UUID for your site (from Twist Innovation).

## Installation

### Via HACS (custom repository)

This integration isn't in the default HACS store yet, so add it as a custom repository:

1. In HACS, go to **Integrations** → the **⋮** menu → **Custom repositories**.
2. Add `https://github.com/twist-innovation/twist-ha-integration` as category **Integration**.
3. Find **Twist** in HACS and install it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/twist` from this repo into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

Configuration is done entirely through the UI — no YAML required.

1. Go to **Settings → Devices & Services → Add Integration**, search for **Twist**.
2. Enter:
   - **Backend URL** — your Twist backend endpoint (defaults to the production backend).
   - **API key** — issued for your installation.
   - **Installation UUID** — identifies your site on the Twist backend.

The integration validates the connection and fetches your device list before completing setup.

## Troubleshooting

- **Entities unavailable / not updating** — confirm the MQTT integration is set up and reachable from Home Assistant, and that your Twist gateway is publishing to the same broker.
- **Covers appear to move the wrong direction** — shutter position is derived from firmware-reported state; if this ever looks inverted for your installation, check `custom_components/twist/cover.py`'s `TwistCover` position handling before assuming it's a backend issue.
- Enable debug logging for more detail:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.twist: debug
  ```

## Contributing

Issues and pull requests are welcome at [twist-innovation/twist-ha-integration](https://github.com/twist-innovation/twist-ha-integration). This integration depends on [twist-innovation-api](https://github.com/twist-innovation/twist-innovation-api) for backend/MQTT communication.
