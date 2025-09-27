"""
Enhanced stock data fetcher with multiple sources and fallback
Based on the working tele_bot.py implementation
"""

import os
import asyncio
import aiohttp
import requests
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class StockData:
    """Data structure for stock information"""
    ticker: str
    company_name: str
    price: float
    change_pct: float
    change_amount: float
    previous_close: float
    volume: int
    market_cap: Optional[int]
    currency: str
    timestamp: datetime
    data_source: str

class DataSource(Enum):
    """Available data sources"""
    ALPHA_VANTAGE = "alpha_vantage"
    FINNHUB = "finnhub"
    TWELVE_DATA = "twelve_data"
    POLYGON = "polygon"
    YAHOO_BACKUP = "yahoo_backup"

class StockFetcher:
    """Enhanced stock data fetcher with multiple sources and fallback"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # API keys from environment
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.twelve_data_key = os.getenv('TWELVE_DATA_API_KEY')
        self.polygon_key = os.getenv('POLYGON_API_KEY')
        
        # Rate limiting
        self.last_request_time = {}
        self.min_request_interval = 12  # seconds between requests
        
        # Session with retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    async def fetch_stock_data(self, ticker: str) -> Optional[StockData]:
        """
        Fetch stock data with multiple fallback sources
        """
        sources = [
            DataSource.ALPHA_VANTAGE,
            DataSource.FINNHUB,
            DataSource.TWELVE_DATA,
            DataSource.POLYGON,
            DataSource.YAHOO_BACKUP
        ]
        
        for source in sources:
            try:
                # Rate limiting
                await self._rate_limit(source)
                
                data = await self._fetch_from_source(ticker, source)
                if data:
                    self.logger.info(f"✅ Successfully fetched {ticker} from {source.value}")
                    return data
                    
            except Exception as e:
                self.logger.warning(f"❌ Failed to fetch {ticker} from {source.value}: {e}")
                continue
        
        self.logger.error(f"Failed to fetch data for {ticker} from all sources")
        return None
    
    async def _rate_limit(self, source: DataSource):
        """Implement rate limiting per source"""
        source_key = source.value
        if source_key in self.last_request_time:
            elapsed = time.time() - self.last_request_time[source_key]
            if elapsed < self.min_request_interval:
                wait_time = self.min_request_interval - elapsed
                await asyncio.sleep(wait_time)
        
        self.last_request_time[source_key] = time.time()
    
    async def _fetch_from_source(self, ticker: str, source: DataSource) -> Optional[StockData]:
        """Fetch data from specific source"""
        
        if source == DataSource.ALPHA_VANTAGE and self.alpha_vantage_key:
            return await self._fetch_alpha_vantage(ticker)
        elif source == DataSource.FINNHUB and self.finnhub_key:
            return await self._fetch_finnhub(ticker)
        elif source == DataSource.TWELVE_DATA and self.twelve_data_key:
            return await self._fetch_twelve_data(ticker)
        elif source == DataSource.POLYGON and self.polygon_key:
            return await self._fetch_polygon(ticker)
        elif source == DataSource.YAHOO_BACKUP:
            return await self._fetch_yahoo_backup(ticker)
        
        return None
    
    async def _fetch_alpha_vantage(self, ticker: str) -> Optional[StockData]:
        """Fetch from Alpha Vantage API"""
        try:
            # Get quote data
            quote_url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': ticker,
                'apikey': self.alpha_vantage_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(quote_url, params=params) as response:
                    data = await response.json()
            
            quote_data = data.get('Global Quote', {})
            if not quote_data:
                return None
            
            price = float(quote_data.get('05. price', 0))
            change = float(quote_data.get('09. change', 0))
            change_pct = float(quote_data.get('10. change percent', '0').replace('%', ''))
            prev_close = price - change
            
            return StockData(
                ticker=ticker,
                company_name=ticker,  # Alpha Vantage doesn't provide company name in quote
                price=price,
                change_pct=change_pct,
                change_amount=change,
                previous_close=prev_close,
                volume=int(quote_data.get('06. volume', 0)),
                market_cap=None,
                currency='USD',
                timestamp=datetime.now(timezone.utc),
                data_source='Alpha Vantage'
            )
            
        except Exception as e:
            self.logger.error(f"Alpha Vantage error: {e}")
            return None
    
    async def _fetch_finnhub(self, ticker: str) -> Optional[StockData]:
        """Fetch from Finnhub API"""
        try:
            base_url = "https://finnhub.io/api/v1"
            
            # Get quote data
            async with aiohttp.ClientSession() as session:
                # Current price
                quote_url = f"{base_url}/quote"
                quote_params = {'symbol': ticker, 'token': self.finnhub_key}
                
                async with session.get(quote_url, params=quote_params) as response:
                    quote_data = await response.json()
                
                # Company profile for name
                profile_url = f"{base_url}/stock/profile2"
                profile_params = {'symbol': ticker, 'token': self.finnhub_key}
                
                async with session.get(profile_url, params=profile_params) as response:
                    profile_data = await response.json()
            
            current_price = quote_data.get('c', 0)
            prev_close = quote_data.get('pc', 0)
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            return StockData(
                ticker=ticker,
                company_name=profile_data.get('name', ticker),
                price=current_price,
                change_pct=change_pct,
                change_amount=change,
                previous_close=prev_close,
                volume=0,  # Finnhub free tier doesn't include volume in quote
                market_cap=profile_data.get('marketCapitalization', None),
                currency=profile_data.get('currency', 'USD'),
                timestamp=datetime.now(timezone.utc),
                data_source='Finnhub'
            )
            
        except Exception as e:
            self.logger.error(f"Finnhub error: {e}")
            return None
    
    async def _fetch_twelve_data(self, ticker: str) -> Optional[StockData]:
        """Fetch from Twelve Data API"""
        try:
            url = "https://api.twelvedata.com/price"
            params = {
                'symbol': ticker,
                'apikey': self.twelve_data_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
            
            if 'price' not in data:
                return None
            
            # Get additional data for percentage change
            quote_url = "https://api.twelvedata.com/quote"
            async with aiohttp.ClientSession() as session:
                async with session.get(quote_url, params=params) as response:
                    quote_data = await response.json()
            
            price = float(data['price'])
            prev_close = float(quote_data.get('previous_close', price))
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            return StockData(
                ticker=ticker,
                company_name=quote_data.get('name', ticker),
                price=price,
                change_pct=change_pct,
                change_amount=change,
                previous_close=prev_close,
                volume=int(quote_data.get('volume', 0)),
                market_cap=None,
                currency='USD',
                timestamp=datetime.now(timezone.utc),
                data_source='Twelve Data'
            )
            
        except Exception as e:
            self.logger.error(f"Twelve Data error: {e}")
            return None
    
    async def _fetch_polygon(self, ticker: str) -> Optional[StockData]:
        """Fetch from Polygon API"""
        try:
            # Get previous close
            prev_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"
            params = {'apikey': self.polygon_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(prev_url, params=params) as response:
                    data = await response.json()
            
            results = data.get('results', [])
            if not results:
                return None
            
            result = results[0]
            price = float(result.get('c', 0))  # Close price
            prev_close = float(result.get('o', price))  # Open price as previous
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            return StockData(
                ticker=ticker,
                company_name=ticker,
                price=price,
                change_pct=change_pct,
                change_amount=change,
                previous_close=prev_close,
                volume=int(result.get('v', 0)),
                market_cap=None,
                currency='USD',
                timestamp=datetime.now(timezone.utc),
                data_source='Polygon'
            )
            
        except Exception as e:
            self.logger.error(f"Polygon error: {e}")
            return None
    
    async def _fetch_yahoo_backup(self, ticker: str) -> Optional[StockData]:
        """Backup Yahoo Finance scraping method"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            
            # Try with different approaches
            info = stock.info
            hist = stock.history(period="2d", interval="1d")
            
            if hist.empty or len(hist) < 1:
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            return StockData(
                ticker=ticker,
                company_name=info.get('longName', ticker),
                price=current_price,
                change_pct=change_pct,
                change_amount=change,
                previous_close=prev_close,
                volume=int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
                market_cap=info.get('marketCap'),
                currency=info.get('currency', 'USD'),
                timestamp=datetime.now(timezone.utc),
                data_source='Yahoo Finance (Backup)'
            )
            
        except Exception as e:
            self.logger.error(f"Yahoo backup error: {e}")
            return None

    # Synchronous wrapper for backward compatibility
    def fetch_stock_data_sync(self, ticker: str) -> Optional[Dict]:
        """Synchronous wrapper for backward compatibility"""
        try:
            # Run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.fetch_stock_data(ticker))
            loop.close()
            
            if result:
                # Convert StockData to dict for compatibility
                return {
                    'ticker': result.ticker,
                    'company_name': result.company_name,
                    'price': result.price,
                    'change_pct': result.change_pct,
                    'change_amount': result.change_amount,
                    'previous_close': result.previous_close,
                    'volume': result.volume,
                    'market_cap': result.market_cap,
                    'currency': result.currency,
                    'timestamp': result.timestamp,
                    'data_source': result.data_source
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error in sync wrapper: {e}")
            return None

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_fetcher():
        fetcher = StockFetcher()
        
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        
        for ticker in test_tickers:
            print(f"\n📊 Testing {ticker}...")
            stock_data = await fetcher.fetch_stock_data(ticker)
            
            if stock_data:
                print(f"✅ Success!")
                print(f"   Company: {stock_data.company_name}")
                print(f"   Price: ${stock_data.price:.2f}")
                print(f"   Change: {stock_data.change_pct:+.2f}%")
                print(f"   Source: {stock_data.data_source}")
            else:
                print(f"❌ Failed to fetch data for {ticker}")
    
    print("🧪 Testing Enhanced Stock Data Fetcher")
    asyncio.run(test_fetcher())