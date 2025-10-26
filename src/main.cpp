/*****************************************************************************
 * Hacker News Top Stories E-Paper Demo
 *
 * Fetches the latest Hacker News top stories and renders the headlines on
 * the 2.13" Waveshare e-paper display. The sketch connects to Wi-Fi,
 * performs HTTPS requests against the public HN API, and refreshes
 * periodically with a status screen shown between updates.
 *
 * Update WIFI_SSID and WIFI_PASSWORD with your network credentials before
 * flashing the sketch.
 *****************************************************************************/

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <stdio.h>

#include "DEV_Config.h"
#include "EPD.h"
#include "GUI_Paint.h"
#include "ImageData.h"

namespace hn {

// ---------- Configuration ----------

constexpr char WIFI_SSID[] = "YOUR_WIFI_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

constexpr uint32_t kRefreshIntervalMs = 300000UL;  // 5 minutes
constexpr size_t kMaxStories = 6;
constexpr size_t kMaxTitleLength = 96;
constexpr uint32_t kRequestTimeoutMs = 15000;
constexpr char kTopStoriesEndpoint[] = "https://hacker-news.firebaseio.com/v0/topstories.json";
constexpr char kItemEndpointPrefix[] = "https://hacker-news.firebaseio.com/v0/item/";
constexpr char kItemEndpointSuffix[] = ".json";

constexpr UWORD kPanelWidth = EPD_2in13_V4_WIDTH;
constexpr UWORD kPanelHeight = EPD_2in13_V4_HEIGHT;
constexpr UWORD kDefaultRotate = ROTATE_90;

// ---------- Story representation ----------

struct Story {
    uint32_t id = 0;
    char title[kMaxTitleLength] = {0};
};

Story gStories[kMaxStories];
size_t gStoryCount = 0;

UBYTE *gFrame = nullptr;

// ---------- Utility helpers ----------

constexpr UWORD imageSizeBytes()
{
    return ((kPanelWidth + 7U) / 8U) * kPanelHeight;
}

bool ensureFrameBuffer()
{
    if (gFrame != nullptr) {
        return true;
    }
    gFrame = static_cast<UBYTE *>(malloc(imageSizeBytes()));
    if (gFrame == nullptr) {
        Debug("Failed to allocate frame buffer\r\n");
        return false;
    }
    return true;
}

void initCanvas(UWORD background = WHITE)
{
    Paint_NewImage(gFrame, kPanelWidth, kPanelHeight, kDefaultRotate, background);
    Paint_SelectImage(gFrame);
    Paint_Clear(background);
}

void fullRefresh(bool fast = false)
{
    if (fast) {
        EPD_2in13_V4_Init_Fast();
        EPD_2in13_V4_Display_Fast(gFrame);
    } else {
        EPD_2in13_V4_Init();
        EPD_2in13_V4_Display_Base(gFrame);
    }
}

void showStatus(const char *line1, const char *line2 = nullptr)
{
    initCanvas();
    Paint_DrawRectangle(0, 0, Paint.Width - 1, 26, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawString_EN(6, 4, "Hacker News", &Font16, WHITE, BLACK);

    UWORD y = 50;
    if (line1 != nullptr) {
        Paint_DrawString_EN(20, y, line1, &Font16, BLACK, WHITE);
        y += Font16.Height + 6;
    }
    if (line2 != nullptr) {
        Paint_DrawString_EN(20, y, line2, &Font12, BLACK, WHITE);
    }

    fullRefresh(true);
}

bool ensureWifi()
{
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000UL) {
        delay(500);
    }
    return WiFi.status() == WL_CONNECTED;
}

bool httpGet(const char *url, String &outBody)
{
    WiFiClientSecure client;
    client.setTimeout(kRequestTimeoutMs / 1000);
    client.setInsecure();  // Hacker News API uses HTTPS (no static cert here)

    HTTPClient http;
    http.setConnectTimeout(kRequestTimeoutMs);

    if (!http.begin(client, url)) {
        Debug("HTTP begin failed\r\n");
        return false;
    }

    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        Debug("HTTP GET failed\r\n");
        http.end();
        return false;
    }

    outBody = http.getString();
    http.end();
    return true;
}

bool parseTopIds(const String &json, uint32_t *ids, size_t maxIds, size_t &outCount)
{
    outCount = 0;
    uint32_t current = 0;
    bool inNumber = false;

    for (size_t i = 0; i < json.length(); ++i) {
        char c = json[i];
        if (c >= '0' && c <= '9') {
            current = current * 10 + static_cast<uint32_t>(c - '0');
            inNumber = true;
        } else if (inNumber) {
            ids[outCount++] = current;
            if (outCount >= maxIds) {
                return true;
            }
            current = 0;
            inNumber = false;
        }
    }

    if (inNumber && outCount < maxIds) {
        ids[outCount++] = current;
    }
    return outCount > 0;
}

bool decodeJsonString(const String &json, size_t valueStart, char *buffer, size_t bufferLen)
{
    if (bufferLen == 0) {
        return false;
    }
    size_t j = 0;
    bool inEscape = false;

    for (size_t i = valueStart; i < json.length(); ++i) {
        char c = json[i];
        if (inEscape) {
            char decoded = c;
            switch (c) {
                case '"':
                case '\\':
                case '/':
                    decoded = c;
                    break;
                case 'n':
                case 'r':
                    decoded = ' ';
                    break;
                case 't':
                    decoded = ' ';
                    break;
                default:
                    decoded = ' ';
                    break;
            }
            if (j + 1 < bufferLen) {
                buffer[j++] = decoded;
            }
            inEscape = false;
            continue;
        }

        if (c == '\\') {
            inEscape = true;
            continue;
        }
        if (c == '"') {
            break;
        }
        if (j + 1 < bufferLen) {
            buffer[j++] = c;
        }
    }

    buffer[j] = '\0';
    return j > 0;
}

void sanitizeAscii(char *text)
{
    size_t len = strlen(text);
    size_t readIdx = 0;
    size_t writeIdx = 0;
    while (readIdx < len) {
        unsigned char c = static_cast<unsigned char>(text[readIdx]);
        if (c < 32 || c == 127) {
            text[writeIdx++] = ' ';
            ++readIdx;
            continue;
        }
        if (c >= 128) {
            text[writeIdx++] = '?';
            ++readIdx;
            // Skip continuation bytes (UTF-8)
            while (readIdx < len) {
                unsigned char next = static_cast<unsigned char>(text[readIdx]);
                if ((next & 0xC0) != 0x80) {
                    break;
                }
                ++readIdx;
            }
            continue;
        }
        text[writeIdx++] = static_cast<char>(c);
        ++readIdx;
    }
    text[writeIdx] = '\0';
}

bool extractTitle(const String &json, char *buffer, size_t bufferLen)
{
    const char *key = "\"title\"";
    int keyIndex = json.indexOf(key);
    if (keyIndex < 0) {
        return false;
    }
    int colonIndex = json.indexOf(':', keyIndex + strlen(key));
    if (colonIndex < 0) {
        return false;
    }
    int quoteIndex = json.indexOf('"', colonIndex);
    if (quoteIndex < 0) {
        return false;
    }
    return decodeJsonString(json, static_cast<size_t>(quoteIndex + 1), buffer, bufferLen);
}

bool fetchStory(uint32_t id, Story &story)
{
    String url;
    url.reserve(128);
    url = kItemEndpointPrefix;
    url += id;
    url += kItemEndpointSuffix;

    String body;
    if (!httpGet(url.c_str(), body)) {
        return false;
    }

    if (!extractTitle(body, story.title, sizeof(story.title))) {
        strncpy(story.title, "(untitled)", sizeof(story.title));
        story.title[sizeof(story.title) - 1] = '\0';
    }
    sanitizeAscii(story.title);
    story.id = id;
    return true;
}

size_t drawWrappedText(UWORD x, UWORD y, const char *text, UWORD maxWidth, sFONT *font)
{
    if (text == nullptr || font == nullptr || maxWidth < font->Width) {
        return 0;
    }

    const UWORD maxCharsPerLine = maxWidth / font->Width;
    const UWORD lineHeight = font->Height + 2;
    size_t linesDrawn = 0;

    const char *ptr = text;
    char lineBuf[80];

    while (*ptr != '\0') {
        size_t len = 0;
        size_t lastSpace = SIZE_MAX;
        while (ptr[len] != '\0' && len < maxCharsPerLine) {
            if (ptr[len] == ' ') {
                lastSpace = len;
            }
            ++len;
        }

        size_t copyLen = len;
        if (ptr[len] != '\0' && lastSpace != SIZE_MAX) {
            copyLen = lastSpace;
        }
        if (copyLen == 0) {
            copyLen = len;
        }
        if (copyLen >= sizeof(lineBuf)) {
            copyLen = sizeof(lineBuf) - 1;
        }

        strncpy(lineBuf, ptr, copyLen);
        lineBuf[copyLen] = '\0';
        Paint_DrawString_EN(x, y, lineBuf, font, BLACK, WHITE);
        ++linesDrawn;

        ptr += copyLen;
        while (*ptr == ' ') {
            ++ptr;
        }
        if (*ptr == '\0') {
            break;
        }
        y += lineHeight;
    }
    return linesDrawn;
}

void renderStories()
{
    initCanvas();

    Paint_DrawRectangle(0, 0, Paint.Width - 1, 26, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawString_EN(6, 4, "Hacker News Top Stories", &Font12, WHITE, BLACK);

    if (gStoryCount == 0) {
        Paint_DrawString_EN(20, 54, "No stories available.", &Font16, BLACK, WHITE);
        fullRefresh(false);
        return;
    }

    UWORD y = 32;
    const sFONT *font = &Font12;
    const UWORD numberColumnWidth = 20;
    const UWORD textLeft = 14 + numberColumnWidth;
    const UWORD textWidth = Paint.Width > textLeft + 4 ? static_cast<UWORD>(Paint.Width - textLeft - 4) : Paint.Width;
    const UWORD lineHeight = font->Height + 4;

    for (size_t i = 0; i < gStoryCount; ++i) {
        if (y + font->Height >= Paint.Height) {
            break;
        }
        char prefix[6];
        snprintf(prefix, sizeof(prefix), "%u.", static_cast<unsigned>(i + 1));
        Paint_DrawString_EN(14, y, prefix, &Font12, BLACK, WHITE);

        size_t lines = drawWrappedText(textLeft, y, gStories[i].title, textWidth, &Font12);
        if (lines == 0) {
            lines = 1;
        }
        y += static_cast<UWORD>(lines * lineHeight);
    }

    fullRefresh(false);
}

void fetchTopStories()
{
    gStoryCount = 0;

    uint32_t ids[kMaxStories];
    size_t idCount = 0;

    String body;
    if (!httpGet(kTopStoriesEndpoint, body)) {
        Debug("Failed to fetch top story IDs\r\n");
        return;
    }

    if (!parseTopIds(body, ids, kMaxStories, idCount)) {
        Debug("Failed to parse top story IDs\r\n");
        return;
    }

    for (size_t i = 0; i < idCount; ++i) {
        Story story;
        if (fetchStory(ids[i], story)) {
            if (gStoryCount < kMaxStories) {
                gStories[gStoryCount++] = story;
            }
        }
    }
}

void cycleCleanup()
{
    EPD_2in13_V4_Init();
    EPD_2in13_V4_Clear();
    EPD_2in13_V4_Sleep();
}

void runOnce()
{
    if (!ensureFrameBuffer()) {
        return;
    }

    showStatus("Connecting Wi-Fi...");
    if (!ensureWifi()) {
        showStatus("Wi-Fi connection failed");
        cycleCleanup();
        return;
    }

    showStatus("Fetching top stories...");
    fetchTopStories();

    if (gStoryCount == 0) {
        showStatus("No stories fetched");
        cycleCleanup();
        return;
    }

    renderStories();
    cycleCleanup();
}

}  // namespace hn

// ---------- Arduino entry points ----------

void setup()
{
    Serial.begin(115200);
    DEV_Module_Init();
    hn::runOnce();
}

void loop()
{
    DEV_Delay_ms(hn::kRefreshIntervalMs);
    hn::runOnce();
}
