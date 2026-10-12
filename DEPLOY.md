# Deployment runbook

How to get the whole system running on a new machine. Written to be followed
top to bottom by a person or an AI agent: every step ends with a check, and
nothing here needs to be guessed.

## Overview

| Part | Where | Runs on |
|------|-------|---------|
| Server: renders scenes, rotates them, web dashboard on port 8000 | `server/` | Docker on an always-on Linux host (NAS, mini PC, Pi 64-bit) or a Mac |
| Firmware: receives 4000-byte 1-bit frames over HTTP and shows them | `src/` | ESP32 + Waveshare 2.13" V4, flashed once over USB |
| Optional: MCP endpoint for Claude, public through a Cloudflare Tunnel | `server/` (`cloudflared` service) | Same Docker host |

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
- Keep port 8000 on the LAN. There is no authentication, except for the MCP
  endpoint `/mcp/` (section 4).
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

## 4. Claude over MCP (optional)

The server has an MCP endpoint at `/mcp/`. With it Claude can see what the
display shows and control it: messages, custom layouts, notifications, scenes,
the rotation, the Agent Board and the AI Digest. Claude Code on the LAN
connects to it directly. claude.ai, Claude Desktop and the mobile apps connect
from Anthropic's cloud, so they need a public HTTPS address: a Cloudflare
Tunnel that routes only `/mcp`.

### 4.1 Turn it on

```bash
cd epaper/server
openssl rand -hex 32          # put the output in .env as MCP_TOKEN
docker compose up -d
```

Checks:

```bash
docker compose logs epaper-server | grep MCP                                    # MCP enabled at /mcp/
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/mcp/   # 401 (no token)
```

### 4.2 Claude Code on the LAN

```bash
claude mcp add --transport http epaper http://<host>:8000/mcp/ \
  --header "Authorization: Bearer <MCP_TOKEN>"
```

Check: `/mcp` in Claude Code lists `epaper` as connected, and "What's on the
e-paper display?" gets an answer with a picture of the screen.

### 4.3 claude.ai, Claude Desktop and mobile (Cloudflare Tunnel)

Requirements: a domain on Cloudflare (the free plan is enough).

1. Cloudflare dashboard > Zero Trust > Networks > Tunnels > Create a tunnel >
   Cloudflared, name `epaper`. Copy the token from the install command (the
   long string after `--token`) into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
2. Add a public hostname to the tunnel: subdomain `epaper`, your domain,
   **path `^/mcp`**, service `HTTP` `epaper-server:8000`. Never add a hostname
   without the path: the dashboard and REST API have no authentication, and
   `/api/scenes` shows the API keys. (The server also refuses everything but
   `/mcp/` from the tunnel, as a second line of defense.) With
   `DOCKER_NETWORK_MODE=host` the service is `<host LAN IP>:8000` instead.
3. Start the tunnel:
   ```bash
   docker compose --profile tunnel up -d
   ```
4. Checks:
   ```bash
   docker compose logs cloudflared | grep -i "registered tunnel connection"   # 4 connections
   curl -s -o /dev/null -w "%{http_code}\n" https://epaper.<domain>/         # 404
   curl -s -o /dev/null -w "%{http_code}\n" -X POST https://epaper.<domain>/mcp/   # 401
   ```
5. claude.ai > Customize > Connectors > Add custom connector:
   - URL `https://epaper.<domain>/mcp/` (with the trailing slash)
   - Authentication: **No sign in**
   - Request header: `Authorization` = `Bearer <MCP_TOKEN>`

   The connector is then also available in Claude Desktop and the mobile apps.
   Check: in a chat with the connector on, "Show 'Hello from Claude' on the
   e-paper display" changes the panel within a few seconds.
6. Optional hardening: a Cloudflare WAF custom rule for this hostname that
   blocks requests not coming from Anthropic's IP ranges (listed in Anthropic's
   docs). Claude Code keeps using the LAN address.

Changing the token: edit `.env`, `docker compose up -d`, then remove and re-add
the claude.ai connector (connectors can't be edited) and re-run
`claude mcp add` with the new token.

### 4.4 AI Digest (optional)

The AI Digest scene has Claude write news headlines with web search, at the
times in its settings. In the dashboard open **AI Digest**, set the Anthropic
API key (console.anthropic.com), topics, language and times, turn it on, then
**Run now**. A run costs roughly $0.15-0.30 with the default model.

Check: the scene shows headlines and no Error badge.

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
| `/mcp/` answers 503 | `MCP_TOKEN` isn't set in `.env`, then `docker compose up -d`. |
| claude.ai can't connect to the connector | The URL must end in `/mcp/` and the header must be `Authorization: Bearer <MCP_TOKEN>`. `curl -X POST https://epaper.<domain>/mcp/` must give 401: 404 means the tunnel path is wrong, 502 that the tunnel can't reach the server (host network mode: use the LAN IP as the service). |
| A tool says "The display was just updated" | MCP updates are limited to one per `MCP_MIN_PUSH_SECONDS` (10 s): every update is a full refresh. |
| AI Digest shows "Last run failed" | Open the scene for the error: usually a missing or wrong API key, or no credit on the Anthropic account. |
