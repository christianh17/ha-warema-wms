# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-05-28

### Added
- Automatic product detection: on first connect, the integration reads the
  motor's `productType` from Block 37 (productParameters) and remembers it in
  the config entry. The cover entity then exposes the right HA
  `CoverDeviceClass` (`awning`, `blind`, `shutter`, `shade`, `window`) and
  enables slat tilt only for products that actually have slats
  (ExternalVenetianBlind, InternalVenetianBlind, VerticalLouvreBlind), based on
  the motor's own `isWithBlinds` flag.
- All 23 EProductType variants known to WMS Studio Pro are mapped (the Awning
  family, Markisolette, Pergola, Roller Shutter, Pleated Blind, Window, Sun
  Sail, …). Unknown IDs fall back to `CoverDeviceClass.BLIND`.
- The device picker in the setup wizard and the rescan flow now show the
  product name (e.g. "PergolaAwning") instead of the generic actuator hardware
  name ("Plug receiver"), so users pick the right device by what's actually
  installed on their facade.
- New helper `WmsStick.read_product_info()` (single MB8 read on Block 37) and
  `pywarema.protocol.PRODUCT_TYPE_NAMES` table derived from the
   `the protocol notes` `EProductType` enum.

### Changed
- The previous hard-coded "tilt only for actuator types 20/2E" rule from 1.0.2
  is now only a *fallback* used when Block 37 cannot be read (e.g. motor
  asleep at setup time). The authoritative source is the motor's own
  `isWithBlinds` flag, so a Raffstore on a plug receiver now correctly gets
  tilt controls.
- The HA device-info `model` field shows `ProductName (Hardware)` (e.g.
  "ExternalVenetianBlind (Actuator UP)") instead of only the hardware name.

## [1.1.0] - 2026-05-26

### Added
- Read and write the persistent motor firmware parameters that WMS Studio Pro
  configures: *Position bei manueller Bedienung*, *Winkel bei manueller
  Bedienung*, *Haltezeit*, *Komfortposition* and *Status Abwesend*. These live
  in Block 38 on the motor and also apply when the handheld remote operates it.
- Options-Flow menu entry **Configure motor firmware parameters** with a device
  picker (friendly names from the device registry) and a form pre-filled with
  the current values read from the motor. Empty fields leave the corresponding
  parameter unchanged.
- New `MotorParameters` dataclass and `read_motor_parameters()` /
  `write_motor_parameters()` methods on `WmsStick`. The write path drives the
  full 2-phase transfer-block protocol (8 data chunks to Block 8 → header,
  trailers → commit at addr `0x01F7` → verify read-back), derived
  from a protocol capture and the , custom
  JavaScript engine + PList schemas of the manufacturer app.
- Generic MB8 block read/write (`mb8_read`/`mb8_write`, opcodes
  `0x8010`/`0x8020`) for arbitrary block/addr access on top of the existing
  hard-coded position/clock/auto request types.
- Bundled PList JSONs for the Zwischenstecker (Plug Receiver v3, SW
  `05930141007`) × ExternalVenetianBlind variant `E100AF-AFA6`, used to map
  parameter FQNs to `(block, addr)` pairs.

### Fixed
- Race condition in `WmsStick._process_queue`: a fast device response could
  clear `_current_msg` before `_send_frame` returned, raising `AttributeError`
  on `.timeout`. The current message is now captured into a local before send.

### Verified
- Round-trip tested against real hardware on two Zwischenstecker devices.

## [1.0.3] - 2026-05-23

### Fixed
- Declared the `usb` integration as a dependency so USB auto-discovery of the
  WMS stick works reliably and the manifest passes Home Assistant's hassfest
  validation.
- Removed an invalid `homeassistant` key from `manifest.json` (the minimum HA
  version belongs in `hacs.json`) and reordered the manifest keys to the
  hassfest convention.

### Added
- Bundled brand icons (`icon.png`, `dark_icon.png`, plus `@2x` hDPI variants) in
  `custom_components/warema_wms/brand/`. From Home Assistant 2026.3 these are
  served through the local Brands Proxy API, so the integration shows its own
  icon in the UI without a separate brands-repository submission.
- Continuous integration: HACS Action and hassfest validation now run on every
  push, plus a daily scheduled check.

## [1.0.2] - 2026-05-22

### Fixed
- Sensors and the moving binary_sensor now appear on first setup, not only after a
  later rescan. If no device is explicitly ticked in the setup wizard, all discovered
  blinds are added, so `CONF_DEVICES` is always populated and every platform creates
  its entities consistently.

### Changed
- Tilt controls are now only exposed for actuator types 20 (Actuator UP) and 2E
  (Actuator 230V UP), which drive slatted blinds (Raffstoren). Awnings and roller
  shutters on plug receivers (21) or radio motors (25) no longer show a meaningless
  tilt control.

## [1.0.1] - 2026-05-22

### Fixed
- Position polling no longer lets the serial queue grow without bound: background
  position queries (pos-update / watch-moving) now skip motors that already have a
  pending `blindGetPos` request (dedup guard).
- Reduced retry count for background position polls (new `POS_POLL_RETRY`), so an
  unreachable motor costs ~1 s instead of ~3 s per cycle and the 5 s poll cycle
  stays ahead of the backlog even with one or two flaky motors. Working blinds keep
  updating reliably. Explicit user commands (stop/move follow-ups) keep full retries.

## [1.0.0] - 2026-05-21

### Added
- Initial Home Assistant integration for Warema WMS venetian blinds control
- Config flow UI for easy setup with multiple discovery methods:
  - Manual configuration with IP/port
  - Wandsender auto-pairing
  - New network creation
- Cover entities with full blind control:
  - Open, close, stop, set position and tilt
  - Position and angle feedback
- Sensor entities for position and angle monitoring
- Binary sensor entities for motion detection (moving/stopped)
- USB auto-detection for FTDI FT232R (Warema WMS USB Stick)
- Support for 4 blind device types: Type 20, Type 21, Type 25, Type 2E
- Localized UI strings with English translation
- Brand assets (logos and icons) for Home Assistant UI

### Requirements
- Python 3.9+
- Home Assistant 2023.1.0+
- pyserial >= 3.5
- Warema WMS compatible hardware (venetian blinds/shades)
