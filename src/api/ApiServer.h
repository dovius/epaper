/*****************************************************************************
 * ApiServer.h - HTTP API Server for remote display control
 * 
 * Provides REST API endpoints for controlling the e-paper display.
 * Designed for integration with NAS/Docker-based image generation.
 *****************************************************************************/
#ifndef API_SERVER_H
#define API_SERVER_H

#include <Arduino.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include "../config/Config.h"
#include "../display/Display.h"

namespace api {

/**
 * API Server class
 * Handles HTTP requests for display control
 */
class ApiServer {
public:
    ApiServer(uint16_t port = 80);
    ~ApiServer();

    /**
     * Initialize and start the server
     * @return true if successful
     */
    bool begin();

    /**
     * Stop the server
     */
    void stop();

    /**
     * Check if server is running
     */
    bool isRunning() const { return m_running; }

    /**
     * Get server port
     */
    uint16_t getPort() const { return m_port; }

private:
    AsyncWebServer* m_server;
    uint16_t m_port;
    bool m_running;
    uint32_t m_requestCount;

    // Setup route handlers
    void setupRoutes();

    // API Handlers
    void handleRoot(AsyncWebServerRequest* request);
    void handleStatus(AsyncWebServerRequest* request);
    void handleDisplayRaw(AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total);
    void handleDisplayClear(AsyncWebServerRequest* request);
    void handleDisplayText(AsyncWebServerRequest* request, JsonVariant& json);
    void handleDisplayRefresh(AsyncWebServerRequest* request);
    void handleNotFound(AsyncWebServerRequest* request);

    // Helpers
    void sendJsonResponse(AsyncWebServerRequest* request, int code, const char* status, const char* message = nullptr);
    void sendJsonError(AsyncWebServerRequest* request, int code, const char* error);
    String getUptimeString();
    static const char* getResetReason();
};

// Global server instance
extern ApiServer server;

}  // namespace api

#endif  // API_SERVER_H

