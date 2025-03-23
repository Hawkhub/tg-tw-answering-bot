#!/usr/bin/env python3
import asyncio
import os
import time
import sys
import logging

# Add parent directory to path to import from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import X_USERNAME, X_PASSWORD
from tweet_fetcher.extractors.auth_playwright.browser import create_authenticated_browser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_login')

async def test_login_and_fetch_tweet():
    """
    Test the login process and fetch a tweet to verify functionality.
    
    1. Tests username/password authentication
    2. Navigates to a specific tweet
    3. Takes screenshots at each step
    4. Verifies that tweet content can be extracted
    """
    if not X_USERNAME or not X_PASSWORD:
        print("ERROR: X_USERNAME and X_PASSWORD must be set in the .env file")
        print("Please update your .env file with valid credentials and run 'source .env'")
        return
    
    print(f"Starting login test with username: {X_USERNAME}")
    
    # Ensure temp directories exist
    os.makedirs(".temp/screenshots/login", exist_ok=True)
    
    # Create authenticated browser with credentials
    playwright, context, auth_manager = None, None, None
    try:
        print("Creating authenticated browser...")
        playwright, context, auth_manager = await create_authenticated_browser(
            username=X_USERNAME,
            password=X_PASSWORD
        )
        
        # Create a page
        page = await context.new_page()
        
        # Take a screenshot to verify login status
        timestamp = int(time.time())
        screenshot_path = os.path.join(".temp/screenshots/login", f"login_result_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        print(f"Saved login status screenshot to: {screenshot_path}")
        
        # Navigate to the example tweet
        tweet_url = "https://x.com/ImjustPage/status/1855969758681972736"
        print(f"Navigating to tweet: {tweet_url}")
        
        await page.goto(tweet_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # Wait for page to load fully
        
        # Take a screenshot of the tweet page
        screenshot_path = os.path.join(".temp/screenshots/login", f"tweet_page_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        print(f"Saved tweet page screenshot to: {screenshot_path}")
        
        # Check if tweet content is visible
        tweet_text = await page.query_selector("article div[data-testid='tweetText']")
        if tweet_text:
            text_content = await tweet_text.inner_text()
            print(f"Successfully found tweet text: '{text_content}'")
        else:
            print("Could not find tweet text. Check the screenshots.")
        
        # Check if we can interact with the page
        print("Testing interaction by scrolling the page...")
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(1)
        
        # Take a final screenshot after interaction
        screenshot_path = os.path.join(".temp/screenshots/login", f"after_interaction_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        print(f"Saved post-interaction screenshot to: {screenshot_path}")
        
        # Try to exit profile to verify navigation works
        print("Testing navigation to home page...")
        await page.goto("https://x.com/home", timeout=30000)
        await asyncio.sleep(2)
        
        # Take a final screenshot after navigation
        screenshot_path = os.path.join(".temp/screenshots/login", f"home_page_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        print(f"Saved home page screenshot to: {screenshot_path}")
        
        # Verify we're logged in by checking user menu
        user_menu = await page.query_selector("div[data-testid='SideNav_AccountSwitcher_Button']")
        if user_menu:
            print("User menu found - authentication appears successful")
        else:
            print("User menu not found - login may have failed")
        
        return True
    
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Close the browser
        if playwright:
            await playwright.stop()
            print("Browser closed")

if __name__ == "__main__":
    asyncio.run(test_login_and_fetch_tweet()) 