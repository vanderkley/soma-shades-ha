from unittest.mock import patch

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from custom_components.soma_shades.const import CONF_TILT, DOMAIN

from .conftest import MAC

INFO = BluetoothServiceInfo(
    name="S",
    address=MAC,
    rssi=-80,
    manufacturer_data={880: bytes([2, 75, 0, 0]) + b"Living Room0   "},
    service_data={},
    service_uuids=[],
    source="local",
)
TILT_INFO = BluetoothServiceInfo(
    name="S",
    address=MAC,
    rssi=-80,
    manufacturer_data={880: bytes([2, 0x80 | 75, 50, 50]) + b"Living Room0   "},  # the Tilt flag in the battery level
    service_data={},
    service_uuids=[],
    source="local",
)


def setup_entry():
    return patch("custom_components.soma_shades.async_setup_entry", return_value=True)


async def test_bluetooth_discovery(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=INFO)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with setup_entry():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {CONF_ADDRESS: MAC, CONF_NAME: "living_room", CONF_TILT: False}


async def test_bluetooth_discovery_of_a_tilt(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=TILT_INFO)
    with setup_entry():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TILT] is True


async def test_bluetooth_discovery_of_a_configured_shade(hass, entry):
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_picks_a_shade(hass):
    with patch("custom_components.soma_shades.config_flow.async_discovered_service_info", return_value=[INFO]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with setup_entry():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: MAC})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"


async def test_user_without_shades(hass):
    with patch("custom_components.soma_shades.config_flow.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
