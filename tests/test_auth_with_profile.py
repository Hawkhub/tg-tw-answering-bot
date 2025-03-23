#!/usr/bin/env python3
import asyncio
import os
import random
import time
from config import X_COOKIE_TABLE
from tweet_fetcher.extractors.auth_playwright.auth import TwitterAuth
from tweet_fetcher.extractors.auth_playwright.browser import create_authenticated_browser

async def test_auth_workflow():
    """
    Test the cookie-based authentication workflow by:
    1. Loading a specific tweet
    2. Taking a screenshot
    3. Clicking on profile avatar
    4. Taking a screenshot of the profile page
    """
    print("Starting authentication test workflow...")
    
    if not X_COOKIE_TABLE:
        print("ERROR: X_COOKIE_TABLE environment variable is not set!")
        print("Please add it to your .env file and then run 'source .env'")
        return
    
    print(f"X_COOKIE_TABLE is set with {len(X_COOKIE_TABLE)} characters")
    
    # Ensure screenshot directory exists
    os.makedirs(".temp/screenshots", exist_ok=True)
    
    # Create authenticated browser with cookie table
    print("Creating authenticated browser...")
    playwright, context, auth_manager = await create_authenticated_browser(cookie_table=X_COOKIE_TABLE)
    
    try:
        # Create a new page
        page = await context.new_page()
        
        # 1. Navigate to the specified tweet
        tweet_url = "https://x.com/ImjustPage/status/1855969758681972736"
        print(f"Navigating to tweet: {tweet_url}")
        
        await page.goto(tweet_url, wait_until="domcontentloaded")
        print("Waiting for content to load...")
        
        # Wait for either the tweet content or some common element to appear
        try:
            await page.wait_for_selector("article", timeout=15000)
        except Exception as e:
            print(f"Warning: {e}")
        
        # Slight delay to ensure page is rendered
        await asyncio.sleep(3)
        
        # 2. Take a screenshot of the tweet page
        tweet_screenshot = f".temp/screenshots/tweet_page_{int(time.time())}.png"
        await page.screenshot(path=tweet_screenshot, full_page=True)
        print(f"Tweet page screenshot saved to: {tweet_screenshot}")
        
        # 3. Find and click on the profile avatar (header account icon)
        print("Looking for profile avatar to click...")
        
        # Try different selectors that might contain the profile link
        selectors = [
            "header a[href*='/home'] ~ div", # Navigation menu with profile
            "header div[data-testid='SideNav_AccountSwitcher_Button']", # Account switcher
            "a[data-testid='AppTabBar_Profile_Link']", # Profile tab in mobile view
            "a[href*='/settings/profile']", # Link to profile settings
            "header a[href*='/settings']", # General settings link
            "a[aria-label*='Profile']", # Profile link with aria label
            "a[data-testid*='Profile']" # Any profile-related testid
        ]
        
        avatar_found = False
        for selector in selectors:
            try:
                avatar = await page.query_selector(selector)
                if avatar:
                    print(f"Found profile element with selector: {selector}")
                    # Get the element position for a more reliable click
                    avatar_box = await avatar.bounding_box()
                    if avatar_box:
                        # Click in the middle of the element
                        await page.mouse.click(
                            avatar_box["x"] + avatar_box["width"] / 2,
                            avatar_box["y"] + avatar_box["height"] / 2
                        )
                        avatar_found = True
                        break
            except Exception as e:
                print(f"Error with selector {selector}: {e}")
        
        if not avatar_found:
            # Try a fallback approach - click on a common header area where profile might be
            print("Avatar not found with selectors, trying fallback approach...")
            
            # Get viewport size
            viewport_size = await page.evaluate("""
                () => {
                    return {
                        width: window.innerWidth,
                        height: window.innerHeight
                    }
                }
            """)
            
            # Click in the top-right area where profile links often are
            right_side = viewport_size["width"] - 50
            top_area = 50
            await page.mouse.click(right_side, top_area)
            
            # Wait to see if a dropdown or navigation appears
            await asyncio.sleep(2)
            
            # Now try to find a profile-related link in any dropdown that appeared
            profile_links = await page.query_selector_all("a[href*='/settings/profile'], a[href*='/with_replies'], a[href*='/home'] ~ div a")
            
            if profile_links:
                print(f"Found {len(profile_links)} potential profile links after clicking")
                # Click the first one
                await profile_links[0].click()
                avatar_found = True
        
        # Wait for navigation and content to load
        await asyncio.sleep(5)
        
        # 4. Take a screenshot of the profile page
        profile_screenshot = f".temp/screenshots/profile_page_{int(time.time())}.png"
        await page.screenshot(path=profile_screenshot, full_page=True)
        print(f"Profile page screenshot saved to: {profile_screenshot}")
        
        # 5. Check if we're on a profile page
        current_url = page.url
        print(f"Current URL after clicking profile: {current_url}")
        
        if "/home" in current_url or "/settings" in current_url or "profile" in current_url:
            print("Success! Authentication worked and we navigated to a profile-related page")
        else:
            print("Warning: Not sure if we reached a profile page. Check the screenshots")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        # Close the browser
        await playwright.stop()
        print("Test completed. Check the screenshots in .temp/screenshots/")


if __name__ == "__main__":
    asyncio.run(test_auth_workflow()) 