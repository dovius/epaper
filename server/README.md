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
| `/api/notifications` | GET/POST/DELETE | List/add/clear notifications |
| `/api/notifications/{id}/read` | POST | Mark notification as read |
| `/api/display/text` | POST | Send text message (form fields `title`, `text`) |
| `/api/display/image` | POST | Upload image (form field `file`) |
| `/api/display/clear` | POST | Clear display (`?white=false` for black) |
| `/api/display/refresh` | POST | Re-render and send the current scene |
| `/api/last-image` | GET | Last image sent to the display, as PNG |

Anything sent manually stays on the display for a full rotation interval.

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

## Adding a Scene

Subclass `Scene` in `scenes/` and implement `fetch_data()` (async, get the
data) and `render()` (draw a 250x122 image with the `generator` helpers), then
add it to `scenes/__init__.py` and `SceneManager._init_scenes()`.

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
