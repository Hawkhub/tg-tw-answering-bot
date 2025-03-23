import random
import logging
import os
from playwright.async_api import async_playwright

from tweet_fetcher.config import USER_AGENTS, PROFILES_DIR

logger = logging.getLogger('tweet_fetcher')

async def create_browser_context(user_data_dir=None):
    """
    Create a browser context with stealth and anti-detection measures
    
    Args:
        user_data_dir (str): Optional path to a user data directory
                            If None, a random profile will be used
                            
    Returns:
        tuple: (playwright instance, browser context)
    """
    logger.info("Creating browser context with stealth measures")
    
    p = await async_playwright().start()
    browser_type = p.chromium
    
    # Create user data directory if not provided
    if not user_data_dir:
        profile_id = random.randint(1, 5)
        user_data_dir = os.path.join(PROFILES_DIR, f"profile_{profile_id}")
    
    # Randomized browser configuration
    viewport = {"width": random.randint(1280, 1920), "height": random.randint(800, 1080)}
    user_agent = random.choice(USER_AGENTS)
    locale = random.choice(["en-US", "en-GB", "en-CA"])
    timezone_id = random.choice(["America/New_York", "Europe/London", "Asia/Tokyo"])
    color_scheme = random.choice(["light", "dark"])
    device_scale_factor = random.choice([1, 2])
    has_touch = random.choice([True, False])
    
    # Create browser context
    try:
        context = await browser_type.launch_persistent_context(
            user_data_dir,
            headless=True,
            viewport=viewport,
            user_agent=user_agent,
            locale=locale,
            timezone_id=timezone_id,
            color_scheme=color_scheme,
            device_scale_factor=device_scale_factor,
            has_touch=has_touch,
            is_mobile=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',
                '--disable-site-isolation-trials'
            ]
        )
        
        # Add fingerprint evasion
        await context.add_init_script("""
            // Override fingerprinting functions
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // Randomize certain WebGL parameters
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris Graphics';
                }
                return originalGetParameter.call(this, parameter);
            };
            
            // Spoof navigator properties
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Random plugins length to avoid fingerprinting
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return { length: Math.floor(Math.random() * 10) + 1 };
                }
            });
        """)
        
        return p, context
    except Exception as e:
        await p.stop()
        logger.error(f"Failed to create browser context: {e}")
        raise 