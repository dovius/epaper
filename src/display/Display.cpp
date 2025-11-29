/*****************************************************************************
 * Display.cpp - Unified display implementation
 *****************************************************************************/
#include "Display.h"

namespace display {

// Global instance
Display epd;

Display::Display()
    : m_initialized(false)
{
}

bool Display::begin(Rotation rotation) {
    LOGLN("[Display] Initializing...");

    // Initialize driver
    if (!m_driver.begin()) {
        LOGLN("[Display] Driver initialization failed");
        return false;
    }

    // Initialize canvas
    if (!m_canvas.begin(rotation)) {
        LOGLN("[Display] Canvas initialization failed");
        return false;
    }

    m_initialized = true;
    LOGLN("[Display] Initialization complete");
    return true;
}

void Display::update(RefreshMode mode) {
    if (!m_initialized) return;
    
    m_driver.display(m_canvas.getBuffer(), mode);
}

void Display::updateFast() {
    update(RefreshMode::FAST);
}

void Display::updatePartial() {
    update(RefreshMode::PARTIAL);
}

void Display::clear(bool white) {
    if (!m_initialized) return;
    
    m_canvas.clear(white ? Color::WHITE : Color::BLACK);
    m_driver.clear(white);
}

void Display::sleep() {
    if (m_initialized) {
        m_driver.sleep();
    }
}

void Display::wake() {
    if (m_initialized) {
        m_driver.wake();
    }
}

bool Display::displayRawBitmap(const uint8_t* data, size_t length, RefreshMode mode) {
    if (!m_initialized || !data) return false;
    
    if (length != config::FRAME_BUFFER_SIZE) {
        LOGF("[Display] Invalid bitmap size: %d\n", length);
        return false;
    }
    
    // Load into canvas (for consistency)
    m_canvas.loadRawBitmap(data, length);
    
    // Display
    m_driver.display(data, mode);
    
    return true;
}

}  // namespace display

