#!/usr/bin/env python3
"""
Session Persistence Test Script

This script tests whether our authentication session is properly persisted between
separate tweet extraction calls.
"""

import os
import sys
import asyncio
import argparse
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('session_test')

# Get screenshots directory
try:
    from tweet_fetcher.config import SCREENSHOTS_DIR
    TEST_DIR = os.path.join(SCREENSHOTS_DIR, "test_session")
    os.makedirs(TEST_DIR, exist_ok=True)
except ImportError:
    TEST_DIR = ".temp/screenshots/test_session"
    os.makedirs(TEST_DIR, exist_ok=True)

def fetch_tweet(tweet_url, save_screenshot=True):
    """Fetch a tweet using the authenticated session"""
    
    from tweet_fetcher import get_tweet_from_url
    
    logger.info(f"Fetching tweet from URL: {tweet_url}")
    
    # Extract tweet using the authenticated approach
    # This will use the credentials from .env file
    start_time = time.time()
    result = get_tweet_from_url(
        url=tweet_url,
        use_auth=True  # Force authenticated mode
    )
    end_time = time.time()
    
    # Log the result
    logger.info(f"Tweet fetched in {end_time - start_time:.2f} seconds")
    
    if "error" in result:
        logger.error(f"Error fetching tweet: {result['error']}")
        return False
    
    # Save a screenshot of the tweet content
    if save_screenshot:
        # Take a screenshot if possible - this is just for debugging
        try:
            from playwright.async_api import async_playwright
            
            async def save_screenshot():
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch()
                context = await browser.new_context()
                page = await context.new_page()
                
                # Go to the tweet URL
                await page.goto(tweet_url)
                
                # Take a screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(TEST_DIR, f"tweet_{timestamp}.png")
                await page.screenshot(path=screenshot_path)
                logger.info(f"Saved tweet screenshot to {screenshot_path}")
                
                await browser.close()
                await playwright.stop()
            
            # Run the screenshot function
            asyncio.run(save_screenshot())
        except Exception as e:
            logger.warning(f"Could not save tweet screenshot: {e}")
    
    tweet_text = result.get('text', 'No text found')
    logger.info(f"Tweet text: {tweet_text[:100]}...")
    logger.info(f"Media URLs count: {len(result.get('media_urls', []))}")
    
    # Print all media URLs
    for i, url in enumerate(result.get('media_urls', [])):
        logger.info(f"Media URL {i+1}: {url}")
    
    return result

def main():
    """Main function to test session persistence"""
    parser = argparse.ArgumentParser(description='Test Twitter/X session persistence')
    parser.add_argument('--url', default="https://x.com/ImjustPage/status/1855969758681972736",
                      help='URL of tweet to fetch (default: %(default)s)')
    parser.add_argument('--repeats', type=int, default=3,
                      help='Number of times to fetch the tweet (default: %(default)s)')
    parser.add_argument('--delay', type=int, default=5,
                      help='Delay between fetches in seconds (default: %(default)s)')
    parser.add_argument('--screenshots', action='store_true',
                      help='Save screenshots of tweets for debugging')
    
    args = parser.parse_args()
    
    # Log important info about the test
    logger.info("Starting session persistence test")
    logger.info(f"Tweet URL: {args.url}")
    logger.info(f"Will fetch {args.repeats} times with {args.delay}s delay between fetches")
    logger.info(f"Using auth credentials: {os.environ.get('X_USERNAME')}")
    logger.info(f"Save screenshots: {args.screenshots}")
    
    # Verify we're authenticated first
    logger.info("Checking authentication status")
    from check_auth import check_auth_status
    auth_result = asyncio.run(check_auth_status())
    if not auth_result:
        logger.error("Not authenticated to Twitter/X. Please run ./check_auth.py first")
        return False
    
    # Fetch the tweet multiple times
    for i in range(args.repeats):
        logger.info(f"\n--- Fetch #{i+1} ---")
        result = fetch_tweet(args.url, save_screenshot=args.screenshots)
        
        if i < args.repeats - 1:
            logger.info(f"Waiting {args.delay} seconds before next fetch...")
            time.sleep(args.delay)
    
    logger.info("\nSession persistence test complete")
    logger.info("Check logs to see if authentication was reused correctly")
    logger.info("If authentication is persistent, there should be no login attempts after the first fetch")

if __name__ == "__main__":
    main() 