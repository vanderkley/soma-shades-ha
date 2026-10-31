# Soma Smart Shades (Bluetooth) for Home Assistant

Control [Soma Smart Shades 2](https://www.somasmarthome.com/) directly over Bluetooth LE from Home Assistant, without
the SOMA Connect hub, an MQTT broker or a separate bridge. It uses the Bluetooth adapters of Home Assistant, and the
[soma-shades](https://github.com/vanderkley/soma-shades) library.

Every shade is a device with:
- a cover with live position updates
- sensors for the battery level, battery voltage, input voltage of the solar panel or USB charger, and the start of
  the connection
- *Identify* and *Sync time* buttons
- a *Bluetooth connection* switch

The Smart Shades 3 are not supported.

## Installation
1. In HACS, add this repository as a custom repository of the type *Integration*, and download it.
2. Restart Home Assistant.
3. The shades are discovered automatically. You can also add one under *Settings > Devices & services > Add
   integration > Soma Smart Shades (Bluetooth)*.

## Bluetooth
The integration keeps a connection open to every shade, for a fast response. Every shade takes a connection slot of
the adapter, shared with the other Bluetooth devices of Home Assistant, so use an adapter from the
[list of Home Assistant](https://www.home-assistant.io/integrations/bluetooth/#known-working-high-performance-adapters).

To configure a shade in the Soma app, turn off its *Bluetooth connection* switch. The shade stays free, also after a
restart, until you turn the switch on again.

Is Home Assistant out of range of the shades? Run the [MQTT bridge](https://github.com/vanderkley/soma-shades) on a
separate device closer to the shades, e.g. a Raspberry Pi.
