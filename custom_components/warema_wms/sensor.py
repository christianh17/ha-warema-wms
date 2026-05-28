"""Sensor platform for Warema WMS integration.

Exposes per-blind sensors:
  - WMS Position  (0 = open, 100 = closed) in %
  - WMS Angle     (decoded value, same range as get_position.py output)
  - Motor SNR     (serial number as text)
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BLIND_DEVICE_TYPES,
    CONF_DEVICES,
    DOMAIN,
    SIGNAL_NEW_WEATHER_STATION,
)
from .coordinator import WaremaCoordinator

_LOGGER = logging.getLogger(__name__)

# (key, friendly_name, unit, icon)
_SENSOR_DEFS = [
    ("position", "WMS Position", "%", "mdi:window-shutter"),
    ("angle", "WMS Angle", None, "mdi:angle-acute"),
]

# (attr, translation_key, unit, device_class, icon) for weather station readings.
_WEATHER_SENSOR_DEFS = [
    (
        "temp",
        "weather_temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        "mdi:thermometer",
    ),
    (
        "wind",
        "weather_wind_speed",
        UnitOfSpeed.METERS_PER_SECOND,
        SensorDeviceClass.WIND_SPEED,
        "mdi:weather-windy",
    ),
    (
        "lumen",
        "weather_brightness",
        LIGHT_LUX,
        SensorDeviceClass.ILLUMINANCE,
        "mdi:white-balance-sunny",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warema WMS sensor entities from a config entry."""
    coordinator: WaremaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for device in entry.data.get(CONF_DEVICES, []):
        device_type = device.get("device_type", "20")
        if device_type not in BLIND_DEVICE_TYPES:
            continue

        snr = device.get("snr")
        snr_hex = device.get("snr_hex", "")
        device_type_str = device.get("device_type_str", "Blind")
        snr_int = int(snr) if not isinstance(snr, int) else snr

        # Position and angle sensors
        for key, name, unit, icon in _SENSOR_DEFS:
            entities.append(
                WaremaWmsSensor(
                    coordinator=coordinator,
                    snr=snr_int,
                    snr_hex=snr_hex,
                    device_type_str=device_type_str,
                    entry_id=entry.entry_id,
                    key=key,
                    name=name,
                    unit=unit,
                    icon=icon,
                )
            )

        # Motor SNR sensor (static text sensor showing the device ID)
        entities.append(
            WaremaSnrSensor(
                snr=snr_int,
                snr_hex=snr_hex,
                device_type_str=device_type_str,
                entry_id=entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d Warema WMS sensor entities", len(entities))

    # Weather stations are not part of CONF_DEVICES: they broadcast
    # unsolicited. Create their sensors dynamically the first time a station is
    # seen, and cover any station that already broadcast before this platform
    # finished setting up.
    added_stations: set[int] = set()

    @callback
    def _add_weather_station(snr: int) -> None:
        if snr in added_stations:
            return
        added_stations.add(snr)
        async_add_entities(
            WaremaWeatherSensor(coordinator, snr, entry.entry_id, *defn)
            for defn in _WEATHER_SENSOR_DEFS
        )

    for snr in coordinator.weather_data:
        _add_weather_station(snr)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{SIGNAL_NEW_WEATHER_STATION}_{entry.entry_id}",
            _add_weather_station,
        )
    )


class WaremaWmsSensor(CoordinatorEntity[WaremaCoordinator], SensorEntity):
    """A numeric sensor that mirrors one field from the WMS position payload."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: WaremaCoordinator,
        snr: int,
        snr_hex: str,
        device_type_str: str,
        entry_id: str,
        key: str,
        name: str,
        unit: str | None,
        icon: str,
    ) -> None:
        super().__init__(coordinator, context=snr)
        self._snr = snr
        self._snr_hex = snr_hex
        self._device_type_str = device_type_str
        self._entry_id = entry_id
        self._key = key

        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{snr_hex}_{key}"

    def _get_blind_state(self):
        """Get the current blind state from coordinator data."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._snr)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._snr_hex)},
            name=f"{self._device_type_str} {self._snr}",
            manufacturer="Warema",
            model=self._device_type_str,
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def native_value(self) -> int | None:
        """Return the sensor value from coordinator data."""
        state = self._get_blind_state()
        if not state:
            return None
        if self._key == "position":
            return state.position if state.position >= 0 else None
        return state.angle if state.position >= 0 else None


class WaremaSnrSensor(SensorEntity):
    """Text sensor that displays the motor SNR (serial number)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        snr: int,
        snr_hex: str,
        device_type_str: str,
        entry_id: str,
    ) -> None:
        self._snr = snr
        self._snr_hex = snr_hex
        self._device_type_str = device_type_str
        self._entry_id = entry_id

        self._attr_name = "Motor SNR"
        self._attr_unique_id = f"{DOMAIN}_{snr_hex}_snr"
        self._attr_icon = "mdi:identifier"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._snr_hex)},
            name=f"{self._device_type_str} {self._snr}",
            manufacturer="Warema",
            model=self._device_type_str,
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def native_value(self) -> str:
        """Return the SNR as a formatted string (dec and hex)."""
        return f"{self._snr} (hex: {self._snr_hex})"


class WaremaWeatherSensor(CoordinatorEntity[WaremaCoordinator], SensorEntity):
    """A numeric sensor mirroring one field of a WMS weather broadcast."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: WaremaCoordinator,
        snr: int,
        entry_id: str,
        attr: str,
        translation_key: str,
        unit: str,
        device_class: SensorDeviceClass,
        icon: str,
    ) -> None:
        super().__init__(coordinator, context=snr)
        self._snr = snr
        self._entry_id = entry_id
        self._field = attr

        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_weather_{snr}_{attr}"

    def _get_state(self):
        return self.coordinator.weather_data.get(self._snr)

    @property
    def device_info(self) -> DeviceInfo:
        state = self._get_state()
        snr_hex = state.snr_hex if state else ""
        return DeviceInfo(
            identifiers={(DOMAIN, f"weather_{self._snr}")},
            name=f"Weather station {self._snr}",
            manufacturer="Warema",
            model="Weather station",
            via_device=(DOMAIN, self._entry_id),
            serial_number=snr_hex or None,
        )

    @property
    def available(self) -> bool:
        return self._get_state() is not None

    @property
    def native_value(self) -> float | int | None:
        state = self._get_state()
        if state is None:
            return None
        return getattr(state, self._field)
