/*****************************************************************************
 * Config.h - Global configuration and pin definitions
 * 
 * Central place for all hardware and software configuration.
 *****************************************************************************/
#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include <stdint.h>

// ============================================================================
// Debug Configuration
// ============================================================================
#define DEBUG_ENABLED 1

#if DEBUG_ENABLED
    #define LOG(msg) Serial.print(msg)
    #define LOGLN(msg) Serial.println(msg)
    #define LOGF(fmt, ...) Serial.printf(fmt, ##__VA_ARGS__)
#else
    #define LOG(msg)
    #define LOGLN(msg)
    #define LOGF(fmt, ...)
#endif

// ============================================================================
// Display Hardware Configuration
// ============================================================================
namespace config {

// E-Paper display resolution (Waveshare 2.13" V4)
constexpr uint16_t DISPLAY_WIDTH = 122;
constexpr uint16_t DISPLAY_HEIGHT = 250;
constexpr uint16_t DISPLAY_WIDTH_BYTES = (DISPLAY_WIDTH + 7) / 8;  // 16 bytes per row
constexpr uint32_t FRAME_BUFFER_SIZE = DISPLAY_WIDTH_BYTES * DISPLAY_HEIGHT;  // 4000 bytes

// SPI Pin Configuration (ESP32)
namespace pins {
    constexpr int8_t SPI_SCK  = 13;   // SPI Clock
    constexpr int8_t SPI_MOSI = 14;   // SPI Master Out Slave In
    constexpr int8_t SPI_CS   = 15;   // Chip Select
    constexpr int8_t EPD_RST  = 26;   // Reset
    constexpr int8_t EPD_DC   = 27;   // Data/Command
    constexpr int8_t EPD_BUSY = 25;   // Busy signal
}

// SPI Configuration
constexpr uint32_t SPI_FREQUENCY = 4000000;  // 4 MHz (max for e-paper)

// Timing Configuration
namespace timing {
    constexpr uint32_t BUSY_TIMEOUT_MS = 10000;      // 10 seconds busy timeout
    constexpr uint32_t BUSY_POLL_INTERVAL_MS = 10;   // Poll every 10ms
    constexpr uint32_t RESET_PULSE_MS = 10;          // Reset pulse duration
    constexpr uint32_t POST_RESET_DELAY_MS = 10;     // Delay after reset
}

// Default refresh interval
constexpr uint32_t DEFAULT_REFRESH_INTERVAL_MS = 300000;  // 5 minutes

}  // namespace config

// ============================================================================
// Type Definitions (legacy compatibility)
// ============================================================================
using UBYTE = uint8_t;
using UWORD = uint16_t;
using UDOUBLE = uint32_t;

#endif  // CONFIG_H

