/*****************************************************************************
 * WiFiManager.cpp - WiFi connection management implementation
 *****************************************************************************/
#include "WiFiManager.h"

namespace network {

// Global instance
WiFiManager wifi;

WiFiManager::WiFiManager()
    : m_ssid(nullptr)
    , m_password(nullptr)
    , m_state(WiFiState::DISCONNECTED)
    , m_autoReconnect(true)
    , m_lastReconnectAttempt(0)
{
}

void WiFiManager::begin(const char* ssid, const char* password) {
    m_ssid = ssid;
    m_password = password;
    
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    
    LOGF("[WiFi] Configured for SSID: %s\n", ssid);
}

bool WiFiManager::connect(uint32_t timeoutMs) {
    if (!m_ssid || !m_password) {
        LOGLN("[WiFi] No credentials configured");
        m_state = WiFiState::CONNECTION_FAILED;
        return false;
    }

    if (isConnected()) {
        LOGLN("[WiFi] Already connected");
        m_state = WiFiState::CONNECTED;
        return true;
    }

    LOGF("[WiFi] Connecting to %s...\n", m_ssid);
    m_state = WiFiState::CONNECTING;

    WiFi.begin(m_ssid, m_password);

    uint32_t start = millis();
    while (!isConnected() && (millis() - start) < timeoutMs) {
        delay(500);
        LOG(".");
    }
    LOGLN();

    if (isConnected()) {
        m_state = WiFiState::CONNECTED;
        LOGF("[WiFi] Connected! IP: %s\n", getIPAddress().c_str());
        LOGF("[WiFi] Signal strength: %d dBm\n", getRSSI());
        return true;
    }

    m_state = WiFiState::CONNECTION_FAILED;
    LOGLN("[WiFi] Connection failed");
    return false;
}

void WiFiManager::disconnect() {
    WiFi.disconnect(true);
    m_state = WiFiState::DISCONNECTED;
    LOGLN("[WiFi] Disconnected");
}

void WiFiManager::loop() {
    if (!m_autoReconnect) return;

    // Check if we need to reconnect
    if (!isConnected() && m_ssid && m_password) {
        uint32_t now = millis();
        if (now - m_lastReconnectAttempt >= RECONNECT_INTERVAL_MS) {
            m_lastReconnectAttempt = now;
            LOGLN("[WiFi] Auto-reconnecting...");
            connect(10000);
        }
    } else if (isConnected() && m_state != WiFiState::CONNECTED) {
        m_state = WiFiState::CONNECTED;
    }
}

String WiFiManager::getIPAddress() const {
    if (isConnected()) {
        return WiFi.localIP().toString();
    }
    return "0.0.0.0";
}

void WiFiManager::setHostname(const char* hostname) {
    WiFi.setHostname(hostname);
    LOGF("[WiFi] Hostname set to: %s\n", hostname);
}

}  // namespace network

