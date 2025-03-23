#!/usr/bin/env python3
"""
Twitter/X Authentication Status Check

This script checks if we're currently authenticated to Twitter/X
and attempts to authenticate if not.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('auth_check')

async def check_auth_status():
    """Check the current authentication status with Twitter/X"""
    try:
        from tweet_fetcher.extractors.auth_playwright.auth import TwitterAuth
        from tweet_fetcher.extractors.auth_playwright.browser import create_authenticated_browser
        from tweet_fetcher.config import SCREENSHOTS_DIR
        
        # Get credentials from environment variables
        username = os.environ.get('X_USERNAME')
        password = os.environ.get('X_PASSWORD')
        phone_number = os.environ.get('X_PHONE_NUMBER')
        
        if not username or not password:
            logger.error("X_USERNAME and X_PASSWORD environment variables must be set")
            return False
            
        logger.info(f"Checking authentication status for {username}")
        
        # Create browser and auth manager
        try:
            playwright, context, auth_manager = await create_authenticated_browser(
                username, 
                password,
                phone_number,
                record_video=True
            )
            
            # Create a page to check authentication
            page = await context.new_page()
            
            # Navigate to Twitter home
            logger.info("Navigating to Twitter home page")
            await page.goto("https://x.com/home")
            
            # Take screenshot for verification
            timestamp = int(time.time())
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"auth_check_{timestamp}.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Saved screenshot to {screenshot_path}")
            
            # Check if we're authenticated
            is_auth = await auth_manager.is_authenticated(page)
            
            if is_auth:
                logger.info("✅ Successfully authenticated to Twitter/X")
                profile_dir = auth_manager.get_auth_profile_dir()
                logger.info(f"Profile directory: {profile_dir}")
                logger.info("Browser session is ready to use")
                return True
            else:
                logger.error("❌ Not authenticated to Twitter/X")
                logger.info("Will attempt to authenticate now...")
                
                # Try to authenticate
                auth_result = await auth_manager.authenticate(page)
                
                if auth_result:
                    logger.info("✅ Authentication successful")
                    return True
                else:
                    logger.error("❌ Authentication failed")
                    return False
                
        except Exception as e:
            logger.error(f"Error creating browser: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # Clean up
            if 'playwright' in locals():
                await playwright.stop()
    
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point"""
    result = asyncio.run(check_auth_status())
    if result:
        print("\n✅ Twitter/X authentication is working correctly")
    else:
        print("\n❌ Twitter/X authentication is NOT working")
        print("Please check the logs for details")
    return result

if __name__ == "__main__":
    exit(0 if main() else 1) 