# E-Paper Display Server

Python server for controlling ESP32 e-paper display with a beautiful web interface.

## Features

- 🖼️ **Image Generation** - Generate 1-bit images with text, dashboards
- 🌐 **Web Dashboard** - Beautiful control panel
- 📡 **ESP32 Integration** - Send images directly to display
- 🔄 **Live Preview** - See what will be displayed before sending
- 📊 **Dashboard Templates** - Key-value displays for sensor data
- 📝 **Text Messages** - Quick notifications with auto word-wrap

## Quick Start

### Windows
```cmd
cd server
run.bat
```

### Linux/macOS
```bash
cd server
chmod +x run.sh
./run.sh
```

### Manual
```bash
cd server
pip install -r requirements.txt
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Access

Open browser: **http://localhost:8000**

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/api/device/status` | GET | Check ESP32 connection |
| `/api/device/config` | POST | Set ESP32 IP address |
| `/api/display/clear` | POST | Clear display |
| `/api/display/text` | POST | Send text message |
| `/api/display/dashboard` | POST | Send dashboard data |
| `/api/display/image` | POST | Upload custom image |
| `/api/preview` | GET | Generate preview image |

## Examples

### Send text via curl
```bash
curl -X POST http://localhost:8000/api/display/text \
  -F "title=Alert" \
  -F "text=Server CPU at 95%!"
```

### Send dashboard data
```bash
curl -X POST http://localhost:8000/api/display/dashboard \
  -F "title=Sensors" \
  -F 'data={"Temperature": "24°C", "Humidity": "65%"}'
```

### Python example
```python
import requests

# Configure ESP32 IP
requests.post("http://localhost:8000/api/device/config", 
              json={"ip": "192.168.1.100"})

# Send text
requests.post("http://localhost:8000/api/display/text",
              data={"title": "Hello", "text": "World!"})
```

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

## Configuration

Set ESP32 IP address in the web interface or via API:

```bash
curl -X POST http://localhost:8000/api/device/config \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.100"}'
```

