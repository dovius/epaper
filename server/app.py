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
from contextlib import asynccontextmanager
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

from scene_manager import SceneManager
from scenes import NotificationsScene, SystemScene

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISPLAY_WIDTH = 122
DISPLAY_HEIGHT = 250
FRAME_BUFFER_SIZE = ((DISPLAY_WIDTH + 7) // 8) * DISPLAY_HEIGHT

ESP32_DEFAULT_IP = "192.168.1.231"
TIMEOUT = 30


# ============================================================================
# Models
# ============================================================================

class DeviceConfig(BaseModel):
    ip: str = ESP32_DEFAULT_IP
    port: int = 80


class SceneConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval: Optional[int] = None
    priority: Optional[int] = None
    settings: Optional[dict] = None


class NotificationCreate(BaseModel):
    title: str
    message: str
    priority: str = "normal"


# ============================================================================
# Image Generator
# ============================================================================

class ImageGenerator:
    """Generate images for e-paper display"""
    
    def __init__(self):
        self.width = DISPLAY_HEIGHT  # Rotated
        self.height = DISPLAY_WIDTH  # Rotated
        self._load_fonts()
    
    def _load_fonts(self):
        """Load IBM Plex fonts with fallbacks"""
        self.fonts = {'bold': {}, 'medium': {}, 'mono': {}}
        
        # Font paths by style
        font_paths = {
            'bold': [
                "/System/Library/Fonts/Supplemental/IBMPlexSans-Bold.otf",
                "/usr/share/fonts/opentype/ibm-plex/IBMPlexSans-Bold.otf",
                "C:/Windows/Fonts/IBMPlexSans-Bold.otf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ],
            'medium': [
                "/System/Library/Fonts/Supplemental/IBMPlexSans-Medium.otf",
                "/usr/share/fonts/opentype/ibm-plex/IBMPlexSans-Medium.otf",
                "C:/Windows/Fonts/IBMPlexSans-Medium.otf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ],
            'mono': [
                "/System/Library/Fonts/Supplemental/IBMPlexMono-Bold.otf",
                "/usr/share/fonts/opentype/ibm-plex/IBMPlexMono-Bold.otf",
                "C:/Windows/Fonts/IBMPlexMono-Bold.otf",
                "/System/Library/Fonts/Menlo.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            ],
        }
        
        sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48]
        
        for style, paths in font_paths.items():
            for size in sizes:
                font = None
                for path in paths:
                    try:
                        font = ImageFont.truetype(path, size)
                        break
                    except:
                        continue
                
                if font is None:
                    font = ImageFont.load_default()
                
                self.fonts[style][size] = font
        
        logger.info("Loaded IBM Plex fonts: Sans Bold, Sans Medium, Mono Bold")
    
    def get_font(self, size: int, style: str = "medium") -> ImageFont.FreeTypeFont:
        """Get font by size and style (bold, medium, mono)"""
        style = style if style in self.fonts else "medium"
        style_fonts = self.fonts[style]
        
        if size in style_fonts:
            return style_fonts[size]
        available = sorted(style_fonts.keys())
        nearest = min(available, key=lambda x: abs(x - size))
        return style_fonts[nearest]
    
    def create_blank(self, white: bool = True) -> Image.Image:
        """Create blank grayscale image (for better text rendering)"""
        color = 255 if white else 0
        return Image.new('L', (self.width, self.height), color)
    
    def draw_text(self, img: Image.Image, text: str, x: int, y: int, 
                  font_size: int = 16, color: int = 0, style: str = "medium") -> Image.Image:
        """Draw text on image"""
        draw = ImageDraw.Draw(img)
        font = self.get_font(font_size, style)
        draw.text((x, y), text, font=font, fill=color)
        return img
    
    def draw_header(self, img: Image.Image, title: str) -> Image.Image:
        """Draw header bar (thinner with bold font)"""
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, self.width, 22], fill=0)
        font = self.get_font(14, "bold")
        draw.text((6, 3), title, font=font, fill=255)
        return img
    
    def draw_line(self, img: Image.Image, y: int) -> Image.Image:
        """Draw horizontal line"""
        draw = ImageDraw.Draw(img)
        draw.line([(0, y), (self.width, y)], fill=0, width=1)
        return img
    
    def draw_notification(self, title: str, message: str, 
                          timestamp: Optional[str] = None) -> Image.Image:
        """Draw a notification card"""
        img = self.create_blank()
        self.draw_header(img, title)
        
        draw = ImageDraw.Draw(img)
        font = self.get_font(18, "medium")
        
        # Word wrap
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
        
        y = 28
        for line in lines[:5]:
            draw.text((8, y), line, font=font, fill=0)
            y += 20
        
        if timestamp:
            font_small = self.get_font(14, "mono")
            draw.text((8, self.height - 18), timestamp, font=font_small, fill=0)
        
        return img
    
    def to_raw_bytes(self, img: Image.Image) -> bytes:
        """Convert image to raw bytes for e-paper (with threshold for clean edges)"""
        # Convert grayscale to 1-bit with threshold for cleaner text edges
        if img.mode == 'L':
            img = img.point(lambda x: 255 if x > 128 else 0, '1')
        elif img.mode != '1':
            img = img.convert('L').point(lambda x: 255 if x > 128 else 0, '1')
        
        img = img.rotate(-90, expand=True)
        
        raw = bytearray(FRAME_BUFFER_SIZE)
        pixels = img.load()
        
        for y in range(DISPLAY_HEIGHT):
            for x in range(DISPLAY_WIDTH):
                byte_idx = (x // 8) + y * ((DISPLAY_WIDTH + 7) // 8)
                bit_idx = 7 - (x % 8)
                
                if pixels[x, y]:
                    raw[byte_idx] |= (1 << bit_idx)
        
        return bytes(raw)


# ============================================================================
# Global State
# ============================================================================

generator = ImageGenerator()
device_config = DeviceConfig()
scene_manager: Optional[SceneManager] = None
last_image: Optional[bytes] = None
last_update: Optional[datetime] = None


# ============================================================================
# ESP32 Communication
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
# App Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown"""
    global scene_manager
    
    # Initialize
    SystemScene.init_start_time()
    scene_manager = SceneManager(generator)
    scene_manager.set_send_callback(send_to_esp32)
    
    # Start rotation if enabled
    if scene_manager.rotation_enabled:
        scene_manager.start_rotation()
    
    logger.info("E-Paper server started")
    
    yield
    
    # Cleanup
    if scene_manager:
        scene_manager.stop_rotation()
    
    logger.info("E-Paper server stopped")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="E-Paper Display Server",
    description="Generate and send images to ESP32 e-paper display",
    version="2.0.0",
    lifespan=lifespan,
)

# Templates & Static
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============================================================================
# Page Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "device_ip": device_config.ip,
        "last_update": last_update.isoformat() if last_update else None
    })


# ============================================================================
# Device API
# ============================================================================

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
    return {"status": "ok", "config": config.model_dump()}


@app.get("/api/device/config")
async def api_get_device_config():
    """Get current device configuration"""
    return device_config.model_dump()


# ============================================================================
# Scene Manager API
# ============================================================================

@app.get("/api/scenes")
async def api_get_scenes():
    """Get all scenes and their configurations"""
    return {
        "scenes": scene_manager.get_all_scenes_info(),
        "manager": scene_manager.get_status(),
    }


@app.get("/api/scenes/{scene_id}")
async def api_get_scene(scene_id: str):
    """Get specific scene info"""
    if scene_id not in scene_manager.scenes:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene_manager.scenes[scene_id].get_info()


@app.patch("/api/scenes/{scene_id}")
async def api_update_scene(scene_id: str, config: SceneConfigUpdate):
    """Update scene configuration"""
    config_dict = config.model_dump(exclude_none=True)
    if not scene_manager.update_scene_config(scene_id, config_dict):
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "ok", "scene": scene_manager.scenes[scene_id].get_info()}


@app.post("/api/scenes/{scene_id}/show")
async def api_show_scene(scene_id: str):
    """Render and send a specific scene to display"""
    global last_image, last_update
    
    img = await scene_manager.render_scene(scene_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    raw = generator.to_raw_bytes(img)
    
    try:
        result = await send_to_esp32(raw)
        last_image = raw
        last_update = datetime.now()
        scene_manager.set_scene(scene_id)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenes/{scene_id}/preview")
async def api_preview_scene(scene_id: str):
    """Get preview image of a scene"""
    img = await scene_manager.render_scene(scene_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    buf = io.BytesIO()
    preview = img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST)
    preview.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")


# ============================================================================
# Scene Rotation API
# ============================================================================

@app.get("/api/rotation")
async def api_get_rotation():
    """Get rotation status"""
    return scene_manager.get_status()


@app.post("/api/rotation/start")
async def api_start_rotation():
    """Start scene rotation"""
    scene_manager.rotation_enabled = True
    scene_manager.start_rotation()
    scene_manager.save_config()
    return {"status": "ok", "rotation_enabled": True}


@app.post("/api/rotation/stop")
async def api_stop_rotation():
    """Stop scene rotation"""
    scene_manager.rotation_enabled = False
    scene_manager.stop_rotation()
    scene_manager.save_config()
    return {"status": "ok", "rotation_enabled": False}


@app.post("/api/rotation/next")
async def api_next_scene():
    """Go to next scene"""
    global last_image, last_update
    
    scene_id = scene_manager.next_scene()
    img = await scene_manager.render_current_scene()
    
    if img:
        raw = generator.to_raw_bytes(img)
        try:
            result = await send_to_esp32(raw)
            last_image = raw
            last_update = datetime.now()
            return {"status": "ok", "scene": scene_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return {"status": "ok", "scene": scene_id}


@app.post("/api/rotation/prev")
async def api_prev_scene():
    """Go to previous scene"""
    global last_image, last_update
    
    scene_id = scene_manager.prev_scene()
    img = await scene_manager.render_current_scene()
    
    if img:
        raw = generator.to_raw_bytes(img)
        try:
            result = await send_to_esp32(raw)
            last_image = raw
            last_update = datetime.now()
            return {"status": "ok", "scene": scene_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return {"status": "ok", "scene": scene_id}


@app.post("/api/rotation/interval")
async def api_set_interval(interval: int):
    """Set rotation interval in seconds"""
    scene_manager.rotation_interval = max(10, min(3600, interval))
    scene_manager.save_config()
    return {"status": "ok", "interval": scene_manager.rotation_interval}


@app.put("/api/rotation/order")
async def api_set_order(order: list[str]):
    """Update scene rotation order"""
    if not scene_manager.update_rotation_order(order):
        raise HTTPException(status_code=400, detail="Invalid scene IDs in order")
    return {"status": "ok", "order": order}


# ============================================================================
# Notifications API
# ============================================================================

@app.get("/api/notifications")
async def api_get_notifications():
    """Get all notifications"""
    return {
        "notifications": NotificationsScene._notifications,
        "unread_count": NotificationsScene.get_unread_count(),
    }


@app.post("/api/notifications")
async def api_add_notification(notif: NotificationCreate):
    """Add a notification"""
    NotificationsScene.add_notification(
        title=notif.title,
        message=notif.message,
        priority=notif.priority,
    )
    return {"status": "ok", "unread_count": NotificationsScene.get_unread_count()}


@app.delete("/api/notifications")
async def api_clear_notifications():
    """Clear all notifications"""
    NotificationsScene.clear_notifications()
    return {"status": "ok"}


@app.post("/api/notifications/{notif_id}/read")
async def api_mark_notification_read(notif_id: int):
    """Mark notification as read"""
    NotificationsScene.mark_read(notif_id)
    return {"status": "ok"}


# ============================================================================
# Display Control API
# ============================================================================

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


@app.post("/api/display/image")
async def api_display_image(file: UploadFile = File(...)):
    """Upload and display custom image"""
    global last_image, last_update
    
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        
        img = img.resize((generator.width, generator.height), Image.Resampling.LANCZOS)
        img = img.convert('1')
        
        raw = generator.to_raw_bytes(img)
        result = await send_to_esp32(raw)
        
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/display/current")
async def api_get_current():
    """Get current scene and render it"""
    scene = scene_manager.get_current_scene()
    if not scene:
        return {"scene": None}
    
    return {
        "scene": scene.get_info(),
        "manager": scene_manager.get_status(),
    }


@app.post("/api/display/refresh")
async def api_refresh_display():
    """Refresh current scene on display"""
    global last_image, last_update
    
    img = await scene_manager.render_current_scene()
    if img is None:
        raise HTTPException(status_code=404, detail="No scene to render")
    
    raw = generator.to_raw_bytes(img)
    
    try:
        result = await send_to_esp32(raw)
        last_image = raw
        last_update = datetime.now()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/last-image")
async def api_last_image():
    """Get the last sent image as PNG"""
    if last_image is None:
        raise HTTPException(status_code=404, detail="No image sent yet")
    
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
