/*****************************************************************************
 * ApiServer.cpp - HTTP API Server implementation
 *****************************************************************************/
#include "ApiServer.h"
#include <AsyncJson.h>
#include <esp_system.h>
#include <esp_timer.h>
#include "../network/WiFiManager.h"

namespace api {

// Global instance
ApiServer server;

// Buffer for receiving raw image data
static uint8_t* s_imageBuffer = nullptr;
static size_t s_imageBufferSize = 0;
static bool s_imageComplete = false;

ApiServer::ApiServer(uint16_t port)
    : m_server(nullptr)
    , m_port(port)
    , m_running(false)
    , m_requestCount(0)
{
}

ApiServer::~ApiServer() {
    stop();
    if (s_imageBuffer) {
        free(s_imageBuffer);
        s_imageBuffer = nullptr;
    }
}

bool ApiServer::begin() {
    if (m_running) {
        LOGLN("[API] Server already running");
        return true;
    }

    // Allocate image receive buffer
    if (!s_imageBuffer) {
        s_imageBuffer = static_cast<uint8_t*>(malloc(config::FRAME_BUFFER_SIZE));
        if (!s_imageBuffer) {
            LOGLN("[API] Failed to allocate image buffer");
            return false;
        }
    }

    // Create server
    m_server = new AsyncWebServer(m_port);
    if (!m_server) {
        LOGLN("[API] Failed to create server");
        return false;
    }

    setupRoutes();
    m_server->begin();
    m_running = true;

    LOGF("[API] Server started on port %d\n", m_port);
    LOGF("[API] Endpoints:\n");
    LOGF("  GET  /              - Web UI\n");
    LOGF("  GET  /api/status    - Device status\n");
    LOGF("  POST /api/display/raw     - Upload raw bitmap\n");
    LOGF("  POST /api/display/clear   - Clear display\n");
    LOGF("  POST /api/display/text    - Draw text\n");
    LOGF("  POST /api/display/refresh - Force refresh\n");

    return true;
}

void ApiServer::stop() {
    if (m_server) {
        m_server->end();
        delete m_server;
        m_server = nullptr;
    }
    m_running = false;
    LOGLN("[API] Server stopped");
}

void ApiServer::setupRoutes() {
    // Root - simple web UI
    m_server->on("/", HTTP_GET, [this](AsyncWebServerRequest* request) {
        handleRoot(request);
    });

    // Status endpoint
    m_server->on("/api/status", HTTP_GET, [this](AsyncWebServerRequest* request) {
        handleStatus(request);
    });

    // Clear display
    m_server->on("/api/display/clear", HTTP_POST, [this](AsyncWebServerRequest* request) {
        handleDisplayClear(request);
    });

    // Force refresh
    m_server->on("/api/display/refresh", HTTP_POST, [this](AsyncWebServerRequest* request) {
        handleDisplayRefresh(request);
    });

    // Raw bitmap upload
    m_server->on("/api/display/raw", HTTP_POST,
        // Request complete handler
        [this](AsyncWebServerRequest* request) {
            m_requestCount++;
            if (s_imageComplete && s_imageBufferSize == config::FRAME_BUFFER_SIZE) {
                // Display the received image
                display::epd.displayRawBitmap(s_imageBuffer, s_imageBufferSize);
                sendJsonResponse(request, 200, "ok", "Image displayed");
                LOGLN("[API] Raw image displayed");
            } else {
                char msg[64];
                snprintf(msg, sizeof(msg), "Invalid size: received %u, expected %u",
                         static_cast<unsigned>(request->contentLength()),
                         static_cast<unsigned>(config::FRAME_BUFFER_SIZE));
                sendJsonError(request, 400, msg);
                LOGF("[API] Raw image error: %s\n", msg);
            }
            s_imageBufferSize = 0;
            s_imageComplete = false;
        },
        // Upload handler (not used for raw body)
        nullptr,
        // Body handler
        [this](AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
            handleDisplayRaw(request, data, len, index, total);
        }
    );

    // Text display (JSON body). The JSON handler buffers bodies split across
    // several TCP packets and answers 400 itself for an empty or invalid body.
    auto* textHandler = new AsyncCallbackJsonWebHandler("/api/display/text",
        [this](AsyncWebServerRequest* request, JsonVariant& json) {
            handleDisplayText(request, json);
        }
    );
    textHandler->setMethod(HTTP_POST);
    m_server->addHandler(textHandler);

    // 404 handler
    m_server->onNotFound([this](AsyncWebServerRequest* request) {
        handleNotFound(request);
    });

    // CORS headers for all responses
    DefaultHeaders::Instance().addHeader("Access-Control-Allow-Origin", "*");
    DefaultHeaders::Instance().addHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    DefaultHeaders::Instance().addHeader("Access-Control-Allow-Headers", "Content-Type");
}

void ApiServer::handleRoot(AsyncWebServerRequest* request) {
    m_requestCount++;
    
    String html = R"rawhtml(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>E-Paper Controller</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee; min-height: 100vh; padding: 20px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { 
            text-align: center; margin-bottom: 30px;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            font-size: 2em;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px; padding: 20px; margin-bottom: 20px;
        }
        .card h2 { color: #00d9ff; margin-bottom: 15px; font-size: 1.1em; }
        .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .status-item { padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px; }
        .status-label { font-size: 0.8em; color: #888; }
        .status-value { font-size: 1.1em; color: #00ff88; }
        .btn {
            display: block; width: 100%; padding: 12px;
            border: none; border-radius: 8px; cursor: pointer;
            font-size: 1em; margin-bottom: 10px;
            transition: transform 0.1s, opacity 0.2s;
        }
        .btn:hover { transform: scale(1.02); }
        .btn:active { transform: scale(0.98); }
        .btn-primary { background: linear-gradient(90deg, #00d9ff, #00a8cc); color: #000; }
        .btn-danger { background: linear-gradient(90deg, #ff4757, #ff6b81); color: #fff; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
        textarea {
            width: 100%; padding: 12px; border-radius: 8px;
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2);
            color: #fff; font-family: monospace; resize: vertical; min-height: 80px;
        }
        .log { 
            font-family: monospace; font-size: 0.9em;
            background: #000; padding: 10px; border-radius: 8px;
            max-height: 150px; overflow-y: auto;
        }
        .log-entry { padding: 2px 0; border-bottom: 1px solid #222; }
        .log-ok { color: #00ff88; }
        .log-err { color: #ff4757; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ E-Paper Controller</h1>
        
        <div class="card">
            <h2>📊 Status</h2>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">IP Address</div>
                    <div class="status-value" id="ip">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Signal</div>
                    <div class="status-value" id="rssi">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Uptime</div>
                    <div class="status-value" id="uptime">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Requests</div>
                    <div class="status-value" id="requests">-</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>🖼️ Display Control</h2>
            <button class="btn btn-danger" onclick="clearDisplay()">Clear Display</button>
            <button class="btn btn-secondary" onclick="refreshDisplay()">Force Refresh</button>
        </div>

        <div class="card">
            <h2>✏️ Draw Text</h2>
            <textarea id="textInput" placeholder="Enter text to display..."></textarea>
            <br><br>
            <button class="btn btn-primary" onclick="sendText()">Send Text</button>
        </div>

        <div class="card">
            <h2>📜 Log</h2>
            <div class="log" id="log"></div>
        </div>
    </div>

    <script>
        function log(msg, ok=true) {
            const el = document.getElementById('log');
            const cls = ok ? 'log-ok' : 'log-err';
            el.innerHTML = `<div class="log-entry ${cls}">[${new Date().toLocaleTimeString()}] ${msg}</div>` + el.innerHTML;
        }

        async function api(endpoint, method='GET', body=null) {
            try {
                const opts = { method };
                if (body) {
                    opts.headers = { 'Content-Type': 'application/json' };
                    opts.body = JSON.stringify(body);
                }
                const res = await fetch('/api/' + endpoint, opts);
                const data = await res.json();
                log(`${method} /api/${endpoint}: ${data.status || data.error}`);
                return data;
            } catch(e) {
                log(`Error: ${e.message}`, false);
                return null;
            }
        }

        async function updateStatus() {
            const data = await api('status');
            if (data) {
                document.getElementById('ip').textContent = data.ip || '-';
                document.getElementById('rssi').textContent = (data.rssi || '-') + ' dBm';
                document.getElementById('uptime').textContent = data.uptime || '-';
                document.getElementById('requests').textContent = data.requests || '-';
            }
        }

        function clearDisplay() { api('display/clear', 'POST'); }
        function refreshDisplay() { api('display/refresh', 'POST'); }
        function sendText() {
            const text = document.getElementById('textInput').value;
            if (text) api('display/text', 'POST', { text, x: 10, y: 40 });
        }

        updateStatus();
        setInterval(updateStatus, 5000);
    </script>
</body>
</html>
)rawhtml";
    
    request->send(200, "text/html", html);
}

void ApiServer::handleStatus(AsyncWebServerRequest* request) {
    m_requestCount++;
    
    JsonDocument doc;
    doc["status"] = "ok";
    doc["ip"] = network::wifi.getIPAddress();
    doc["rssi"] = network::wifi.getRSSI();
    doc["uptime"] = getUptimeString();
    doc["uptimeSeconds"] = static_cast<uint32_t>(esp_timer_get_time() / 1000000);
    doc["requests"] = m_requestCount;
    doc["freeHeap"] = ESP.getFreeHeap();
    doc["minFreeHeap"] = ESP.getMinFreeHeap();
    doc["heapSize"] = ESP.getHeapSize();
    doc["hostname"] = network::wifi.getHostname();
    doc["mac"] = network::wifi.getMACAddress();
    doc["ssid"] = WiFi.SSID();
    doc["chip"] = ESP.getChipModel();
    doc["sdk"] = ESP.getSdkVersion();
    doc["resetReason"] = getResetReason();
    doc["display"]["width"] = display::epd.width();
    doc["display"]["height"] = display::epd.height();
    doc["display"]["bufferSize"] = config::FRAME_BUFFER_SIZE;

    String response;
    serializeJson(doc, response);
    request->send(200, "application/json", response);
}

void ApiServer::handleDisplayRaw(AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
    // First chunk - reset buffer
    if (index == 0) {
        s_imageBufferSize = 0;
        s_imageComplete = false;
        LOGF("[API] Receiving raw image: %u bytes\n", static_cast<unsigned>(total));
    }

    // Wrong size: ignore the body, the request handler answers 400
    if (total != config::FRAME_BUFFER_SIZE) {
        return;
    }

    // Copy data to buffer
    if (s_imageBuffer && (index + len) <= config::FRAME_BUFFER_SIZE) {
        memcpy(s_imageBuffer + index, data, len);
        s_imageBufferSize = index + len;
    }

    // Last chunk
    if (index + len == total) {
        s_imageComplete = true;
        LOGF("[API] Raw image received: %u bytes\n", static_cast<unsigned>(s_imageBufferSize));
    }
}

void ApiServer::handleDisplayClear(AsyncWebServerRequest* request) {
    m_requestCount++;
    
    // Check for color parameter
    bool white = true;
    if (request->hasParam("color", true)) {
        String color = request->getParam("color", true)->value();
        white = (color != "black");
    }
    
    display::epd.clear(white);
    sendJsonResponse(request, 200, "ok", white ? "Display cleared to white" : "Display cleared to black");
    LOGLN("[API] Display cleared");
}

void ApiServer::handleDisplayText(AsyncWebServerRequest* request, JsonVariant& json) {
    m_requestCount++;
    
    if (!json.is<JsonObject>()) {
        sendJsonError(request, 400, "Invalid JSON");
        return;
    }

    JsonObject obj = json.as<JsonObject>();
    
    if (!obj["text"].is<const char*>()) {
        sendJsonError(request, 400, "Missing 'text' field");
        return;
    }

    const char* text = obj["text"];
    int16_t x = obj["x"] | 10;
    int16_t y = obj["y"] | 40;
    int fontSize = obj["fontSize"] | 12;
    bool clear = obj["clear"] | true;
    bool refresh = obj["refresh"] | true;

    // Select font
    sFONT* font = &Font12;
    switch (fontSize) {
        case 8:  font = &Font8;  break;
        case 12: font = &Font12; break;
        case 16: font = &Font16; break;
        case 20: font = &Font20; break;
        case 24: font = &Font24; break;
    }

    auto& canvas = display::epd.getCanvas();
    
    if (clear) {
        canvas.clear();
    }
    
    canvas.drawText(x, y, text, font);
    
    if (refresh) {
        display::epd.updateFast();
    }

    sendJsonResponse(request, 200, "ok", "Text drawn");
    LOGF("[API] Text drawn: \"%s\" at (%d,%d)\n", text, x, y);
}

void ApiServer::handleDisplayRefresh(AsyncWebServerRequest* request) {
    m_requestCount++;
    
    String mode = "full";
    if (request->hasParam("mode", true)) {
        mode = request->getParam("mode", true)->value();
    }

    if (mode == "fast") {
        display::epd.updateFast();
    } else if (mode == "partial") {
        display::epd.updatePartial();
    } else {
        display::epd.update();
    }

    sendJsonResponse(request, 200, "ok", "Display refreshed");
    LOGLN("[API] Display refreshed");
}

void ApiServer::handleNotFound(AsyncWebServerRequest* request) {
    sendJsonError(request, 404, "Not found");
}

void ApiServer::sendJsonResponse(AsyncWebServerRequest* request, int code, const char* status, const char* message) {
    JsonDocument doc;
    doc["status"] = status;
    if (message) {
        doc["message"] = message;
    }
    
    String response;
    serializeJson(doc, response);
    request->send(code, "application/json", response);
}

void ApiServer::sendJsonError(AsyncWebServerRequest* request, int code, const char* error) {
    JsonDocument doc;
    doc["status"] = "error";
    doc["error"] = error;
    
    String response;
    serializeJson(doc, response);
    request->send(code, "application/json", response);
}

const char* ApiServer::getResetReason() {
    // Why the ESP32 last restarted: helps spot crashes and brownouts
    switch (esp_reset_reason()) {
        case ESP_RST_POWERON:   return "power-on";
        case ESP_RST_EXT:       return "external";
        case ESP_RST_SW:        return "software";
        case ESP_RST_PANIC:     return "panic";
        case ESP_RST_INT_WDT:   return "interrupt watchdog";
        case ESP_RST_TASK_WDT:  return "task watchdog";
        case ESP_RST_WDT:       return "watchdog";
        case ESP_RST_DEEPSLEEP: return "deep sleep";
        case ESP_RST_BROWNOUT:  return "brownout";
        case ESP_RST_SDIO:      return "SDIO";
        default:                return "unknown";
    }
}

String ApiServer::getUptimeString() {
    // Time since boot from the 64-bit timer: millis() wraps after ~49 days
    uint32_t seconds = static_cast<uint32_t>(esp_timer_get_time() / 1000000);
    uint32_t minutes = seconds / 60;
    uint32_t hours = minutes / 60;
    uint32_t days = hours / 24;

    char buf[32];
    if (days > 0) {
        snprintf(buf, sizeof(buf), "%lud %luh %lum", days, hours % 24, minutes % 60);
    } else if (hours > 0) {
        snprintf(buf, sizeof(buf), "%luh %lum %lus", hours, minutes % 60, seconds % 60);
    } else if (minutes > 0) {
        snprintf(buf, sizeof(buf), "%lum %lus", minutes, seconds % 60);
    } else {
        snprintf(buf, sizeof(buf), "%lus", seconds);
    }
    return String(buf);
}

}  // namespace api

