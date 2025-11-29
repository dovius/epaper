"""
Base Scene class and configuration
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from PIL import Image


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
    
    def __init__(self, config: Optional[SceneConfig] = None):
        self.config = config or SceneConfig()
        self._last_data: Optional[dict] = None
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
            self._last_data = data
            self._last_error = None
            return self.render(data, generator)
        except Exception as e:
            self._last_error = str(e)
            # Render error state
            return self._render_error(generator, str(e))
    
    def _render_error(self, generator: Any, error: str) -> Image.Image:
        """Render error state"""
        img = generator.create_blank()
        generator.draw_header(img, f"⚠️ {self.name}")
        generator.draw_text(img, "Error:", 8, 32, font_size=12)
        
        # Word wrap error message
        words = error.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if len(test) < 28:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        
        y = 48
        for line in lines[:4]:
            generator.draw_text(img, line, 8, y, font_size=10)
            y += 14
        
        return img
    
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
        }

