"""Constants for the Tuya Monitor integration."""

DOMAIN = "tuya_monitor"
PLATFORMS = ["sensor"]

CONF_USER_ID = "user_id"
CONF_DEVICES = "devices"
CONF_DEVICE_ID = "device_id"
CONF_PROPERTIES = "properties"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRATION = "token_expiration"

# Token expiration buffer (5 minutes in seconds)
TOKEN_EXPIRY_BUFFER = 300
