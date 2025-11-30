"""
Weather Scene - Display weather for Vilnius (today, tomorrow, day after)
"""

import httpx
from datetime import datetime, timedelta
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class WeatherScene(Scene):
    """Display weather forecast"""
    
    id = "weather"
    name = "Weather"
    description = "Weather forecast for Vilnius (3 days)"
    icon = "🌤️"
    
    settings_schema = [
        {
            'key': 'city',
            'label': 'City',
            'type': 'text',
            'default': 'Vilnius',
        },
        {
            'key': 'country_code',
            'label': 'Country Code',
            'type': 'text',
            'default': 'LT',
        },
        {
            'key': 'units',
            'label': 'Units',
            'type': 'select',
            'options': ['metric', 'imperial'],
            'default': 'metric',
        }
    ]
    
    # Weather condition to simple icon mapping
    WEATHER_ICONS = {
        'clear': '☀️',
        'sunny': '☀️',
        'partly': '⛅',
        'cloud': '☁️',
        'overcast': '☁️',
        'rain': '🌧️',
        'drizzle': '🌦️',
        'thunder': '⛈️',
        'snow': '❄️',
        'mist': '🌫️',
        'fog': '🌫️',
    }
    
    async def fetch_data(self) -> dict:
        """Fetch weather data from Open-Meteo (free, no API key)"""
        city = self.config.settings.get('city', 'Vilnius')
        
        # Vilnius coordinates (default)
        lat, lon = 54.6872, 25.2797
        
        async with httpx.AsyncClient(timeout=10) as client:
            # First, geocode the city if not Vilnius
            if city.lower() != 'vilnius':
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search"
                params = {'name': city, 'count': 1}
                resp = await client.get(geo_url, params=params)
                if resp.status_code == 200:
                    geo_data = resp.json()
                    if geo_data.get('results'):
                        lat = geo_data['results'][0]['latitude']
                        lon = geo_data['results'][0]['longitude']
            
            # Fetch weather
            url = "https://api.open-meteo.com/v1/forecast"
            units = self.config.settings.get('units', 'metric')
            temp_unit = 'celsius' if units == 'metric' else 'fahrenheit'
            
            params = {
                'latitude': lat,
                'longitude': lon,
                'daily': 'temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max',
                'current_weather': 'true',
                'temperature_unit': temp_unit,
                'timezone': 'auto',
                'forecast_days': 3,
            }
            
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            current = data.get('current_weather', {})
            daily = data.get('daily', {})
            
            # Parse daily forecasts
            forecasts = []
            dates = daily.get('time', [])
            temps_max = daily.get('temperature_2m_max', [])
            temps_min = daily.get('temperature_2m_min', [])
            codes = daily.get('weathercode', [])
            precip = daily.get('precipitation_probability_max', [])
            
            day_names = ['Šiandien', 'Rytoj', 'Poryt']
            
            for i in range(min(3, len(dates))):
                forecasts.append({
                    'day': day_names[i] if i < len(day_names) else dates[i],
                    'temp_max': temps_max[i] if i < len(temps_max) else 0,
                    'temp_min': temps_min[i] if i < len(temps_min) else 0,
                    'code': codes[i] if i < len(codes) else 0,
                    'precip': precip[i] if i < len(precip) else 0,
                })
            
            return {
                'city': city,
                'current_temp': current.get('temperature', 0),
                'forecasts': forecasts,
                'unit': '°C' if units == 'metric' else '°F',
            }
    
    def _get_weather_icon(self, code: int) -> str:
        """Convert WMO weather code to emoji"""
        # WMO Weather interpretation codes
        if code == 0:
            return '☀️'  # Clear sky
        elif code in [1, 2, 3]:
            return '⛅'  # Partly cloudy
        elif code in [45, 48]:
            return '🌫️'  # Fog
        elif code in [51, 53, 55, 56, 57]:
            return '🌦️'  # Drizzle
        elif code in [61, 63, 65, 66, 67]:
            return '🌧️'  # Rain
        elif code in [71, 73, 75, 77]:
            return '❄️'  # Snow
        elif code in [80, 81, 82]:
            return '🌧️'  # Rain showers
        elif code in [85, 86]:
            return '❄️'  # Snow showers
        elif code in [95, 96, 99]:
            return '⛈️'  # Thunderstorm
        return '☁️'
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render weather forecast"""
        img = generator.create_blank()
        city = data.get('city', 'Weather')
        generator.draw_header(img, f"{city}")
        
        draw = ImageDraw.Draw(img)
        forecasts = data.get('forecasts', [])
        
        font_day = generator.get_font(14, "bold")
        font_temp = generator.get_font(20, "mono")
        font_weather = generator.get_font(16, "bold")
        font_precip = generator.get_font(14, "mono")
        
        y = 26
        row_height = 32
        
        for forecast in forecasts:
            day = forecast.get('day', '')
            temp_max = forecast.get('temp_max', 0)
            temp_min = forecast.get('temp_min', 0)
            code = forecast.get('code', 0)
            precip = forecast.get('precip', 0)
            
            weather_text = self._get_weather_text(code)
            
            # Day name (short)
            draw.text((4, y), day[:3], font=font_day, fill=0)
            
            # Weather text
            draw.text((4, y + 14), weather_text, font=font_weather, fill=0)
            
            # Temperatures (right side)
            temp_str = f"{temp_max:.0f}/{temp_min:.0f}"
            draw.text((140, y + 4), temp_str, font=font_temp, fill=0)
            
            # Precipitation chance
            if precip > 0:
                draw.text((200, y + 6), f"{precip}%", font=font_precip, fill=0)
            
            y += row_height
            
            if y > generator.height - 16:
                break
        
        return img
    
    def _get_weather_text(self, code: int) -> str:
        """Get short weather description"""
        if code == 0:
            return "Giedra"
        elif code in [1, 2, 3]:
            return "Debesuota"
        elif code in [45, 48]:
            return "Rūkas"
        elif code in [51, 53, 55, 56, 57]:
            return "Dulksna"
        elif code in [61, 63, 65, 66, 67]:
            return "Lietus"
        elif code in [71, 73, 75, 77]:
            return "Sniegas"
        elif code in [80, 81, 82]:
            return "Liūtys"
        elif code in [85, 86]:
            return "Sn. liūtys"
        elif code in [95, 96, 99]:
            return "Perkūnija"
        return "Debesuota"

