"""Constants of the Soma Smart Shades integration, all durations in seconds."""

DOMAIN = "soma_shades"

CONF_BLUETOOTH_ENABLED = "bluetooth_enabled"

CONNECT_TIMEOUT = 15
RECONNECT_BACKOFF_MIN = 1
RECONNECT_BACKOFF_MAX = 5 * 60
STABLE_CONNECTION_TIME = 60  # a connection lasting shorter does not reset the reconnect backoff
KEEPALIVE_INTERVAL = 2 * 60  # the shades drop a connection 3 minutes after the last write
REFRESH_INTERVAL = 15 * 60  # refresh the position and the diagnostics of a connected shade
OFFLINE_GRACE_PERIOD = 2 * 60  # only report a shade unavailable when reconnecting takes longer
