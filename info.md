## Warema WMS

Control your Warema WMS blinds and shades directly via the **Warema WMS USB Stick** — no cloud, no gateway, no MQTT broker required.

> This integration talks **directly to the WMS radio network** (433 MHz, AES-encrypted). It does **not** support WMS WebControl pro.

---

### What you get

| Entity | Description |
|--------|-------------|
| **Cover** | Open / close / stop / set position and tilt angle |
| **Sensor** | Position, tilt angle and motor serial number |
| **Binary sensor** | Moving / stopped |
| **Button** | Identify — waves the blind so you can match it to an entity |
| **Weather station** | Temperature, wind speed, brightness and rain (auto-discovered) |

Slat tilt is enabled automatically for products with slats (Raffstoren, Venetian blinds); awnings and roller shutters get no tilt control.

---

### Requirements

- **Warema WMS USB Stick** (FTDI FT232R, USB VID `0403` / PID `6001`)
- Home Assistant **2023.1.0** or later
- Supported actuator types: **20** (Actuator UP), **21** (Plug receiver), **25** (Radio motor), **2E** (Actuator 230V UP)

---

### Setup

The setup wizard auto-detects the USB stick and offers three ways to obtain the WMS network parameters:

1. **Enter manually** — if you already know channel, PAN ID and key
2. **Wandsender pairing** — wizard captures parameters from a WMS Wandsender (handheld transmitter) automatically
3. **Create new network** — generates fresh credentials; pair motors to it afterwards
