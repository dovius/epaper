"""
Bitcoin Scene - Display BTC price and stats
"""

import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class BitcoinScene(Scene):
    """Display Bitcoin price and stats"""
    
    id = "bitcoin"
    name = "Bitcoin"
    description = "Display BTC price, 24h change, and stats"
    icon = "₿"
    
    settings_schema = [
        {
            'key': 'currency',
            'label': 'Display Currency',
            'type': 'select',
            'options': ['USD', 'EUR', 'GBP'],
            'default': 'USD',
        },
        {
            'key': 'show_24h_stats',
            'label': 'Show 24h Stats',
            'type': 'checkbox',
            'default': True,
        }
    ]
    
    async def fetch_data(self) -> dict:
        """Fetch BTC data from CoinGecko"""
        currency = self.config.settings.get('currency', 'USD').lower()
        
        async with httpx.AsyncClient(timeout=10) as client:
            # CoinGecko free API
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': 'bitcoin',
                'vs_currencies': currency,
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true',
                'include_market_cap': 'true',
            }
            
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            btc = data.get('bitcoin', {})
            
            return {
                'price': btc.get(currency, 0),
                'change_24h': btc.get(f'{currency}_24h_change', 0),
                'volume_24h': btc.get(f'{currency}_24h_vol', 0),
                'market_cap': btc.get(f'{currency}_market_cap', 0),
                'currency': currency.upper(),
            }
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render BTC price"""
        img = generator.create_blank()
        generator.draw_header(img, "₿ Bitcoin")
        
        draw = ImageDraw.Draw(img)
        
        price = data.get('price', 0)
        change = data.get('change_24h', 0)
        currency = data.get('currency', 'USD')
        
        # Currency symbols
        symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
        sym = symbols.get(currency, '$')
        
        # Large price
        font_large = generator.get_font(24)
        font_label = generator.get_font(10)
        font_value = generator.get_font(12)
        
        # Format price
        if price >= 1000:
            price_str = f"{sym}{price:,.0f}"
        else:
            price_str = f"{sym}{price:.2f}"
        
        draw.text((8, 30), price_str, font=font_large, fill=0)
        
        # 24h change
        arrow = "▲" if change >= 0 else "▼"
        change_str = f"{arrow} {abs(change):.2f}%"
        
        draw.text((8, 58), "24h Change:", font=font_label, fill=0)
        draw.text((75, 56), change_str, font=font_value, fill=0)
        
        if self.config.settings.get('show_24h_stats', True):
            # Volume
            vol = data.get('volume_24h', 0)
            if vol >= 1e9:
                vol_str = f"{sym}{vol/1e9:.1f}B"
            elif vol >= 1e6:
                vol_str = f"{sym}{vol/1e6:.1f}M"
            else:
                vol_str = f"{sym}{vol:,.0f}"
            
            draw.text((8, 76), "24h Volume:", font=font_label, fill=0)
            draw.text((75, 74), vol_str, font=font_value, fill=0)
            
            # Market cap
            mcap = data.get('market_cap', 0)
            if mcap >= 1e12:
                mcap_str = f"{sym}{mcap/1e12:.2f}T"
            elif mcap >= 1e9:
                mcap_str = f"{sym}{mcap/1e9:.1f}B"
            else:
                mcap_str = f"{sym}{mcap/1e6:.1f}M"
            
            draw.text((8, 94), "Market Cap:", font=font_label, fill=0)
            draw.text((75, 92), mcap_str, font=font_value, fill=0)
        
        return img

