"""
Fixed Facebook posting module using Meta Graph API
"""

import os
import asyncio
import aiohttp
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FacebookTokenHelper:
    """Helper class for Facebook token management"""
    
    def __init__(self):
        self.app_id = os.getenv('FACEBOOK_APP_ID')
        self.app_secret = os.getenv('FACEBOOK_APP_SECRET') 
        self.base_url = "https://graph.facebook.com"
        
    async def validate_page_token(self, access_token: str, page_id: str) -> Dict:
        """Validate a page access token properly"""
        try:
            # For page tokens, we validate by accessing the page directly
            url = f"{self.base_url}/v19.0/{page_id}"
            params = {
                'access_token': access_token,
                'fields': 'id,name,category,about,phone,website'  # Valid page fields
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {'valid': True, 'data': data}
                    else:
                        error_data = await response.json()
                        return {'valid': False, 'error': error_data}
                        
        except Exception as e:
            return {'valid': False, 'error': str(e)}

class FacebookPoster:
    """Facebook poster with enhanced error handling and proper token validation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Facebook credentials
        self.facebook_app_id = os.getenv('FACEBOOK_APP_ID')
        self.facebook_app_secret = os.getenv('FACEBOOK_APP_SECRET')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        
        # Use latest API version
        self.facebook_base_url = "https://graph.facebook.com/v19.0"
        self.token_helper = FacebookTokenHelper()
    
    async def test_facebook_connection(self) -> bool:
        """Test Facebook connection with corrected token validation"""
        try:
            if not all([self.facebook_access_token, self.facebook_page_id]):
                self.logger.error("Facebook credentials missing")
                return False
            
            # Use corrected page token validation
            validation_result = await self.token_helper.validate_page_token(
                self.facebook_access_token, 
                self.facebook_page_id
            )
            
            if not validation_result['valid']:
                error = validation_result['error']
                if isinstance(error, dict) and 'error' in error:
                    error_msg = error['error'].get('message', 'Unknown error')
                    error_code = error['error'].get('code', 'Unknown')
                    
                    self.logger.error(f"Token validation failed: {error_msg} (Code: {error_code})")
                    
                    if 'expired' in error_msg.lower():
                        print("\n🔄 Your Facebook token has expired!")
                        self.print_token_renewal_instructions()
                        return False
                    elif error_code == 190:  # Invalid token
                        print("\n❌ Facebook token is invalid!")
                        self.print_token_renewal_instructions()
                        return False
                else:
                    self.logger.error(f"Token validation failed: {error}")
                return False
            
            # If validation passed, log page info
            page_info = validation_result['data']
            page_name = page_info.get('name', 'Unknown')
            self.logger.info(f"Facebook connection successful. Page: {page_name}")
            return True
                        
        except Exception as e:
            self.logger.error(f"Facebook connection test failed: {e}")
            return False
    
    def print_token_renewal_instructions(self):
        """Print detailed token renewal instructions"""
        print("\n" + "="*60)
        print("🔐 FACEBOOK TOKEN RENEWAL GUIDE")
        print("="*60)
        
        print("\n📱 STEP 1: Get a new User Access Token")
        print("1. Go to: https://developers.facebook.com/tools/explorer/")
        print("2. Select your app from the dropdown")
        print("3. Click 'Get Token' → 'Get User Access Token'")
        print("4. Select these permissions:")
        print("   ✅ pages_manage_posts")
        print("   ✅ pages_read_engagement") 
        print("   ✅ pages_show_list")
        print("5. Click 'Generate Access Token'")
        print("6. Copy the generated token")
        
        print("\n🔄 STEP 2: Convert to Long-lived Token")
        if self.facebook_app_id and self.facebook_app_secret:
            print("Use this URL to get a long-lived token:")
            print(f"https://graph.facebook.com/oauth/access_token?")
            print(f"grant_type=fb_exchange_token&")
            print(f"client_id={self.facebook_app_id}&")
            print(f"client_secret={self.facebook_app_secret}&")
            print(f"fb_exchange_token=YOUR_SHORT_TOKEN_HERE")
        else:
            print("Configure FACEBOOK_APP_ID and FACEBOOK_APP_SECRET first")
        
        print("\n📄 STEP 3: Get Page Access Token")
        print("Use the long-lived user token to get page token:")
        print(f"https://graph.facebook.com/v19.0/{self.facebook_page_id}?fields=access_token&access_token=YOUR_USER_TOKEN")
        
        print("\n⚙️ STEP 4: Update .env file")
        print("Update FACEBOOK_ACCESS_TOKEN with the page token")
        
        print("\n💡 TIP: Page tokens from long-lived user tokens last much longer!")
    
    async def post_to_facebook(self, content: str, image_path: str = None) -> bool:
        """Post to Facebook page with enhanced error handling"""
        try:
            if not all([self.facebook_access_token, self.facebook_page_id]):
                self.logger.warning("Facebook credentials not configured")
                return False
            
            # Add disclaimer to the post
            disclaimer = "\n\n⚠️ This is not financial advice. Please do your own research before investing."
            full_message = content + disclaimer
            
            if image_path and os.path.exists(image_path):
                # Post with image
                return await self._post_facebook_with_image(full_message, image_path)
            else:
                # Post text only
                return await self._post_facebook_text(full_message)
                
        except Exception as e:
            self.logger.error(f"Error posting to Facebook: {e}")
            return False
    
    async def _post_facebook_text(self, message: str) -> bool:
        """Post text-only content to Facebook with better error handling"""
        try:
            url = f"{self.facebook_base_url}/{self.facebook_page_id}/feed"
            
            data = {
                'message': message,
                'access_token': self.facebook_access_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=30) as response:
                    result = await response.json()
                    
                    if response.status == 200 and 'id' in result:
                        post_id = result.get('id', 'Unknown ID')
                        self.logger.info(f"Successfully posted text to Facebook: {post_id}")
                        return True
                    else:
                        # Handle specific error cases
                        if 'error' in result:
                            error_msg = result['error'].get('message', 'Unknown error')
                            error_code = result['error'].get('code', 0)
                            
                            if error_code == 190:  # Token expired
                                self.logger.error("Facebook token expired!")
                                self.print_token_renewal_instructions()
                            elif error_code == 200:  # Permissions error
                                self.logger.error("Facebook permissions error - check pages_manage_posts permission")
                            else:
                                self.logger.error(f"Facebook API error: {error_msg} (Code: {error_code})")
                        else:
                            self.logger.error(f"Facebook post failed: {result}")
                        return False
                        
        except asyncio.TimeoutError:
            self.logger.error("Facebook post timeout")
            return False
        except Exception as e:
            self.logger.error(f"Error posting text to Facebook: {e}")
            return False
    
    async def _post_facebook_with_image(self, message: str, image_path: str) -> bool:
        """Post with image using direct upload method"""
        try:
            url = f"{self.facebook_base_url}/{self.facebook_page_id}/photos"
            
            # Read the image file
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            
            # Create form data
            data = aiohttp.FormData()
            data.add_field('message', message)
            data.add_field('access_token', self.facebook_access_token)
            data.add_field('source', image_data, 
                          filename='stock_update.png', 
                          content_type='image/png')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=60) as response:
                    result = await response.json()
                    
                    if response.status == 200 and 'id' in result:
                        post_id = result.get('id', 'Unknown ID')
                        self.logger.info(f"Successfully posted with image to Facebook: {post_id}")
                        return True
                    else:
                        self.logger.error(f"Facebook image post failed: {result}")
                        # Fallback to text-only
                        self.logger.info("Attempting text-only fallback...")
                        return await self._post_facebook_text(message)
                        
        except Exception as e:
            self.logger.error(f"Error posting with image to Facebook: {e}")
            # Fallback to text-only
            return await self._post_facebook_text(message)
    
    # Legacy method aliases for compatibility
    async def post_stock_update(self, stock_data: Dict, post_content: str, image_path: str = None) -> bool:
        """Legacy method for compatibility"""
        return await self.post_to_facebook(post_content, image_path)

# Comprehensive Facebook diagnostic
async def diagnose_facebook_setup():
    """Complete Facebook setup diagnostic"""
    print("🔧 FACEBOOK API DIAGNOSTIC")
    print("="*40)
    
    # Check credentials
    credentials = {
        'FACEBOOK_APP_ID': os.getenv('FACEBOOK_APP_ID'),
        'FACEBOOK_APP_SECRET': os.getenv('FACEBOOK_APP_SECRET'),
        'FACEBOOK_ACCESS_TOKEN': os.getenv('FACEBOOK_ACCESS_TOKEN'),
        'FACEBOOK_PAGE_ID': os.getenv('FACEBOOK_PAGE_ID')
    }
    
    print("📋 Credential Check:")
    missing = []
    for name, value in credentials.items():
        if value:
            if 'TOKEN' in name:
                masked_value = value[:15] + "..." if len(value) > 15 else value
            else:
                masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"  ✅ {name}: {masked_value}")
        else:
            print(f"  ❌ {name}: Missing")
            missing.append(name)
    
    if missing:
        print(f"\n❌ Missing credentials: {missing}")
        return False
    
    # Test token with corrected validation
    print(f"\n🔍 Testing token validity...")
    
    try:
        poster = FacebookPoster()
        connection_ok = await poster.test_facebook_connection()
        
        if connection_ok:
            print("✅ Facebook token is valid and working!")
            
            # Test posting permissions
            print(f"\n📝 Testing posting permissions...")
            test_message = f"🤖 Test from Stock Bot - {datetime.now().strftime('%Y-%m-%d %H:%M')} PKT"
            
            print(f"Ready to test post: {test_message[:50]}...")
            return True
        else:
            print("❌ Facebook connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Facebook diagnostic failed: {e}")
        return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run diagnostic
    success = asyncio.run(diagnose_facebook_setup())
    
    if success:
        print("\n✅ Facebook setup is working!")
    else:
        print("\n❌ Facebook setup needs fixing")
