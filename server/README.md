# E-Paper Display Server

Python (FastAPI) server that renders scenes for the ESP32 e-paper display and
pushes them as 1-bit images, with a web dashboard to control it.

## Features

- 🎬 **Scenes** - Stocks, Bitcoin, Weather, OctoPrint, Notifications, System
- 🔄 **Auto rotation** - Cycles through enabled scenes on an interval
- 🌐 **Web dashboard** - Enable/configure scenes, rotation, notifications
- 👁️ **Live preview** - Shows exactly what is on the display right now
- 🔔 **Notifications** - Push messages over the API, they take priority
- 🖼️ **Images & text** - Send any image or a text message
- 🧱 **Layouts** - Compose a screen from blocks (header, text, list, ...) as JSON
- 🤖 **MCP** - Claude (claude.ai, the apps, Claude Code) controls the display
- 📰 **AI Digest** - News headlines Claude writes with web search, on a schedule

## Quick Start

### Linux/macOS
```bash
cd server
./run.sh
```

### Windows
```cmd
cd server
run.bat
```

Both scripts create a virtualenv in `server/.venv` on first run and install
`requirements.txt` into it.

### Docker (e.g. on the NAS)
```bash
cd server
cp .env.example .env   # set ESP32_IP
docker compose up -d --build
```

Full step-by-step guide with checks: [../DEPLOY.md](../DEPLOY.md).

Variables (in `.env` or the environment):

| Variable | Default | Description |
|----------|---------|-------------|
| `ESP32_IP` | `192.168.1.231` | Display address (can also be changed in the UI) |
| `TZ` | `Europe/Vilnius` | Timezone for the clock and timestamps |
| `DOCKER_NETWORK_MODE` | `bridge` | `host` gives the container direct LAN access on Linux |
| `MCP_TOKEN` | (empty) | Bearer token for the MCP endpoint `/mcp/`; empty turns MCP off |
| `MCP_MIN_PUSH_SECONDS` | `10` | Minimum time between display updates made over MCP |
| `CLOUDFLARE_TUNNEL_TOKEN` | (empty) | For the optional `cloudflared` service (`--profile tunnel`) |

Settings are stored in `server/data/scene_config.json`. To keep an existing
local config, copy it there before the first start:
`mkdir -p data && cp scene_config.json data/`.

## Access

Open browser: **http://localhost:8000** (interactive API docs at `/docs`)

## Configuration

Scene settings (API keys, city, ...) are edited in the web dashboard and saved
to `scene_config.json`. That file contains secrets, so it is gitignored. Set
`SCENE_CONFIG=/path/to/file.json` to store it elsewhere.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/api/device/status` | GET | Check ESP32 connection |
| `/api/device/config` | GET/POST | Get/set ESP32 IP address and port |
| `/api/scenes` | GET | All scenes, rotation status (next scene, seconds to it) and what the display shows |
| `/api/scenes/{id}` | GET/PATCH | Get/update scene config (`enabled`, `settings`, ...) |
| `/api/scenes/{id}/show` | POST | Render and display a scene |
| `/api/scenes/{id}/preview` | GET | Scene preview as PNG, not sent to the display (`?cached=true` reuses the last data instead of calling the APIs) |
| `/api/rotation` | GET | Rotation status |
| `/api/rotation/start` `/stop` `/next` `/prev` | POST | Control rotation |
| `/api/rotation/interval?interval=60` | POST | Rotation interval in seconds |
| `/api/rotation/order` | PUT | Rotation order, JSON list of scene IDs |
| `/api/rotation/resume` | POST | End a hold and continue rotating |
| `/api/notifications` | GET/POST/DELETE | List/add/clear notifications (POST takes `expires_in_minutes` and `show_now`) |
| `/api/notifications/{id}/read` | POST | Mark notification as read |
| `/api/display/text` | POST | Send text message (form fields `title`, `text`) |
| `/api/display/image` | POST | Upload image (form field `file`) |
| `/api/display/clear` | POST | Clear display (`?white=false` for black) |
| `/api/display/refresh` | POST | Re-render and send the current scene |
| `/api/display/layout` | POST | Show a layout, JSON `{"blocks": [...], "hold_minutes": 10}` |
| `/api/layout/preview` | POST | Layout as PNG without sending it; warnings in the `X-Layout-Warnings` header |
| `/api/digest/run` | POST | Write a new AI Digest now (Claude API, costs a little) |
| `/api/last-image` | GET | Last image sent to the display, as PNG |
| `/mcp/` | MCP | MCP endpoint (Streamable HTTP), `Authorization: Bearer $MCP_TOKEN` |

Anything sent manually stays on the display for a full rotation interval, or
for `hold_minutes` where an endpoint takes it.

## Examples

### Send text via curl
```bash
curl -X POST http://localhost:8000/api/display/text \
  -F "title=Alert" \
  -F "text=Server CPU at 95%!"
```

### Push a notification
```bash
curl -X POST http://localhost:8000/api/notifications \
  -H "Content-Type: application/json" \
  -d '{"title": "Backup", "message": "TrueNAS backup finished", "priority": "high"}'
```

### Show a scene
```bash
curl -X POST http://localhost:8000/api/scenes/weather/show
```

### Show a layout for 10 minutes
```bash
curl -X POST http://localhost:8000/api/display/layout \
  -H "Content-Type: application/json" \
  -d '{"hold_minutes": 10, "blocks": [
        {"type": "header", "text": "Backup", "right": "03:12"},
        {"type": "big_number", "value": "1.2 TB", "label": "copied to the offsite box"},
        {"type": "progress", "value": 1, "label": "Done"}]}'
```

Block types: `header` (`text`, `right`), `text` (`text`, `size` s/m/l, `bold`,
`align`), `big_number` (`value`, `label`), `list` (`items`), `kv` (`rows` of
`key`/`value`), `progress` (`value` 0-1, `label`), `divider`, `spacer`
(`height`). The response lists anything that didn't fit in `warnings`.

### Python example
```python
import httpx

# Configure ESP32 IP
httpx.post("http://localhost:8000/api/device/config",
           json={"ip": "192.168.1.100"})

# Send text
httpx.post("http://localhost:8000/api/display/text",
           data={"title": "Hello", "text": "World!"})
```

## MCP (Claude)

With `MCP_TOKEN` set, `/mcp/` is an MCP server (`mcp_server.py`). Tools:

| Tool | What it does |
|------|--------------|
| `get_status`, `get_display_image` | Device, rotation, unread notifications; a picture of the current frame |
| `list_scenes`, `preview_scene`, `show_scene` | Scenes (API keys hidden), previews, show one |
| `show_message`, `preview_layout`, `show_layout`, `show_image` | Notes, custom layouts, pictures from public https URLs |
| `notify`, `list_notifications`, `mark_notification_read`, `clear_notifications` | Notifications |
| `control_rotation`, `set_scene_enabled` | Start/stop/next/prev/resume, interval, scenes in the rotation |
| `set_agent_scene`, `clear_agent_scene`, `refresh_digest` | Agent Board and AI Digest scenes |

Tools that change the display return a picture of the result and warnings
about cut-off text. Display updates over MCP are limited to one per
`MCP_MIN_PUSH_SECONDS`.

Connecting Claude Code and claude.ai (through a Cloudflare Tunnel) is
described in [../DEPLOY.md](../DEPLOY.md), section 4.

## Adding a Scene

Subclass `Scene` in `scenes/` and implement `fetch_data()` (async, get the
data) and `render()` (draw a 250x122 image with the `generator` helpers), then
add it to `scenes/__init__.py` and `SceneManager._init_scenes()`. For
text-heavy scenes, `layout.render_layout()` does the wrapping and fitting.

## Architecture

```
┌─────────────────┐     HTTP      ┌──────────────┐
│  Python Server  │ ───────────── │    ESP32     │
│  (FastAPI)      │               │  (E-Paper)   │
└────────┬────────┘               └──────────────┘
         │
         │ Port 8000
         │
┌────────┴────────┐
│    Browser      │
│  (Web Dashboard)│
└─────────────────┘
```

Fonts: IBM Plex Sans/Mono, bundled in `fonts/` (SIL Open Font License,
`fonts/IBMPlex-OFL.txt`).
