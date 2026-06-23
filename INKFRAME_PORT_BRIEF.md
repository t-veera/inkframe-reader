# INKFRAME ← CrossPoint Port Brief

**Read this file completely before doing anything. Do NOT ask the user about
hardware, pins, the display, or the architecture — it is all here. When in
doubt, prefer the decisions in this file over re-deriving them.**

---

## 0. What we are doing (one paragraph)

We are porting the **CrossPoint** e-reader firmware
(`github.com/crosspoint-reader/crosspoint-reader`, default/`master` branch) to
run on the **INKFRAME** hardware: an ESP32-S3-N16R8 dev board driving a
**Waveshare GDEQ0583T31** 5.83" SPI e-paper panel (UC8179 controller). The user
already has a **working V1 firmware** that drives this exact panel using the
**GxEPD2** library. The plan is NOT to port CrossPoint's hand-rolled UC81xx
driver. The plan is to **reimplement CrossPoint's display HAL as a thin shim
over GxEPD2**, reusing the user's proven-working display path. The entire reader
UI, EPUB engine, fonts, WiFi upload server, and settings come for free from
CrossPoint and must not be touched.

**Hard constraints:**
- **B&W only.** This panel has no grayscale. Do not port, tune, or keep any
  grayscale/LUT code paths. Stub them.
- **The display layer must stay a single, cleanly swappable unit.** It is the
  first thing the user will replace when they move to a better display. No
  display-specific assumptions may leak into the app/UI layer.

---

## 1. Verified hardware (DO NOT re-ask, DO NOT change)

**MCU:** ESP32-S3-N16R8 dev board (Robodo). 16MB Flash, 8MB OPI PSRAM.
- Memory is NOT scarce here (8MB PSRAM). CrossPoint's C3 memory-frugality
  assumptions are safe to relax; a full framebuffer in RAM is fine.

**Display:** Waveshare GDEQ0583T31, 5.83", 648×480 px, UC8179 controller,
SPI 4-wire. **PWR pin must be driven HIGH before the panel responds** (BUSY
stays permanently LOW otherwise). This quirk is already handled correctly by
GxEPD2 + the manual PWR-HIGH in the user's V1 (see §3).

**Pin map (from the V2 KiCad schematic — AUTHORITATIVE, overrides V1 config.h):**
```
DISPLAY (EPD, SPI 4-wire):
  EPD_PWR_EN = GPIO6     (drive HIGH before display init — the PWR quirk)
  EPD_BUSY   = GPIO7
  EPD_RST    = GPIO8
  EPD_DC     = GPIO9
  EPD_CS     = GPIO10
  EPD_DIN    = GPIO13    (= MOSI; shared display + SD)  ** see B0 **
  EPD_SCK    = GPIO47    (shared display + SD)

SD CARD (shared SPI bus):
  SD_MOSI = GPIO13   (same net as EPD_DIN)
  SD_MISO = GPIO21
  SD_SCK  = GPIO47   (same net as EPD_SCK)
  SD_CS   = GPIO48

5-WAY NAV SWITCH (digital GPIO inputs, active-low, use INPUT_PULLUP):
  UP     = GPIO1     -> previous page
  DOWN   = GPIO2     -> next page
  LEFT   = GPIO4     -> back
  RIGHT  = GPIO5     -> menu
  CENTER = GPIO17    -> select / OK

POWER / SYSTEM:
  MAIN_SWITCH (power/wake) = GPIO0   (strapping pin; used for wake — fine for a
                                      button, but do NOT also use for I/O)
  BAT_ADC = GPIO15   (volts = raw/4095 * 3.3 * 2.0;  % = (V-3.0)/1.2*100)
  CHRG    = GPIO38   (TP4056 charge status, internal pull-up, LOW=charging)
  STDBY   = GPIO39   (TP4056 standby, internal pull-up, LOW=done; both HIGH=discharging)
  BOOST_EN (MT3608) = GPIO45   (HIGH=boost on/battery; LOW=boost off/USB present)
```
**Display and SD share ONE SPI bus** (FSPI): SCK=47, MOSI/DIN=13, MISO=21.
Display CS=10, SD CS=48. This is critical — see bottleneck B2.

**Reserved GPIOs (N16R8 — never use for I/O):** OPI PSRAM/Flash internal pins,
GPIO33/34/35/36/37 (Octal data lines on N16R8), GPIO43/44 (UART).

**Navigation input:** single 5-way tactile switch (Sunrom 4379) wired to 5
discrete digital GPIOs above + a separate power button on GPIO0. This is NOT an
ADC resistor-ladder — CrossPoint ships an ADC-ladder InputManager that must be
replaced with a digital-GPIO reader. See bottleneck B3.

---

## 2. CrossPoint architecture (already analyzed — trust this)

CrossPoint is cleanly layered. The app never touches hardware directly.

```
src/                      app + UI + reader + activities  (DISPLAY-AGNOSTIC, do not touch)
  └─ calls →
lib/hal/HalDisplay.{h,cpp}   thin wrapper (~105 lines), pure passthrough
  └─ wraps →
open-x4-sdk (submodule: github.com/crosspoint-reader/community-sdk)
  └─ libs/display/EInkDisplay/   ← THE HARDWARE DRIVER. This is the ONE place we change.
```

`open-x4-sdk` is a **git submodule** (`git submodule update --init --recursive`).
The real driver is `open-x4-sdk/libs/display/EInkDisplay/src/EInkDisplay.cpp`
(~1839 lines) targeting **SSD1677** (Xteink X4) and **UC81xx** (Xteink X3) —
**neither is our panel**.

The app talks to the display through this surface (via `HalDisplay`, which
forwards to `EInkDisplay`):
- `begin(bool seamless=false)`
- `clearScreen(uint8_t color=0xFF)`
- `drawImage(...)`, `drawImageTransparent(...)`
- `displayBuffer(RefreshMode, bool turnOffScreen)`
- `refreshDisplay(RefreshMode, bool turnOffScreen)`
- `getFrameBuffer()` → `uint8_t*` (1bpp packed, DISPLAY_WIDTH_BYTES = W/8)
- `deepSleep()`
- geometry getters: `getDisplayWidth/Height/WidthBytes/BufferSize`
- grayscale methods (`copyGrayscale*`, `displayGrayBuffer`,
  `writeGrayscalePlaneStrip`, `supportsStripGrayscale`) → **STUB THESE** (B&W only)

**Strategy: replace the body of `EInkDisplay` (or provide an INKFRAME build
variant of it) so every method above is backed by a GxEPD2
`GxEPD2_BW<GxEPD2_583_GDEQ0583T31, ...>` instance.** Keep the class name,
constructor signature `(sclk, mosi, cs, dc, rst, busy)`, and public API identical
so `HalDisplay` and everything above compile unchanged.

The 1bpp framebuffer model already matches: CrossPoint's BW buffer is
`(W/8)*H` packed monochrome, which maps directly onto GxEPD2's paged/full
buffer. Geometry: **648×480**, `DISPLAY_WIDTH_BYTES = 81`, `BUFFER_SIZE = 38880`.

---

## 3. The proven-good display path (reuse this exactly)

From the user's working V1 `main.cpp` — this is the known-good GxEPD2 path on
the real panel. **NOTE:** V1 used MOSI=GPIO14, but the V2 schematic moved
MOSI/DIN to **GPIO13** (see pin map §1 and bottleneck B0). Use GPIO13.

```cpp
#include <GxEPD2_BW.h>
GxEPD2_BW<GxEPD2_583_GDEQ0583T31, GxEPD2_583_GDEQ0583T31::HEIGHT>
  display(GxEPD2_583_GDEQ0583T31(/*CS=*/10, /*DC=*/9, /*RST=*/8, /*BUSY=*/7));

SPIClass fspi(FSPI);

// init sequence that WORKS (pins per V2 schematic):
#define EPD_PWR 6
#define EPD_CS 10
#define SD_CS 48
#define EPD_SCK 47
#define EPD_MOSI 13    // V2 schematic: DIN/MOSI on GPIO13 (was 14 in V1)
#define SD_MISO 21

pinMode(EPD_CS,  OUTPUT); digitalWrite(EPD_CS,  HIGH);
pinMode(SD_CS,   OUTPUT); digitalWrite(SD_CS,   HIGH);
pinMode(EPD_PWR, OUTPUT); digitalWrite(EPD_PWR, HIGH);   // <-- the PWR quirk
delay(100);
fspi.begin(EPD_SCK, SD_MISO, EPD_MOSI, SD_CS);           // shared bus
SD.begin(SD_CS, fspi, 400000);                           // SD on SAME bus
display.epd2.selectSPI(fspi, SPISettings(4000000, MSBFIRST, SPI_MODE0));
display.init(115200, true, 10, false);
display.setRotation(1);   // DEFAULT_ROTATION = 1 (landscape)
```

GxEPD2 owns init, BUSY polarity, reset timing, and refresh waveforms for this
panel — all already correct. The shim must reproduce this init inside
`EInkDisplay::begin()` and route `displayBuffer/refreshDisplay` to GxEPD2's
full-window update (`display.setFullWindow(); display.firstPage()/nextPage()`
or `display.drawBitmap` + `display.display()` depending on buffer flow).

`platformio.ini` essentials from V1 (merge into CrossPoint's, do not overwrite
CrossPoint's lib_deps wholesale):
```
board = esp32-s3-devkitc-1
board_build.mcu = esp32s3
board_build.arduino.memory_type = qio_opi
board_upload.flash_size = 16MB
build_flags = -DBOARD_HAS_PSRAM
lib_deps += ZinggJM/GxEPD2 @ ^1.6.0
```

---

## 4. Bottlenecks / where this will fail (watch these)

**B0 — MOSI/DIN on GPIO13: VERIFY FIRST if nothing renders.** V1 ran MOSI on
GPIO14 and worked. The V2 schematic moved DIN/MOSI to **GPIO13**. GPIO13 should
be a free GPIO on the N16R8, but it sits adjacent to the Octal-memory pin range
and is the single most likely culprit if the panel stays blank or garbled. If
Phase 1 boots but the display shows nothing/garbage, check GPIO13 continuity and
that no PSRAM conflict exists before touching anything else. (If it turns out
GPIO13 conflicts on this specific board, the fix is a hardware re-route, not
firmware — flag it to the user, don't work around it in code.)

**B1 — Init / BUSY / PWR: LOW RISK.** Because we use GxEPD2 (proven on this
panel), init-byte and BUSY-polarity risks are eliminated. Just ensure the
PWR-HIGH-before-init step (GPIO6 HIGH, delay 100ms) is in `begin()`. If the panel
hangs at boot waiting on BUSY, check this first.

**B2 — SD card bus: MEDIUM RISK, must fix.** CrossPoint's
`open-x4-sdk/libs/hardware/SDCardManager` hardcodes `SD_CS=12` and uses the
DEFAULT SPI bus. Our SD is on the SHARED FSPI bus (SCK47/MOSI14/MISO21) with
`SD_CS=48`. Rewrite SDCardManager (or the storage HAL) to:
`SD.begin(48, fspi, <freq>)` using the same `fspi` instance the display uses.
Display + SD sharing one bus works (V1 proves it) but both CS lines must be
managed and the bus initialized once.

**B3 — Input: MEDIUM RISK, isolated.** CrossPoint's InputManager
(`open-x4-sdk/libs/hardware/InputManager`) reads an ADC resistor-ladder (one
analog pin, voltage thresholds). INKFRAME uses a 5-way switch on **discrete
digital GPIOs** + a separate power button. Reimplement the input HAL to read
these GPIOs with `INPUT_PULLUP` (active-low, debounce ~20-30ms) and emit the
button events CrossPoint expects:
```
GPIO1  UP     -> previous page
GPIO2  DOWN   -> next page
GPIO17 CENTER -> select / OK
GPIO4  LEFT   -> back
GPIO5  RIGHT  -> menu
GPIO0  POWER  -> power / wake (separate button; strapping pin, input only)
```
Map these to whatever event enum CrossPoint's InputManager exposes
(prev/next/select/back/menu/power) so the activities above are unchanged. Keep
this isolated like the display layer.

**B4 — Platform C3→S3: LOW-MEDIUM RISK.** CrossPoint master targets
esp32-c3-devkitm-1. Audit and adjust for S3:
- `board`, `board_build.mcu`, `memory_type = qio_opi`, PSRAM flags.
- `src/platform/skip_efuse_blk_check.c` and the `-Wl,--wrap=...` panic/efuse
  linker tricks are C3-oriented — verify they build on S3; drop/adjust if they
  break the link.
- USB CDC boot flags (`-DARDUINO_USB_MODE=1 -DARDUINO_USB_CDC_ON_BOOT=1`) are
  fine on S3.
- `partitions.csv` — keep CrossPoint's (16MB, app + storage).

**B5 — Grayscale compile breakage: LOW RISK, tedious.** Even B&W-only, the
grayscale methods are referenced across `HalDisplay` and possibly activities.
Don't delete — stub them (empty body / fall through to B&W path /
`supportsStripGrayscale()` → false) so it compiles. `EINK_DISPLAY_SINGLE_BUFFER_MODE`
is already a build flag CrossPoint uses; keep single-buffer mode on.

**B6 — Cannot be verified without hardware.** "Compiles + boots + renders text
on the real panel" can only be confirmed by the user flashing and reading
serial. Deliver to "compiles clean, shim built from the proven GxEPD2 path,
ready to flash" — then iterate on serial output with the user.

---

## 5. Phase plan (do Phase 1, then STOP for the user to flash)

**Phase 1 — Boot + render (the milestone):**
1. Clone CrossPoint, `git submodule update --init --recursive`, branch
   `inkframe-s3-uc8179`.
2. Add GxEPD2 to lib_deps; switch platformio.ini env to S3 (§3, B4).
3. Reimplement `EInkDisplay` as the GxEPD2 shim (§2, §3). Keep API identical.
   Stub grayscale (B5). Put the PWR-HIGH in `begin()`.
4. Fix SDCardManager for the shared FSPI bus + SD_CS=48 (B2).
5. Get it **compiling**. Commit.
6. **STOP.** Hand back to user to flash and report serial + what the panel shows.

**Phase 2 — Input + navigation:** reimplement input HAL for the 5-way switch on
digital GPIOs 1/2/4/5/17 + power on GPIO0 (B3). Wire battery ADC on GPIO15
(formula in §1). Optionally surface charge status (CHRG=GPIO38, STDBY=GPIO39).

**Phase 3 — Dashboard integration (NO firmware change needed):** see §6.

**Phase 4 — sleep/wake, NVS, polish:** only after the reader runs.

Commit after each phase with clear messages. The user pushes (or you push with
their git auth in their environment) to `github.com/t-veera/inkframe-firmware`.

---

## 6. Home-library dashboard (separate app, zero firmware change)

CrossPoint ALREADY exposes everything the user's "press a button to send a book
over the LAN" dashboard needs. Do not add firmware for this.

- **HTTP upload:** `POST /upload` (multipart) — sends an EPUB straight to the
  device storage.
- **Fast binary upload:** a WebSocket server (port reported by discovery, see
  below) for large files.
- **Auto-discovery:** the device listens on UDP (LOCAL_UDP_PORT) for the literal
  payload `hello` and replies `crosspoint (on <hostname>);<wsPort>`. So the
  dashboard finds the reader on the LAN with no hardcoded IP.
- **File listing:** `GET /api/files` (JSON), `GET /files` (HTML). WebDAV handler
  also present.
- Other endpoints: `/api/status`, `/download`, `/mkdir`, `/rename`, `/move`,
  `/delete`, `/api/settings`, `/api/wifi`, `/api/fonts/*`, `/api/opds/*`.

Dashboard flow: UDP-broadcast `hello` → parse reply for IP+wsPort → `POST /upload`
(or WS binary). This is a small standalone web/desktop app; no hardware
dependency. Build it after the reader boots.

---

## 7. Things NOT to do
- Do not touch `src/` UI/reader/activity code to accommodate the display.
- Do not port CrossPoint's UC81xx or SSD1677 raw driver code; GxEPD2 replaces it.
- Do not implement grayscale.
- Do not add firmware for the dashboard.
- Do not ask the user to re-explain hardware; it is all in §1.
- Do not relitigate the GxEPD2-shim decision; it is final.
