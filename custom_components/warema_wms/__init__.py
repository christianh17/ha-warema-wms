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
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .coordinator import WaremaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
]

SERVICE_TEST_MOVE_VALANCE = "test_move_valance"
_TEST_MOVE_VALANCE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("valance_1"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional("valance_2"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)


async def _async_handle_test_move_valance(hass: HomeAssistant, call: ServiceCall) -> None:
    """EXPERIMENTAL/untested: handler for the test_move_valance service.

    See the comment on the "blindMoveToPos" command in
    pywarema/protocol.py for what this relies on.
    """
    entity_id = call.data["entity_id"]
    valance_1 = call.data.get("valance_1")
    valance_2 = call.data.get("valance_2")

    if valance_1 is None and valance_2 is None:
        raise HomeAssistantError(
            "test_move_valance: valance_1 oder valance_2 muss gesetzt sein."
        )

    registry = er.async_get(hass)
    entity_entry = registry.async_get(entity_id)
    if entity_entry is None or entity_entry.platform != DOMAIN:
        raise HomeAssistantError(
            f"'{entity_id}' ist keine Warema-WMS-Cover-Entity."
        )

    coordinator: WaremaCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entity_entry.config_entry_id
    )
    if coordinator is None:
        raise HomeAssistantError(
            f"Keine aktive Warema-WMS-Verbindung für '{entity_id}' gefunden."
        )

    # unique_id is "{DOMAIN}_{snr_hex}" (see cover.py) - snr_hex is the last
    # token after the domain prefix.
    snr_hex = entity_entry.unique_id.rsplit("_", 1)[-1]
    snr = int(snr_hex, 16)

    _LOGGER.warning(
        "test_move_valance: EXPERIMENTAL command, snr=%s valance_1=%s valance_2=%s",
        snr_hex,
        valance_1,
        valance_2,
    )
    await hass.async_add_executor_job(
        coordinator.set_valance_position, snr, valance_1, valance_2
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Warema WMS from a config entry."""
    coordinator = WaremaCoordinator(hass, entry)

    try:
        await coordinator.async_connect()
    except Exception as exc:
        _LOGGER.error("Failed to connect to Warema WMS stick: %s", exc)
        raise ConfigEntryNotReady(f"Cannot connect to WMS stick: {exc}") from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if not hass.services.has_service(DOMAIN, SERVICE_TEST_MOVE_VALANCE):

        async def _service_handler(call: ServiceCall) -> None:
            await _async_handle_test_move_valance(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_TEST_MOVE_VALANCE,
            _service_handler,
            schema=_TEST_MOVE_VALANCE_SCHEMA,
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
