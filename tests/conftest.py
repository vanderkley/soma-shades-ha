from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry
from soma_shades import ShadeClient

from custom_components.soma_shades.const import DOMAIN

MAC = "C7:D4:E5:FE:C4:67"


class FakeShade(ShadeClient):
    """A shade with the real state handling, without Bluetooth."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands: list[str] = []
        self.fail_connect = False

    def is_connected(self) -> bool:
        return self.connected

    async def connect(self, timeout: float, max_attempts: int = 3) -> None:
        if self.fail_connect:
            raise OSError("no connection")
        self.ble_client = MagicMock()
        self.connected = True
        self._disconnected.clear()

    async def disconnect(self) -> None:
        self.ble_client = None
        self.connected = False
        self.last_connect_time = None
        self._disconnected.set()

    def lose_connection(self) -> None:
        self.connected = False
        self.last_connect_time = None
        self._disconnected.set()

    async def get_info(self) -> None:
        self.manufacturer = "Wazombi Labs"
        self.firmware_version = "2.1"

    async def get_position(self) -> int:
        self._position = self._target_position = 30
        self._notify_update()
        return 30

    async def get_battery_level(self) -> int:
        return self._set_battery_level(bytes([84]))

    async def start_notify(self, notification) -> None:
        self.commands.append(f"notify {notification}")

    async def get_battery_voltage(self) -> int:
        self.battery_voltage = 4100
        return 4100

    async def get_charging(self) -> tuple[int, int]:
        self.input_voltage, self.charging_current = 604, 12
        return 604, 12

    async def move_up(self) -> None:
        self.commands.append("up")

    async def move_down(self) -> None:
        self.commands.append("down")

    async def stop(self) -> None:
        self.commands.append("stop")

    async def set_position(self, target) -> None:
        self.commands.append(f"position {target}")

    async def sync_time(self) -> None:
        self.commands.append("sync time")

    async def identify(self, sound: int = 1) -> None:
        self.commands.append("identify")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def bluetooth_setup(enable_bluetooth) -> None:
    pass


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id=MAC, title="Living Room", data={CONF_ADDRESS: MAC, CONF_NAME: "living_room"}
    )


@pytest.fixture
def fake_bluetooth() -> Generator[None]:
    with (
        patch("custom_components.soma_shades.coordinator.ShadeClient", FakeShade),
        patch("homeassistant.components.bluetooth.async_ble_device_from_address", return_value=MagicMock()),
    ):
        yield
