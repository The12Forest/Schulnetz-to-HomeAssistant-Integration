"""Constants for the Schulnetz integration."""

DOMAIN = "schulnetz"

DEFAULT_PORT = 80
DEFAULT_SCHOOL = "bbzw"
DEFAULT_SCAN_INTERVAL_MINUTES = 30
DEFAULT_DEVICE_NAME_TEMPLATE = "{full}"
DEFAULT_EXAM_NAME_TEMPLATE = "{exam}"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TOTP_SECRET = "totp_secret"
CONF_SCHOOL = "school"
CONF_CUSTOM_URL = "custom_url"

CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_DEVICE_NAME_TEMPLATE = "device_name_template"
CONF_EXAM_NAME_TEMPLATE = "exam_name_template"
CONF_SUBJECT_ALIASES = "subject_aliases"

COORDINATOR = "coordinator"
SESSION = "session"
STRUCTURE_HASH = "structure_hash"

MANUFACTURER = "Schulnetz"
