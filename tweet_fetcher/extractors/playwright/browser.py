import random
import logging
import os
import time
from playwright.async_api import async_playwright

from tweet_fetcher.config import USER_AGENTS, PROFILES_DIR, POPULAR_RESOLUTIONS, SCREENSHOTS_DIR

logger = logging.getLogger('tweet_fetcher')

async def create_browser_context(record_video=False, record_quality='medium'):
    """
    Create a browser context with stealth measures for tweet extraction
    
    Args:
        record_video (bool): Whether to record the browser session
        record_quality (str): Recording quality ('low', 'medium', 'high')
    
    Returns:
        tuple: (playwright, browser_context)
    """
    # Map quality settings to resolutions
    quality_to_resolution = {
        'low': {'width': 854, 'height': 480},
        'medium': {'width': 1280, 'height': 720},
        'high': {'width': 1920, 'height': 1080}
    }
    
    # Default to medium if quality not found
    video_size = quality_to_resolution.get(record_quality, quality_to_resolution['medium'])
    
    # Generate a random viewport size that matches the recording resolution
    if record_video:
        viewport = video_size.copy()
    else:
        # Use a random resolution from config
        viewport = random.choice(POPULAR_RESOLUTIONS)
    
    try:
        playwright = await async_playwright().start()
        
        # Choose a random user agent
        user_agent = random.choice(USER_AGENTS)
        
        # Setup recording options if enabled
        recording_options = {}
        if record_video:
            # Create a unique filename for the recording
            timestamp = int(time.time())
            videos_dir = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "videos")
            os.makedirs(videos_dir, exist_ok=True)
            
            recording_options = {
                "record_video_dir": videos_dir,
                "record_video_size": video_size
            }
            
        # Launch browser with anti-detection measures
        browser = await playwright.chromium.launch(
            headless=True,
            args=BROWSER_ARGS
        )
        
        # Create a context with privacy and anti-fingerprinting measures
        context = await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale=random.choice(['en-US', 'en-GB', 'en-CA']),
            timezone_id=random.choice(['America/New_York', 'Europe/London', 'Asia/Tokyo']),
            **recording_options
        )
        
        # Stealth setup - prevent detection
        await context.add_init_script("""
            // Overwrite the navigator properties to make detection harder
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Hide automation flags in Chrome
            if (window.chrome) {
                window.chrome.runtime = {};
            }
            
            // Make permissions API return random values
            if (navigator.permissions) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = (parameters) => {
                    if (parameters.name === 'notifications' || parameters.name === 'geolocation') {
                        return Promise.resolve({ state: "prompt" });
                    }
                    return originalQuery(parameters);
                };
            }
        """)
        
        # Return created browser and context
        return playwright, context
        
    except Exception as e:
        logger.error(f"Failed to create browser context: {e}")
        if 'playwright' in locals():
            await playwright.stop()
        raise 