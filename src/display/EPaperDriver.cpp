/*****************************************************************************
 * EPaperDriver.cpp - Low-level e-paper display driver implementation
 * 
 * Uses ESP32 hardware SPI for fast, efficient communication.
 *****************************************************************************/
#include "EPaperDriver.h"

namespace display {

// Global instance
EPaperDriver Driver;

EPaperDriver::EPaperDriver() 
    : m_spi(nullptr)
    , m_initialized(false)
{
}

EPaperDriver::~EPaperDriver() {
    if (m_spi) {
        m_spi->end();
    }
}

bool EPaperDriver::begin() {
    // Configure control pins
    pinMode(config::pins::EPD_RST, OUTPUT);
    pinMode(config::pins::EPD_DC, OUTPUT);
    pinMode(config::pins::SPI_CS, OUTPUT);
    pinMode(config::pins::EPD_BUSY, INPUT);

    // Set default states
    digitalWrite(config::pins::SPI_CS, HIGH);
    digitalWrite(config::pins::EPD_RST, HIGH);
    digitalWrite(config::pins::EPD_DC, HIGH);

    // Initialize hardware SPI
    m_spi = new SPIClass(VSPI);
    m_spi->begin(config::pins::SPI_SCK, -1, config::pins::SPI_MOSI, config::pins::SPI_CS);  // SCK, MISO (unused), MOSI, SS

    LOGLN("[EPD] Hardware SPI initialized");

    // Hardware reset and initialize
    hardwareReset();
    
    if (!waitUntilReady(5000)) {
        LOGLN("[EPD] Display not responding after reset");
        return false;
    }

    m_initialized = true;
    LOGLN("[EPD] Driver initialized successfully");
    return true;
}

void EPaperDriver::hardwareReset() {
    using namespace config::pins;
    using namespace config::timing;

    digitalWrite(EPD_RST, HIGH);
    delay(POST_RESET_DELAY_MS);
    digitalWrite(EPD_RST, LOW);
    delay(RESET_PULSE_MS);
    digitalWrite(EPD_RST, HIGH);
    delay(POST_RESET_DELAY_MS);
}

void EPaperDriver::sendCommand(uint8_t cmd) {
    digitalWrite(config::pins::EPD_DC, LOW);
    digitalWrite(config::pins::SPI_CS, LOW);
    
    m_spi->beginTransaction(SPISettings(config::SPI_FREQUENCY, MSBFIRST, SPI_MODE0));
    m_spi->transfer(cmd);
    m_spi->endTransaction();
    
    digitalWrite(config::pins::SPI_CS, HIGH);
}

void EPaperDriver::sendData(uint8_t data) {
    digitalWrite(config::pins::EPD_DC, HIGH);
    digitalWrite(config::pins::SPI_CS, LOW);
    
    m_spi->beginTransaction(SPISettings(config::SPI_FREQUENCY, MSBFIRST, SPI_MODE0));
    m_spi->transfer(data);
    m_spi->endTransaction();
    
    digitalWrite(config::pins::SPI_CS, HIGH);
}

void EPaperDriver::sendDataBuffer(const uint8_t* data, size_t length) {
    if (!data || length == 0) return;

    digitalWrite(config::pins::EPD_DC, HIGH);
    digitalWrite(config::pins::SPI_CS, LOW);
    
    m_spi->beginTransaction(SPISettings(config::SPI_FREQUENCY, MSBFIRST, SPI_MODE0));
    m_spi->writeBytes(data, length);
    m_spi->endTransaction();
    
    digitalWrite(config::pins::SPI_CS, HIGH);
}

bool EPaperDriver::isBusy() const {
    return digitalRead(config::pins::EPD_BUSY) == HIGH;
}

bool EPaperDriver::waitUntilReady(uint32_t timeoutMs) {
    uint32_t start = millis();
    
    while (isBusy()) {
        delay(config::timing::BUSY_POLL_INTERVAL_MS);
        
        if (millis() - start >= timeoutMs) {
            LOGLN("[EPD] Busy timeout!");
            return false;
        }
    }
    
    delay(10);  // Small delay after busy release
    return true;
}

void EPaperDriver::setWindow(uint16_t xStart, uint16_t yStart, uint16_t xEnd, uint16_t yEnd) {
    // Set RAM X address (0x44)
    sendCommand(0x44);
    sendData((xStart >> 3) & 0xFF);
    sendData((xEnd >> 3) & 0xFF);

    // Set RAM Y address (0x45)
    sendCommand(0x45);
    sendData(yStart & 0xFF);
    sendData((yStart >> 8) & 0xFF);
    sendData(yEnd & 0xFF);
    sendData((yEnd >> 8) & 0xFF);
}

void EPaperDriver::setCursor(uint16_t x, uint16_t y) {
    sendCommand(0x4E);
    sendData(x & 0xFF);

    sendCommand(0x4F);
    sendData(y & 0xFF);
    sendData((y >> 8) & 0xFF);
}

void EPaperDriver::setFullWindow() {
    setWindow(0, 0, config::DISPLAY_WIDTH - 1, config::DISPLAY_HEIGHT - 1);
    setCursor(0, 0);
}

void EPaperDriver::triggerUpdate(uint8_t control) {
    sendCommand(0x22);
    sendData(control);
    sendCommand(0x20);
    waitUntilReady();
}

void EPaperDriver::writeImageToRAM(uint8_t cmd, const uint8_t* image) {
    if (!image) return;
    
    sendCommand(cmd);
    sendDataBuffer(image, config::FRAME_BUFFER_SIZE);
}

void EPaperDriver::fillRAM(uint8_t cmd, uint8_t value) {
    sendCommand(cmd);
    
    digitalWrite(config::pins::EPD_DC, HIGH);
    digitalWrite(config::pins::SPI_CS, LOW);
    
    m_spi->beginTransaction(SPISettings(config::SPI_FREQUENCY, MSBFIRST, SPI_MODE0));
    for (uint32_t i = 0; i < config::FRAME_BUFFER_SIZE; ++i) {
        m_spi->transfer(value);
    }
    m_spi->endTransaction();
    
    digitalWrite(config::pins::SPI_CS, HIGH);
}

// ============================================================================
// Public API
// ============================================================================

void EPaperDriver::initFull() {
    hardwareReset();
    waitUntilReady();

    sendCommand(0x12);  // Software reset
    waitUntilReady();

    // Driver output control
    sendCommand(0x01);
    sendData(0xF9);
    sendData(0x00);
    sendData(0x00);

    // Data entry mode
    sendCommand(0x11);
    sendData(0x03);

    setFullWindow();

    // Border waveform control
    sendCommand(0x3C);
    sendData(0x05);

    // Display update control
    sendCommand(0x21);
    sendData(0x00);
    sendData(0x80);

    // Temperature sensor control
    sendCommand(0x18);
    sendData(0x80);

    waitUntilReady();
    LOGLN("[EPD] Initialized for full refresh");
}

void EPaperDriver::initFast() {
    hardwareReset();

    sendCommand(0x12);  // Software reset
    waitUntilReady();

    // Temperature sensor control
    sendCommand(0x18);
    sendData(0x80);

    // Data entry mode
    sendCommand(0x11);
    sendData(0x03);

    setFullWindow();

    // Load temperature
    triggerUpdate(0xB1);

    // Temperature register
    sendCommand(0x1A);
    sendData(0x64);
    sendData(0x00);

    // Apply temperature
    triggerUpdate(0x91);

    LOGLN("[EPD] Initialized for fast refresh");
}

void EPaperDriver::initPartial() {
    initFull();
    
    // Border control for partial
    sendCommand(0x3C);
    sendData(0x80);
    
    LOGLN("[EPD] Initialized for partial refresh");
}

void EPaperDriver::display(const uint8_t* buffer, RefreshMode mode) {
    if (!buffer) return;

    switch (mode) {
        case RefreshMode::FAST:
            initFast();
            writeImageToRAM(0x24, buffer);
            triggerUpdate(0xC7);
            break;
            
        case RefreshMode::PARTIAL:
            hardwareReset();
            
            sendCommand(0x3C);
            sendData(0x80);
            
            sendCommand(0x01);
            sendData(0xF9);
            sendData(0x00);
            sendData(0x00);
            
            sendCommand(0x11);
            sendData(0x03);
            
            setFullWindow();
            writeImageToRAM(0x24, buffer);
            triggerUpdate(0xFF);
            break;
            
        case RefreshMode::FULL:
        default:
            initFull();
            writeImageToRAM(0x24, buffer);
            triggerUpdate(0xF7);
            break;
    }

    // Waveshare: don't leave the panel powered between refreshes. Every
    // refresh starts with a hardware reset, which wakes it up again.
    sleep();
}

void EPaperDriver::displayBase(const uint8_t* buffer) {
    if (!buffer) return;
    
    initFull();
    writeImageToRAM(0x24, buffer);
    writeImageToRAM(0x26, buffer);
    triggerUpdate(0xF7);
    sleep();
}

void EPaperDriver::clear(bool white) {
    initFull();
    fillRAM(0x24, white ? 0xFF : 0x00);
    triggerUpdate(0xF7);
    sleep();
    LOGLN(white ? "[EPD] Cleared to white" : "[EPD] Cleared to black");
}

void EPaperDriver::sleep() {
    sendCommand(0x10);
    sendData(0x01);
    delay(100);
    LOGLN("[EPD] Entered deep sleep");
}

void EPaperDriver::wake() {
    hardwareReset();
    waitUntilReady();
    LOGLN("[EPD] Woke from sleep");
}

}  // namespace display

