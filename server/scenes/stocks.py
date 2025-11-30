"""
Stocks Scene - Display stock prices with mini 7-day charts
"""

import asyncio
import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class StocksScene(Scene):
    """Display stock prices with 7-day mini charts"""
    
    id = "stocks"
    name = "Stocks"
    description = "IBM, NVIDIA, GOOGLE"
    icon = "📈"
    
    settings_schema = [
        {
            'key': 'finnhub_key',
            'label': 'Finnhub API Key',
            'type': 'password',
            'default': '',
            'description': 'Free: finnhub.io'
        }
    ]
    
    SYMBOLS = ['IBM', 'NVDA', 'GOOGL']
    
    async def fetch_data(self) -> dict:
        api_key = self.config.settings.get('finnhub_key', '')
        stocks = {}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }
        
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for i, symbol in enumerate(self.SYMBOLS):
                try:
                    price_data = {'price': 0, 'change_pct': 0}
                    history = []
                    
                    # Get price from Finnhub
                    if api_key:
                        try:
                            resp = await client.get(
                                "https://finnhub.io/api/v1/quote",
                                params={'symbol': symbol, 'token': api_key}
                            )
                            if resp.status_code == 200:
                                quote = resp.json()
                                price_data = {
                                    'price': quote.get('c', 0),
                                    'change_pct': quote.get('dp', 0),
                                }
                        except:
                            pass
                    
                    # Delay between Yahoo requests
                    if i > 0:
                        await asyncio.sleep(0.3)
                    
                    # Get chart from Yahoo
                    try:
                        resp = await client.get(
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                            params={'interval': '1d', 'range': '5d'}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            result = data.get('chart', {}).get('result', [{}])[0]
                            quotes = result.get('indicators', {}).get('quote', [{}])[0]
                            closes = quotes.get('close', [])
                            history = [p for p in closes if p is not None]
                    except:
                        pass
                    
                    stocks[symbol] = {**price_data, 'history': history}
                    
                except Exception as e:
                    stocks[symbol] = {'price': 0, 'change_pct': 0, 'history': []}
        
        return {'stocks': stocks}
    
    def render(self, data: dict, generator) -> Image.Image:
        img = generator.create_blank()
        generator.draw_header(img, "Stocks")
        
        draw = ImageDraw.Draw(img)
        stocks = data.get('stocks', {})
        
        font_sym = generator.get_font(12, "bold")
        font_price = generator.get_font(14, "mono")
        font_chg = generator.get_font(11, "mono")
        
        y = 25
        row_height = 32
        
        for symbol in self.SYMBOLS:
            info = stocks.get(symbol, {})
            
            price = info.get('price', 0)
            change_pct = info.get('change_pct', 0)
            history = info.get('history', [])
            
            # Left side: Symbol, Price, Change (stacked)
            draw.text((4, y), symbol, font=font_sym, fill=0)
            
            if price > 0:
                draw.text((4, y + 12), f"${price:.0f}", font=font_price, fill=0)
                arrow = "+" if change_pct >= 0 else ""
                draw.text((50, y + 14), f"{arrow}{change_pct:.1f}%", font=font_chg, fill=0)
            else:
                draw.text((4, y + 12), "--", font=font_price, fill=0)
            
            # Right side: Chart
            chart_x = 100
            chart_w = generator.width - chart_x - 4
            chart_h = 26
            chart_y = y + 2
            
            if len(history) >= 2:
                self._draw_chart(draw, history, chart_x, chart_y, chart_w, chart_h)
            
            y += row_height
        
        return img
    
    def _draw_chart(self, draw: ImageDraw.Draw, prices: list, x: int, y: int, w: int, h: int):
        """Simple sparkline chart"""
        min_p = min(prices)
        max_p = max(prices)
        rng = max_p - min_p if max_p != min_p else 1
        
        # Calculate points
        pts = []
        for i, p in enumerate(prices):
            px = x + int(i / (len(prices) - 1) * w)
            py = y + h - int((p - min_p) / rng * h)
            pts.append((px, py))
        
        # Fill under curve
        fill = pts + [(x + w, y + h), (x, y + h)]
        draw.polygon(fill, fill=0)
        
        # Diagonal white stripes
        for sx in range(x - h, x + w + h, 4):
            draw.line([(sx, y + h), (sx + h, y)], fill=255, width=1)
        
        # Clear above curve
        above = [(x, y)] + pts + [(x + w, y)]
        draw.polygon(above, fill=255)
        
        # Thick line
        draw.line(pts, fill=0, width=3)
