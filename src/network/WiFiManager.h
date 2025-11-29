/*****************************************************************************
 * WiFiManager.h - WiFi connection management
 * 
 * Handles WiFi connection, reconnection, and status.
 *****************************************************************************/
#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include "../config/Config.h"

namespace network {

/**
 * WiFi connection states
 */
enum class WiFiState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    CONNECTION_FAILED
};

/**
 * WiFi connection manager
 */
class WiFiManager {
public:
    WiFiManager();

    /**
     * Initialize WiFi with credentials
     * @param ssid Network SSID
     * @param password Network password
     */
    void begin(const char* ssid, const char* password);

    /**
     * Attempt to connect to WiFi
     * @param timeoutMs Connection timeout
     * @return true if connected
     */
    bool connect(uint32_t timeoutMs = 20000);

    /**
     * Disconnect from WiFi
     */
    void disconnect();

    /**
     * Check and maintain connection
     * Call this in loop() for auto-reconnect
     */
    void loop();

    /**
     * Get current connection state
     */
    WiFiState getState() const { return m_state; }

    /**
     * Check if connected
     */
    bool isConnected() const { return WiFi.status() == WL_CONNECTED; }

    /**
     * Get IP address as string
     */
    String getIPAddress() const;

    /**
     * Get RSSI (signal strength)
     */
    int32_t getRSSI() const { return WiFi.RSSI(); }

    /**
     * Get MAC address
     */
    String getMACAddress() const { return WiFi.macAddress(); }

    /**
     * Get hostname
     */
    String getHostname() const { return WiFi.getHostname(); }

    /**
     * Set hostname
     */
    void setHostname(const char* hostname);

    /**
     * Enable/disable auto-reconnect
     */
    void setAutoReconnect(bool enable) { m_autoReconnect = enable; }

private:
    const char* m_ssid;
    const char* m_password;
    WiFiState m_state;
    bool m_autoReconnect;
    uint32_t m_lastReconnectAttempt;
    static constexpr uint32_t RECONNECT_INTERVAL_MS = 30000;
};

// Global instance
extern WiFiManager wifi;

}  // namespace network

#endif  // WIFI_MANAGER_H

