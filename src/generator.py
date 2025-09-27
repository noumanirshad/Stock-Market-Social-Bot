"""
Final fix for Gemini content generator - handles multi-part responses properly
"""

import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
import google.generativeai as genai

logger = logging.getLogger(__name__)

class ContentGenerator:
    """Generate AI-powered social media content using Google Gemini with proper response handling"""
    
    def __init__(self):
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.working_model_name = None
        
        # Configure Gemini
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self._initialize_model()
            except Exception as e:
                self.logger.error(f"Failed to configure Gemini: {e}")
                self.model = None
        else:
            self.logger.warning("GEMINI_API_KEY not found in environment variables")
    
    def _initialize_model(self):
        """Initialize Gemini model with current 2024 model names"""
        model_names = [
            'gemini-2.5-flash',         # Latest and fastest
            'gemini-2.5-pro',           # Most capable
            'gemini-1.5-flash',         # Backup option
            'gemini-1.5-pro',           # Another backup
        ]
        
        for model_name in model_names:
            try:
                self.logger.info(f"Trying to initialize {model_name}...")
                model = genai.GenerativeModel(model_name)
                
                # Test the model with a simple request
                test_response = model.generate_content(
                    "Say 'Working'",
                    generation_config=genai.types.GenerationConfig(
                        candidate_count=1,
                        max_output_tokens=50,
                        temperature=0.1,
                    )
                )
                
                # Use proper response handling
                test_text = self._extract_text_from_response(test_response)
                
                if test_text and 'Working' in test_text:
                    self.model = model
                    self.working_model_name = model_name
                    self.logger.info(f"Successfully initialized Gemini model: {model_name}")
                    return
                else:
                    self.logger.warning(f"Model {model_name} initialized but test failed")
                    
            except Exception as e:
                self.logger.warning(f"Failed to initialize model {model_name}: {e}")
                continue
        
        if not self.model:
            self.logger.error("Failed to initialize any Gemini model")
    
    def _extract_text_from_response(self, response) -> Optional[str]:
        """Safely extract text from Gemini response, handling both simple and multi-part responses"""
        try:
            # First try the simple accessor
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
        except Exception:
            # If that fails, try the parts accessor
            pass
        
        try:
            # Try accessing parts directly
            if hasattr(response, 'parts') and response.parts:
                text_parts = []
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                if text_parts:
                    return ' '.join(text_parts).strip()
        except Exception:
            pass
        
        try:
            # Try the full candidate path
            if (hasattr(response, 'candidates') and 
                response.candidates and 
                len(response.candidates) > 0):
                
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    text_parts = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        return ' '.join(text_parts).strip()
        except Exception:
            pass
        
        # If all else fails
        self.logger.warning("Could not extract text from Gemini response")
        return None
    
    def generate_post_content(self, stock_data, platform: str = "facebook") -> str:
        """Generate social media post content using Gemini with proper response handling"""
        
        # Determine sentiment and emoji
        if stock_data.change_pct > 0:
            sentiment = "bullish"
            emoji = "📈"
        elif stock_data.change_pct < 0:
            sentiment = "bearish"
            emoji = "📉"
        else:
            sentiment = "neutral"
            emoji = "📊"
        
        # Create optimized prompt for Gemini
        prompt = f"""Create a Facebook post about this stock update:

Stock: {stock_data.company_name} ({stock_data.ticker})
Price: ${stock_data.price:.2f}
Change: {stock_data.change_pct:+.2f}%

Requirements:
- Start with {emoji} emoji
- Include ticker, price, and percentage change
- Add relevant hashtags
- Keep under 200 characters
- Professional tone
- No financial advice

Example format: "{emoji} AAPL at $150.25 (+1.5% today). Tech sector showing strength! #Stocks #AAPL #Finance"

Generate similar post:"""
        
        try:
            if self.model and self.gemini_api_key:
                # Configure generation for reliability
                generation_config = genai.types.GenerationConfig(
                    candidate_count=1,
                    max_output_tokens=200,
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40
                )
                
                # Safety settings
                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH", 
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                # Use the safe text extraction method
                content = self._extract_text_from_response(response)
                
                if content:
                    # Clean up the content
                    content = content.replace('"', '').replace("'", "")
                    # Remove any unwanted prefixes/suffixes
                    if content.startswith('Post:') or content.startswith('Facebook post:'):
                        content = content.split(':', 1)[1].strip()
                    
                    self.logger.info(f"Generated content with Gemini ({self.working_model_name}): {len(content)} chars")
                    return content
                else:
                    self.logger.warning("Empty or blocked response from Gemini")
                    
            else:
                self.logger.warning("Gemini not properly configured, using fallback")
                
        except Exception as e:
            self.logger.error(f"Error generating content with Gemini: {e}")
        
        # Enhanced fallback template with more variety
        change_emoji = "🔥" if abs(stock_data.change_pct) > 3 else emoji
        
        # Create contextual message based on change
        if stock_data.change_pct > 2:
            context = "Strong performance today!"
        elif stock_data.change_pct > 0:
            context = "Positive momentum continues."
        elif stock_data.change_pct < -2:
            context = "Market volatility in focus."
        elif stock_data.change_pct < 0:
            context = "Slight pullback today."
        else:
            context = "Steady trading session."
        
        fallback_content = (
            f"{change_emoji} {stock_data.ticker} trading at ${stock_data.price:.2f} "
            f"({stock_data.change_pct:+.2f}% today). {context} "
            f"#Stocks #{stock_data.ticker} #Finance"
        )
        
        self.logger.info("Using enhanced fallback content")
        return fallback_content
    
    def generate_stock_post(self, stock_data) -> str:
        """Alias for generate_post_content for compatibility"""
        return self.generate_post_content(stock_data, "facebook")
    
    def test_gemini_connection(self) -> bool:
        """Test if Gemini is working properly"""
        try:
            if not self.model:
                return False
            
            test_response = self.model.generate_content(
                "Test: Say 'Connection OK'",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=50,
                    temperature=0.1
                )
            )
            
            test_text = self._extract_text_from_response(test_response)
            result = bool(test_text and 'OK' in test_text)
            
            if result:
                self.logger.info(f"Gemini connection test passed with model: {self.working_model_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Gemini connection test failed: {e}")
            return False

# Test the fix
def test_response_extraction():
    """Test the response extraction fix"""
    print("🧪 Testing Gemini Response Extraction Fix")
    print("="*45)
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return False
    
    try:
        generator = ContentGenerator()
        
        if generator.model:
            print(f"✅ Model initialized: {generator.working_model_name}")
            
            # Test content generation
            class TestStockData:
                def __init__(self):
                    self.ticker = 'AAPL'
                    self.company_name = 'Apple Inc.'
                    self.price = 255.46
                    self.change_pct = -0.55
                    self.change_amount = -1.41
                    self.currency = 'USD'
            
            test_data = TestStockData()
            content = generator.generate_post_content(test_data)
            
            print(f"📝 Generated content: {content}")
            print(f"📏 Length: {len(content)} characters")
            
            return True
        else:
            print("❌ Failed to initialize Gemini model")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test the fix
    success = test_response_extraction()
    
    if success:
        print("\n✅ Gemini response extraction fix working!")
    else:
        print("\n❌ Fix needs more work")
        
        

# """
# Fixed AI content generator using Google Gemini API with current 2024 model names
# Addresses the 404 model not found errors
# """

# import os
# import logging
# from typing import Dict, Optional, List
# from datetime import datetime
# import google.generativeai as genai

# logger = logging.getLogger(__name__)

# class ContentGenerator:
#     """Generate AI-powered social media content using Google Gemini with 2024 model names"""
    
#     def __init__(self):
#         self.gemini_api_key = os.getenv('GEMINI_API_KEY')
#         self.logger = logging.getLogger(__name__)
#         self.model = None
#         self.working_model_name = None
        
#         # Configure Gemini
#         if self.gemini_api_key:
#             try:
#                 genai.configure(api_key=self.gemini_api_key)
#                 self._initialize_model()
#             except Exception as e:
#                 self.logger.error(f"Failed to configure Gemini: {e}")
#                 self.model = None
#         else:
#             self.logger.warning("GEMINI_API_KEY not found in environment variables")
    
#     def _initialize_model(self):
#         """Initialize Gemini model with current 2024 model names"""
#         # Current valid Gemini model names as of 2024
#         model_names = [
#             'gemini-2.5-flash',         # Latest and fastest
#             'gemini-2.5-pro',           # Most capable
#             'gemini-1.5-flash',         # Backup option
#             'gemini-1.5-pro',           # Another backup
#             'models/gemini-2.5-flash',  # Full path version
#             'models/gemini-1.5-flash'   # Full path backup
#         ]
        
#         for model_name in model_names:
#             try:
#                 self.logger.info(f"Trying to initialize {model_name}...")
#                 model = genai.GenerativeModel(model_name)
                
#                 # Test the model with a simple request
#                 test_response = model.generate_content(
#                     "Say 'Working'",
#                     generation_config=genai.types.GenerationConfig(
#                         candidate_count=1,
#                         max_output_tokens=50,
#                         temperature=0.1,
#                     )
#                 )
                
#                 if test_response.text and 'Working' in test_response.text:
#                     self.model = model
#                     self.working_model_name = model_name
#                     self.logger.info(f"Successfully initialized Gemini model: {model_name}")
#                     return
#                 else:
#                     self.logger.warning(f"Model {model_name} initialized but test failed")
                    
#             except Exception as e:
#                 self.logger.warning(f"Failed to initialize model {model_name}: {e}")
#                 continue
        
#         if not self.model:
#             self.logger.error("Failed to initialize any Gemini model")
    
#     def list_available_models(self) -> List[str]:
#         """List all available Gemini models"""
#         try:
#             models = genai.list_models()
#             available_models = []
#             for model in models:
#                 if 'generateContent' in model.supported_generation_methods:
#                     available_models.append(model.name)
#                     self.logger.info(f"Available model: {model.name}")
#             return available_models
#         except Exception as e:
#             self.logger.error(f"Failed to list models: {e}")
#             return []
    
#     def generate_post_content(self, stock_data, platform: str = "facebook") -> str:
#         """Generate social media post content using Gemini"""
        
#         # Determine sentiment and emoji
#         if stock_data.change_pct > 0:
#             sentiment = "bullish"
#             emoji = "📈"
#         elif stock_data.change_pct < 0:
#             sentiment = "bearish"
#             emoji = "📉"
#         else:
#             sentiment = "neutral"
#             emoji = "📊"
        
#         # Create optimized prompt for Gemini
#         prompt = f"""Create a Facebook post about this stock update:

# Stock: {stock_data.company_name} ({stock_data.ticker})
# Price: ${stock_data.price:.2f}
# Change: {stock_data.change_pct:+.2f}%

# Requirements:
# - Start with {emoji} emoji
# - Include ticker, price, and percentage change
# - Add relevant hashtags
# - Keep under 200 characters
# - Professional tone
# - No financial advice

# Example format: "{emoji} AAPL at $150.25 (+1.5% today). Tech sector showing strength! #Stocks #AAPL #Finance"

# Generate similar post:"""
        
#         try:
#             if self.model and self.gemini_api_key:
#                 # Configure generation for reliability
#                 generation_config = genai.types.GenerationConfig(
#                     candidate_count=1,
#                     max_output_tokens=200,
#                     temperature=0.7,
#                     top_p=0.8,
#                     top_k=40
#                 )
                
#                 # Safety settings
#                 safety_settings = [
#                     {
#                         "category": "HARM_CATEGORY_HARASSMENT",
#                         "threshold": "BLOCK_MEDIUM_AND_ABOVE"
#                     },
#                     {
#                         "category": "HARM_CATEGORY_HATE_SPEECH", 
#                         "threshold": "BLOCK_MEDIUM_AND_ABOVE"
#                     },
#                     {
#                         "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
#                         "threshold": "BLOCK_MEDIUM_AND_ABOVE"
#                     },
#                     {
#                         "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
#                         "threshold": "BLOCK_MEDIUM_AND_ABOVE"
#                     }
#                 ]
                
#                 response = self.model.generate_content(
#                     prompt,
#                     generation_config=generation_config,
#                     safety_settings=safety_settings
#                 )
                
#                 if response.text and response.text.strip():
#                     content = response.text.strip()
#                     # Clean up the content
#                     content = content.replace('"', '').replace("'", "")
#                     # Remove any unwanted prefixes/suffixes
#                     if content.startswith('Post:') or content.startswith('Facebook post:'):
#                         content = content.split(':', 1)[1].strip()
                    
#                     self.logger.info(f"Generated content with Gemini ({self.working_model_name}): {len(content)} chars")
#                     return content
#                 else:
#                     self.logger.warning("Empty or blocked response from Gemini")
                    
#             else:
#                 self.logger.warning("Gemini not properly configured, using fallback")
                
#         except Exception as e:
#             self.logger.error(f"Error generating content with Gemini: {e}")
        
#         # Enhanced fallback template with more variety
#         change_emoji = "🔥" if abs(stock_data.change_pct) > 3 else emoji
        
#         # Create contextual message based on change
#         if stock_data.change_pct > 2:
#             context = "Strong performance today!"
#         elif stock_data.change_pct > 0:
#             context = "Positive momentum continues."
#         elif stock_data.change_pct < -2:
#             context = "Market volatility in focus."
#         elif stock_data.change_pct < 0:
#             context = "Slight pullback today."
#         else:
#             context = "Steady trading session."
        
#         fallback_content = (
#             f"{change_emoji} {stock_data.ticker} trading at ${stock_data.price:.2f} "
#             f"({stock_data.change_pct:+.2f}% today). {context} "
#             f"#Stocks #{stock_data.ticker} #Finance"
#         )
        
#         self.logger.info("Using enhanced fallback content")
#         return fallback_content
    
#     def generate_stock_post(self, stock_data) -> str:
#         """Alias for generate_post_content for compatibility"""
#         return self.generate_post_content(stock_data, "facebook")
    
#     def test_gemini_connection(self) -> bool:
#         """Test if Gemini is working properly"""
#         try:
#             if not self.model:
#                 return False
            
#             test_response = self.model.generate_content(
#                 "Test: Say 'Connection OK'",
#                 generation_config=genai.types.GenerationConfig(
#                     max_output_tokens=50,
#                     temperature=0.1
#                 )
#             )
            
#             result = bool(test_response.text and 'OK' in test_response.text)
#             if result:
#                 self.logger.info(f"Gemini connection test passed with model: {self.working_model_name}")
#             return result
            
#         except Exception as e:
#             self.logger.error(f"Gemini connection test failed: {e}")
#             return False

# # Diagnostic function to check available models
# def diagnose_gemini_setup():
#     """Comprehensive Gemini setup diagnostic"""
#     print("🔧 GEMINI API DIAGNOSTIC")
#     print("="*40)
    
#     api_key = os.getenv('GEMINI_API_KEY')
#     if not api_key:
#         print("❌ GEMINI_API_KEY not found in environment")
#         return False
    
#     print(f"✅ API Key found: {api_key[:10]}...")
    
#     try:
#         import google.generativeai as genai
#         genai.configure(api_key=api_key)
        
#         print("\n📋 Listing available models...")
#         try:
#             models = genai.list_models()
#             available_models = []
            
#             for model in models:
#                 if 'generateContent' in model.supported_generation_methods:
#                     available_models.append(model.name)
#                     print(f"  ✅ {model.name}")
            
#             if not available_models:
#                 print("❌ No models support generateContent")
#                 return False
                
#         except Exception as e:
#             print(f"❌ Failed to list models: {e}")
#             print("Trying with hardcoded model names...")
        
#         # Test current model names
#         print("\n🧪 Testing model initialization...")
#         test_models = [
#             'gemini-2.5-flash',
#             'gemini-2.5-pro', 
#             'gemini-1.5-flash',
#             'gemini-1.5-pro'
#         ]
        
#         working_models = []
#         for model_name in test_models:
#             try:
#                 model = genai.GenerativeModel(model_name)
#                 response = model.generate_content("Say 'Working'")
                
#                 if response.text and 'Working' in response.text:
#                     print(f"  ✅ {model_name}: {response.text.strip()}")
#                     working_models.append(model_name)
#                 else:
#                     print(f"  ❌ {model_name}: Empty response")
                    
#             except Exception as e:
#                 print(f"  ❌ {model_name}: {str(e)[:60]}...")
        
#         if working_models:
#             print(f"\n🎉 Working models found: {working_models}")
            
#             # Test content generation
#             print("\n📝 Testing content generation...")
#             best_model = genai.GenerativeModel(working_models[0])
            
#             test_prompt = "Create a short social media post about Apple stock at $255.46 with -0.55% change."
#             response = best_model.generate_content(test_prompt)
            
#             if response.text:
#                 print(f"✅ Generated: {response.text.strip()}")
#                 return True
#             else:
#                 print("❌ Content generation failed")
#                 return False
#         else:
#             print("\n❌ No working models found")
#             return False
            
#     except ImportError:
#         print("❌ google-generativeai package not installed")
#         print("Run: pip install google-generativeai")
#         return False
#     except Exception as e:
#         print(f"❌ Gemini setup failed: {e}")
#         return False

# if __name__ == "__main__":
#     # Load environment variables
#     from dotenv import load_dotenv
#     load_dotenv()
    
#     # Run diagnostic
#     success = diagnose_gemini_setup()
    
#     if success:
#         print("\n✅ Gemini setup is working!")
#     else:
#         print("\n❌ Gemini setup needs fixing")

