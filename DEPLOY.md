# Deployment runbook

How to get the whole system running on a new machine. Written to be followed
top to bottom by a person or an AI agent: every step ends with a check, and
nothing here needs to be guessed.

## Overview

| Part | Where | Runs on |
|------|-------|---------|
| Server: renders scenes, rotates them, web dashboard on port 8000 | `server/` | Docker on an always-on Linux host (NAS, mini PC, Pi 64-bit) or a Mac |
| Firmware: receives 4000-byte 1-bit frames over HTTP and shows them | `src/` | ESP32 + Waveshare 2.13" V4, flashed once over USB |

The server calls the ESP32 (`POST http://ESP32_IP/api/display/raw`); the ESP32
never calls the server. Both must be on the same LAN. The server also needs
internet access for the scene data (Finnhub, Yahoo, CoinGecko, Open-Meteo).

## 1. Server (Docker)

Requirements: Docker Engine with Compose v2. Check with
`docker compose version`. Some installs (e.g. Homebrew on macOS) only have the
standalone binary: if `docker-compose version` works instead, use
`docker-compose` wherever this guide says `docker compose`.

```bash
git clone git@github.com:dovius/epaper.git
cd epaper/server
cp .env.example .env          # set ESP32_IP (and TZ if not Europe/Vilnius)
mkdir -p data
```

Scene settings (API keys, city, rotation order, ...) live in
`server/data/scene_config.json`, which is gitignored. Either configure the
scenes in the dashboard after the first start, or restore the settings the
owner used before (Finnhub key, OctoPrint URL and key) from git history:

```bash
git show b932b80:server/scene_config.json > data/scene_config.json
```

Start:

```bash
docker compose up -d --build
```

Checks (all must pass):

```bash
docker compose ps                                   # STATUS: Up ... (healthy), give it ~30 s
docker compose logs epaper-server | grep "Font '"   # 3 lines, all /app/fonts/IBMPlex...
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/   # 200
curl -s http://localhost:8000/api/device/status     # "online" once the ESP32 is up (step 2)
docker compose exec epaper-server date              # local time, not UTC
```

The dashboard is at `http://<host>:8000`. Interactive API docs: `/docs`.

Updating later: `git pull && docker compose up -d --build`. Settings survive
because they are in `./data`.

Notes:
- Keep port 8000 on the LAN. There is no authentication.
- The default `bridge` network reaches LAN IPs (ESP32, OctoPrint) through NAT.
  If it can't, set `DOCKER_NETWORK_MODE=host` in `.env` (Linux only).
- An older container named `epaper-server` from a previous setup is simply
  recreated by `up`. Old versions mounted a single `scene_config.json` file;
  this one mounts the `./data` directory.
- Without Docker: `./run.sh` (creates `server/.venv`, needs Python 3.10+).

## 2. Firmware (ESP32)

Requirements: PlatformIO Core (`pipx install platformio`, or
`pip install platformio` in a virtualenv), a USB data cable, and the USB serial
driver for the board (CP210x or CH340) if the OS doesn't have it.

```bash
cd epaper
cp src/config/Secrets.h.example src/config/Secrets.h
```

Edit `src/config/Secrets.h` and set `WIFI_SSID` and `WIFI_PASSWORD`. Ask the
owner for them. Never commit this file (it is gitignored).

```bash
pio run                 # must end with [SUCCESS]; the first run downloads the toolchain
pio device list         # find the ESP32's serial port
pio run -t upload       # flash; if it can't connect, hold the board's BOOT button
pio device monitor      # optional: 115200 baud log, prints the IP after WiFi connects
```

Checks:
- The display shows **Ready** with its IP address and signal strength.
- `curl http://<esp32-ip>/api/status` returns JSON that includes `"chip"` and
  `"resetReason"` (older firmware doesn't have these fields).
- `http://epaper.local/` works from machines with mDNS (macOS, most Linux).
  Docker containers usually can't resolve `.local` names, so the server uses
  the IP.

Give the ESP32 a fixed IP (DHCP reservation on the router), put it in
`server/.env` as `ESP32_IP`, then apply it with `docker compose up -d`.

Wiring (ESP32 pin -> panel): SCK 13, MOSI 14, CS 15, RST 26, DC 27, BUSY 25.
These are set in `src/config/Config.h`.

## 3. End-to-end check

1. Open the dashboard. The top bar shows **Online** with the ESP32's IP and signal.
2. Press **Refresh**. Within about 3 s the panel flashes and shows the current
   scene. The dashboard preview matches it, and Activity shows
   `POST /api/display/refresh · 200`.
3. With **Auto-rotate** on, the scene changes every interval. The countdown
   under "Up next" shows when.
4. Scenes with an **Error** badge: open them to see the message. It usually means
   an external API is down or rate limited, or an API key is missing.

## Troubleshooting

| Symptom | Likely cause and fix |
|---------|---------------------|
| Dashboard says **Offline** | Wrong `ESP32_IP`, ESP32 not on WiFi, or a different subnet. Check the IP on the display, `curl http://<ip>/api/status` from the host, then try `DOCKER_NETWORK_MODE=host`. |
| Container not healthy | `docker compose logs epaper-server`. Port 8000 already in use: change the left side of `ports`. |
| Text in the images is tiny | The fonts weren't loaded. The logs must show `/app/fonts/IBMPlex...`, so build from a full checkout. |
| Clock on the display is off by hours | `TZ` in `.env`, then `docker compose up -d`. |
| Stocks show `--` | No Finnhub key: set it in the Stocks scene settings (free at finnhub.io). |
| OctoPrint shows Offline | The printer is off, or the URL/key in the scene settings is wrong. |
| `pio run` fails on `Secrets.h` | Copy `Secrets.h.example` to `Secrets.h` (step 2). |
| Panel stays blank after flashing | Check the wiring and look at `pio device monitor` for `[EPD] Busy timeout!`. |
