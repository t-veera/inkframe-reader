# INKFRAME Reader

INKFRAME is an open-source, DRM-free, repairable DIY e-reader built on the
[CrossPoint](https://github.com/crosspoint-reader/crosspoint-reader) firmware,
ported to custom INKFRAME hardware. It is designed to be fully hackable,
component-swappable, and free from vendor lock-in — forever.

> **This is a fork of CrossPoint.** The full reader engine, UI, EPUB parsing,
> WiFi upload server, and settings are CrossPoint's work. INKFRAME replaces
> only the hardware layer (display driver, SD card, input) to run on custom
> hardware. See [SYNCING_WITH_CROSSPOINT.md](./SYNCING_WITH_CROSSPOINT.md) for
> how to pull upstream CrossPoint updates.

---

## Hardware

| Component | Part |
|---|---|
| MCU | ESP32-S3-N16R8 (16MB Flash, 8MB OPI PSRAM) |
| Display | Waveshare GDEQ0583T31 — 5.83", 648×480px, 135 DPI, UC8179 controller |
| Display driver | Waveshare e-Paper Driver HAT (breadboard / V1) |
| Storage | MicroSD card, FAT32 |
| Navigation | Sunrom 4379 5-way tactile switch |
| Charging | TP4056 + MT3608 boost |

### Pin map (V2 schematic — authoritative)

| Signal | GPIO |
|---|---|
| EPD_PWR_EN | 6 |
| EPD_BUSY | 7 |
| EPD_RST | 8 |
| EPD_DC | 9 |
| EPD_CS | 10 |
| EPD_DIN / SD_MOSI | 13 (shared bus) |
| EPD_SCK / SD_SCK | 47 (shared bus) |
| SD_MISO | 21 |
| SD_CS | 48 |
| NAV UP | 1 |
| NAV DOWN | 2 |
| NAV LEFT | 4 |
| NAV RIGHT | 5 |
| NAV CENTER | 17 |
| POWER button | 0 |
| BAT_ADC | 15 |
| CHRG (TP4056) | 38 |
| STDBY (TP4056) | 39 |
| BOOST_EN (MT3608) | 45 |

---

## What it does (inherited from CrossPoint)

- **Reader engine** — EPUB 2/3 rendering, image handling, hyphenation,
  chapter navigation, footnotes, bookmarks, go-to-percent, auto page turn,
  KOReader progress sync
- **Formats** — `.epub`, `.txt`, `.bmp`
- **Custom fonts** — drop `.ttf` files into `/fonts/` on the SD card
- **Library workflow** — folder browser, recent books, SD cache management
- **Wireless workflows** — file transfer web UI, WebSocket fast uploads,
  WebDAV, WiFi AP/STA mode, Calibre wireless connect, OPDS browser, OTA
- **Themes** — Classic, Lyra, Lyra Extended, RoundedRaff
- **Localization** — 24 UI languages, RTL support

---

## SD card folder structure

```
/
├── books/          ← put EPUB files here
├── fonts/          ← custom .ttf font families
└── .crosspoint/    ← settings and reading position (auto-created)
```

### Recommended fonts for 135 DPI e-ink

| Font | Source | Why |
|---|---|---|
| **Gelasio** | Google Fonts | Georgia clone, designed for low-DPI screens — best pick |
| **Bitstream Charter** | nicoverbruggen/ebook-fonts | Designed for 300 DPI laser/fax — holds up perfectly at 135 DPI |
| **Atkinson Hyperlegible** | Google Fonts | Engineered for degraded rendering conditions |

Avoid Garamond, Baskerville, and Bookerly — their hairline strokes break up
at 135 DPI.

---

## Building and flashing

### Requirements
- PlatformIO (VS Code extension or CLI)
- ESP32-S3-N16R8 dev board connected via USB (not UART) port

### Clone
```bash
git clone https://github.com/t-veera/inkframe-reader.git
cd inkframe-reader
git checkout inkframe-s3-uc8179
git submodule update --init --recursive
```

### Build
```bash
pio run
```

### Flash
```bash
pio run -t upload
```

### Monitor
```bash
pio device monitor
```

> **N16R8 is required.** `platformio.ini` sets
> `board_build.arduino.memory_type = qio_opi` for the Octal PSRAM. Compiling
> without this flag (for N8R8) will cause silent failures.

---

## Architecture

INKFRAME follows a clean five-layer stack. Only layer 3 (the HAL) differs from
upstream CrossPoint. See [ARCHITECTURE_LAYERS.md](./ARCHITECTURE_LAYERS.md).

```
5 · UI                   CrossPoint — untouched
4 · Application/logic    CrossPoint — untouched
3 · Driver / HAL         INKFRAME — GxEPD2 shim, shared SPI, 5-way switch
2 · Framework / RTOS     Arduino-ESP32 + FreeRTOS — given by Espressif
1 · Hardware             Your board and wiring
```

**INKFRAME-specific files (layer 3 only):**
- `open-x4-sdk/libs/display/EInkDisplay/src/EInkDisplay_inkframe.cpp` — GxEPD2 shim
- `open-x4-sdk/libs/hardware/SDCardManager/src/SDCardManager.cpp` — shared SPI SD
- `lib/hal/inkframe_pins.h` — single source of truth for all pin numbers
- `platformio.ini` — S3 board, OPI PSRAM, GxEPD2 dependency

All changes are guarded by `#ifdef INKFRAME_HW` so CrossPoint's originals are
preserved and upstream syncs remain clean.

---

## Syncing with upstream CrossPoint

See [SYNCING_WITH_CROSSPOINT.md](./SYNCING_WITH_CROSSPOINT.md) for the full
workflow. Short version:

```bash
git remote add upstream https://github.com/crosspoint-reader/crosspoint-reader.git
git fetch upstream
git rebase upstream/master
```

---

## Roadmap

| Phase | Status | What |
|---|---|---|
| Phase 1 | ✅ Done | Boot + display rendering CrossPoint UI on INKFRAME hardware |
| Phase 2 | 🔜 Next | 5-way switch input, battery ADC (GPIO15), power management |
| Phase 3 | Planned | Home-library dashboard (UDP discovery + POST /upload) |
| Phase 4 | Planned | Deep sleep/wake, NVS position caching, polish |
| V3 | Future | Custom PCB, GDEY display, OTA, ≤9mm thickness |

---

## Licence

INKFRAME firmware inherits CrossPoint's licence. See
[LICENSE](./LICENSE) for details. Hardware design files are released under
CERN-OHL-S.

---

## Credits

Built on [CrossPoint](https://github.com/crosspoint-reader/crosspoint-reader)
by the CrossPoint community. Display driver via
[GxEPD2](https://github.com/ZinggJM/GxEPD2) by Jean-Marc Zingg. EPUB engine
originally from [atomic14](https://github.com/atomic14/esp32-ereader).
