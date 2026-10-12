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
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont, ImageOps

from layout import Block, HeaderBlock, TextBlock, layout_name, render_layout
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

ESP32_DEFAULT_IP = os.environ.get("ESP32_IP", "192.168.1.231")
TIMEOUT = 30

FONTS_DIR = Path(__file__).parent / "fonts"


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
    expires_in_minutes: Optional[int] = Field(None, gt=0, le=10080)
    show_now: bool = False


class LayoutRequest(BaseModel):
    blocks: list[Block] = Field(max_length=20)
    hold_minutes: Optional[float] = Field(None, gt=0, le=1440)


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
        """Load bundled IBM Plex fonts (fonts/), falling back to system fonts"""
        self.fonts = {'bold': {}, 'medium': {}, 'mono': {}}
        
        # Font paths by style. The bundled fonts come first so rendering is
        # identical everywhere, including the Docker image (which has no fonts).
        font_paths = {
            'bold': [
                FONTS_DIR / "IBMPlexSans-Bold.otf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ],
            'medium': [
                FONTS_DIR / "IBMPlexSans-Medium.otf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ],
            'mono': [
                FONTS_DIR / "IBMPlexMono-Bold.otf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/System/Library/Fonts/Menlo.ttc",
            ],
        }
        
        sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48]
        
        for style, paths in font_paths.items():
            path = next((p for p in paths if Path(p).is_file()), None)
            if path:
                logger.info(f"Font '{style}': {path}")
            else:
                logger.warning(f"No font found for '{style}', using Pillow default")
            
            for size in sizes:
                if path:
                    font = ImageFont.truetype(str(path), size)
                else:
                    font = ImageFont.load_default(size)
                self.fonts[style][size] = font
    
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
    
    def render_message(self, title: str, message: str,
                       timestamp: Optional[str] = None) -> tuple[Image.Image, list[str]]:
        """Message card: title bar (with the time on the right) and wrapped text.
        Also returns warnings about text that didn't fit (see layout.py)."""
        return render_layout([
            HeaderBlock.model_construct(text=title, right=timestamp),
            TextBlock.model_construct(text=message),
        ], self)
    
    def draw_notification(self, title: str, message: str, 
                          timestamp: Optional[str] = None) -> Image.Image:
        """Draw a notification card"""
        return self.render_message(title, message, timestamp)[0]
    
    def fit_image(self, data: bytes) -> Image.Image:
        """Decode an uploaded image and fit it to the display (scaled, white borders)"""
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        
        # Transparent areas should end up white, not black
        if img.has_transparency_data:
            img = img.convert('RGBA')
            img = Image.alpha_composite(Image.new('RGBA', img.size, 'white'), img)
        
        img = ImageOps.pad(img.convert('L'), (self.width, self.height),
                           method=Image.Resampling.LANCZOS, color=255)
        return img.convert('1')  # Dithered, better for photos than a threshold
    
    def to_1bit(self, img: Image.Image) -> Image.Image:
        """Convert to pure black/white exactly as the panel shows it"""
        # Threshold instead of dithering for cleaner text edges
        if img.mode != '1':
            img = img.convert('L').point(lambda x: 255 if x > 128 else 0, '1')
        return img
    
    def to_raw_bytes(self, img: Image.Image) -> bytes:
        """Convert image to the e-paper frame buffer format"""
        img = self.to_1bit(img).rotate(-90, expand=True)
        # Mode '1' packs each row MSB-first, padded to whole bytes, 1 = white:
        # the same layout as the ESP32 frame buffer
        return img.tobytes()


def frame_to_image(frame: bytes) -> Image.Image:
    """The landscape image a raw frame shows"""
    return Image.frombytes('1', (DISPLAY_WIDTH, DISPLAY_HEIGHT), frame).rotate(90, expand=True)


# ============================================================================
# Global State
# ============================================================================

generator = ImageGenerator()
device_config = DeviceConfig()
scene_manager: Optional[SceneManager] = None
last_image: Optional[bytes] = None
last_update: Optional[datetime] = None
# What the last image shows: {"kind": "scene"|"message"|"image"|"layout"|"blank",
# "name", "scene_id", "source": "api"|"mcp"|"rotation"}
last_content: Optional[dict] = None
# How long the last POST took: transfer + the ESP32's panel refresh
last_refresh_ms: Optional[int] = None

# The ESP32 has a single receive buffer, so frames are sent one at a time
send_lock = asyncio.Lock()


# ============================================================================
# ESP32 Communication
# ============================================================================

async def send_to_esp32(data: bytes, content: Optional[dict] = None) -> dict:
    """Send raw image data to ESP32 and remember it as the last image"""
    global last_image, last_update, last_content, last_refresh_ms

    url = f"http://{device_config.ip}:{device_config.port}/api/display/raw"

    async with send_lock:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                url,
                content=data,
                headers={"Content-Type": "application/octet-stream"}
            )
            response.raise_for_status()
        last_refresh_ms = round((time.perf_counter() - started) * 1000)

    last_image = data
    last_update = datetime.now()
    last_content = content
    return response.json()


async def push_image(img: Image.Image, content: dict, hold_minutes: Optional[float] = None) -> dict:
    """Send an image on request (web UI, API, MCP). It stays up for a full
    rotation interval, or for hold_minutes."""
    result = await send_to_esp32(generator.to_raw_bytes(img), content)
    scene_manager.hold(hold_minutes)
    return result


async def display_image(img: Image.Image, content: dict, hold_minutes: Optional[float] = None) -> dict:
    """push_image for the REST API: errors become HTTP 500"""
    try:
        result = await push_image(img, {**content, "source": "api"}, hold_minutes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) or type(e).__name__)
    return {"status": "ok", "result": result}


def png_preview(img: Image.Image) -> bytes:
    """PNG of an image as the panel shows it (black/white), scaled 2x for screens"""
    img = generator.to_1bit(img)
    buf = io.BytesIO()
    img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST).save(buf, format='PNG')
    return buf.getvalue()


def scene_content(scene) -> dict:
    """Describe a scene image for last_content"""
    return {"kind": "scene", "name": scene.name, "scene_id": scene.id}


def display_info() -> dict:
    """What is on the display right now (for the web UI)"""
    return {
        "kind": None, "name": None, "scene_id": None,
        **(last_content or {}),
        "last_update": last_update.isoformat() if last_update else None,
        "age": round((datetime.now() - last_update).total_seconds(), 1) if last_update else None,
        "refresh_ms": last_refresh_ms,
    }


async def get_esp32_status() -> dict:
    """Get ESP32 status"""
    url = f"http://{device_config.ip}:{device_config.port}/api/status"
    
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
    return templates.TemplateResponse(request, "index.html", {
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
        "display": display_info(),
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
    img = await scene_manager.render_scene(scene_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    response = await display_image(img, scene_content(scene_manager.scenes[scene_id]))
    scene_manager.set_scene(scene_id)
    return response


@app.get("/api/scenes/{scene_id}/preview")
async def api_preview_scene(scene_id: str, cached: bool = False):
    """Get preview image of a scene (black/white, as the panel shows it).
    cached=true re-renders the last fetched data instead of calling the APIs."""
    scene = scene_manager.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    if cached:
        img = await scene.render_cached(generator)
    else:
        img = await scene_manager.render_scene(scene_id)

    return Response(png_preview(img), media_type="image/png")


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
    scene_id = scene_manager.next_scene()
    img = await scene_manager.render_current_scene()
    
    if img:
        await display_image(img, scene_content(scene_manager.get_current_scene()))
    
    return {"status": "ok", "scene": scene_id}


@app.post("/api/rotation/prev")
async def api_prev_scene():
    """Go to previous scene"""
    scene_id = scene_manager.prev_scene()
    img = await scene_manager.render_current_scene()
    
    if img:
        await display_image(img, scene_content(scene_manager.get_current_scene()))
    
    return {"status": "ok", "scene": scene_id}


@app.post("/api/rotation/interval")
async def api_set_interval(interval: int):
    """Set rotation interval in seconds"""
    scene_manager.rotation_interval = max(10, min(3600, interval))
    scene_manager.save_config()
    scene_manager.reset_timer()
    return {"status": "ok", "interval": scene_manager.rotation_interval}


@app.post("/api/rotation/resume")
async def api_resume_rotation():
    """End a hold (an image shown with hold_minutes) and continue rotating"""
    scene_manager.release_hold()
    return {"status": "ok"}


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
        "notifications": NotificationsScene.get_notifications(),
        "unread_count": NotificationsScene.get_unread_count(),
    }


@app.post("/api/notifications")
async def api_add_notification(notif: NotificationCreate):
    """Add a notification. show_now=true sends the Notifications scene right away
    instead of at the next rotation."""
    added = NotificationsScene.add_notification(
        title=notif.title,
        message=notif.message,
        priority=notif.priority,
        expires_in_minutes=notif.expires_in_minutes,
    )
    if notif.show_now:
        scene = scene_manager.scenes['notifications']
        await display_image(await scene.generate(generator), scene_content(scene))
    return {"status": "ok", "id": added['id'], "unread_count": NotificationsScene.get_unread_count()}


@app.delete("/api/notifications")
async def api_clear_notifications():
    """Clear all notifications"""
    NotificationsScene.clear_notifications()
    return {"status": "ok"}


@app.post("/api/notifications/{notif_id}/read")
async def api_mark_notification_read(notif_id: int):
    """Mark notification as read"""
    if not NotificationsScene.mark_read(notif_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


# ============================================================================
# Display Control API
# ============================================================================

@app.post("/api/display/clear")
async def api_clear_display(white: bool = True):
    """Clear the display"""
    content = {"kind": "blank", "name": "White" if white else "Black"}
    return await display_image(generator.create_blank(white), content)


@app.post("/api/display/text")
async def api_display_text(
    text: str = Form(...),
    title: str = Form("Message"),
):
    """Display text message"""
    img = generator.draw_notification(
        title, 
        text,
        datetime.now().strftime("%H:%M")
    )
    return await display_image(img, {"kind": "message", "name": title})


@app.post("/api/display/image")
async def api_display_image(file: UploadFile = File(...)):
    """Upload and display custom image (scaled to fit, white borders)"""
    try:
        img = generator.fit_image(await file.read())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
        
    return await display_image(img, {"kind": "image", "name": file.filename or "Image"})


@app.post("/api/display/layout")
async def api_display_layout(layout: LayoutRequest):
    """Render blocks (header, text, list, ... see layout.py) and send them to the display"""
    img, warnings = render_layout(layout.blocks, generator)
    response = await display_image(img, {"kind": "layout", "name": layout_name(layout.blocks)},
                                   layout.hold_minutes)
    return {**response, "warnings": warnings}


@app.post("/api/layout/preview")
async def api_preview_layout(layout: LayoutRequest):
    """Render blocks to a PNG without sending them. Warnings about anything that
    didn't fit are in the X-Layout-Warnings header (JSON list)."""
    img, warnings = render_layout(layout.blocks, generator)
    return Response(png_preview(img), media_type="image/png",
                    headers={"X-Layout-Warnings": json.dumps(warnings)})


@app.get("/api/display/current")
async def api_get_current():
    """Get current scene and render it"""
    scene = scene_manager.get_current_scene()
    if not scene:
        return {"scene": None, "display": display_info()}

    return {
        "scene": scene.get_info(),
        "manager": scene_manager.get_status(),
        "display": display_info(),
    }


@app.post("/api/display/refresh")
async def api_refresh_display():
    """Refresh current scene on display"""
    img = await scene_manager.render_current_scene()
    if img is None:
        raise HTTPException(status_code=404, detail="No scene to render")
    
    return await display_image(img, scene_content(scene_manager.get_current_scene()))


@app.get("/api/last-image")
async def api_last_image():
    """Get the last sent image as PNG"""
    if last_image is None:
        raise HTTPException(status_code=404, detail="No image sent yet")
    
    return Response(png_preview(frame_to_image(last_image)), media_type="image/png")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
