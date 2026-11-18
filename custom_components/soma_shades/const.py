"""Constants of the Soma Smart Shades integration."""

DOMAIN = "soma_shades"

CONF_BLUETOOTH_ENABLED = "bluetooth_enabled"
CONF_SHOW_AS_TILT = "show_as_tilt"
CONF_TILT = "tilt"

SERVICE_MOVE_SLOWLY = "move_slowly"
ATTR_SPEED = "speed"
DEFAULT_SLOW_SPEED = 10
SLOW_MOVE_TIMEOUT = 3600  # seconds, set the motor speed back at the latest after this time, a slow move is long
