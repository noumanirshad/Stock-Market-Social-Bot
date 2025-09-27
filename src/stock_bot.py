"""
Main Stock Bot orchestrator
Based on the working tele_bot.py implementation
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import pytz

from fetcher import StockFetcher, StockData
from generator import ContentGenerator
from image_generator import ImageGenerator
from facebook_poster import FacebookPoster

class StockBot:
    """Main bot class that orchestrates the entire process"""
    
    def __init__(self, config_path: str = "config/tickers.json"):
        """
        Initialize the stock bot
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # Initialize components
        self.fetcher = StockFetcher()
        self.generator = ContentGenerator()
        self.image_generator = ImageGenerator()
        self.facebook_poster = FacebookPoster()
        
        # State tracking
        self.last_posted = self._load_last_posted()
        self.pkt_tz = pytz.timezone('Asia/Karachi')
        
        # Configuration
        self.tickers = self.config.get("tickers", ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"])
        self.post_threshold = float(self.config.get("thresholds", {}).get("min_change_percent", 1.0))
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {
                "tickers": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"],
                "thresholds": {"min_change_percent": 1.0}
            }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration"""
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Configure logging
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_file = os.getenv("LOG_FILE", "logs/stock_bot.log")
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        return logging.getLogger(__name__)
    
    def _load_last_posted(self) -> Dict:
        """Load last posted data from file"""
        try:
            with open("logs/last_posted.json", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            self.logger.error(f"Error loading last posted data: {e}")
            return {}
    
    def _save_last_posted(self, ticker: str, data: StockData):
        """Save last posted data to file"""
        try:
            self.last_posted[ticker] = {
                'timestamp': data.timestamp.isoformat(),
                'price': data.price,
                'change_pct': data.change_pct
            }
            
            with open("logs/last_posted.json", 'w') as f:
                json.dump(self.last_posted, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving last posted data: {e}")
    
    def should_post(self, ticker: str, stock_data: StockData) -> bool:
        """
        Determine if we should post for this ticker
        
        Args:
            ticker (str): Stock ticker
            stock_data (StockData): Current stock data
            
        Returns:
            bool: True if should post
        """
        # Check if change is significant
        if abs(stock_data.change_pct) >= self.post_threshold:
            self.logger.info(f"Significant change for {ticker}: {stock_data.change_pct:+.2f}%")
            return True
        
        # Check if we've posted recently for this ticker
        if ticker in self.last_posted:
            last_post = self.last_posted[ticker]
            last_timestamp = datetime.fromisoformat(last_post['timestamp'].replace('Z', '+00:00'))
            time_diff = datetime.now(timezone.utc) - last_timestamp
            
            # Don't post if we posted within the last 4 hours
            if time_diff.total_seconds() < 4 * 3600:
                self.logger.info(f"Posted {ticker} recently, skipping")
                return False
        
        # Post if no previous data
        return ticker not in self.last_posted
    
    async def process_ticker(self, ticker: str) -> bool:
        """
        Process a single ticker: fetch, generate, and post
        
        Args:
            ticker (str): Stock ticker to process
            
        Returns:
            bool: True if successful
        """
        try:
            self.logger.info(f"Processing ticker: {ticker}")
            
            # Fetch stock data
            stock_data = await self.fetcher.fetch_stock_data(ticker)
            if not stock_data:
                self.logger.error(f"Failed to fetch data for {ticker}")
                return False
            
            # Check if we should post
            if not self.should_post(ticker, stock_data):
                return True  # Not an error, just skipping
            
            # Generate post content
            post_content = self.generator.generate_post_content(stock_data, "facebook")
            if not post_content:
                self.logger.error(f"Failed to generate content for {ticker}")
                return False
            
            # Generate thumbnail image
            image_path = None
            if os.getenv("POST_WITH_IMAGE", "true").lower() == "true":
                image_path = f"temp_{ticker}_thumbnail.png"
                if not self.image_generator.create_thumbnail(stock_data, image_path):
                    self.logger.warning(f"Failed to generate thumbnail for {ticker}, posting text only")
                    image_path = None
            
            # Post to Facebook
            result = await self.facebook_poster.post_to_facebook(post_content, image_path)
            if not result:
                self.logger.error(f"Failed to post {ticker} to Facebook")
                return False
            
            # Save last posted data
            self._save_last_posted(ticker, stock_data)
            
            # Clean up temporary image
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    self.logger.warning(f"Could not remove temp image {image_path}: {e}")
            
            self.logger.info(f"Successfully processed {ticker}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing {ticker}: {str(e)}")
            return False
    
    async def run(self) -> Dict[str, bool]:
        """
        Run the bot for all configured tickers
        
        Returns:
            Dict[str, bool]: Results for each ticker
        """
        self.logger.info("Starting Stock Bot run")
        
        results = {}
        
        for ticker in self.tickers:
            try:
                results[ticker] = await self.process_ticker(ticker)
            except Exception as e:
                self.logger.error(f"Unexpected error processing {ticker}: {str(e)}")
                results[ticker] = False
        
        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        self.logger.info(f"Bot run completed: {successful}/{total} tickers processed successfully")
        
        return results
    
    async def test_components(self) -> Dict[str, bool]:
        """
        Test all bot components
        
        Returns:
            Dict[str, bool]: Test results for each component
        """
        self.logger.info("Testing bot components")
        
        results = {}
        
        # Test stock fetcher
        try:
            test_data = await self.fetcher.fetch_stock_data("AAPL")
            results['fetcher'] = test_data is not None
        except Exception as e:
            self.logger.error(f"Fetcher test failed: {e}")
            results['fetcher'] = False
        
        # Test content generator
        try:
            if test_data:
                test_post = self.generator.generate_post_content(test_data, "facebook")
                results['generator'] = test_post is not None
            else:
                results['generator'] = False
        except Exception as e:
            self.logger.error(f"Generator test failed: {e}")
            results['generator'] = False
        
        # Test image generator
        try:
            if test_data:
                test_image = self.image_generator.create_thumbnail(test_data, "test_thumb.png")
                results['image_generator'] = test_image is not None
                if test_image and os.path.exists("test_thumb.png"):
                    os.remove("test_thumb.png")
            else:
                results['image_generator'] = False
        except Exception as e:
            self.logger.error(f"Image generator test failed: {e}")
            results['image_generator'] = False
        
        # Test Facebook poster
        try:
            results['facebook_poster'] = await self.facebook_poster.test_facebook_connection()
        except Exception as e:
            self.logger.error(f"Facebook poster test failed: {e}")
            results['facebook_poster'] = False
        
        # Log test results
        for component, success in results.items():
            status = "PASS" if success else "FAIL"
            self.logger.info(f"Component test - {component}: {status}")
        
        return results

def main():
    """Main entry point"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create and run the bot
    bot = StockBot()
    
    # Test components first
    print("Testing bot components...")
    test_results = asyncio.run(bot.test_components())
    
    if all(test_results.values()):
        print("All components working! Running bot...")
        results = asyncio.run(bot.run())
        print(f"Bot run completed: {results}")
    else:
        print("Some components failed. Please check configuration.")
        print(f"Test results: {test_results}")

if __name__ == "__main__":
    main()