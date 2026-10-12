"""
MCP server
==========
Lets Claude (claude.ai, the Claude apps, Claude Code) control the display
over the Model Context Protocol. app.py mounts it at /mcp/ behind a static
bearer token (MCP_TOKEN). Over the Cloudflare tunnel only /mcp/ is reachable,
because the dashboard and the REST API have no authentication.
"""

import asyncio
import hmac
import io
import ipaddress
import logging
import math
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Awaitable, Callable, Literal, Optional

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from PIL import Image as PILImage
from pydantic import Field
from starlette.responses import JSONResponse

from layout import Block, layout_name, render_layout
from scenes import NotificationsScene

logger = logging.getLogger(__name__)

# Every update is a full e-paper refresh, so don't let an agent loop on it
MIN_PUSH_SECONDS = float(os.environ.get("MCP_MIN_PUSH_SECONDS", "10"))
MAX_IMAGE_BYTES = 5 * 1024 * 1024

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
CHANGES_DISPLAY = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

INSTRUCTIONS = f"""\
Controls a small black-and-white e-paper display (Waveshare 2.13", 250 x 122 px,
landscape) on the owner's desk in their homelab.

- Every change is a full refresh: the panel flashes for about 3 seconds. Update it
  once per request, never in a loop. Updates less than {MIN_PUSH_SECONDS:.0f} s apart are rejected.
- Normally a rotation cycles through scenes (stocks, bitcoin, weather, 3D printer,
  notifications, clock, ...). What you show stays up for one rotation interval, or
  for hold_minutes, then the rotation continues.
- Pick the tool by intent: show_message for a quick note; notify for something the
  owner should act on (unread notifications take over the display until read);
  show_layout for a custom screen (check it with preview_layout first).
- The fonts have Latin letters (Lithuanian too), digits and common symbols
  (• … ° € → ✓) but no emoji, which are removed.
- Tools that change the display return a picture of the result. Look at it and at
  the warnings, and shorten the text if something was cut off.
"""

HoldMinutes = Annotated[Optional[float], Field(
    gt=0, le=1440,
    description="Keep it on the display this many minutes instead of one rotation interval",
)]
Blocks = Annotated[list[Block], Field(min_length=1, max_length=20, description=(
    "Blocks stacked top to bottom on the 250 x 122 px screen. Start with a header. "
    "Roughly: header 23 px, text s/m/l lines 16/20/27 px, big_number ~45 px, "
    "kv and list rows 16 px, progress 26 px."
))]


@dataclass
class ServerContext:
    """What the tools need from app.py, passed in to avoid a circular import"""
    generator: Any
    scene_manager: Callable[[], Any]  # created in the app's lifespan
    push_image: Callable[..., Awaitable[dict]]
    display_info: Callable[[], dict]
    device_status: Callable[[], Awaitable[dict]]
    device_address: Callable[[], str]
    last_frame: Callable[[], Optional[PILImage.Image]]
    png_preview: Callable[[PILImage.Image], bytes]


class RateLimit:
    """Minimum time between two actions"""

    def __init__(self, seconds: float, what: str):
        self.seconds = seconds
        self.what = what
        self._last = -math.inf

    def check(self):
        wait = self._last + self.seconds - time.monotonic()
        if wait > 0:
            raise ToolError(f"{self.what} was just updated. Try again in {math.ceil(wait)} s: "
                            "every update is a full e-paper refresh.")

    def mark(self):
        self._last = time.monotonic()


# ============================================================================
# Remote images
# ============================================================================

async def _public_address(host: str, port: int) -> str:
    """Resolve host, refusing private, loopback and other non-public addresses
    (the server sits on the LAN, so it must not fetch internal URLs)"""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ToolError(f"Can't resolve {host}: {e}") from e
    addresses = sorted({info[4][0] for info in infos})
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ToolError(f"{host} resolves to {address}, which is not a public address")
    return addresses[0]


async def fetch_public_image(url: str) -> bytes:
    """Download an image from a public https URL (at most 5 MB, 3 redirects)"""
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(4):
            target = httpx.URL(url)
            if target.scheme != "https":
                raise ToolError("Only https:// image URLs are supported")
            address = await _public_address(target.host, target.port or 443)
            # Connect to the address that was checked, so DNS can't change in between
            host_header = target.host if target.port in (None, 443) else f"{target.host}:{target.port}"
            async with client.stream("GET", target.copy_with(host=address), headers={"Host": host_header},
                                     extensions={"sni_hostname": target.host}) as response:
                if response.is_redirect:
                    url = str(target.join(response.headers["location"]))
                    continue
                if response.status_code != 200:
                    raise ToolError(f"Fetching the image failed: HTTP {response.status_code}")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ToolError("The image is larger than 5 MB")
                return bytes(data)
    raise ToolError("Too many redirects")


# ============================================================================
# Tools
# ============================================================================

def build_mcp(ctx: ServerContext) -> MCPServer:
    """Create the MCP server and its tools"""
    mcp = MCPServer("epaper", title="E-Paper display", instructions=INSTRUCTIONS)
    push_limit = RateLimit(MIN_PUSH_SECONDS, "The display")
    gen = ctx.generator

    def get_scene(scene_id: str):
        scene = ctx.scene_manager().scenes.get(scene_id)
        if scene is None:
            ids = ", ".join(ctx.scene_manager().scenes)
            raise ToolError(f"No scene '{scene_id}'. Scenes: {ids}")
        return scene

    def stays_up(hold_minutes: Optional[float]) -> str:
        manager = ctx.scene_manager()
        if hold_minutes:
            return f"It stays up for {hold_minutes:g} min."
        if not manager.rotation_enabled:
            return "Rotation is off, so it stays up until something else is shown."
        return f"It stays up until the next rotation, in {manager.rotation_interval} s."

    def result(img, text: str, warnings=()) -> list:
        """A picture of img plus text and warnings"""
        lines = [text] + [f"Warning: {w}" for w in warnings]
        return [Image(data=ctx.png_preview(img), format="png"), "\n".join(lines)]

    async def push(img, content: dict, hold_minutes: Optional[float] = None):
        push_limit.check()
        logger.info(f"MCP: showing {content.get('kind')} '{content.get('name')}'")
        try:
            await ctx.push_image(img, {**content, "source": "mcp"}, hold_minutes)
        except Exception as e:
            raise ToolError(f"The display at {ctx.device_address()} didn't take the image: "
                            f"{e or type(e).__name__}") from e
        finally:
            push_limit.mark()

    def scene_content(scene) -> dict:
        return {"kind": "scene", "name": scene.name, "scene_id": scene.id}

    # --- Reading -------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    async def get_status() -> dict:
        """What the display shows now, whether it is online, the rotation state,
        unread notifications and scenes whose data source is failing."""
        manager = ctx.scene_manager()
        try:
            status = await ctx.device_status()
            device = {"online": True, **{k: status.get(k) for k in ("ip", "rssi", "uptime", "freeHeap", "chip")}}
        except Exception as e:
            device = {"online": False, "address": ctx.device_address(), "error": str(e) or type(e).__name__}

        rotation = manager.get_status()
        infos = [scene.get_info() for scene in manager.scenes.values()]
        return {
            "device": device,
            "showing": ctx.display_info(),
            "rotation": {k: rotation[k] for k in (
                "rotation_enabled", "rotation_interval", "current_scene", "next_scene",
                "next_rotation_in", "held_until", "enabled_scenes")},
            "unread_notifications": NotificationsScene.get_unread_count(),
            "scene_errors": {info["id"]: info["last_error"] for info in infos if info["last_error"]},
        }

    @mcp.tool(annotations=READ_ONLY)
    async def get_display_image() -> list:
        """A picture of what the display shows right now (the last frame sent to it)."""
        img = ctx.last_frame()
        if img is None:
            raise ToolError("Nothing has been sent to the display since the server started")
        info = ctx.display_info()
        what = info["name"] if info["kind"] == "scene" else f"{info['kind']}: {info['name']}"
        return result(img, f"Showing {what}, sent {info['age']:.0f} s ago by {info.get('source') or 'the server'}.")

    @mcp.tool(annotations=READ_ONLY)
    async def list_scenes() -> list[dict]:
        """All scenes: whether they are in the rotation, their last error and their
        settings (API keys hidden)."""
        manager = ctx.scene_manager()
        enabled = manager.get_enabled_scenes()
        scenes = []
        for scene in manager.scenes.values():
            info = scene.get_info()
            secret = {f["key"] for f in info["settings_schema"] if f.get("type") == "password"}
            settings = {
                key: ("(set)" if value else "(not set)") if key in secret else value
                for key, value in info["config"]["settings"].items()
            }
            scenes.append({
                "id": info["id"], "name": info["name"], "description": info["description"],
                "in_rotation": info["id"] in enabled,
                "last_error": info["last_error"], "last_data_at": info["last_data_at"],
                "settings": settings,
            })
        return scenes

    @mcp.tool(annotations=READ_ONLY)
    async def preview_scene(
        scene_id: Annotated[str, Field(description="Scene id from list_scenes")],
        fresh: Annotated[bool, Field(description="Fetch new data from the scene's APIs instead of reusing the last data")] = False,
    ) -> list:
        """Render a scene without sending it to the display."""
        scene = get_scene(scene_id)
        img = await (scene.generate(gen) if fresh else scene.render_cached(gen))
        return result(img, f"Preview of {scene.name} (not sent to the display).")

    @mcp.tool(annotations=READ_ONLY)
    async def list_notifications() -> list[dict]:
        """Notifications that haven't expired, newest last, read ones included."""
        return NotificationsScene.get_notifications()

    # --- Showing -------------------------------------------------------------

    @mcp.tool(annotations=CHANGES_DISPLAY)
    async def show_scene(
        scene_id: Annotated[str, Field(description="Scene id from list_scenes")],
        hold_minutes: HoldMinutes = None,
    ) -> list:
        """Render a scene with fresh data and show it. The rotation continues from there."""
        scene = get_scene(scene_id)
        img = await ctx.scene_manager().render_scene(scene_id)
        await push(img, scene_content(scene), hold_minutes)
        ctx.scene_manager().set_scene(scene_id)
        return result(img, f"Showing {scene.name}. {stays_up(hold_minutes)}")

    @mcp.tool(annotations=CHANGES_DISPLAY)
    async def show_message(
        title: Annotated[str, Field(max_length=60, description="Shown in the black title bar, about 26 characters fit")],
        text: Annotated[str, Field(max_length=500, description="Up to 4 lines of about 24 characters (~90 in total); the rest is cut off")],
        hold_minutes: HoldMinutes = None,
    ) -> list:
        """Show a short note: a title bar with the current time and up to 4 lines of
        large text. For anything longer or structured use show_layout."""
        img, warnings = gen.render_message(title, text, datetime.now().strftime("%H:%M"))
        await push(img, {"kind": "message", "name": title}, hold_minutes)
        return result(img, f"Message shown. {stays_up(hold_minutes)}", warnings)

    @mcp.tool(annotations=READ_ONLY)
    async def preview_layout(blocks: Blocks) -> list:
        """Render a layout without sending it, to check that everything fits."""
        img, warnings = render_layout(blocks, gen)
        return result(img, "Layout preview (not sent to the display).", warnings)

    @mcp.tool(annotations=CHANGES_DISPLAY)
    async def show_layout(blocks: Blocks, hold_minutes: HoldMinutes = None) -> list:
        """Show a custom screen built from blocks: header, text, big_number, list,
        kv (label/value rows), progress, divider, spacer."""
        img, warnings = render_layout(blocks, gen)
        await push(img, {"kind": "layout", "name": layout_name(blocks)}, hold_minutes)
        return result(img, f"Layout shown. {stays_up(hold_minutes)}", warnings)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True))
    async def show_image(
        url: Annotated[str, Field(description="Public https:// URL of a PNG, JPEG, GIF or WebP image (at most 5 MB)")],
        hold_minutes: HoldMinutes = None,
    ) -> list:
        """Show a picture from the web, scaled to fit and dithered to black and white.
        Photos lose a lot of detail; simple, high-contrast images work best."""
        data = await fetch_public_image(url)
        try:
            with PILImage.open(io.BytesIO(data)) as probe:
                if probe.width * probe.height > 40_000_000:
                    raise ToolError("The image is too large (over 40 megapixels)")
            img = gen.fit_image(data)
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"Not an image the server can read: {e}") from e
        await push(img, {"kind": "image", "name": url.rsplit("/", 1)[-1][:40] or "Image"}, hold_minutes)
        return result(img, f"Image shown. {stays_up(hold_minutes)}")

    # --- Notifications -------------------------------------------------------

    @mcp.tool(annotations=CHANGES_DISPLAY)
    async def notify(
        title: Annotated[str, Field(max_length=60, description="About 20 characters are shown")],
        message: Annotated[str, Field(max_length=500, description="About 28 characters are shown in the list")],
        priority: Literal["low", "normal", "high"] = "normal",
        expires_in_minutes: Annotated[Optional[int], Field(gt=0, le=10080, description="Remove it after this long, read or not")] = None,
        show_now: Annotated[bool, Field(description="Show the Notifications scene right away instead of at the next rotation")] = False,
    ) -> list:
        """Add a notification. While there are unread notifications the display shows
        them instead of rotating, so use this for things the owner should act on and
        set expires_in_minutes for anything time-bound. For a passing note use
        show_message."""
        added = NotificationsScene.add_notification(title, message, priority, expires_in_minutes)
        scene = get_scene("notifications")
        warnings = []
        if len(title) > 20:
            warnings.append(f"The display shows the title as '{title[:20]}'")
        if len(message) > 28:
            warnings.append(f"The display shows the message as '{message[:28]}...'")
        if not scene.config.enabled:
            warnings.append("The Notifications scene is off, so it won't appear on the display "
                            "(turn it on with set_scene_enabled)")

        text = f"Notification {added['id']} added, {NotificationsScene.get_unread_count()} unread."
        if show_now:
            img = await scene.generate(gen)
            await push(img, scene_content(scene))
            return result(img, f"{text} Shown now.", warnings)
        manager = ctx.scene_manager()
        if scene.config.enabled and manager.rotation_enabled:
            text += f" It appears at the next rotation, in about {manager.get_status()['next_rotation_in']:.0f} s."
        return ["\n".join([text] + [f"Warning: {w}" for w in warnings])]

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True))
    async def mark_notification_read(notification_id: int) -> str:
        """Mark a notification as read, so it stops taking over the display."""
        if not NotificationsScene.mark_read(notification_id):
            raise ToolError(f"No notification {notification_id}")
        return f"Marked as read, {NotificationsScene.get_unread_count()} unread left."

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True))
    async def clear_notifications() -> str:
        """Delete all notifications, read and unread."""
        NotificationsScene.clear_notifications()
        return "All notifications deleted."

    # --- Rotation ------------------------------------------------------------

    @mcp.tool(annotations=CHANGES_DISPLAY)
    async def control_rotation(
        action: Annotated[Optional[Literal["start", "stop", "next", "prev", "resume"]], Field(
            description="start/stop the automatic rotation, show the next/prev scene now, "
                        "or resume rotating after a hold")] = None,
        interval_seconds: Annotated[Optional[int], Field(ge=10, le=3600, description="New rotation interval")] = None,
    ) -> list:
        """Control the scene rotation. Returns the rotation state."""
        manager = ctx.scene_manager()
        out = []
        if interval_seconds is not None:
            manager.rotation_interval = interval_seconds
            manager.save_config()
            manager.reset_timer()
        if action == "start":
            manager.rotation_enabled = True
            manager.start_rotation()
            manager.save_config()
        elif action == "stop":
            manager.rotation_enabled = False
            manager.stop_rotation()
            manager.save_config()
        elif action == "resume":
            manager.release_hold()
        elif action in ("next", "prev"):
            push_limit.check()
            if action == "next":
                manager.next_scene()
            else:
                manager.prev_scene()
            scene = manager.get_current_scene()
            if scene:
                img = await manager.render_current_scene()
                await push(img, scene_content(scene))
                out.append(Image(data=ctx.png_preview(img), format="png"))
        status = manager.get_status()
        out.append({k: status[k] for k in (
            "rotation_enabled", "rotation_interval", "current_scene", "next_scene",
            "next_rotation_in", "held_until")})
        return out

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True))
    async def set_scene_enabled(
        scene_id: Annotated[str, Field(description="Scene id from list_scenes")],
        enabled: bool,
    ) -> str:
        """Add a scene to the rotation or take it out."""
        scene = get_scene(scene_id)
        ctx.scene_manager().update_scene_config(scene_id, {"enabled": enabled})
        return f"{scene.name} {'added to' if enabled else 'removed from'} the rotation."

    return mcp


# ============================================================================
# HTTP protection
# ============================================================================

class BearerAuth:
    """ASGI wrapper: only requests with "Authorization: Bearer <MCP_TOKEN>" get
    through. Without a token configured the endpoint is off."""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode() if token else None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if self.expected is None:
                response = JSONResponse({"error": "MCP is disabled: set MCP_TOKEN"}, status_code=503)
                return await response(scope, receive, send)
            header = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(header, self.expected):
                response = JSONResponse({"error": "Missing or wrong bearer token"}, status_code=401)
                return await response(scope, receive, send)
        await self.app(scope, receive, send)


class TunnelGuard:
    """ASGI middleware: requests that came through the Cloudflare tunnel (they carry
    Cloudflare's headers) may only reach /mcp/. The dashboard and REST API have no
    authentication and stay on the LAN."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            from_tunnel = b"cf-ray" in headers or b"cf-connecting-ip" in headers
            path = scope["path"]
            if from_tunnel and not (path == "/mcp" or path.startswith("/mcp/")):
                return await JSONResponse({"detail": "Not Found"}, status_code=404)(scope, receive, send)
        await self.app(scope, receive, send)
