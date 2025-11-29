/*****************************************************************************
 * Canvas.h - High-level graphics abstraction
 * 
 * Provides clean interface for drawing on the e-paper display.
 * Manages framebuffer and provides drawing primitives.
 *****************************************************************************/
#ifndef CANVAS_H
#define CANVAS_H

#include <Arduino.h>
#include "../config/Config.h"

// Include font definitions
#include "../fonts.h"

namespace display {

/**
 * Text alignment options
 */
enum class TextAlign {
    LEFT,
    CENTER,
    RIGHT
};

/**
 * Display rotation
 */
enum class Rotation {
    ROTATE_0 = 0,
    ROTATE_90 = 90,
    ROTATE_180 = 180,
    ROTATE_270 = 270
};

/**
 * Color constants
 */
namespace Color {
    constexpr uint8_t BLACK = 0x00;
    constexpr uint8_t WHITE = 0xFF;
}

/**
 * Canvas class - manages framebuffer and drawing operations
 */
class Canvas {
public:
    Canvas();
    ~Canvas();

    /**
     * Initialize canvas with framebuffer
     * @param rotation Display rotation
     * @return true if successful
     */
    bool begin(Rotation rotation = Rotation::ROTATE_90);

    /**
     * Get raw framebuffer pointer (for direct manipulation or display)
     */
    uint8_t* getBuffer() { return m_buffer; }
    const uint8_t* getBuffer() const { return m_buffer; }

    /**
     * Get canvas dimensions (after rotation)
     */
    uint16_t width() const { return m_width; }
    uint16_t height() const { return m_height; }

    /**
     * Clear canvas
     * @param color Fill color (WHITE or BLACK)
     */
    void clear(uint8_t color = Color::WHITE);

    /**
     * Set a single pixel
     */
    void setPixel(int16_t x, int16_t y, uint8_t color);

    /**
     * Draw a line
     */
    void drawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, 
                  uint8_t color, uint8_t thickness = 1);

    /**
     * Draw rectangle (outline)
     */
    void drawRect(int16_t x, int16_t y, int16_t w, int16_t h, 
                  uint8_t color, uint8_t thickness = 1);

    /**
     * Draw filled rectangle
     */
    void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t color);

    /**
     * Draw circle (outline)
     */
    void drawCircle(int16_t cx, int16_t cy, int16_t r, 
                    uint8_t color, uint8_t thickness = 1);

    /**
     * Draw filled circle
     */
    void fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t color);

    /**
     * Draw text string
     * @param x X position
     * @param y Y position
     * @param text String to draw
     * @param font Font to use (Font8, Font12, Font16, Font20, Font24)
     * @param fg Foreground color
     * @param bg Background color
     */
    void drawText(int16_t x, int16_t y, const char* text, sFONT* font,
                  uint8_t fg = Color::BLACK, uint8_t bg = Color::WHITE);

    /**
     * Draw text with word wrapping
     * @param x X position
     * @param y Y position
     * @param text String to draw
     * @param maxWidth Maximum width before wrapping
     * @param font Font to use
     * @param fg Foreground color
     * @param bg Background color
     * @return Number of lines drawn
     */
    uint16_t drawTextWrapped(int16_t x, int16_t y, const char* text,
                             uint16_t maxWidth, sFONT* font,
                             uint8_t fg = Color::BLACK, uint8_t bg = Color::WHITE);

    /**
     * Draw centered text
     */
    void drawTextCentered(int16_t y, const char* text, sFONT* font,
                          uint8_t fg = Color::BLACK, uint8_t bg = Color::WHITE);

    /**
     * Draw a number
     */
    void drawNumber(int16_t x, int16_t y, int32_t number, sFONT* font,
                    uint8_t fg = Color::BLACK, uint8_t bg = Color::WHITE);

    /**
     * Draw raw bitmap
     * @param x X position
     * @param y Y position
     * @param bitmap Bitmap data
     * @param w Width of bitmap
     * @param h Height of bitmap
     */
    void drawBitmap(int16_t x, int16_t y, const uint8_t* bitmap, 
                    uint16_t w, uint16_t h);

    /**
     * Copy raw data directly to framebuffer
     * @param data Raw 1-bit bitmap data
     * @param length Data length (should be FRAME_BUFFER_SIZE)
     * @return true if successful
     */
    bool loadRawBitmap(const uint8_t* data, size_t length);

    /**
     * Draw horizontal line (optimized)
     */
    void drawHLine(int16_t x, int16_t y, int16_t w, uint8_t color);

    /**
     * Draw vertical line (optimized)
     */
    void drawVLine(int16_t x, int16_t y, int16_t h, uint8_t color);

    /**
     * Get text width in pixels
     */
    uint16_t getTextWidth(const char* text, sFONT* font);

private:
    uint8_t* m_buffer;
    uint16_t m_width;
    uint16_t m_height;
    uint16_t m_widthBytes;
    Rotation m_rotation;
    bool m_initialized;

    // Coordinate transformation
    void transformCoords(int16_t& x, int16_t& y);
    bool inBounds(int16_t x, int16_t y) const;
};

// Global canvas instance
extern Canvas canvas;

}  // namespace display

#endif  // CANVAS_H

