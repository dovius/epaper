"""
Base Scene class and configuration
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from PIL import Image

from layout import wrap_text

logger = logging.getLogger(__name__)


@dataclass
class SceneConfig:
    """Configuration for a scene"""
    enabled: bool = True
    interval: int = 60  # seconds between updates when active
    priority: int = 10  # lower = higher priority
    settings: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'interval': self.interval,
            'priority': self.priority,
            'settings': self.settings,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SceneConfig':
        return cls(
            enabled=data.get('enabled', True),
            interval=data.get('interval', 60),
            priority=data.get('priority', 10),
            settings=data.get('settings', {}),
        )


class Scene(ABC):
    """Base class for all scenes"""
    
    # Scene metadata - override in subclasses
    id: str = "base"
    name: str = "Base Scene"
    description: str = "Base scene class"
    icon: str = "📺"
    
    # Default settings schema for UI
    settings_schema: list[dict] = []
    
    # Where scenes keep runtime state (next to scene_config.json, set by SceneManager)
    data_dir: Path = Path(__file__).parent.parent
    
    def __init__(self, config: Optional[SceneConfig] = None):
        self.config = config or SceneConfig()
        self._last_data: Optional[dict] = None
        self._last_data_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
    
    @abstractmethod
    async def fetch_data(self) -> dict:
        """Fetch data needed for rendering. Override in subclasses."""
        pass
    
    @abstractmethod
    def render(self, data: dict, generator: Any) -> Image.Image:
        """Render the scene to an image. Override in subclasses."""
        pass
    
    async def generate(self, generator: Any) -> Image.Image:
        """Fetch data and render the scene"""
        try:
            data = await self.fetch_data()
            img = self.render(data, generator)
            self._last_data = data
            self._last_data_at = datetime.now()
            self._last_error = None
            return img
        except Exception as e:
            self._last_error = str(e)
            # APIs fail now and then (e.g. a 503 for a few seconds): keep
            # showing the last good data instead of an error screen. The
            # error still shows up in the web UI via last_error.
            if self._last_data is not None:
                logger.warning(f"{self.name}: {e}, showing last good data")
                try:
                    return self.render(self._last_data, generator)
                except Exception:
                    pass
            # Render error state
            return self._render_error(generator, str(e))
    
    async def render_cached(self, generator: Any) -> Image.Image:
        """Render the last fetched data again (cheap thumbnails), fetch if none yet"""
        if self._last_data is not None:
            try:
                return self.render(self._last_data, generator)
            except Exception:
                pass
        return await self.generate(generator)
    
    def _render_error(self, generator: Any, error: str) -> Image.Image:
        """Render error state"""
        img = generator.create_blank()
        generator.draw_header(img, f"{self.name}")
        generator.draw_text(img, "Error:", 8, 30, font_size=16, style="bold")
        
        lines = wrap_text(error, generator.get_font(14, "medium"), generator.width - 16)
        y = 50
        for line in lines[:4]:
            generator.draw_text(img, line, 8, y, font_size=14, style="medium")
            y += 18
        
        return img
    
    @classmethod
    def load_state(cls, name: str, default: Any = None) -> Any:
        """Read a JSON state file from data_dir"""
        path = cls.data_dir / name
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return default
    
    @classmethod
    def save_state(cls, name: str, data: Any):
        """Write a JSON state file to data_dir (atomically, like the scene config)"""
        path = cls.data_dir / name
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.tmp')
            with open(tmp, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")
    
    def get_info(self) -> dict:
        """Get scene info for API"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'config': self.config.to_dict(),
            'settings_schema': self.settings_schema,
            'last_error': self._last_error,
            'last_data_at': self._last_data_at.isoformat(timespec='seconds') if self._last_data_at else None,
        }

