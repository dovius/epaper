"""
Scene Manager
=============
Manages scene rotation, configuration, and display updates.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PIL import Image

from scenes import (
    Scene,
    SceneConfig,
    StocksScene,
    BitcoinScene,
    WeatherScene,
    NotificationsScene,
    NetworkScene,
    SystemScene,
    AgentScene,
    DigestScene,
)

logger = logging.getLogger(__name__)


class SceneManager:
    """Manages all scenes and rotation"""
    
    # Holds API keys, so it's gitignored. In Docker point SCENE_CONFIG at a
    # mounted directory (see docker-compose.yml).
    CONFIG_FILE = Path(os.environ.get("SCENE_CONFIG", Path(__file__).parent / "scene_config.json"))
    
    def __init__(self, generator):
        self.generator = generator
        self.scenes: dict[str, Scene] = {}
        self.rotation_order: list[str] = []
        self.current_scene_idx: int = 0
        self.rotation_enabled: bool = True
        self.rotation_interval: int = 60  # seconds
        self._rotation_task: Optional[asyncio.Task] = None
        self._timer_reset = asyncio.Event()
        self._next_rotation: Optional[datetime] = None
        self._last_update: Optional[datetime] = None
        self._send_callback = None
        # A manually sent image stays up until then (see hold())
        self.hold_until: Optional[datetime] = None
        
        # Scenes keep their runtime state next to the config
        Scene.data_dir = self.CONFIG_FILE.parent
        NotificationsScene.load()
        
        # Initialize all available scenes
        self._init_scenes()
        self._load_config()
    
    def _init_scenes(self):
        """Initialize all available scenes with default configs"""
        scene_classes = [
            StocksScene,
            BitcoinScene,
            WeatherScene,
            NotificationsScene,
            NetworkScene,
            SystemScene,
            AgentScene,
            DigestScene,
        ]
        
        for cls in scene_classes:
            scene = cls()
            self.scenes[scene.id] = scene
            self.rotation_order.append(scene.id)
    
    def _load_config(self):
        """Load configuration from file"""
        if not self.CONFIG_FILE.exists():
            return
        
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # Load global settings
            self.rotation_enabled = config.get('rotation_enabled', True)
            self.rotation_interval = config.get('rotation_interval', 60)
            saved_order = config.get('rotation_order', self.rotation_order)
            # Scenes added since the config was saved go at the end
            self.rotation_order = saved_order + [sid for sid in self.rotation_order if sid not in saved_order]
            self.current_scene_idx = config.get('current_scene_idx', 0)
            
            # Load scene configs
            scenes_config = config.get('scenes', {})
            for scene_id, scene_config in scenes_config.items():
                if scene_id in self.scenes:
                    self.scenes[scene_id].config = SceneConfig.from_dict(scene_config)
            
            logger.info(f"Loaded scene config from {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to load scene config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        config = {
            'rotation_enabled': self.rotation_enabled,
            'rotation_interval': self.rotation_interval,
            'rotation_order': self.rotation_order,
            'current_scene_idx': self.current_scene_idx,
            'scenes': {
                scene_id: scene.config.to_dict()
                for scene_id, scene in self.scenes.items()
            }
        }
        
        try:
            self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Write to a temp file and swap it in, so a crash mid-write can't
            # leave a truncated config (and lose the API keys)
            tmp_file = self.CONFIG_FILE.with_name(self.CONFIG_FILE.name + '.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(config, f, indent=2)
            os.replace(tmp_file, self.CONFIG_FILE)
            logger.info(f"Saved scene config to {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save scene config: {e}")
    
    def set_send_callback(self, callback):
        """Set callback for sending images to display"""
        self._send_callback = callback
    
    def get_enabled_scenes(self) -> list[str]:
        """Get list of enabled scene IDs in rotation order"""
        return [
            sid for sid in self.rotation_order
            if sid in self.scenes and self.scenes[sid].config.enabled
        ]
    
    def get_current_scene(self) -> Optional[Scene]:
        """Get current scene based on rotation index"""
        enabled = self.get_enabled_scenes()
        if not enabled:
            return None
        
        # Handle notifications priority
        priority = self._priority_scene()
        if priority:
            return priority
        
        idx = self.current_scene_idx % len(enabled)
        return self.scenes.get(enabled[idx])
    
    def get_next_scene(self) -> Optional[Scene]:
        """Get the scene the rotation will show next"""
        enabled = self.get_enabled_scenes()
        if not enabled:
            return None
        
        priority = self._priority_scene()
        if priority:
            return priority
        
        idx = (self.current_scene_idx + 1) % len(enabled)
        return self.scenes.get(enabled[idx])
    
    def _priority_scene(self) -> Optional[Scene]:
        """Notifications take over the display while there are unread ones"""
        notif_scene = self.scenes.get('notifications')
        if notif_scene and notif_scene.config.enabled and NotificationsScene.has_notifications():
            return notif_scene
        return None
    
    async def render_current_scene(self) -> Optional[Image.Image]:
        """Render the current scene"""
        scene = self.get_current_scene()
        if not scene:
            return None
        
        logger.info(f"Rendering scene: {scene.name}")
        return await scene.generate(self.generator)
    
    async def render_scene(self, scene_id: str) -> Optional[Image.Image]:
        """Render a specific scene by ID"""
        if scene_id not in self.scenes:
            return None
        
        return await self.scenes[scene_id].generate(self.generator)
    
    def next_scene(self) -> str:
        """Move to next scene in rotation"""
        enabled = self.get_enabled_scenes()
        if enabled:
            self.current_scene_idx = (self.current_scene_idx + 1) % len(enabled)
            self.save_config()
        return self.get_current_scene().id if self.get_current_scene() else ""
    
    def prev_scene(self) -> str:
        """Move to previous scene in rotation"""
        enabled = self.get_enabled_scenes()
        if enabled:
            self.current_scene_idx = (self.current_scene_idx - 1) % len(enabled)
            self.save_config()
        return self.get_current_scene().id if self.get_current_scene() else ""
    
    def set_scene(self, scene_id: str) -> bool:
        """Set current scene by ID"""
        enabled = self.get_enabled_scenes()
        if scene_id in enabled:
            self.current_scene_idx = enabled.index(scene_id)
            self.save_config()
            return True
        return False
    
    def update_scene_config(self, scene_id: str, config_data: dict) -> bool:
        """Update configuration for a specific scene"""
        if scene_id not in self.scenes:
            return False
        
        scene = self.scenes[scene_id]
        
        if 'enabled' in config_data:
            scene.config.enabled = config_data['enabled']
        if 'interval' in config_data:
            scene.config.interval = config_data['interval']
        if 'priority' in config_data:
            scene.config.priority = config_data['priority']
        if 'settings' in config_data:
            scene.config.settings.update(config_data['settings'])
        
        self.save_config()
        return True
    
    def update_rotation_order(self, order: list[str]) -> bool:
        """Update scene rotation order"""
        # Validate all IDs exist
        if not all(sid in self.scenes for sid in order):
            return False
        
        self.rotation_order = order
        self.save_config()
        return True
    
    def reset_timer(self):
        """Restart the rotation countdown (manual display change, new interval)"""
        self._timer_reset.set()
    
    def hold(self, minutes: Optional[float] = None):
        """Keep a manually sent image up for minutes, or one rotation interval (None)"""
        self.hold_until = datetime.now() + timedelta(minutes=minutes) if minutes else None
        self.reset_timer()
    
    def release_hold(self):
        """End a hold: rotation continues one interval from now"""
        self.hold(None)
    
    async def _rotation_loop(self):
        """Background rotation loop"""
        while True:
            try:
                self._timer_reset.clear()
                # A full interval, or until the hold ends
                wait = self.rotation_interval
                if self.hold_until:
                    wait = max(1.0, (self.hold_until - datetime.now()).total_seconds())
                self._next_rotation = datetime.now() + timedelta(seconds=wait)
                try:
                    await asyncio.wait_for(self._timer_reset.wait(), wait)
                    continue  # Timer was reset, start counting again
                except asyncio.TimeoutError:
                    pass
                self.hold_until = None
                
                if not self.rotation_enabled:
                    continue
                
                self.next_scene()
                
                if self._send_callback:
                    scene = self.get_current_scene()
                    img = await self.render_current_scene()
                    # Don't overwrite an image sent manually while rendering
                    if img and not self._timer_reset.is_set():
                        raw = self.generator.to_raw_bytes(img)
                        try:
                            content = {'kind': 'scene', 'name': scene.name, 'scene_id': scene.id,
                                       'source': 'rotation'}
                            await self._send_callback(raw, content)
                            self._last_update = datetime.now()
                        except Exception as e:
                            logger.error(f"Failed to send scene: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rotation loop error: {e}")
    
    def start_rotation(self):
        """Start automatic scene rotation"""
        if self._rotation_task is None or self._rotation_task.done():
            self._rotation_task = asyncio.create_task(self._rotation_loop())
            logger.info("Scene rotation started")
    
    def stop_rotation(self):
        """Stop automatic scene rotation"""
        if self._rotation_task:
            self._rotation_task.cancel()
            self._rotation_task = None
            self._next_rotation = None
            logger.info("Scene rotation stopped")
    
    def get_status(self) -> dict:
        """Get manager status for API"""
        current = self.get_current_scene()
        upcoming = self.get_next_scene()
        
        # Seconds until the next automatic change (None when rotation is off)
        next_in = None
        if self.rotation_enabled and self._next_rotation:
            next_in = round(max(0.0, (self._next_rotation - datetime.now()).total_seconds()), 1)
        
        return {
            'rotation_enabled': self.rotation_enabled,
            'rotation_interval': self.rotation_interval,
            'current_scene': current.id if current else None,
            'current_scene_name': current.name if current else None,
            'enabled_scenes': self.get_enabled_scenes(),
            'rotation_order': self.rotation_order,
            'last_update': self._last_update.isoformat() if self._last_update else None,
            'next_scene': upcoming.id if upcoming else None,
            'next_scene_name': upcoming.name if upcoming else None,
            'next_rotation_in': next_in,
            'held_until': self.hold_until.isoformat(timespec='seconds') if self.hold_until else None,
        }
    
    def get_all_scenes_info(self) -> list[dict]:
        """Get info for all scenes"""
        return [
            {
                **scene.get_info(),
                'in_rotation': scene.id in self.rotation_order,
                'rotation_index': self.rotation_order.index(scene.id) if scene.id in self.rotation_order else -1,
            }
            for scene in self.scenes.values()
        ]

