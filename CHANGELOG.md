# Changelog

All notable changes to this project will be documented in this file.

## [1.5.0] - 2026-06-09

### Added
- **Lamellendach (slat-roof) support.** Warema slat-roof systems
  (SlatRoofL60 / SlatRoofL70 / SlatRoofL70Tilting) are now discovered and
  controllable. These products use a dedicated radio motor type
  (`RADIO_MOTOR_L60_L70`, device type `2A`) that was previously filtered out of
  the device-discovery wizard, so the roof never appeared as a selectable device
  even though it answered the network scan. Device type `2A` is now recognised:
  - added to `BLIND_DEVICE_TYPES` so the slat-roof motor shows up in the scan
  - mapped to the `awning` HA cover device class with slat-tilt enabled
  - product types `27`/`28`/`29` added to the product-name and tilt tables
  The mapping was confirmed against the  WMS Studio Pro core
  (`EDeviceType` / `EProductType` enums).

## [1.4.0] - 2026-05-29

### Added
- **Full motor-parameter configuration.** The *Configure motor firmware
  parameters* options flow now exposes all 17 writable block-38 parameters
  instead of the original 5:
  - *Komfortfunktionen* (`comfort_auto_enabled`) — enable/disable the sensor
    automatics (sun, wind) on the handheld remote
  - *Position/Winkel bei Status Abwesend* (`absent_position`, `absent_angle`)
    — position and slat angle applied when the "Away" status is active
  - *Laufzeit Hoch/Tief* (`run_time_up`, `run_time_down`) — seconds for a
    full travel stroke, used for accurate position tracking
  - *Kalibrierung Hoch/Tief* (`calibration_up`, `calibration_down`) — extra
    run time after hitting the end stop for precise referencing
  - *Wendezeit* (`tilting_time`) — seconds for a full 180° slat rotation
  - *Minimaler/Maximaler Lamellenwinkel* (`min_angle`, `max_angle`) — slat
    travel limits in degrees (−127 … +127)
  - *Wendeschritte pro Wendung* (`tilting_steps`) — intermediate steps per
    full slat rotation (finer = smoother)
  - *Motordrehrichtung umkehren* (`motor_rotation`) — reverses motor direction
    if the blind moves the wrong way
  Each field is pre-filled with the value currently stored in the motor. Only
  changed fields are written; unchanged fields are never touched.
- **Firmware/hardware diagnostic sensors.** Two read-only diagnostic entities
  are now created for each configured blind:
  - *Softwareversion* — firmware version string read from block 81
  - *Gerätetyp* — hardware device-type name read from block 81
  Both are marked `entity_category: diagnostic` and appear in the device's
  diagnostic card in the HA UI.
- **German translations for all options-flow strings.** The
  `translations/de.json` file now contains full German labels and one-sentence
  field descriptions for all 17 firmware parameters, matching the ZHA style
  (clean label + concise description below the input).
- **Copy parameters from another blind.** The device picker now has an optional
  *Load values from* dropdown. Choose another configured blind as the source and
  the form opens pre-filled with that blind's values, ready to write to the
  selected device; leave it on *current values of the device* to edit the device's
  own settings. Handy for replicating a tuned setup across identical blinds.

### Changed
- **Redesigned the motor-parameter form for clarity.** Numeric fields are now
  **input boxes instead of sliders** (with %/s/° units shown), the 17 fields are
  organised into **collapsible sections** (Manual operation, Comfort, Away
  status, Run times & calibration, Slats, Other), and the redundant current-value
  table above the form was removed since every field is pre-filled with its
  current value.
- **Parameters are read up front with a loading indicator.** Selecting the device
  (and optional copy source) leads through a short progress step that reads the
  values over the radio network before the form opens. The form's *Submit* now
  only writes — the previous two-step "submit to load, submit again to write" copy
  flow is gone. The form title shows which device is being edited.
- **Minimum Home Assistant version raised to 2024.6.0** (`hacs.json`), required
  for the collapsible form sections.

## [1.3.1] - 2026-05-29

### Fixed
- **Motor-parameter writes no longer risk corrupting unrelated settings.**
  Writing firmware parameters (manual/comfort position & slat angle, dwell time,
  absent flag) previously staged a full 496-byte snapshot of block 38 into a
  staging buffer and committed it atomically ("transfer block"). On some
  firmware a partial commit could silently overwrite *unrelated* bytes — most
  critically `motorRotation` (block 38, addr 475), which inverts a blind's
  up/down direction. Because verification only re-checked the bytes that were
  intended to change, this corruption went undetected.

  Writes are now **targeted single-byte writes** to the exact block-38 address
  for each changed field. Only the requested bytes are ever touched, so a failed
  or interrupted write can no longer scramble other parameters. Each write is
  retried, no-op writes are skipped, and every written byte is read back and
  verified before the operation reports success.

## [1.3.0] - 2026-05-28

### Added
- **Weather station sensors.** WMS weather stations (device type `06`) broadcast
  their readings periodically over the radio network. The integration now
  decodes those broadcasts and exposes them as Home Assistant entities:
  - Temperature (`°C`, device class `temperature`)
  - Wind speed (`m/s`, device class `wind_speed`)
  - Brightness (`lx`, device class `illuminance`)
  - Rain (binary sensor, device class `moisture`)

  Weather stations are not part of the device-selection wizard because they
  transmit unsolicited; their entities are created **automatically** the first
  time a broadcast is received (typically within a few minutes of startup), each
  grouped under its own "Weather station &lt;SNR&gt;" device.
- **Identify button.** Every cover now has an *Identify* button
  (`ButtonDeviceClass.IDENTIFY`) that sends a wave/beckon request, making the
  blind briefly move so you can tell which physical device an entity controls.
- Entity names are now provided through Home Assistant translation keys, with
  **German translations** (`translations/de.json`) for the new weather and
  identify entities (Temperatur, Windgeschwindigkeit, Helligkeit, Regen,
  Identifizieren).

### Notes
- The brightness value is decoded empirically from the weather broadcast and is
  exposed in lux; the exact magnitude may need calibration against your station.

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
