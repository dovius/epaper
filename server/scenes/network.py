"""
Network Scene - Display OctoPrint and TrueNAS status
"""

import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class NetworkScene(Scene):
    """Display network service status (OctoPrint, TrueNAS)"""
    
    id = "network"
    name = "Network Services"
    description = "Monitor OctoPrint and TrueNAS status"
    icon = "🖧"
    
    settings_schema = [
        {
            'key': 'octoprint_url',
            'label': 'OctoPrint URL',
            'type': 'text',
            'default': 'http://octopi.local',
            'description': 'OctoPrint server URL'
        },
        {
            'key': 'octoprint_api_key',
            'label': 'OctoPrint API Key',
            'type': 'password',
            'default': '',
        },
        {
            'key': 'truenas_url',
            'label': 'TrueNAS URL',
            'type': 'text',
            'default': 'http://truenas.local',
            'description': 'TrueNAS server URL'
        },
        {
            'key': 'truenas_api_key',
            'label': 'TrueNAS API Key',
            'type': 'password',
            'default': '',
        },
    ]
    
    async def fetch_data(self) -> dict:
        """Fetch status from OctoPrint and TrueNAS"""
        octoprint_url = self.config.settings.get('octoprint_url', 'http://octopi.local')
        octoprint_key = self.config.settings.get('octoprint_api_key', '')
        truenas_url = self.config.settings.get('truenas_url', 'http://truenas.local')
        truenas_key = self.config.settings.get('truenas_api_key', '')
        
        result = {
            'octoprint': await self._check_octoprint(octoprint_url, octoprint_key),
            'truenas': await self._check_truenas(truenas_url, truenas_key),
        }
        
        return result
    
    async def _check_octoprint(self, url: str, api_key: str) -> dict:
        """Check OctoPrint status"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if api_key:
                    headers['X-Api-Key'] = api_key
                
                # Check connection
                resp = await client.get(f"{url}/api/connection", headers=headers)
                
                if resp.status_code == 200:
                    conn_data = resp.json()
                    state = conn_data.get('current', {}).get('state', 'Unknown')
                    
                    # Check printer status
                    job_resp = await client.get(f"{url}/api/job", headers=headers)
                    job_data = {}
                    if job_resp.status_code == 200:
                        job_data = job_resp.json()
                    
                    job_state = job_data.get('state', 'Idle')
                    progress = job_data.get('progress', {}).get('completion', 0)
                    
                    return {
                        'status': 'online',
                        'code': resp.status_code,
                        'state': state,
                        'job_state': job_state,
                        'progress': progress or 0,
                    }
                else:
                    return {
                        'status': 'error',
                        'code': resp.status_code,
                        'state': 'HTTP Error',
                    }
        except httpx.ConnectError:
            return {'status': 'offline', 'code': 0, 'state': 'Unreachable'}
        except Exception as e:
            return {'status': 'error', 'code': 0, 'state': str(e)[:20]}
    
    async def _check_truenas(self, url: str, api_key: str) -> dict:
        """Check TrueNAS status"""
        try:
            async with httpx.AsyncClient(timeout=5, verify=False) as client:
                headers = {}
                if api_key:
                    headers['Authorization'] = f'Bearer {api_key}'
                
                # Check system info
                resp = await client.get(f"{url}/api/v2.0/system/info", headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # Get pool status
                    pool_resp = await client.get(f"{url}/api/v2.0/pool", headers=headers)
                    pools = []
                    if pool_resp.status_code == 200:
                        pool_data = pool_resp.json()
                        for pool in pool_data[:2]:  # Max 2 pools
                            pools.append({
                                'name': pool.get('name', 'Unknown'),
                                'status': pool.get('status', 'Unknown'),
                            })
                    
                    return {
                        'status': 'online',
                        'code': resp.status_code,
                        'hostname': data.get('hostname', 'TrueNAS'),
                        'version': data.get('version', 'Unknown'),
                        'pools': pools,
                    }
                else:
                    return {
                        'status': 'error',
                        'code': resp.status_code,
                        'state': 'HTTP Error',
                    }
        except httpx.ConnectError:
            return {'status': 'offline', 'code': 0, 'state': 'Unreachable'}
        except Exception as e:
            return {'status': 'error', 'code': 0, 'state': str(e)[:20]}
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render network service status"""
        img = generator.create_blank()
        generator.draw_header(img, "🖧 Network")
        
        draw = ImageDraw.Draw(img)
        
        font_label = generator.get_font(12)
        font_value = generator.get_font(10)
        font_small = generator.get_font(9)
        
        y = 30
        
        # OctoPrint
        octo = data.get('octoprint', {})
        draw.text((8, y), "OctoPrint", font=font_label, fill=0)
        
        status = octo.get('status', 'unknown')
        status_icon = "●" if status == 'online' else "○"
        status_text = f"{status_icon} {status.upper()}"
        draw.text((100, y), status_text, font=font_value, fill=0)
        
        if status == 'online':
            state = octo.get('state', '')
            job = octo.get('job_state', '')
            progress = octo.get('progress', 0)
            
            y += 14
            draw.text((12, y), f"Printer: {state}", font=font_small, fill=0)
            
            if job and job != 'Idle':
                y += 12
                draw.text((12, y), f"Job: {job} ({progress:.0f}%)", font=font_small, fill=0)
        
        y += 22
        
        # Separator
        draw.line([(8, y), (generator.width - 8, y)], fill=0, width=1)
        y += 8
        
        # TrueNAS
        truenas = data.get('truenas', {})
        draw.text((8, y), "TrueNAS", font=font_label, fill=0)
        
        status = truenas.get('status', 'unknown')
        status_icon = "●" if status == 'online' else "○"
        status_text = f"{status_icon} {status.upper()}"
        draw.text((100, y), status_text, font=font_value, fill=0)
        
        if status == 'online':
            hostname = truenas.get('hostname', '')
            pools = truenas.get('pools', [])
            
            y += 14
            if hostname:
                draw.text((12, y), f"Host: {hostname}", font=font_small, fill=0)
            
            for pool in pools:
                y += 12
                name = pool.get('name', '')
                pstatus = pool.get('status', '')
                draw.text((12, y), f"Pool {name}: {pstatus}", font=font_small, fill=0)
        
        return img

