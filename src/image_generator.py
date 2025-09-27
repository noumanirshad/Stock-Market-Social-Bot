"""
Thumbnail image generator for social media posts
Based on the working tele_bot.py implementation
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Generate thumbnail images for social media posts"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def create_thumbnail(self, stock_data, output_path: str = None) -> str:
        """Create a thumbnail image for the stock data"""
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"thumbnails/{stock_data.ticker}_{timestamp}.png"
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(exist_ok=True)
        
        try:
            # Create image
            width, height = 800, 400
            img = Image.new('RGB', (width, height), color='#1a1a1a')
            draw = ImageDraw.Draw(img)
            
            # Colors based on performance
            if stock_data.change_pct > 0:
                accent_color = '#00ff88'  # Green
            elif stock_data.change_pct < 0:
                accent_color = '#ff4444'  # Red
            else:
                accent_color = '#888888'  # Gray
            
            # Try to load fonts, fallback to default
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 60)
                subtitle_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 40)
                detail_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 30)
            except:
                try:
                    # Try Windows fonts
                    title_font = ImageFont.truetype("arial.ttf", 60)
                    subtitle_font = ImageFont.truetype("arial.ttf", 40)
                    detail_font = ImageFont.truetype("arial.ttf", 30)
                except:
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()
                    detail_font = ImageFont.load_default()
            
            # Draw content
            # Company/Ticker
            draw.text((50, 50), stock_data.ticker, fill='white', font=title_font)
            
            # Price
            price_text = f"${stock_data.price:.2f}"
            draw.text((50, 130), price_text, fill=accent_color, font=subtitle_font)
            
            # Change
            change_text = f"{stock_data.change_pct:+.2f}%"
            draw.text((50, 190), change_text, fill=accent_color, font=subtitle_font)
            
            # Additional info
            company_name = stock_data.company_name[:30] + "..." if len(stock_data.company_name) > 30 else stock_data.company_name
            draw.text((50, 250), company_name, fill='#cccccc', font=detail_font)
            
            # Timestamp
            time_text = stock_data.timestamp.strftime("%Y-%m-%d %H:%M UTC")
            draw.text((50, 290), time_text, fill='#888888', font=detail_font)
            
            # Source
            draw.text((50, 320), f"Source: {stock_data.data_source}", fill='#666666', font=detail_font)
            
            # Save image
            img.save(output_path, 'PNG', quality=95)
            self.logger.info(f"✅ Thumbnail created: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error creating thumbnail: {e}")
            return None

    # Alias for backward compatibility
    def generate_stock_thumbnail(self, stock_data, output_path: str = None) -> str:
        """Alias for create_thumbnail for backward compatibility"""
        return self.create_thumbnail(stock_data, output_path)

# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Test the image generator
    generator = ImageGenerator()
    
    # Sample stock data
    from fetcher import StockData
    sample_data = StockData(
        ticker='AAPL',
        company_name='Apple Inc.',
        price=175.45,
        change_pct=1.2,
        change_amount=2.08,
        previous_close=173.37,
        volume=50000000,
        market_cap=2800000000000,
        currency='USD',
        timestamp=datetime.now(),
        data_source='Test'
    )
    
    # Generate thumbnail
    thumbnail_path = generator.create_thumbnail(sample_data, "test_thumbnail.png")
    if thumbnail_path:
        print(f"Thumbnail generated: {thumbnail_path}")
    else:
        print("Failed to generate thumbnail")