# E-Paper Dashboard

ESP32 + Waveshare 2.13" e-paper display for the homelab. The ESP32 is a "dumb"
display with an HTTP API; everything you see is rendered by a Python server
(Docker on the NAS) and pushed to it as a ready-made 1-bit image:

- **Stocks** with mini charts (Finnhub + Yahoo)
- **Bitcoin** price in EUR with a 7-day chart (CoinGecko)
- **Weather** forecast for 3 days (Open-Meteo)
- **OctoPrint** printer status
- **Notifications** pushed over the API
- **System** clock and uptime
- **AI Digest**: news headlines Claude writes with web search
- **Agent Board**: a screen Claude keeps up to date

Claude can also control the display directly over MCP (claude.ai, the Claude
apps, Claude Code): messages, layouts, notifications, scenes.

```
┌─────────────────┐   POST /api/display/raw   ┌──────────────┐
│  Python server  │ ────────────────────────▶ │    ESP32     │
│  (FastAPI)      │   4000 byte 1-bit frame   │  (e-paper)   │
└────────┬────────┘                           └──────────────┘
         │ :8000
   web dashboard / scripts
```

Setting it up on a new machine (Docker server + flashing the ESP32): see
**[DEPLOY.md](DEPLOY.md)**.

## Firmware (ESP32)

Built with PlatformIO.

1. Copy `src/config/Secrets.h.example` to `src/config/Secrets.h` and fill in
   your WiFi credentials (the file is gitignored).
2. Build and flash: `pio run -t upload`, serial monitor: `pio device monitor`.

After boot the display shows its IP address. The device is also reachable as
`http://epaper.local/` (mDNS, hostname from `Secrets.h`) and has a small web UI
of its own.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Device status (JSON) |
| `/api/display/raw` | POST | Show a raw 1-bit frame (4000 bytes, 122x250, MSB first, 1 = white) |
| `/api/display/clear` | POST | Clear display (`color=black` form field for black) |
| `/api/display/text` | POST | Draw ASCII text, JSON `{"text", "x", "y", "fontSize"}` |
| `/api/display/refresh` | POST | Redraw the buffer, `mode=full\|fast\|partial` |

`tools/epaper_client.py` talks to these endpoints directly (useful for testing
without the server).

## Server

See [server/README.md](server/README.md).

## Hardware

- ESP32 board (ESP-WROVER-KIT or generic ESP32)
- Waveshare 2.13" e-paper display V4, wired as in `src/config/Config.h`
