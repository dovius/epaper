/*****************************************************************************
 * E-Paper Display Controller
 * 
 * Modular e-paper display system for ESP32.
 * Designed for remote control via API from NAS/Docker.
 * 
 * Architecture:
 * - display/  : E-paper driver, canvas, display manager
 * - network/  : WiFi management
 * - config/   : Configuration and secrets
 *****************************************************************************/

#include <Arduino.h>
#include "config/Config.h"
#include "config/Secrets.h"
#include "display/Display.h"
#include "network/WiFiManager.h"

// For fonts
extern sFONT Font8;
extern sFONT Font12;
extern sFONT Font16;
extern sFONT Font20;
extern sFONT Font24;

namespace app {

// ============================================================================
// Demo/Test functions (will be replaced by API handlers in Phase 2)
// ============================================================================

void showBootScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    
    // Header bar
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "E-Paper Controller", &Font16, 
                    display::Color::WHITE, display::Color::BLACK);
    
    // Status info
    canvas.drawText(10, 40, "Initializing...", &Font12);
    
    display::epd.updateFast();
}

void showConnectingScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    
    // Header
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "E-Paper Controller", &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    
    // Connection status
    canvas.drawText(10, 40, "Connecting to WiFi...", &Font12);
    canvas.drawText(10, 60, secrets::WIFI_SSID, &Font12);
    
    display::epd.updateFast();
}

void showReadyScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    
    // Header
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "Ready", &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    
    // Connection info
    String ip = network::wifi.getIPAddress();
    char ipBuf[32];
    snprintf(ipBuf, sizeof(ipBuf), "IP: %s", ip.c_str());
    
    canvas.drawText(10, 36, ipBuf, &Font12);
    
    char rssi[32];
    snprintf(rssi, sizeof(rssi), "Signal: %d dBm", network::wifi.getRSSI());
    canvas.drawText(10, 52, rssi, &Font12);
    
    // Instructions
    canvas.drawLine(0, 70, canvas.width(), 70, display::Color::BLACK);
    canvas.drawText(10, 78, "API Endpoints:", &Font12);
    canvas.drawText(10, 94, "POST /api/display/raw", &Font8);
    canvas.drawText(10, 106, "POST /api/display/clear", &Font8);
    canvas.drawText(10, 118, "GET  /api/status", &Font8);
    
    display::epd.update();
}

void showErrorScreen(const char* error) {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    
    // Header - red (inverted)
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "ERROR", &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    
    // Error message
    canvas.drawTextWrapped(10, 40, error, canvas.width() - 20, &Font12);
    
    display::epd.updateFast();
}

void showDemoScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    
    // Header
    canvas.fillRect(0, 0, canvas.width(), 24, display::Color::BLACK);
    canvas.drawText(6, 4, "Demo Mode", &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    
    // Draw some shapes
    canvas.drawRect(10, 35, 60, 40, display::Color::BLACK, 2);
    canvas.fillRect(80, 35, 60, 40, display::Color::BLACK);
    canvas.drawCircle(180, 55, 20, display::Color::BLACK, 2);
    canvas.fillCircle(220, 55, 15, display::Color::BLACK);
    
    // Draw lines
    canvas.drawLine(10, 85, 240, 85, display::Color::BLACK);
    canvas.drawLine(10, 87, 240, 87, display::Color::BLACK);
    
    // Draw text samples
    canvas.drawText(10, 95, "Font8 Sample Text", &Font8);
    canvas.drawText(10, 108, "Font12 Sample", &Font12);
    canvas.drawText(10, 124, "Font16", &Font16);
    
    display::epd.update();
}

}  // namespace app

// ============================================================================
// Arduino Entry Points
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    LOGLN("\n========================================");
    LOGLN("   E-Paper Display Controller v1.0");
    LOGLN("========================================\n");

    // Initialize display
    LOGLN("[Main] Initializing display...");
    if (!display::epd.begin()) {
        LOGLN("[Main] Display initialization failed!");
        while (1) { delay(1000); }
    }
    
    app::showBootScreen();
    delay(1000);

    // Initialize WiFi
    LOGLN("[Main] Initializing WiFi...");
    network::wifi.setHostname(secrets::MDNS_HOSTNAME);
    network::wifi.begin(secrets::WIFI_SSID, secrets::WIFI_PASSWORD);
    
    app::showConnectingScreen();
    
    if (network::wifi.connect()) {
        LOGLN("[Main] WiFi connected successfully");
        app::showReadyScreen();
    } else {
        LOGLN("[Main] WiFi connection failed, continuing in offline mode");
        app::showErrorScreen("WiFi connection failed.\nRunning in offline mode.");
    }
    
    delay(3000);
    
    // Show demo screen
    app::showDemoScreen();
    
    LOGLN("[Main] Setup complete!");
    LOGLN("[Main] Ready for API commands (Phase 2)");
}

void loop() {
    // Maintain WiFi connection
    network::wifi.loop();
    
    // TODO: Phase 2 - Add API server handling here
    // server.handleClient();
    
    delay(100);
}
