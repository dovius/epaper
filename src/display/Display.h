/*****************************************************************************
 * Display.h - Unified display interface
 * 
 * Combines EPaperDriver and Canvas for easy display management.
 *****************************************************************************/
#ifndef DISPLAY_H
#define DISPLAY_H

#include "EPaperDriver.h"
#include "Canvas.h"

namespace display {

/**
 * High-level display manager
 * Provides unified interface for drawing and displaying
 */
class Display {
public:
    Display();

    /**
     * Initialize display hardware and canvas
     * @param rotation Display rotation
     * @return true if successful
     */
    bool begin(Rotation rotation = Rotation::ROTATE_90);

    /**
     * Get canvas reference for drawing
     */
    Canvas& getCanvas() { return m_canvas; }

    /**
     * Get driver reference for low-level control
     */
    EPaperDriver& getDriver() { return m_driver; }

    /**
     * Update display with current canvas contents
     * @param mode Refresh mode
     */
    void update(RefreshMode mode = RefreshMode::FULL);

    /**
     * Quick update (fast refresh)
     */
    void updateFast();

    /**
     * Partial update (fastest, may have ghosting)
     */
    void updatePartial();

    /**
     * Clear display and canvas
     * @param white Clear to white if true
     */
    void clear(bool white = true);

    /**
     * Put display to sleep
     */
    void sleep();

    /**
     * Wake display from sleep
     */
    void wake();

    /**
     * Display raw bitmap data directly
     * @param data Bitmap data
     * @param length Data length
     * @param mode Refresh mode
     * @return true if successful
     */
    bool displayRawBitmap(const uint8_t* data, size_t length, 
                          RefreshMode mode = RefreshMode::FULL);

    // Convenience accessors
    uint16_t width() const { return m_canvas.width(); }
    uint16_t height() const { return m_canvas.height(); }
    bool isReady() const { return m_initialized; }

private:
    EPaperDriver m_driver;
    Canvas m_canvas;
    bool m_initialized;
};

// Global display instance
extern Display epd;

}  // namespace display

#endif  // DISPLAY_H

