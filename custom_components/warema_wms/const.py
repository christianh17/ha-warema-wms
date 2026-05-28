"""Constants for the Warema WMS integration."""

DOMAIN = "warema_wms"

# Config entry keys
CONF_SERIAL_PORT = "serial_port"
CONF_CHANNEL = "channel"
CONF_PAN_ID = "pan_id"
CONF_NETWORK_KEY = "network_key"
CONF_DEVICES = "devices"

# Default values
DEFAULT_SERIAL_PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AV0K28M2-if00-port0"
DEFAULT_CHANNEL = 17

# Position polling interval (seconds)
# Note: Determines how fast remote control moves are detected.
# Shorter interval = faster detection but more network traffic.
POS_UPDATE_INTERVAL = 5

# Watch moving blinds interval (seconds)
WATCH_MOVING_INTERVAL = 0.5

# Discovery wizard
CONF_DISCOVERY_MODE = "discovery_mode"
DISCOVERY_MODE_MANUAL = "manual"
DISCOVERY_MODE_WANDSENDER = "wandsender"
DISCOVERY_MODE_NEW_NETWORK = "new_network"

# Default channel for new network creation
DEFAULT_NEW_NETWORK_CHANNEL = 24

# Topics from pywarema callback
TOPIC_INIT_COMPLETION = "wms-vb-init-completion"
TOPIC_BLIND_POSITION_UPDATE = "wms-vb-blind-position-update"
TOPIC_SCANNED_DEVICES = "wms-vb-scanned-devices"
TOPIC_WEATHER_BROADCAST = "wms-vb-rcv-weather-broadcast"

# Dispatcher signal fired when a previously unseen weather station broadcasts.
# Carries the station's integer SNR; formatted per config entry at use site.
SIGNAL_NEW_WEATHER_STATION = f"{DOMAIN}_new_weather_station"

# Device type strings
DEVICE_TYPE_STRINGS = {
    "02": "Stick/software",
    "06": "Weather station",
    "07": "Remote control (+)",
    "20": "Actuator UP",
    "21": "Plug receiver",
    "25": "Radio motor",
    "2E": "Actuator 230V UP",
    "63": "Web control",
}

# Blind device types (controllable covers)
BLIND_DEVICE_TYPES = {"20", "21", "25", "2E"}

# Device types that support slat tilt (in-wall actuators used for Raffstoren).
# Plug receiver (21) and radio motor (25) drive awnings/roller shutters
# without slats, so tilt is not exposed for them.
#
# Used ONLY as a fallback when we cannot read the per-device productType from
# Block 37 (e.g. motor asleep during config_flow). The authoritative answer
# comes from is_with_blinds in the device's productParameters.
TILT_DEVICE_TYPES = {"20", "2E"}


# Map productType (from motor Block 37 addr 12) to HA CoverDeviceClass strings.
# Kept as strings here to avoid importing homeassistant from const.py - cover.py
# wraps them in CoverDeviceClass(...). Anything not listed falls through to
# CoverDeviceClass.BLIND.
#
# Source: EProductType in the protocol notes (see
# pywarema.protocol.PRODUCT_TYPE_NAMES for the full table).
PRODUCT_TYPE_TO_DEVICE_CLASS: dict[int, str] = {
    0: "blind",  # ExternalVenetianBlind (Raffstore)
    1: "blind",  # InternalVenetianBlind
    2: "shutter",  # RollerShutter (Rollladen)
    3: "awning",  # Awning
    4: "awning",  # AwningOneValance
    5: "awning",  # AwningOneOrTwoWindsensors
    6: "awning",  # AwningOneValanceOneOrTwoWindsensors
    7: "awning",  # ConservatoryAwning (Wintergarten)
    8: "awning",  # FacadeAwning (Fassadenmarkise)
    9: "awning",  # DroparmAwning (Gelenkarm)
    10: "awning",  # VerticalAwning (Senkrechtmarkise)
    11: "awning",  # Markisolette
    12: "shade",  # PleatedBlindInside (Plissee)
    13: "shade",  # RollerBlindInside (Innenrollo)
    14: "blind",  # VerticalLouvreBlind (Vertikallamellen)
    15: "window",  # Window
    21: "awning",  # Valance (Volant)
    22: "awning",  # AwningTwoValances
    23: "awning",  # AwningTwoValancesOneOrTwoWindsensors
    24: "awning",  # SunSail
    25: "awning",  # PergolaAwning
}
