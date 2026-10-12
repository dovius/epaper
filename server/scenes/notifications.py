"""
Notifications Scene - Display pending notifications
"""

from datetime import datetime, timedelta
from typing import Optional
from PIL import Image, ImageDraw

from layout import clean_text
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
    
    # Class-level notification storage, kept in notifications.json so it
    # survives restarts. Ids keep counting up, also after a clear.
    STATE_FILE = "notifications.json"
    _notifications: list[dict] = []
    _next_id: int = 0
    
    @classmethod
    def load(cls):
        """Load saved notifications (called once by SceneManager)"""
        state = cls.load_state(cls.STATE_FILE, {})
        cls._notifications = state.get('notifications', [])
        cls._next_id = state.get('next_id', max((n['id'] for n in cls._notifications), default=-1) + 1)
        cls._prune()
    
    @classmethod
    def _save(cls):
        cls.save_state(cls.STATE_FILE, {'next_id': cls._next_id, 'notifications': cls._notifications})
    
    @classmethod
    def _prune(cls):
        """Drop expired notifications"""
        now = datetime.now().isoformat()
        active = [n for n in cls._notifications if not n.get('expires_at') or n['expires_at'] > now]
        if len(active) != len(cls._notifications):
            cls._notifications = active
            cls._save()
    
    @classmethod
    def add_notification(cls, title: str, message: str, priority: str = "normal",
                         expires_in_minutes: Optional[int] = None) -> dict:
        """Add a notification. With expires_in_minutes it disappears after that,
        read or not."""
        now = datetime.now()
        notification = {
            'id': cls._next_id,
            'title': title,
            'message': message,
            'priority': priority,  # low, normal, high
            'timestamp': now.isoformat(),
            'expires_at': (now + timedelta(minutes=expires_in_minutes)).isoformat() if expires_in_minutes else None,
            'read': False,
        }
        cls._next_id += 1
        cls._notifications.append(notification)
        cls._save()
        return notification
    
    @classmethod
    def get_notifications(cls) -> list[dict]:
        """All notifications that haven't expired, read ones included"""
        cls._prune()
        return cls._notifications
    
    @classmethod
    def clear_notifications(cls):
        """Clear all notifications"""
        cls._notifications = []
        cls._save()
    
    @classmethod
    def mark_read(cls, notification_id: int) -> bool:
        """Mark notification as read. False if there is no such notification."""
        for n in cls._notifications:
            if n['id'] == notification_id:
                n['read'] = True
                cls._save()
                return True
        return False
    
    @classmethod
    def get_unread_count(cls) -> int:
        """Get count of unread notifications"""
        return sum(1 for n in cls.get_notifications() if not n.get('read', False))
    
    @classmethod
    def has_notifications(cls) -> bool:
        """Check if there are any unread notifications"""
        return cls.get_unread_count() > 0
    
    async def fetch_data(self) -> dict:
        """Get current notifications"""
        max_count = self.config.settings.get('max_notifications', 5)
        
        # Get unread notifications, sorted by timestamp (newest first)
        unread = [n for n in self.get_notifications() if not n.get('read', False)]
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
            
            # Emoji etc. would be drawn as boxes
            title = clean_text(title, font_title)[0]
            message = clean_text(message, font_msg)[0]
            
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
            
            # Separator line (below the message text, not through it)
            if y < generator.height - 20:
                draw.line([(8, y - 1), (generator.width - 8, y - 1)], fill=0, width=1)
            
            if y > generator.height - 20:
                break
        
        return img

