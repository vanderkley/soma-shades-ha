# Soma Smart Shades for Home Assistant

Control [Soma Smart Shades 2 and Tilt 2](https://www.somasmarthome.com/) over Bluetooth LE from Home Assistant, without
the SOMA Connect hub, an MQTT broker or a separate bridge. The Smart Shades 3 are not supported.

```
┌──────────────┐               ┌──────────────────────┐
│ Soma Smart   │ Bluetooth LE  │ Home Assistant       │
│ Shades       │◄─────────────►│ connection per shade │
│              │               │ keepalive, reconnect │
└──────────────┘               └──────────────────────┘
```

Every shade is a device with:
- a cover with live position updates
  - a Tilt has a tilt position: closed downwards at 0, open at 50 and closed upwards at 100, as in the SOMA Connect
    integration. For e.g. a remote without tilt support, turn off *Show as tilt* under *Configure*
- battery, charging and connection sensors
- *Identify* and *Sync time* buttons
- a *Bluetooth connection* switch

## Installation
1. Under *Settings > Marketplace*, search for *Soma Smart Shades*, install it and restart Home Assistant. On Home
   Assistant 2026.10 or older, use HACS.
2. Add the discovered shades, or add one under *Settings > Devices & services > Add integration > Soma Smart Shades*.

<img src="https://raw.githubusercontent.com/vanderkley/soma-shades-ha/main/docs/discovered-shades.png" width="480" alt="Two discovered shades in Home Assistant, ready to add">

## Bluetooth
A connection to every shade stays open, for a fast response. Each one takes a connection slot of the adapter, shared
with your other Bluetooth devices, so
[choose a good adapter](https://github.com/vanderkley/soma-shades#bluetooth-adapter).

Is Home Assistant out of range of the shades? Add a
[Bluetooth proxy](https://www.home-assistant.io/integrations/bluetooth/#remote-adapters-bluetooth-proxies) close to
them, Home Assistant then connects to the shades through it. A proxy holds only a few connections at the same time,
usually 3, and every shade keeps one open. Or run the
[MQTT bridge](https://github.com/vanderkley/soma-shades#mqtt-bridge) on a device in a central spot between the shades,
e.g. a Raspberry Pi with a good adapter that holds the connections to all of them.

## Soma app
A shade accepts a single connection. To configure it in the Soma app, turn off its *Bluetooth connection* switch. It
stays free, also after a restart, until you turn the switch on again.

## Credits
Built on the [soma-shades](https://github.com/vanderkley/soma-shades) library.
