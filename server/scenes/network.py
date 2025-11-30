"""
Network Scene - Display OctoPrint status
"""

import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class NetworkScene(Scene):
    """Display OctoPrint printer status"""
    
    id = "network"
    name = "OctoPrint"
    description = "3D Printer status"
    icon = "🖨️"
    
    settings_schema = [
        {
            'key': 'octoprint_url',
            'label': 'OctoPrint URL',
            'type': 'text',
            'default': 'http://192.168.1.188',
            'description': 'OctoPrint server URL'
        },
        {
            'key': 'octoprint_api_key',
            'label': 'OctoPrint API Key',
            'type': 'password',
            'default': '',
            'description': 'From OctoPrint Settings > API'
        },
    ]
    
    async def fetch_data(self) -> dict:
        """Fetch OctoPrint status"""
        url = self.config.settings.get('octoprint_url', 'http://192.168.1.188')
        api_key = self.config.settings.get('octoprint_api_key', '')
        
        return await self._check_octoprint(url, api_key)
    
    async def _check_octoprint(self, url: str, api_key: str) -> dict:
        """Get detailed OctoPrint status"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if api_key:
                    headers['X-Api-Key'] = api_key
                
                # Get printer state and temperatures
                printer_resp = await client.get(f"{url}/api/printer", headers=headers)
                
                if printer_resp.status_code == 200:
                    printer = printer_resp.json()
                    
                    # Temperatures
                    temps = printer.get('temperature', {})
                    tool0 = temps.get('tool0', {})
                    bed = temps.get('bed', {})
                    
                    nozzle_actual = tool0.get('actual', 0)
                    nozzle_target = tool0.get('target', 0)
                    bed_actual = bed.get('actual', 0)
                    bed_target = bed.get('target', 0)
                    
                    # Printer state
                    state = printer.get('state', {})
                    state_text = state.get('text', 'Unknown')
                    is_printing = state.get('flags', {}).get('printing', False)
                    
                    # Get job info
                    job_resp = await client.get(f"{url}/api/job", headers=headers)
                    job_data = {}
                    if job_resp.status_code == 200:
                        job_data = job_resp.json()
                    
                    progress = job_data.get('progress', {})
                    completion = progress.get('completion', 0) or 0
                    print_time = progress.get('printTime', 0) or 0
                    print_time_left = progress.get('printTimeLeft', 0) or 0
                    
                    job = job_data.get('job', {})
                    file_name = job.get('file', {}).get('name', '')
                    
                    return {
                        'status': 'online',
                        'state': state_text,
                        'is_printing': is_printing,
                        'nozzle_temp': nozzle_actual,
                        'nozzle_target': nozzle_target,
                        'bed_temp': bed_actual,
                        'bed_target': bed_target,
                        'progress': completion,
                        'print_time': print_time,
                        'time_left': print_time_left,
                        'file_name': file_name,
                    }
                
                elif printer_resp.status_code == 409:
                    # Printer not connected
                    return {
                        'status': 'online',
                        'state': 'Disconnected',
                        'is_printing': False,
                    }
                else:
                    return {
                        'status': 'error',
                        'state': f'HTTP {printer_resp.status_code}',
                    }
                    
        except httpx.ConnectError:
            return {'status': 'offline', 'state': 'Unreachable'}
        except Exception as e:
            return {'status': 'error', 'state': str(e)[:20]}
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds to HH:MM"""
        if not seconds:
            return "--:--"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render OctoPrint status"""
        img = generator.create_blank()
        generator.draw_header(img, "OctoPrint")
        
        draw = ImageDraw.Draw(img)
        
        font_label = generator.get_font(12, "medium")
        font_temp = generator.get_font(18, "mono")
        font_big = generator.get_font(32, "mono")
        font_time = generator.get_font(14, "mono")
        font_file = generator.get_font(11, "medium")
        
        status = data.get('status', 'unknown')
        state = data.get('state', 'Unknown')
        
        if status != 'online' or state == 'Disconnected':
            draw.text((6, 50), "Offline", font=font_big, fill=0)
            return img
        
        y = 24
        
        # Temperatures - two columns
        nozzle = data.get('nozzle_temp', 0)
        nozzle_t = data.get('nozzle_target', 0)
        bed = data.get('bed_temp', 0)
        bed_t = data.get('bed_target', 0)
        
        # Nozzle (left side)
        draw.text((6, y), "Nozzle", font=font_label, fill=0)
        nozzle_str = f"{nozzle:.0f}"
        if nozzle_t > 0:
            nozzle_str += f"/{nozzle_t:.0f}"
        draw.text((6, y + 12), nozzle_str, font=font_temp, fill=0)
        
        # Bed (right side)
        draw.text((130, y), "Bed", font=font_label, fill=0)
        bed_str = f"{bed:.0f}"
        if bed_t > 0:
            bed_str += f"/{bed_t:.0f}"
        draw.text((130, y + 12), bed_str, font=font_temp, fill=0)
        
        y += 36
        
        # If printing - show progress
        if data.get('is_printing', False):
            progress = data.get('progress', 0)
            time_left = data.get('time_left', 0)
            
            # Progress percentage - big (left)
            draw.text((6, y), f"{progress:.0f}%", font=font_big, fill=0)
            
            # Time left (right)
            time_str = self._format_time(time_left)
            draw.text((130, y + 4), "Left", font=font_label, fill=0)
            draw.text((130, y + 16), time_str, font=font_time, fill=0)
            
            y += 38
            
            # Progress bar
            bar_x = 6
            bar_y = y
            bar_w = generator.width - 12
            bar_h = 8
            
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=0, width=1)
            fill_w = int((progress / 100) * (bar_w - 2))
            if fill_w > 0:
                draw.rectangle([bar_x + 1, bar_y + 1, bar_x + 1 + fill_w, bar_y + bar_h - 1], fill=0)
            
            y += 12
            
            # File name
            file_name = data.get('file_name', '')
            if file_name:
                if len(file_name) > 30:
                    file_name = file_name[:27] + "..."
                draw.text((6, y), file_name, font=font_file, fill=0)
        else:
            # Not printing
            draw.text((6, y + 5), "Ready", font=font_big, fill=0)
        
        return img
