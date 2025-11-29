"""
Stocks Scene - Display stock prices for IBM, NVIDIA, GOOGLE
"""

import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class StocksScene(Scene):
    """Display stock prices"""
    
    id = "stocks"
    name = "Stocks"
    description = "Display stock prices for IBM, NVIDIA, and GOOGLE"
    icon = "📈"
    
    settings_schema = [
        {
            'key': 'symbols',
            'label': 'Stock Symbols',
            'type': 'text',
            'default': 'IBM,NVDA,GOOGL',
            'description': 'Comma-separated stock symbols'
        },
        {
            'key': 'api_key',
            'label': 'Alpha Vantage API Key',
            'type': 'password',
            'default': '',
            'description': 'Free API key from alphavantage.co'
        }
    ]
    
    def __init__(self, config: SceneConfig = None):
        super().__init__(config)
        self._symbols = self.config.settings.get('symbols', 'IBM,NVDA,GOOGL').split(',')
    
    async def fetch_data(self) -> dict:
        """Fetch stock data from Alpha Vantage or Yahoo Finance"""
        api_key = self.config.settings.get('api_key', '')
        stocks = {}
        
        async with httpx.AsyncClient(timeout=10) as client:
            for symbol in self._symbols:
                symbol = symbol.strip().upper()
                try:
                    # Try Yahoo Finance first (no API key needed)
                    data = await self._fetch_yahoo(client, symbol)
                    stocks[symbol] = data
                except Exception as e:
                    # Fallback to Alpha Vantage if API key provided
                    if api_key:
                        try:
                            data = await self._fetch_alphavantage(client, symbol, api_key)
                            stocks[symbol] = data
                        except:
                            stocks[symbol] = {'error': str(e)}
                    else:
                        stocks[symbol] = {'error': str(e)}
        
        return {'stocks': stocks}
    
    async def _fetch_yahoo(self, client: httpx.AsyncClient, symbol: str) -> dict:
        """Fetch from Yahoo Finance"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {'interval': '1d', 'range': '2d'}
        
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        result = data['chart']['result'][0]
        meta = result['meta']
        quote = result['indicators']['quote'][0]
        
        current = meta['regularMarketPrice']
        prev_close = meta.get('chartPreviousClose', meta.get('previousClose', current))
        change = current - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0
        
        return {
            'price': current,
            'change': change,
            'change_pct': change_pct,
            'currency': meta.get('currency', 'USD'),
        }
    
    async def _fetch_alphavantage(self, client: httpx.AsyncClient, symbol: str, api_key: str) -> dict:
        """Fetch from Alpha Vantage"""
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': api_key,
        }
        
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        quote = data.get('Global Quote', {})
        price = float(quote.get('05. price', 0))
        change = float(quote.get('09. change', 0))
        change_pct = float(quote.get('10. change percent', '0%').rstrip('%'))
        
        return {
            'price': price,
            'change': change,
            'change_pct': change_pct,
            'currency': 'USD',
        }
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render stock prices"""
        img = generator.create_blank()
        generator.draw_header(img, "📈 Stocks")
        
        draw = ImageDraw.Draw(img)
        stocks = data.get('stocks', {})
        
        y = 28
        font_symbol = generator.get_font(14)
        font_price = generator.get_font(16)
        font_change = generator.get_font(10)
        
        for symbol, info in stocks.items():
            if 'error' in info:
                draw.text((8, y), f"{symbol}: Error", font=font_symbol, fill=0)
                y += 28
                continue
            
            price = info.get('price', 0)
            change = info.get('change', 0)
            change_pct = info.get('change_pct', 0)
            
            # Symbol
            draw.text((8, y), symbol, font=font_symbol, fill=0)
            
            # Price
            price_str = f"${price:.2f}"
            draw.text((8, y + 14), price_str, font=font_price, fill=0)
            
            # Change with arrow
            arrow = "▲" if change >= 0 else "▼"
            change_str = f"{arrow} {abs(change):.2f} ({abs(change_pct):.1f}%)"
            draw.text((100, y + 16), change_str, font=font_change, fill=0)
            
            y += 38
            
            if y > generator.height - 20:
                break
        
        return img

