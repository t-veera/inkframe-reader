#pragma once
// INKFRAME V2 hardware pin map (KiCad schematic — authoritative).
// Included only when INKFRAME_HW is defined.

// EPD (GDEQ0583T31 / UC8179) — SPI 4-wire
#define INKFRAME_EPD_PWR   6   // Drive HIGH before panel init (PWR quirk)
#define INKFRAME_EPD_BUSY  7
#define INKFRAME_EPD_RST   8
#define INKFRAME_EPD_DC    9
#define INKFRAME_EPD_CS   10
#define INKFRAME_EPD_MOSI 13   // Shared SPI MOSI (= SD MOSI)
#define INKFRAME_EPD_SCK  47   // Shared SPI SCK  (= SD SCK)

// SD card — shares SPI bus with EPD
#define INKFRAME_SD_CS    48
#define INKFRAME_SD_MISO  21   // Shared SPI MISO

// 5-way nav switch (active-low, INPUT_PULLUP)
#define INKFRAME_BTN_UP      1   // previous page
#define INKFRAME_BTN_DOWN    2   // next page
#define INKFRAME_BTN_LEFT    4   // back
#define INKFRAME_BTN_RIGHT   5   // menu
#define INKFRAME_BTN_CENTER 17   // select / OK
#define INKFRAME_BTN_POWER   0   // power / wake (strapping pin — input only)

// Power / system
// NOTE (Phase 2): CrossPoint's HalPowerManager uses BAT_GPIO0 (currently = 0,
// the power-button strapping pin) for ADC battery reads. On INKFRAME the
// battery ADC is GPIO15. Remap BAT_GPIO0 → INKFRAME_BAT_ADC in HalGPIO.h
// when wiring battery monitoring in Phase 2.
#define INKFRAME_BAT_ADC  15   // voltage = raw/4095*3.3*2.0; % = (V-3.0)/1.2*100
#define INKFRAME_CHRG     38   // TP4056 charge status (LOW = charging)
#define INKFRAME_STDBY    39   // TP4056 standby     (LOW = done)
#define INKFRAME_BOOST_EN 45   // MT3608 boost (HIGH = battery, LOW = USB)
