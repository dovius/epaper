#!/usr/bin/env python3
"""
E-Paper Display Client
======================
Simple client for testing and controlling the e-paper display via HTTP API.

Usage:
    python epaper_client.py status
    python epaper_client.py clear
    python epaper_client.py text "Hello World"
    python epaper_client.py image path/to/image.png
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
    from PIL import Image
except ImportError:
    sys.exit("Missing packages, install them with: pip install requests Pillow")


# Display configuration
DISPLAY_WIDTH = 122
DISPLAY_HEIGHT = 250
FRAME_BUFFER_SIZE = ((DISPLAY_WIDTH + 7) // 8) * DISPLAY_HEIGHT  # 4000 bytes


class EPaperClient:
    def __init__(self, host: str = "epaper.local", port: int = 80):
        self.base_url = f"http://{host}:{port}"
        self.timeout = 30
    
    def status(self) -> dict:
        """Get device status"""
        r = requests.get(f"{self.base_url}/api/status", timeout=self.timeout)
        r.raise_for_status()
        return r.json()
    
    def clear(self, color: str = "white") -> dict:
        """Clear display"""
        r = requests.post(
            f"{self.base_url}/api/display/clear",
            data={"color": color},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()
    
    def text(self, text: str, x: int = 10, y: int = 40, font_size: int = 12) -> dict:
        """Draw text on display"""
        r = requests.post(
            f"{self.base_url}/api/display/text",
            json={"text": text, "x": x, "y": y, "fontSize": font_size},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()
    
    def refresh(self, mode: str = "full") -> dict:
        """Force display refresh"""
        r = requests.post(
            f"{self.base_url}/api/display/refresh",
            data={"mode": mode},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()
    
    def send_raw_image(self, data: bytes) -> dict:
        """Send raw 1-bit bitmap data"""
        if len(data) != FRAME_BUFFER_SIZE:
            raise ValueError(f"Invalid data size: {len(data)}, expected {FRAME_BUFFER_SIZE}")
        
        r = requests.post(
            f"{self.base_url}/api/display/raw",
            data=data,
            headers={"Content-Type": "application/octet-stream"},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()
    
    def send_image(self, image_path: str) -> dict:
        """Convert and send an image file"""
        img = Image.open(image_path)
        raw_data = self.image_to_raw(img)
        return self.send_raw_image(raw_data)
    
    @staticmethod
    def image_to_raw(img: Image.Image) -> bytes:
        """Convert PIL Image to raw 1-bit bitmap for e-paper"""
        # Resize to display dimensions (rotated: 250x122 -> 122x250)
        img = img.resize((DISPLAY_HEIGHT, DISPLAY_WIDTH), Image.Resampling.LANCZOS)
        
        # Rotate clockwise into the panel's portrait frame (same as the server,
        # rotating the other way shows the image upside down)
        img = img.rotate(-90, expand=True)
        
        # Convert to 1-bit (black and white)
        img = img.convert('1')
        
        # Mode '1' packs each row MSB-first, padded to whole bytes, 1 = white:
        # the same layout as the e-paper frame buffer
        return img.tobytes()


def main():
    parser = argparse.ArgumentParser(description="E-Paper Display Client")
    parser.add_argument("--host", default="epaper.local", help="Device hostname or IP")
    parser.add_argument("--port", type=int, default=80, help="HTTP port")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Status command
    subparsers.add_parser("status", help="Get device status")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear display")
    clear_parser.add_argument("--color", choices=["white", "black"], default="white")
    
    # Text command
    text_parser = subparsers.add_parser("text", help="Draw text")
    text_parser.add_argument("message", help="Text to display")
    text_parser.add_argument("-x", type=int, default=10, help="X position")
    text_parser.add_argument("-y", type=int, default=40, help="Y position")
    text_parser.add_argument("--font", type=int, default=12, choices=[8, 12, 16, 20, 24])
    
    # Image command
    image_parser = subparsers.add_parser("image", help="Send image file")
    image_parser.add_argument("path", help="Path to image file")
    
    # Refresh command
    refresh_parser = subparsers.add_parser("refresh", help="Force refresh")
    refresh_parser.add_argument("--mode", choices=["full", "fast", "partial"], default="full")
    
    args = parser.parse_args()
    
    client = EPaperClient(args.host, args.port)
    
    try:
        if args.command == "status":
            result = client.status()
            print(json.dumps(result, indent=2))
        
        elif args.command == "clear":
            result = client.clear(args.color)
            print(f"✓ {result.get('message', 'Done')}")
        
        elif args.command == "text":
            result = client.text(args.message, args.x, args.y, args.font)
            print(f"✓ {result.get('message', 'Done')}")
        
        elif args.command == "image":
            print(f"Sending image: {args.path}")
            result = client.send_image(args.path)
            print(f"✓ {result.get('message', 'Done')}")
        
        elif args.command == "refresh":
            result = client.refresh(args.mode)
            print(f"✓ {result.get('message', 'Done')}")
    
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to {args.host}:{args.port}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

