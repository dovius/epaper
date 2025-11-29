#!/usr/bin/env python3
"""
E-Paper Display Server
======================
FastAPI server for generating and sending images to ESP32 e-paper display.

Run with: uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Display configuration
DISPLAY_WIDTH = 122
DISPLAY_HEIGHT = 250
FRAME_BUFFER_SIZE = ((DISPLAY_WIDTH + 7) // 8) * DISPLAY_HEIGHT

# Server configuration
ESP32_DEFAULT_IP = "192.168.1.100"
TIMEOUT = 30

app = FastAPI(
    title="E-Paper Display Server",
    description="Generate and send images to ESP32 e-paper display",
    version="1.0.0"
)

# Templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============================================================================
# Models
# ============================================================================

class DeviceConfig(BaseModel):
    ip: str = ESP32_DEFAULT_IP
    port: int = 80

class TextWidget(BaseModel):
    text: str
    x: int = 10
    y: int = 10
    font_size: int = 16
    bold: bool = False

class DashboardConfig(BaseModel):
    title: str = "Dashboard"
    widgets: list[dict] = []

# Global state
device_config = DeviceConfig()
last_image: Optional[bytes] = None
last_update: Optional[datetime] = None


# ============================================================================
# Image Generation
# ============================================================================

class ImageGenerator:
    """Generate images for e-paper display"""
    
    def __init__(self):
        self.width = DISPLAY_HEIGHT  # Rotated
        self.height = DISPLAY_WIDTH  # Rotated
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts with fallbacks"""
        self.fonts = {}
        
        # Try to load nice fonts, fall back to default
        font_paths = [
            # Windows
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/arial.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            # macOS
            "/System/Library/Fonts/Menlo.ttc",
        ]
        
        for size in [8, 10, 12, 14, 16, 18, 20, 24, 28, 32]:
            font = None
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
            
            self.fonts[size] = font
    
    def get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font by size (or nearest available)"""
        if size in self.fonts:
            return self.fonts[size]
        # Find nearest
        available = sorted(self.fonts.keys())
        nearest = min(available, key=lambda x: abs(x - size))
        return self.fonts[nearest]
    
    def create_blank(self, white: bool = True) -> Image.Image:
        """Create blank image"""
        color = 255 if white else 0
        return Image.new('1', (self.width, self.height), color)
    
    def draw_text(self, img: Image.Image, text: str, x: int, y: int, 
                  font_size: int = 16, color: int = 0) -> Image.Image:
        """Draw text on image"""
        draw = ImageDraw.Draw(img)
        font = self.get_font(font_size)
        draw.text((x, y), text, font=font, fill=color)
        return img
    
    def draw_header(self, img: Image.Image, title: str) -> Image.Image:
        """Draw header bar"""
        draw = ImageDraw.Draw(img)
        # Black header bar
        draw.rectangle([0, 0, self.width, 24], fill=0)
        # White text
        font = self.get_font(16)
        draw.text((8, 4), title, font=font, fill=1)
        return img
    
    def draw_line(self, img: Image.Image, y: int) -> Image.Image:
        """Draw horizontal line"""
        draw = ImageDraw.Draw(img)
        draw.line([(0, y), (self.width, y)], fill=0, width=1)
        return img
    
    def draw_dashboard(self, title: str, lines: list[tuple[str, str]]) -> Image.Image:
        """Draw a dashboard with title and key-value lines"""
        img = self.create_blank()
        self.draw_header(img, title)
        
        draw = ImageDraw.Draw(img)
        y = 30
        font_label = self.get_font(12)
        font_value = self.get_font(14)
        
        for label, value in lines:
            draw.text((8, y), label, font=font_label, fill=0)
            draw.text((8, y + 14), value, font=font_value, fill=0)
            y += 34
            
            if y > self.height - 20:
                break
        
        return img
    
    def draw_notification(self, title: str, message: str, 
                          timestamp: Optional[str] = None) -> Image.Image:
        """Draw a notification card"""
        img = self.create_blank()
        self.draw_header(img, title)
        
        draw = ImageDraw.Draw(img)
        
        # Message with word wrap
        font = self.get_font(14)
        words = message.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = font.getbbox(test_line)
            if bbox[2] < self.width - 16:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        y = 32
        for line in lines[:6]:  # Max 6 lines
            draw.text((8, y), line, font=font, fill=0)
            y += 18
        
        # Timestamp at bottom
        if timestamp:
            font_small = self.get_font(10)
            draw.text((8, self.height - 16), timestamp, font=font_small, fill=0)
        
        return img
    
    def draw_multiline(self, title: str, text: str) -> Image.Image:
        """Draw multiple lines of text"""
        img = self.create_blank()
        self.draw_header(img, title)
        
        draw = ImageDraw.Draw(img)
        font = self.get_font(12)
        
        lines = text.split('\n')
        y = 30
        for line in lines:
            if y > self.height - 16:
                break
            draw.text((8, y), line, font=font, fill=0)
            y += 16
        
        return img
    
    def to_raw_bytes(self, img: Image.Image) -> bytes:
        """Convert image to raw bytes for e-paper"""
        # Ensure 1-bit mode
        if img.mode != '1':
            img = img.convert('1')
        
        # Rotate for display orientation
        img = img.rotate(-90, expand=True)
        
        # Create raw buffer
        raw = bytearray(FRAME_BUFFER_SIZE)
        pixels = img.load()
        
        for y in range(DISPLAY_HEIGHT):
            for x in range(DISPLAY_WIDTH):
                byte_idx = (x // 8) + y * ((DISPLAY_WIDTH + 7) // 8)
                bit_idx = 7 - (x % 8)
                
                if pixels[x, y]:
                    raw[byte_idx] |= (1 << bit_idx)
        
        return bytes(raw)


# Global generator
generator = ImageGenerator()


# ============================================================================
# ESP32 Client
# ============================================================================

async def send_to_esp32(data: bytes, ip: str = None, port: int = 80) -> dict:
    """Send raw image data to ESP32"""
    if ip is None:
        ip = device_config.ip
    
    url = f"http://{ip}:{port}/api/display/raw"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            url,
            content=data,
            headers={"Content-Type": "application/octet-stream"}
        )
        response.raise_for_status()
        return response.json()


async def get_esp32_status(ip: str = None, port: int = 80) -> dict:
    """Get ESP32 status"""
    if ip is None:
        ip = device_config.ip
    
    url = f"http://{ip}:{port}/api/status"
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


# ============================================================================
# API Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "device_ip": device_config.ip,
        "last_update": last_update.isoformat() if last_update else None
    })


@app.get("/api/device/status")
async def api_device_status():
    """Get ESP32 device status"""
    try:
        status = await get_esp32_status()
        return {"status": "online", "device": status}
    except Exception as e:
        return {"status": "offline", "error": str(e)}


@app.post("/api/device/config")
async def api_device_config(config: DeviceConfig):
    """Update device configuration"""
    global device_config
    device_config = config
    return {"status": "ok", "config": config.dict()}


@app.get("/api/device/config")
async def api_get_device_config():
    """Get current device configuration"""
    return device_config.dict()


@app.post("/api/display/clear")
async def api_clear_display(white: bool = True):
    """Clear the display"""
    global last_image, last_update
    
    img = generator.create_blank(white)
    raw = generator.to_raw_bytes(img)
    
    try:
        result = await send_to_esp32(raw)
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/display/text")
async def api_display_text(
    text: str = Form(...),
    title: str = Form("Message"),
):
    """Display text message"""
    global last_image, last_update
    
    img = generator.draw_notification(
        title, 
        text,
        datetime.now().strftime("%H:%M")
    )
    raw = generator.to_raw_bytes(img)
    
    try:
        result = await send_to_esp32(raw)
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/display/dashboard")
async def api_display_dashboard(
    title: str = Form("Dashboard"),
    data: str = Form(...)  # JSON string of key-value pairs
):
    """Display dashboard with key-value pairs"""
    global last_image, last_update
    
    try:
        items = json.loads(data)
        lines = [(k, str(v)) for k, v in items.items()]
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    
    img = generator.draw_dashboard(title, lines)
    raw = generator.to_raw_bytes(img)
    
    try:
        result = await send_to_esp32(raw)
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/display/image")
async def api_display_image(file: UploadFile = File(...)):
    """Upload and display custom image"""
    global last_image, last_update
    
    try:
        # Read and process image
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        
        # Resize to display dimensions
        img = img.resize((generator.width, generator.height), Image.Resampling.LANCZOS)
        img = img.convert('1')
        
        raw = generator.to_raw_bytes(img)
        result = await send_to_esp32(raw)
        
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/preview")
async def api_preview(
    type: str = "text",
    title: str = "Preview",
    content: str = "Hello World"
):
    """Generate preview image (returns PNG)"""
    if type == "text":
        img = generator.draw_notification(title, content)
    elif type == "dashboard":
        try:
            data = json.loads(content)
            lines = [(k, str(v)) for k, v in data.items()]
        except:
            lines = [("Content", content)]
        img = generator.draw_dashboard(title, lines)
    else:
        img = generator.draw_multiline(title, content)
    
    # Convert to PNG
    buf = io.BytesIO()
    # Scale up for preview
    preview = img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST)
    preview.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")


@app.get("/api/last-image")
async def api_last_image():
    """Get the last sent image as PNG"""
    if last_image is None:
        raise HTTPException(status_code=404, detail="No image sent yet")
    
    # Recreate image from raw bytes
    img = Image.new('1', (DISPLAY_WIDTH, DISPLAY_HEIGHT), 1)
    pixels = img.load()
    
    for y in range(DISPLAY_HEIGHT):
        for x in range(DISPLAY_WIDTH):
            byte_idx = (x // 8) + y * ((DISPLAY_WIDTH + 7) // 8)
            bit_idx = 7 - (x % 8)
            if not (last_image[byte_idx] & (1 << bit_idx)):
                pixels[x, y] = 0
    
    img = img.rotate(90, expand=True)
    
    buf = io.BytesIO()
    preview = img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST)
    preview.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

