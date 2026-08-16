"""
Warema WMS custom integration for Home Assistant.

Provides cover entities for Warema WMS venetian blinds/shades
controlled via a WMS USB Stick (FTDI FT232R).

Serial port: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AV0K28M2-if00-port0
Baud rate: 125000
"""

from __future__ import annotations

import logging
import voluptuous as vol
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN
from .coordinator import WaremaCoordinator
from .pywarema.protocol import snr_hex_to_num

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
]

SERVICE_SET_POSITION_AND_VALANCE = "set_position_and_valance"
_SET_POSITION_AND_VALANCE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("position"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional("valance_1"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional("valance_2"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)


def _resolve_snr_and_coordinator(
    hass: HomeAssistant, entity_id: str
) -> tuple[int, WaremaCoordinator]:
    """Shared helper: entity_id -> (snr, coordinator), or raise HomeAssistantError."""
    registry = er.async_get(hass)
    entity_entry = registry.async_get(entity_id)
    if entity_entry is None or entity_entry.platform != DOMAIN:
        raise HomeAssistantError(f"'{entity_id}' ist keine Warema-WMS-Cover-Entity.")

    coordinator: WaremaCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entity_entry.config_entry_id
    )
    if coordinator is None:
        raise HomeAssistantError(
            f"Keine aktive Warema-WMS-Verbindung für '{entity_id}' gefunden."
        )

    snr_hex = entity_entry.unique_id.rsplit("_", 1)[-1]
    return snr_hex_to_num(snr_hex), coordinator


async def _async_handle_set_position_and_valance(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handler for set_position_and_valance.

    Sends the main position AND a valance target in ONE blindMoveToPos
    command. Use this instead of two separate cover.set_cover_position
    calls (one on the main cover, one on the valance cover) whenever both
    target the SAME physical motor (e.g. AwningOneValance) at roughly the
    same time - two separate commands close together can race and abort
    the valance move (see coordinator.set_position_and_valance docstring).

    `position` (and the current slat angle, read live from the coordinator)
    use the same raw 0-100 WMS convention as the "position" attribute shown
    on the entity (0=open/aus, 100=closed/zu) - NOT the inverted spiegel_*
    dashboard convention.
    """
    entity_id = call.data["entity_id"]
    position = call.data["position"]
    valance_1 = call.data.get("valance_1")
    valance_2 = call.data.get("valance_2")

    if valance_1 is None and valance_2 is None:
        raise HomeAssistantError(
            "set_position_and_valance: valance_1 oder valance_2 muss gesetzt sein "
            "(sonst reicht der normale cover.set_cover_position Service)."
        )

    snr, coordinator = _resolve_snr_and_coordinator(hass, entity_id)

    state = coordinator.data.get(snr) if coordinator.data else None
    current_angle = state.angle if state else 0

    try:
        await hass.async_add_executor_job(
            coordinator.set_position_and_valance,
            snr,
            position,
            current_angle,
            valance_1,
            valance_2,
        )
    except Exception as exc:
        raise HomeAssistantError(
            f"set_position_and_valance für '{entity_id}' fehlgeschlagen: {exc}"
        ) from exc


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Warema WMS from a config entry."""
    coordinator = WaremaCoordinator(hass, entry)

    try:
        await coordinator.async_connect()
    except Exception as exc:
        _LOGGER.error("Failed to connect to Warema WMS stick: %s", exc)
        raise ConfigEntryNotReady(f"Cannot connect to WMS stick: {exc}") from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register a "hub" device for this config entry itself, so the
    # via_device=(DOMAIN, entry.entry_id) references in binary_sensor.py,
    # button.py, cover.py and sensor.py resolve to a real device instead of
    # a dangling/non-existent one (HA logs a deprecation warning for that
    # and will start rejecting it outright from 2025.12.0).
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Warema",
        model="WMS USB Stick",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if not hass.services.has_service(DOMAIN, SERVICE_SET_POSITION_AND_VALANCE):

        async def _combined_service_handler(call: ServiceCall) -> None:
            await _async_handle_set_position_and_valance(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_POSITION_AND_VALANCE,
            _combined_service_handler,
            schema=_SET_POSITION_AND_VALANCE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: WaremaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)