"""
System Scene - Display device uptime and current time
"""

from datetime import datetime
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class SystemScene(Scene):
    """Display system uptime and current time"""
    
    id = "system"
    name = "System Info"
    description = "Display device uptime and current time"
    icon = "⏱️"
    
    settings_schema = [
        {
            'key': 'time_format',
            'label': 'Time Format',
            'type': 'select',
            'options': ['24h', '12h'],
            'default': '24h',
        },
        {
            'key': 'show_seconds',
            'label': 'Show Seconds',
            'type': 'checkbox',
            'default': False,
        },
        {
            'key': 'show_date',
            'label': 'Show Date',
            'type': 'checkbox',
            'default': True,
        }
    ]
    
    # Track when the server started
    _start_time: datetime = None
    
    @classmethod
    def init_start_time(cls):
        """Initialize start time"""
        if cls._start_time is None:
            cls._start_time = datetime.now()
    
    @classmethod
    def get_uptime(cls) -> str:
        """Get formatted uptime string"""
        if cls._start_time is None:
            return "0s"
        
        delta = datetime.now() - cls._start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts[:3])  # Max 3 parts
    
    async def fetch_data(self) -> dict:
        """Get current time and uptime"""
        self.init_start_time()
        
        now = datetime.now()
        time_format = self.config.settings.get('time_format', '24h')
        show_seconds = self.config.settings.get('show_seconds', False)
        
        if time_format == '24h':
            fmt = "%H:%M:%S" if show_seconds else "%H:%M"
        else:
            fmt = "%I:%M:%S %p" if show_seconds else "%I:%M %p"
        
        return {
            'time': now.strftime(fmt),
            'date': now.strftime("%Y-%m-%d"),
            'weekday': now.strftime("%A"),
            'weekday_lt': self._get_weekday_lt(now.weekday()),
            'uptime': self.get_uptime(),
            'start_time': self._start_time.strftime("%Y-%m-%d %H:%M") if self._start_time else '',
        }
    
    def _get_weekday_lt(self, weekday: int) -> str:
        """Get Lithuanian weekday name"""
        days = [
            "Pirmadienis",
            "Antradienis", 
            "Trečiadienis",
            "Ketvirtadienis",
            "Penktadienis",
            "Šeštadienis",
            "Sekmadienis"
        ]
        return days[weekday] if 0 <= weekday < 7 else ""
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render system info"""
        img = generator.create_blank()
        generator.draw_header(img, "System")
        
        draw = ImageDraw.Draw(img)
        
        font_time = generator.get_font(42, "mono")
        font_weekday = generator.get_font(20, "bold")
        font_date = generator.get_font(16, "mono")
        font_label = generator.get_font(12, "medium")
        font_value = generator.get_font(14, "mono")
        
        # Large time display
        time_str = data.get('time', '00:00')
        draw.text((8, 24), time_str, font=font_time, fill=0)
        
        # Date and weekday
        if self.config.settings.get('show_date', True):
            date_str = data.get('date', '')
            weekday = data.get('weekday_lt', '')
            
            draw.text((8, 66), weekday, font=font_weekday, fill=0)
            # Right-aligned, so long names like "Ketvirtadienis" don't overlap it
            date_x = generator.width - 6 - draw.textlength(date_str, font=font_date)
            draw.text((date_x, 68), date_str, font=font_date, fill=0)
        
        # Uptime section (two rows that must fit above the bottom edge)
        draw.line([(6, 89), (generator.width - 6, 89)], fill=0, width=1)
        
        draw.text((6, 92), "Uptime:", font=font_label, fill=0)
        uptime = data.get('uptime', '')
        draw.text((60, 92), uptime, font=font_value, fill=0)
        
        # Start time
        start = data.get('start_time', '')
        if start:
            draw.text((6, 106), "Start:", font=font_label, fill=0)
            draw.text((60, 106), start, font=font_value, fill=0)
        
        return img

