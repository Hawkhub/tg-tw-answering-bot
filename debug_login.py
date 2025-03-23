#!/usr/bin/env python3
"""
Debug Login Process Recorder

This script records a video of the Twitter/X login process to help with debugging.
The video will be saved in .temp/videos directory along with screenshots and HTML dumps
of the login flow.
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

async def record_login_process(username=None, password=None):
    """Record a video of the login process"""
    try:
        from tweet_fetcher.extractors.auth_playwright.browser import BrowserSessionManager, VIDEO_DIR
        
        # Get username and password from env vars if not provided
        if not username:
            username = os.environ.get('X_USERNAME')
        if not password:
            password = os.environ.get('X_PASSWORD')
            
        if not username or not password:
            logger.error("Username and password are required. Set X_USERNAME and X_PASSWORD environment variables or pass as arguments.")
            return False
            
        logger.info(f"Starting debug login recording for {username}")
        logger.info(f"Video will be saved to {VIDEO_DIR}")
        
        # Get browser session with video recording enabled
        playwright, context, auth_manager = await BrowserSessionManager.get_browser_session(
            username=username,
            password=password,
            record_video=True
        )
        
        # Wait a moment to ensure login process is completed
        logger.info("Waiting for login process to complete...")
        await asyncio.sleep(5)
        
        # Close browser session
        logger.info("Closing browser session")
        await BrowserSessionManager.close_all_sessions()
        
        logger.info("Debug login recording complete")
        logger.info(f"Check {VIDEO_DIR} for the recorded video")
        return True
        
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
    args = parser.parse_args()
    
    # Run the async function
    asyncio.run(record_login_process(args.username, args.password))

if __name__ == "__main__":
    main() 