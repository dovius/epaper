/*****************************************************************************
 * E-Paper Display Controller
 * 
 * Remote-controlled e-paper display system for ESP32.
 * Controlled via HTTP API from NAS/Docker.
 * 
 * API Endpoints:
 *   GET  /              - Web UI
 *   GET  /api/status    - Device status (JSON)
 *   POST /api/display/raw     - Upload raw 1-bit bitmap
 *   POST /api/display/clear   - Clear display
 *   POST /api/display/text    - Draw text (JSON body)
 *   POST /api/display/refresh - Force display refresh
 *****************************************************************************/

#include <Arduino.h>
#include "config/Config.h"
#include "config/Secrets.h"
#include "display/Display.h"
#include "network/WiFiManager.h"
#include "api/ApiServer.h"

// Font declarations
extern sFONT Font8;
extern sFONT Font12;
extern sFONT Font16;
extern sFONT Font20;
extern sFONT Font24;

namespace app {

// ============================================================================
// Status screens
// ============================================================================

void showBootScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "E-Paper Controller", &Font16, 
                    display::Color::WHITE, display::Color::BLACK);
    canvas.drawText(10, 40, "Initializing...", &Font12);
    
    display::epd.updateFast();
}

void showConnectingScreen() {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, "E-Paper Controller", &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    canvas.drawText(10, 40, "Connecting to WiFi...", &Font12);
    canvas.drawText(10, 58, secrets::WIFI_SSID, &Font12);
    
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
    char buf[64];
    
    snprintf(buf, sizeof(buf), "IP: %s", ip.c_str());
    canvas.drawText(10, 34, buf, &Font12);
    
    snprintf(buf, sizeof(buf), "Signal: %d dBm", network::wifi.getRSSI());
    canvas.drawText(10, 50, buf, &Font12);
    
    // Separator
    canvas.drawLine(0, 68, canvas.width(), 68, display::Color::BLACK);
    
    // API info
    canvas.drawText(10, 76, "API Endpoints:", &Font12);
    
    snprintf(buf, sizeof(buf), "http://%s/", ip.c_str());
    canvas.drawText(10, 94, buf, &Font8);
    
    canvas.drawText(10, 108, "POST /api/display/raw", &Font8);
    canvas.drawText(10, 120, "POST /api/display/clear", &Font8);
    canvas.drawText(10, 132, "POST /api/display/text", &Font8);
    canvas.drawText(10, 144, "GET  /api/status", &Font8);
    
    display::epd.update();
}

void showErrorScreen(const char* title, const char* error) {
    auto& canvas = display::epd.getCanvas();
    
    canvas.clear();
    canvas.fillRect(0, 0, canvas.width(), 26, display::Color::BLACK);
    canvas.drawText(6, 5, title, &Font16,
                    display::Color::WHITE, display::Color::BLACK);
    canvas.drawTextWrapped(10, 40, error, canvas.width() - 20, &Font12);
    
    display::epd.updateFast();
}

}  // namespace app

// ============================================================================
// Arduino Entry Points
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    LOGLN("\n========================================");
    LOGLN("   E-Paper Display Controller v2.0");
    LOGLN("========================================\n");

    // Initialize display
    LOGLN("[Main] Initializing display...");
    if (!display::epd.begin()) {
        LOGLN("[Main] FATAL: Display init failed!");
        while (true) delay(1000);
    }
    
    app::showBootScreen();
    delay(500);

    // Initialize WiFi
    LOGLN("[Main] Connecting to WiFi...");
    network::wifi.setHostname(secrets::MDNS_HOSTNAME);
    network::wifi.begin(secrets::WIFI_SSID, secrets::WIFI_PASSWORD);
    
    app::showConnectingScreen();
    
    if (!network::wifi.connect(30000)) {
        LOGLN("[Main] WiFi connection failed!");
        app::showErrorScreen("WiFi Error", "Could not connect to WiFi. Check credentials and restart.");
        // Continue anyway - will retry in loop
    }

    // Start API server
    if (network::wifi.isConnected()) {
        LOGLN("[Main] Starting API server...");
        if (!api::server.begin()) {
            LOGLN("[Main] API server failed to start!");
            app::showErrorScreen("API Error", "Failed to start HTTP server.");
        } else {
            app::showReadyScreen();
            LOGF("[Main] Ready! Access at: http://%s/\n", network::wifi.getIPAddress().c_str());
        }
    }
    
    LOGLN("[Main] Setup complete!");
}

void loop() {
    // Maintain WiFi connection
    network::wifi.loop();
    
    // Restart API server if WiFi reconnects
    static bool wasConnected = false;
    bool isConnected = network::wifi.isConnected();
    
    if (isConnected && !wasConnected) {
        LOGLN("[Main] WiFi reconnected, restarting API server...");
        api::server.begin();
        app::showReadyScreen();
    }
    wasConnected = isConnected;
    
    delay(10);
}
