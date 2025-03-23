#!/usr/bin/env python3
"""
Simple Debug Login Process Recorder

This script records a video of the Twitter/X login process to help with debugging,
using a simplified approach without localStorage checks that might cause errors.
"""

import os
import sys
import asyncio
import argparse
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('debug_login')

async def record_login_process(username=None, password=None, phone_number=None):
    """Record a video of the login process using a simplified approach"""
    try:
        from playwright.async_api import async_playwright
        from tweet_fetcher.extractors.auth_playwright.auth import TwitterAuth
        from tweet_fetcher.config import POPULAR_RESOLUTIONS, AUTH_USER_AGENT, SCREENSHOTS_DIR
        
        # Create video recordings directory
        VIDEO_DIR = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "videos")
        os.makedirs(VIDEO_DIR, exist_ok=True)
        
        # Get username and password from env vars if not provided
        if not username:
            username = os.environ.get('X_USERNAME')
        if not password:
            password = os.environ.get('X_PASSWORD')
        if not phone_number:
            phone_number = os.environ.get('X_PHONE_NUMBER')
            
        if not username or not password:
            logger.error("Username and password are required. Set X_USERNAME and X_PASSWORD environment variables or pass as arguments.")
            return False
            
        logger.info(f"Starting debug login recording for {username}")
        logger.info(f"Video will be saved to {VIDEO_DIR}")
        if phone_number:
            logger.info(f"Phone number is provided for verification if needed")
        
        # Start playwright
        playwright = await async_playwright().start()
        
        try:
            # Create auth manager
            auth_manager = TwitterAuth(username, password, phone_number)
            
            # Get profile directory
            user_data_dir = auth_manager.get_auth_profile_dir()
            
            # Set up video recording
            timestamp = os.path.basename(__file__).split('.')[0] + "_" + str(int(asyncio.get_event_loop().time()))
            video_path = os.path.join(VIDEO_DIR, f"login_{username}_{timestamp}.webm")
            
            # Launch browser
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                record_video_dir=VIDEO_DIR,
                record_video_size={"width": 1280, "height": 800}
            )
            
            # Create page
            page = await context.new_page()
            
            # Navigate to Twitter login
            logger.info("Navigating to Twitter login page")
            await page.goto("https://x.com/login", timeout=60000)
            
            # Take screenshot
            screenshot_path = os.path.join(SCREENSHOTS_DIR, "login", f"debug_login_{timestamp}.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Saved screenshot to {screenshot_path}")
            
            # Check if we're already logged in
            is_auth = await auth_manager.is_authenticated(page)
            if is_auth:
                logger.info("Already authenticated")
            else:
                # Perform login
                logger.info("Attempting to login")
                await auth_manager.authenticate(page)
                
                # Check authentication status
                is_auth = await auth_manager.is_authenticated(page)
                logger.info(f"Authentication status: {'Success' if is_auth else 'Failed'}")
            
            # Wait a bit to finish recording
            logger.info("Login process completed, waiting to finalize recording")
            await asyncio.sleep(3)
            
            # Save video
            try:
                video = page.video
                if video:
                    video_file_path = await video.path()
                    logger.info(f"Video recorded at {video_file_path}")
                    
                    # Rename to our desired path
                    final_video_path = os.path.join(VIDEO_DIR, f"login_{username}_{timestamp}.webm")
                    if os.path.exists(video_file_path) and not os.path.exists(final_video_path):
                        os.rename(video_file_path, final_video_path)
                        logger.info(f"Video saved as {final_video_path}")
            except Exception as e:
                logger.error(f"Error saving video: {e}")
            
            # Close browser
            await context.close()
            
            logger.info("Debug login recording complete")
            return True
            
        finally:
            await playwright.stop()
            
    except Exception as e:
        logger.error(f"Error recording login process: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Debug Login Process Recorder')
    parser.add_argument('--username', help='Twitter/X username')
    parser.add_argument('--password', help='Twitter/X password')
    parser.add_argument('--phone', help='Phone number for verification (with country code)')
    args = parser.parse_args()
    
    # Run the async function
    asyncio.run(record_login_process(args.username, args.password, args.phone))

if __name__ == "__main__":
    main() 