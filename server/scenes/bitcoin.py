"""
Bitcoin Scene - Display BTC price in EUR with 7-day chart
"""

import httpx
from PIL import Image, ImageDraw

from .base import Scene, SceneConfig


class BitcoinScene(Scene):
    """Display Bitcoin price with 7-day sparkline chart"""
    
    id = "bitcoin"
    name = "Bitcoin"
    description = "BTC price in EUR with 7-day chart"
    icon = "₿"
    
    settings_schema = []  # No settings needed
    
    async def fetch_data(self) -> dict:
        """Fetch BTC data from CoinGecko"""
        async with httpx.AsyncClient(timeout=15) as client:
            # Get current price
            price_url = "https://api.coingecko.com/api/v3/simple/price"
            price_params = {
                'ids': 'bitcoin',
                'vs_currencies': 'eur',
                'include_24hr_change': 'true',
            }
            
            price_resp = await client.get(price_url, params=price_params)
            price_resp.raise_for_status()
            price_data = price_resp.json()
            
            btc = price_data.get('bitcoin', {})
            current_price = btc.get('eur', 0)
            change_24h = btc.get('eur_24h_change', 0)
            
            # Get 7-day hourly history for detailed chart
            history_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
            history_params = {
                'vs_currency': 'eur',
                'days': '7',
            }
            
            history = []
            try:
                history_resp = await client.get(history_url, params=history_params)
                history_resp.raise_for_status()
                history_data = history_resp.json()
                
                prices = history_data.get('prices', [])
                # Get every 2nd point for detailed chart (~84 points)
                for i, (timestamp, price) in enumerate(prices):
                    if i % 2 == 0:
                        history.append(price)
            except Exception:
                pass
            
            return {
                'price': current_price,
                'change_24h': change_24h,
                'history': history,
            }
    
    def render(self, data: dict, generator) -> Image.Image:
        """Render BTC price with chart"""
        img = generator.create_blank()
        generator.draw_header(img, "Bitcoin")
        
        draw = ImageDraw.Draw(img)
        
        price = data.get('price', 0)
        change = data.get('change_24h', 0)
        history = data.get('history', [])
        
        font_large = generator.get_font(28, "mono")
        font_change = generator.get_font(14, "mono")
        font_label = generator.get_font(12, "medium")
        
        # Price on left
        price_str = f"€{price:,.0f}"
        draw.text((6, 26), price_str, font=font_large, fill=0)
        
        # 24h change on right (same line)
        arrow = "+" if change >= 0 else ""
        change_str = f"{arrow}{change:.1f}%"
        draw.text((160, 28), "24h", font=font_label, fill=0)
        draw.text((185, 26), change_str, font=font_change, fill=0)
        
        # Draw 7-day chart with hatched area
        if len(history) >= 2:
            chart_x = 6
            chart_y = 54
            chart_width = generator.width - 12
            chart_height = 60
            self._draw_chart(draw, history, chart_x, chart_y, chart_width, chart_height)
        
        return img
    
    def _draw_chart(self, draw: ImageDraw.Draw, prices: list, x: int, y: int, width: int, height: int):
        """Draw sparkline chart with diagonal hatched area below"""
        if len(prices) < 2:
            return
        
        min_p = min(prices)
        max_p = max(prices)
        p_range = max_p - min_p if max_p != min_p else 1
        
        # Calculate points
        points = []
        for i, price in enumerate(prices):
            px = x + (i / (len(prices) - 1)) * width
            py = y + height - ((price - min_p) / p_range) * height
            points.append((int(px), int(py)))
        
        bottom = int(y + height)
        left = int(x)
        right = int(x + width)
        
        if len(points) >= 2:
            # Step 1: Fill solid black area under curve
            fill_points = points.copy()
            fill_points.append((right, bottom))
            fill_points.append((left, bottom))
            draw.polygon(fill_points, fill=0)
            
            # Step 2: Draw white diagonal lines on top (creates hatching effect)
            spacing = 5
            for start_x in range(left - height, right + height, spacing):
                # Diagonal line from bottom-left to top-right
                x1 = start_x
                y1 = bottom
                x2 = start_x + height
                y2 = y
                
                # Clip to chart bounds
                draw.line([(x1, y1), (x2, y2)], fill=255, width=2)
            
            # Step 3: Clear area above the curve (draw white polygon)
            # Create polygon for area above curve
            above_points = points.copy()
            above_points.insert(0, (left, y))
            above_points.append((right, y))
            draw.polygon(above_points, fill=255)
            
            # Step 4: Draw the main curve line (thick, black)
            draw.line(points, fill=0, width=3)
        
        # End dot
        if points:
            r = 3
            ex, ey = points[-1]
            draw.ellipse([ex-r, ey-r, ex+r, ey+r], fill=0)
