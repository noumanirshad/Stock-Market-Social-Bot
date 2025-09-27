#!/usr/bin/env python3
"""
Enhanced Stock Bot Runner 
Based on the working tele_bot.py implementation
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add src directory to path
sys.path.append('src')

async def main():
    """Main function to run the enhanced bot"""
    print("🤖 Starting Enhanced Stock Bot...")
    
    # Load environment variables
    load_dotenv()
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please copy env.example to .env and fill in your API keys")
        return 1
    
    # Import and run the bot
    try:
        from stock_bot import StockBot
        
        # Create bot instance
        bot = StockBot()
        
        # Test components first
        print("🧪 Testing components...")
        test_results = await bot.test_components()
        
        if not all(test_results.values()):
            print("❌ Some components failed. Please check your configuration.")
            print("Test results:", test_results)
            return 1
        
        print("✅ All components working!")
        
        # Run the bot
        print("🚀 Running bot...")
        results = await bot.run()
        
        # Print results
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        print(f"📊 Bot run completed: {successful}/{total} tickers processed successfully")
        
        for ticker, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {ticker}")
        
        return 0 if successful > 0 else 1
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please make sure all dependencies are installed: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)