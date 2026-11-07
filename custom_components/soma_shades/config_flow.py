"""Add the shades that Home Assistant sees over Bluetooth."""

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from soma_shades import ShadeClient
from soma_shades.ble.protocol import ADVERTISEMENT_NAME, is_tilt, parse_device_name

from .const import CONF_SHOW_AS_TILT, CONF_TILT, DOMAIN


def _display_name(info: BluetoothServiceInfoBleak) -> str:
    """The name of the shade as configured in the Soma app."""
    return ShadeClient(mac=info.address, name=_shade_name(info)).display_name


def _shade_name(info: BluetoothServiceInfoBleak) -> str:
    return parse_device_name(info.manufacturer_data) or info.address.replace(":", "_").lower()


class SomaShadesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SomaShadesOptionsFlow:
        return SomaShadesOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        """Only a Tilt has options."""
        return bool(config_entry.data.get(CONF_TILT))

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": _display_name(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self._create_entry(self._discovery)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders={"name": _display_name(self._discovery)}
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            info = self._discovered[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create_entry(info)

        configured = self._async_current_ids(include_ignore=False)
        self._discovered = {
            info.address: info
            for info in async_discovered_service_info(self.hass)
            if info.name == ADVERTISEMENT_NAME and info.address not in configured
        }
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        names = {address: f"{_display_name(info)} ({address})" for address, info in self._discovered.items()}
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(names)}))

    def _create_entry(self, info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        return self.async_create_entry(
            title=_display_name(info),
            data={CONF_ADDRESS: info.address, CONF_NAME: _shade_name(info), CONF_TILT: is_tilt(info.manufacturer_data)},
        )


class SomaShadesOptionsFlow(OptionsFlowWithReload):
    """Show a Tilt as a cover with a position, for e.g. a remote that does not support tilt."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        schema = vol.Schema({vol.Required(CONF_SHOW_AS_TILT, default=options.get(CONF_SHOW_AS_TILT, True)): bool})
        return self.async_show_form(step_id="init", data_schema=schema)
