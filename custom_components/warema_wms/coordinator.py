"""
Warema WMS coordinator.

Manages the WmsStick connection and provides position updates
to Home Assistant entities via DataUpdateCoordinator pattern.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CHANNEL,
    CONF_DEVICES,
    CONF_NETWORK_KEY,
    CONF_PAN_ID,
    CONF_SERIAL_PORT,
    BLIND_DEVICE_TYPES,
    DOMAIN,
    POS_UPDATE_INTERVAL,
    SIGNAL_NEW_WEATHER_STATION,
    TOPIC_BLIND_POSITION_UPDATE,
    TOPIC_INIT_COMPLETION,
    TOPIC_SCANNED_DEVICES,
    TOPIC_WEATHER_BROADCAST,
    WATCH_MOVING_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlindState:
    """Immutable state of a blind at a point in time."""

    snr: int
    snr_hex: str
    position: int  # 0-100 (0=open, 100=closed), or -1=unknown
    angle: int  # -100 to +100
    moving: bool

    def __eq__(self, other: Any) -> bool:
        """Compare two BlindState objects for equality."""
        if not isinstance(other, BlindState):
            return NotImplemented
        return (
            self.snr == other.snr
            and self.snr_hex == other.snr_hex
            and self.position == other.position
            and self.angle == other.angle
            and self.moving == other.moving
        )


@dataclass(frozen=True)
class WeatherState:
    """Immutable snapshot of a weather station broadcast."""

    snr: int
    snr_hex: str
    temp: float  # degrees Celsius
    wind: float  # m/s
    lumen: int  # brightness (lux)
    rain: bool


class WaremaCoordinator(DataUpdateCoordinator[dict[int, BlindState]]):
    """Manages the WMS Stick and coordinates data with HA entities.

    Runs the pywarema WmsStick in a background thread and bridges
    callbacks to the HA event loop via dispatcher signals.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # No update_interval: WMS stick is push-based (has its own polling threads)
        )
        self.entry = entry
        self.stick = None
        self._init_event = asyncio.Event()
        self._scan_event = asyncio.Event()
        self._scanned_devices: list[dict] = []
        # Initialize empty data dict (filled by _wms_callback)
        self.data: dict[int, BlindState] = {}
        # Latest weather broadcast per station SNR (filled by _wms_callback).
        # Weather stations are not in CONF_DEVICES; their entities are created
        # dynamically on the first broadcast via SIGNAL_NEW_WEATHER_STATION.
        self.weather_data: dict[int, WeatherState] = {}

    async def async_connect(self) -> None:
        """Connect to the WMS stick and wait for initialization.

        Raises:
            Exception: If connection or initialization fails.
        """
        from .pywarema.stick import WmsStick

        port = self.entry.data[CONF_SERIAL_PORT]
        channel = self.entry.data[CONF_CHANNEL]
        pan_id = self.entry.data[CONF_PAN_ID]
        key = self.entry.data[CONF_NETWORK_KEY]

        _LOGGER.info(
            "WaremaCoordinator: Connecting to %s ch=%s pan=%s",
            port,
            channel,
            pan_id,
        )

        self.stick = WmsStick(
            port=port,
            channel=channel,
            pan_id=pan_id,
            key=key,
            callback=self._wms_callback,
        )

        # Connect in executor (blocking serial I/O)
        await self.hass.async_add_executor_job(self.stick.connect)

        # Register all configured blinds with the stick BEFORE waiting for
        # init completion.  The working standalone script (test_move.py) calls
        # stick.blind_add() right after connect() and before any commands.
        devices = self.entry.data.get(CONF_DEVICES, [])
        for device in devices:
            snr = device.get("snr")
            device_type = device.get("device_type", "20")
            if device_type in BLIND_DEVICE_TYPES and snr is not None:
                snr_int = int(snr) if not isinstance(snr, int) else snr
                name = device.get("device_type_str", "Blind") + f" {snr_int}"
                _LOGGER.info(
                    "WaremaCoordinator: Registering blind SNR=%d (%s)",
                    snr_int,
                    name,
                )
                blind = await self.hass.async_add_executor_job(
                    self.stick.blind_add, snr_int, name
                )
                # Replay product info from the config entry onto the Blind so
                # cover entities can read it without an extra wire round-trip.
                # If absent (config from old version), it will be filled in
                # lazily after init via _enrich_product_info().
                if blind is not None:
                    pt = device.get("product_type")
                    if pt is not None:
                        blind.product_type = pt
                        blind.is_with_blinds = device.get("is_with_blinds")
                        blind.product_type_str = device.get("product_type_str")

        # Wait for initialization to complete (up to 30 seconds)
        try:
            await asyncio.wait_for(self._init_event.wait(), timeout=30.0)
        except asyncio.TimeoutError as exc:
            raise Exception("WMS stick initialization timed out") from exc

        _LOGGER.info("WaremaCoordinator: WMS stick ready")

        # Set up position polling
        self.stick.set_pos_upd_interval(POS_UPDATE_INTERVAL)
        self.stick.set_watch_moving_interval(WATCH_MOVING_INTERVAL)

        # Request initial position for all registered blinds
        _LOGGER.info("WaremaCoordinator: Requesting initial positions for all blinds")
        devices = self.entry.data.get(CONF_DEVICES, [])
        for device in devices:
            snr = device.get("snr")
            device_type = device.get("device_type", "20")
            if device_type in BLIND_DEVICE_TYPES and snr is not None:
                snr_int = int(snr) if not isinstance(snr, int) else snr
                _LOGGER.debug(
                    "WaremaCoordinator: Requesting initial position for SNR=%d",
                    snr_int,
                )
                await self.hass.async_add_executor_job(
                    self.stick.blind_get_position, snr_int
                )

        # Inline product-info enrichment for blinds added via an older config
        # entry (no product_type in stored data). Runs only for blinds that
        # still lack info, so steady-state startup cost is zero. The result is
        # persisted back to entry.data so the lookup never repeats.
        await self._enrich_product_info()

    async def _enrich_product_info(self) -> None:
        """Fill in missing product_type / is_with_blinds for blinds.

        Issues a Block 37 read for every Blind missing product info, then
        persists the result back to ``entry.data["devices"]`` so the next
        startup sees it without another wire round-trip. Failures are logged
        at INFO and left as None so the cover entity falls back to
        device-type heuristics.
        """
        if not self.stick:
            return
        devices = list(self.entry.data.get(CONF_DEVICES, []))
        by_snr = {int(d["snr"]): d for d in devices if "snr" in d}
        changed = False

        for blind in self.stick.get_blinds():
            if blind.product_type is not None:
                continue
            try:
                info = await self.hass.async_add_executor_job(
                    self.stick.read_product_info, blind.snr
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "WaremaCoordinator: product info read failed for %s",
                    blind.snr_hex,
                    exc_info=True,
                )
                continue
            if info is None:
                continue
            product_type, is_with_blinds = info
            stored = by_snr.get(blind.snr)
            if stored is not None:
                stored["product_type"] = product_type
                stored["is_with_blinds"] = is_with_blinds
                stored["product_type_str"] = blind.product_type_str
                changed = True

        if changed:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_DEVICES: devices},
            )
            _LOGGER.info(
                "WaremaCoordinator: persisted product info for %d device(s)",
                sum(1 for d in devices if d.get("product_type") is not None),
            )

    async def async_disconnect(self) -> None:
        """Disconnect from the WMS stick."""
        if self.stick:
            await self.hass.async_add_executor_job(self.stick.disconnect)
            self.stick = None
            _LOGGER.info("WaremaCoordinator: Disconnected")

    async def async_scan_devices(self, auto_assign: bool = True) -> list[dict]:
        """Scan for WMS devices and return the list.

        Args:
            auto_assign: If True, automatically add found blinds to the stick.

        Returns:
            List of discovered device dicts.
        """
        if not self.stick:
            return []

        self._scan_event.clear()
        self._scanned_devices = []

        await self.hass.async_add_executor_job(self.stick.scan_devices, auto_assign)

        # Wait for scan to complete (up to 10 seconds)
        try:
            await asyncio.wait_for(self._scan_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            _LOGGER.warning("WaremaCoordinator: Device scan timed out")

        return self._scanned_devices

    def add_blind(self, snr: int, name: str) -> None:
        """Add a blind to the stick."""
        if self.stick:
            self.stick.blind_add(snr, name)

    def get_blinds(self) -> list:
        """Return list of registered blinds."""
        if self.stick:
            return self.stick.get_blinds()
        return []

    def set_position(self, snr: int, position: int, angle: int = 0) -> None:
        """Move a blind to the specified position.

        Args:
            snr: Integer serial number of the blind.
            position: 0-100 (0=open, 100=closed).
            angle: -100 to +100 (slat angle).
        """
        if self.stick:
            self.stick.blind_set_position(snr, position, angle)

    def stop(self, snr: int) -> None:
        """Stop a blind.

        Args:
            snr: Integer serial number of the blind.
        """
        if self.stick:
            self.stick.blind_stop(snr)

    def open_cover(self, snr: int) -> None:
        """Open a blind (position=0, angle=-100).

        Args:
            snr: Integer serial number of the blind.
        """
        if self.stick:
            self.stick.blind_set_position(snr, 0, -100)

    def close_cover(self, snr: int) -> None:
        """Close a blind (position=100, angle=100).

        Args:
            snr: Integer serial number of the blind.
        """
        if self.stick:
            self.stick.blind_set_position(snr, 100, 100)

    def get_position(self, snr: int) -> None:
        """Request current position of a blind.

        Args:
            snr: Integer serial number of the blind.
        """
        if self.stick:
            self.stick.blind_get_position(snr)

    def wave(self, snr: int) -> None:
        """Send a wave (identify) request so the blind briefly moves.

        Args:
            snr: Integer serial number of the blind.
        """
        if self.stick:
            self.stick.blind_wave(snr)

    # -----------------------------------------------------------------------
    # WMS callback (called from background thread)
    # -----------------------------------------------------------------------

    def _wms_callback(self, error: str | None, msg: dict | None) -> None:
        """Handle callbacks from the WMS stick.

        This is called from the background reader thread.
        We schedule HA event loop calls via call_soon_threadsafe.
        """
        if error and error != "timeout":
            _LOGGER.error("WMS callback error: %s", error)

        if not msg:
            return

        topic = msg.get("topic", "")
        payload = msg.get("payload", {})

        _LOGGER.debug("WMS callback: topic=%s payload=%s", topic, payload)

        if topic == TOPIC_INIT_COMPLETION:
            # Signal init complete
            self.hass.loop.call_soon_threadsafe(self._init_event.set)

        elif topic == TOPIC_BLIND_POSITION_UPDATE:
            # Update coordinator data with new blind state (thread-safe)
            snr = payload.get("snr")
            snr_hex = payload.get("snr_hex", "")
            position = payload.get("position", -1)
            angle = payload.get("angle", 0)
            moving = payload.get("moving", False)

            # Build new data dict by copying current data and updating this SNR
            new_data = dict(self.data or {})
            new_data[snr] = BlindState(
                snr=snr,
                snr_hex=snr_hex,
                position=position,
                angle=angle,
                moving=moving,
            )

            # Update coordinator data (thread-safe).
            # NOTE: async_set_updated_data is a synchronous @callback in HA, NOT a
            # coroutine. It must be scheduled on the event loop with
            # call_soon_threadsafe so that async_update_listeners() ->
            # _handle_coordinator_update() -> async_write_ha_state() all run in the
            # event-loop thread. Using run_coroutine_threadsafe here would execute
            # the callback in this reader thread (wrong thread) and silently fail.
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, new_data)

        elif topic == TOPIC_SCANNED_DEVICES:
            # Scan results are consumed via self._scanned_devices + the
            # _scan_event in async_scan_devices(); no dispatcher needed.
            self._scanned_devices = payload.get("devices", [])
            self.hass.loop.call_soon_threadsafe(self._scan_event.set)

        elif topic == TOPIC_WEATHER_BROADCAST:
            weather = payload.get("weather", {})
            snr = weather.get("snr")
            if not snr:
                return
            state = WeatherState(
                snr=snr,
                snr_hex=weather.get("snr_hex", ""),
                temp=weather.get("temp", 0),
                wind=weather.get("wind", 0),
                lumen=weather.get("lumen", 0),
                rain=bool(weather.get("rain", False)),
            )
            is_new = snr not in self.weather_data
            self.weather_data = {**self.weather_data, snr: state}

            if is_new:
                # Tell the sensor/binary_sensor platforms to create entities for
                # this newly seen station.
                self.hass.loop.call_soon_threadsafe(
                    async_dispatcher_send,
                    self.hass,
                    f"{SIGNAL_NEW_WEATHER_STATION}_{self.entry.entry_id}",
                    snr,
                )
            # Refresh existing weather entities with the new reading.
            self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

        elif topic == "wms-vb-rcv-scan-request":
            _LOGGER.debug("WMS scan request from SNR %s", payload.get("snr"))

        elif topic == "wms-vb-rcv-wave-request":
            _LOGGER.debug("WMS wave request from SNR %s", payload.get("snr"))
