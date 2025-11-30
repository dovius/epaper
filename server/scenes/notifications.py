"""
Notifications Scene - Display pending notifications
"""

from datetime import datetime
from typing import Optional
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class NotificationsScene(Scene):
    """Display notifications"""
    
    id = "notifications"
    name = "Notifications"
    description = "Display pending notifications"
    icon = "🔔"
    
    settings_schema = [
        {
            'key': 'max_notifications',
            'label': 'Max Notifications',
            'type': 'number',
            'default': 5,
            'min': 1,
            'max': 10,
        }
    ]
    
    # Class-level notification storage
    _notifications: list[dict] = []
    
    @classmethod
    def add_notification(cls, title: str, message: str, priority: str = "normal"):
        """Add a notification"""
        cls._notifications.append({
            'id': len(cls._notifications),
            'title': title,
            'message': message,
            'priority': priority,  # low, normal, high
            'timestamp': datetime.now().isoformat(),
            'read': False,
        })
    
    @classmethod
    def clear_notifications(cls):
        """Clear all notifications"""
        cls._notifications = []
    
    @classmethod
    def mark_read(cls, notification_id: int):
        """Mark notification as read"""
        for n in cls._notifications:
            if n['id'] == notification_id:
                n['read'] = True
                break
    
    @classmethod
    def get_unread_count(cls) -> int:
        """Get count of unread notifications"""
        return sum(1 for n in cls._notifications if not n.get('read', False))
    
    @classmethod
    def has_notifications(cls) -> bool:
        """Check if there are any unread notifications"""
        return cls.get_unread_count() > 0
    
    async def fetch_data(self) -> dict:
        """Get current notifications"""
        max_count = self.config.settings.get('max_notifications', 5)
        
        # Get unread notifications, sorted by timestamp (newest first)
        unread = [n for n in self._notifications if not n.get('read', False)]
        unread.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            'notifications': unread[:max_count],
            'total_unread': len(unread),
        }
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render notifications"""
        img = generator.create_blank()
        
        notifications = data.get('notifications', [])
        total = data.get('total_unread', 0)
        
        header = f"Notifications ({total})" if total > 0 else "Notifications"
        generator.draw_header(img, header)
        
        draw = ImageDraw.Draw(img)
        
        if not notifications:
            # No notifications
            font = generator.get_font(18, "medium")
            draw.text((8, 50), "No new notifications", font=font, fill=0)
            return img
        
        font_title = generator.get_font(16, "bold")
        font_msg = generator.get_font(14, "medium")
        font_time = generator.get_font(12, "mono")
        
        y = 26
        
        for notif in notifications:
            title = notif.get('title', 'Notification')
            message = notif.get('message', '')
            timestamp = notif.get('timestamp', '')
            priority = notif.get('priority', 'normal')
            
            # Priority indicator
            if priority == 'high':
                draw.rectangle([4, y + 2, 6, y + 14], fill=0)
            
            # Title
            draw.text((10, y), title[:20], font=font_title, fill=0)
            
            # Message (truncated)
            if message:
                msg_short = message[:28] + '...' if len(message) > 28 else message
                draw.text((10, y + 16), msg_short, font=font_msg, fill=0)
            
            # Time
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%H:%M")
                    draw.text((200, y + 2), time_str, font=font_time, fill=0)
                except:
                    pass
            
            y += 36
            
            # Separator line
            if y < generator.height - 20:
                draw.line([(8, y - 6), (generator.width - 8, y - 6)], fill=0, width=1)
            
            if y > generator.height - 20:
                break
        
        return img

