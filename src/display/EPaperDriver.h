/*****************************************************************************
 * EPaperDriver.h - Low-level e-paper display driver
 * 
 * Hardware abstraction for Waveshare 2.13" V4 e-paper display.
 * Uses hardware SPI for fast communication.
 *****************************************************************************/
#ifndef EPAPER_DRIVER_H
#define EPAPER_DRIVER_H

#include <Arduino.h>
#include <SPI.h>
#include "../config/Config.h"

namespace display {

/**
 * E-Paper display refresh mode
 */
enum class RefreshMode {
    FULL,       // Full refresh (slower, no ghosting)
    FAST,       // Fast refresh (faster, possible ghosting)
    PARTIAL     // Partial refresh (fastest, for small updates)
};

/**
 * Low-level e-paper driver class
 * Handles SPI communication and display commands
 */
class EPaperDriver {
public:
    EPaperDriver();
    ~EPaperDriver();

    /**
     * Initialize the display hardware
     * @return true if successful
     */
    bool begin();

    /**
     * Initialize for specific refresh mode
     */
    void initFull();
    void initFast();
    void initPartial();

    /**
     * Display framebuffer contents
     * @param buffer Pointer to framebuffer (4000 bytes)
     * @param mode Refresh mode to use
     */
    void display(const uint8_t* buffer, RefreshMode mode = RefreshMode::FULL);

    /**
     * Display with base layer (for partial updates)
     * @param buffer Pointer to framebuffer
     */
    void displayBase(const uint8_t* buffer);

    /**
     * Clear the display
     * @param white If true, clear to white; otherwise black
     */
    void clear(bool white = true);

    /**
     * Put display into deep sleep mode
     */
    void sleep();

    /**
     * Wake display from sleep
     */
    void wake();

    /**
     * Check if display is busy
     * @return true if busy
     */
    bool isBusy() const;

    /**
     * Wait for display to become ready
     * @param timeoutMs Timeout in milliseconds
     * @return true if ready, false if timeout
     */
    bool waitUntilReady(uint32_t timeoutMs = config::timing::BUSY_TIMEOUT_MS);

private:
    SPIClass* m_spi;
    bool m_initialized;

    // Hardware control
    void hardwareReset();
    void sendCommand(uint8_t cmd);
    void sendData(uint8_t data);
    void sendDataBuffer(const uint8_t* data, size_t length);
    
    // Display configuration
    void setWindow(uint16_t xStart, uint16_t yStart, uint16_t xEnd, uint16_t yEnd);
    void setCursor(uint16_t x, uint16_t y);
    void setFullWindow();
    
    // RAM operations
    void writeImageToRAM(uint8_t cmd, const uint8_t* image);
    void fillRAM(uint8_t cmd, uint8_t value);
    
    // Update trigger
    void triggerUpdate(uint8_t control);
};

// Global driver instance
extern EPaperDriver Driver;

}  // namespace display

#endif  // EPAPER_DRIVER_H

