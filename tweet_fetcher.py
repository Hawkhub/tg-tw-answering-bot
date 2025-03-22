import requests
from bs4 import BeautifulSoup
import random
import re
import logging
import asyncio
from playwright.async_api import async_playwright
import os
import time
import math
import secrets
from datetime import datetime
import json
from typing import Dict, List, Optional, Any, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tweet_fetcher')

# For tweet URL pattern matching
TWEET_URL_PATTERN = r'https?://(?:www\.)?(twitter|x)\.com/(\w+)/status/(\d+)'

# Create directories for temp files (at the top of the file after imports)
def ensure_temp_dirs():
    """Ensure all temporary directories exist"""
    temp_dirs = [
        '.temp',
        '.temp/html',
        '.temp/screenshots',
        '.temp/media',
        '.temp/profiles'
    ]
    for directory in temp_dirs:
        os.makedirs(directory, exist_ok=True)

# Call this when the module is imported
ensure_temp_dirs()

def extract_tweet_info(url):
    """Extract username and tweet ID from Twitter/X URL"""
    match = re.match(TWEET_URL_PATTERN, url)
    if match:
        username = match.group(2)
        tweet_id = match.group(3)
        return username, tweet_id
    return None, None

def parse_cookie_table(cookie_table_text):
    """
    Parse a cookie table text (copied from browser dev tools) into a dictionary
    
    Args:
        cookie_table_text (str): Tab-separated cookie table text from browser
        
    Returns:
        dict: Dictionary of cookie name-value pairs for X authentication
    """
    cookies = {}
    
    # Skip the header row if present
    lines = cookie_table_text.strip().split('\n')
    if not lines:
        return cookies
        
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 3:  # Need at least name, value, and domain
            continue
            
        name = parts[0].strip()
        value = parts[1].strip()
        domain = parts[2].strip() if len(parts) > 2 else ""
        
        # Only include cookies for .x.com domain and with non-empty values
        if name and value and ('.x.com' in domain or domain == 'x.com'):
            # Remove surrounding quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
                
            cookies[name] = value
            
    return cookies

def get_tweet_content(username, tweet_id, auth_token=None, cookies=None, cookie_table=None):
    """
    Multi-tiered approach to get tweet content:
    1. Use Playwright as primary method for reliable extraction
    2. Fall back to minimal metadata extraction
    3. Support for token-based authenticated approach
    
    Parameters:
        username (str): X username
        tweet_id (str): Tweet ID
        auth_token (str, optional): Authentication token
        cookies (Dict[str, str], optional): Dictionary of cookies for authentication
        cookie_table (str, optional): Raw cookie table text from browser dev tools
        
    Returns:
        dict: Content with 'text', 'media_urls', and 'source'
    """
    logger.info(f"Starting tweet content fetch for @{username}/status/{tweet_id}")
    
    # Create base result with X URL
    result = {'text': None, 'media_urls': [], 'source': f"https://x.com/{username}/status/{tweet_id}"}
    
    # If cookie table is provided, parse it
    if cookie_table and not cookies:
        cookies = parse_cookie_table(cookie_table)
        if cookies:
            logger.info(f"Using {len(cookies)} cookies parsed from cookie table")
    
    # First tier: Use Playwright (most reliable)
    try:
        logger.info("Attempting Playwright extraction as primary method...")
        content = get_tweet_content_with_playwright(username, tweet_id, auth_token, cookies)
        if content and (content.get('text') or content.get('media_urls')):
            logger.info(f"Successfully retrieved tweet content via Playwright")
            return content
        logger.warning("Playwright approach failed to find content")
    except Exception as e:
        logger.error(f"Playwright approach failed with error: {e}")
    
    # Second tier: Try minimal metadata
    try:
        logger.info("Falling back to minimal metadata approach...")
        content = get_tweet_metadata(username, tweet_id)
        if content and (content.get('text') or content.get('media_urls')):
            logger.info(f"Retrieved minimal tweet metadata")
            return content
        logger.warning("Minimal metadata approach failed to find content")
    except Exception as e:
        logger.error(f"Minimal metadata approach failed with error: {e}")
    
    # Return what we have, even if empty
    return result

def get_tweet_metadata(username, tweet_id):
    # Try alternative URL format
    urls_to_try = [
        f"https://x.com/{username}/status/{tweet_id}",
        f"https://twitter.com/{username}/status/{tweet_id}"  # Some systems might still work with twitter.com
    ]
    
    # Even more comprehensive headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    for url in urls_to_try:
        try:
            logger.info(f"Trying metadata from: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            
            # Log more details
            logger.info(f"Response size: {len(response.text)} bytes")
            
            # Save the HTML for debugging - updated path
            debug_path = os.path.join('.temp', 'html', f"debug_tweet_{username}_{tweet_id}.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            logger.info(f"Saved HTML to {debug_path}")
            
            # Dump all meta tags for debugging
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_tags = soup.find_all('meta')
            for tag in meta_tags:
                if tag.get('content'):
                    logger.debug(f"Meta tag: {tag.get('name') or tag.get('property')} = {tag.get('content')[:50]}...")
            
            # Just get title and any image we can find
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else None
            
            # Log the raw title to help with debugging
            if title_text:
                logger.debug(f"Raw title: {title_text}")
            
            # Clean up the title if we got one
            if title_text:
                # Try several patterns to extract the actual tweet text
                patterns = [
                    r'(?:on X|on Twitter):\s*"(.+?)".*',  # "Text" on Twitter
                    r'^.*?:\s*(.+?)(?:\s*[/|].*)?$',      # Username: Text | on...
                    r'"(.+?)"'                            # Any quoted text
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, title_text)
                    if match:
                        title_text = match.group(1)
                        break
            
            # Improved media extraction with better filtering
            media_urls = []
            
            # Look for Twitter card image which is usually the tweet media
            card_img = soup.find('meta', attrs={'name': 'twitter:image'})
            if card_img and 'content' in card_img.attrs:
                img_url = card_img['content']
                # Filter out profile images and site icons
                if not any(x in img_url.lower() for x in ['profile_images', 'icon', 'logo']):
                    media_urls.append(img_url)
            
            # Look for OG image as fallback
            if not media_urls:
                og_img = soup.find('meta', attrs={'property': 'og:image'})
                if og_img and 'content' in og_img.attrs:
                    img_url = og_img['content']
                    # Filter out profile images and site icons
                    if not any(x in img_url.lower() for x in ['profile_images', 'icon', 'logo']):
                        media_urls.append(img_url)
            
            # Look for any image with 'media' in URL as last resort
            if not media_urls:
                imgs = soup.find_all('img')
                for img in imgs:
                    if 'src' in img.attrs:
                        img_url = img['src']
                        # Prioritize URLs that look like tweet media
                        if any(x in img_url.lower() for x in ['media', 'photo', 'video', 'tweet']):
                            if not any(x in img_url.lower() for x in ['profile_images', 'icon', 'logo']):
                                media_urls.append(img_url)
                                break
            
            # Log what we found with better context
            logger.info(f"Metadata approach found text: {bool(title_text)} and {len(media_urls)} media items")
            if media_urls:
                logger.info(f"Media URLs: {media_urls}")
            
            return {
                'text': title_text,
                'media_urls': media_urls,
                'source': url
            }
        
        except Exception as e:
            logger.warning(f"Metadata extraction error: {str(e)}")
            continue
    
    logger.error("All metadata retrieval methods failed")
    return None

def download_media(url, output_path):
    """
    Download media from URL to the specified path
    Returns True if successful, False otherwise
    """
    try:
        logger.info(f"Downloading media from {url}")
        response = requests.get(url, stream=True, timeout=30)
        
        if response.status_code != 200:
            logger.warning(f"Download received non-200 status code: {response.status_code}")
            return False
            
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Successfully downloaded media to {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error downloading media: {str(e)}")
        return False

# Testing function - use this to debug specific tweet fetching
def test_tweet_fetch(username, tweet_id):
    """
    Test function to fetch a tweet and print the results for debugging
    """
    print(f"Testing tweet fetch for @{username}/status/{tweet_id}")
    result = get_tweet_content(username, tweet_id)
    
    print("\nRESULT:")
    print(f"Text: {result.get('text')}")
    print(f"Media URLs: {result.get('media_urls')}")
    print(f"Source: {result.get('source')}")
    
    return result

def create_session_fingerprint():
    """Create a unique, consistent fingerprint for this browsing session"""
    # Get a hardware-based seed if possible (like MAC address hash)
    try:
        import uuid
        mac = uuid.getnode()
        base_seed = mac
    except:
        # Fallback to current date (consistent within same day)
        now = datetime.now()
        base_seed = now.year * 10000 + now.month * 100 + now.day
    
    # Generate session fingerprint from seed
    fingerprint = {
        "session_id": f"session_{base_seed}_{secrets.token_hex(4)}",
        "device_name": f"Chrome on {['Windows', 'MacOS'][base_seed % 2]}",
        "screen_width": [1920, 2560, 3440][base_seed % 3],
        "screen_height": [1080, 1440, 1600][base_seed % 3],
        "color_depth": 24,
        "timezone": ["America/New_York", "Europe/London", "Asia/Tokyo"][base_seed % 3],
        "language": ["en-US", "en-GB", "en-CA"][base_seed % 3],
    }
    return fingerprint

class XCookieManager:
    """
    Manages cookies for X.com (Twitter) authentication
    - Stores cookies in a mutable dictionary
    - Allows for initial setup from external source
    - Can persist cookies between sessions
    - Handles browser cookie updates
    """
    
    def __init__(self, initial_cookies: Optional[Dict[str, str]] = None):
        """Initialize with optional dictionary of cookie values"""
        self.cookies = {}
        
        # List of important X.com cookies
        self.essential_cookies = [
            'auth_token',    # Main authentication token
            'ct0',           # CSRF token
            'twid',          # User ID cookie
            'kdt',           # Known device token
            'remember_checked_on',
            'guest_id',
            'personalization_id',
            'lang'
        ]
        
        # Initialize with provided cookies
        if initial_cookies:
            self.set_cookies(initial_cookies)
        
        # Cookie storage path
        self._storage_path = os.path.join('.temp', 'cookies', 'x_cookies.json')
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
    
    def set_cookies(self, cookie_dict: Dict[str, str]) -> None:
        """Set multiple cookies from dictionary"""
        for name, value in cookie_dict.items():
            if value:  # Only add non-empty values
                self.cookies[name] = value
    
    def get_cookie(self, name: str) -> Optional[str]:
        """Get a cookie value by name"""
        return self.cookies.get(name)
    
    def save_cookies(self) -> None:
        """Save cookies to file"""
        try:
            with open(self._storage_path, 'w') as f:
                json.dump(self.cookies, f)
            logger.info(f"Saved {len(self.cookies)} cookies to {self._storage_path}")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
    
    def load_cookies(self) -> bool:
        """Load cookies from file, returns True if successful"""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, 'r') as f:
                    loaded_cookies = json.load(f)
                    self.cookies.update(loaded_cookies)
                logger.info(f"Loaded {len(loaded_cookies)} cookies from {self._storage_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False
    
    def get_browser_cookies(self) -> List[Dict[str, Any]]:
        """Convert to browser-compatible cookie format for Playwright"""
        browser_cookies = []
        
        for name, value in self.cookies.items():
            if not value:  # Skip empty values
                continue
                
            cookie = {
                'name': name,
                'value': value,
                'domain': '.x.com',
                'path': '/',
                'secure': True,
                'sameSite': 'None'
            }
            
            # Add httpOnly for certain cookies
            if name in ['auth_token', 'twid', 'kdt']:
                cookie['httpOnly'] = True
                
            browser_cookies.append(cookie)
            
        return browser_cookies
    
    def update_from_response_cookies(self, response_cookies: List[Dict[str, Any]]) -> None:
        """Update cookies from browser response"""
        for cookie in response_cookies:
            if cookie.get('name') and cookie.get('value'):
                self.cookies[cookie['name']] = cookie['value']
                logger.debug(f"Updated cookie from response: {cookie['name']}")
        
        # Save after update
        self.save_cookies()
    
    def has_auth_token(self) -> bool:
        """Check if we have valid auth token"""
        return bool(self.get_cookie('auth_token'))

async def setup_cookie_monitoring(page, cookie_manager: XCookieManager):
    """Set up cookie monitoring to capture and update cookies from responses"""
    
    async def handle_response(response):
        try:
            # Get cookies from response
            response_cookies = await page.context.cookies()
            if response_cookies:
                # Update our cookie manager
                cookie_manager.update_from_response_cookies(response_cookies)
        except Exception as e:
            logger.debug(f"Error processing response cookies: {e}")
    
    # Listen for responses to capture cookies
    page.on('response', handle_response)
    
    # Return the handler for potential cleanup
    return handle_response

async def get_tweet_content_with_playwright_async(username, tweet_id, auth_token=None, cookies=None):
    """
    Async Playwright implementation with enhanced human-like behavior and cookie support.
    
    Parameters:
        username (str): The X username
        tweet_id (str): The tweet ID
        auth_token (str, optional): Legacy authentication token (will be converted to cookie)
        cookies (Dict[str, str], optional): Dictionary of cookies to use for authentication
    """
    logger.info(f"Starting enhanced human-like extraction for @{username}/status/{tweet_id}")
    
    # Initialize media_urls
    media_urls = []
    
    # Create cookie manager and initialize with provided cookies
    cookie_manager = XCookieManager()
    
    # If auth_token is provided, add it to cookies
    if auth_token:
        cookie_manager.set_cookies({
            'auth_token': auth_token,
            # Generate a basic CSRF token (Twitter usually derives this)
            'ct0': auth_token[:12] + auth_token[-12:]
        })
    
    # If additional cookies are provided, add them
    if cookies:
        cookie_manager.set_cookies(cookies)
    
    # Try to load saved cookies if we don't have auth credentials
    if not cookie_manager.has_auth_token():
        cookie_manager.load_cookies()
    
    # Create session fingerprint and user directory as before
    session = create_session_fingerprint()
    user_data_dir = os.path.join(os.getcwd(), ".temp", "profiles", f"persistent_profile_{session['session_id']}")
    
    try:
        async with async_playwright() as p:
            # Browser setup code (same as before)
            browser_type = p.chromium
            
            # Browser args (same as before)
            browser_args = [
                # Disable automation indicators
                '--disable-blink-features=AutomationControlled',
                
                # Enhanced hardware acceleration and performance
                '--enable-features=NetworkService,NetworkServiceInProcess',
                '--enable-webassembly',
                '--enable-webassembly-threads',
                '--enable-webgl',
                '--use-gl=desktop',
                '--enable-gpu-rasterization',
                '--enable-oop-rasterization',
                '--enable-zero-copy',
                '--enable-accelerated-2d-canvas',
                '--ignore-gpu-blocklist',
                '--enable-surface-synchronization',
                '--canvas-msaa-sample-count=0',
                '--enable-parallel-downloading',
                
                # Advanced media capabilities
                '--autoplay-policy=no-user-gesture-required',
                '--enable-media-stream',
                '--use-fake-device-for-media-stream',
                '--use-fake-ui-for-media-stream',
                '--enable-features=MediaCapabilitiesDecodingInfo',
                
                # Memory and performance settings
                '--js-flags="--max-old-space-size=8192"',
                '--renderer-process-limit=10',
                '--enable-threaded-compositing',
                '--max-active-webgl-contexts=16',
                
                # Security and persistence settings
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--allow-running-insecure-content',
                '--disable-popup-blocking',
                
                # Stability flags
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-zygote',
                '--no-default-browser-check',
                '--disable-notifications',
                '--mute-audio'  # Prevent unexpected sounds
            ]
            
            # Launch the browser with persistent context
            context = await browser_type.launch_persistent_context(
                user_data_dir,
                headless=False,
                viewport={"width": session['screen_width'], "height": session['screen_height']},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                locale=session['language'],
                timezone_id=session['timezone'],
                color_scheme="light",
                device_scale_factor=1.0,
                has_touch=False,
                is_mobile=False,
                args=browser_args,
                bypass_csp=True,
                ignore_https_errors=True,
                accept_downloads=True,
                record_har_path=os.path.join('.temp', 'network_logs', f"{session['session_id']}_{username}_{tweet_id}.har"),
                record_video_dir=os.path.join('.temp', 'videos'),
                persistent_context_options={
                    'accept_downloads': True,
                    'ignore_https_errors': True,
                }
            )
            
            # Create a new page
            page = await context.new_page()
            
            # Set up cookie monitoring to track changes
            await setup_cookie_monitoring(page, cookie_manager)
            
            # Set timeouts
            await page.set_default_timeout(120000)
            await page.set_default_navigation_timeout(120000)
            
            # Apply cookies if we have any
            if cookie_manager.cookies:
                logger.info(f"Setting {len(cookie_manager.get_browser_cookies())} cookies for X authentication")
                
                # First navigate to domain to establish context
                await page.goto("https://x.com", wait_until="domcontentloaded")
                
                # Set all our cookies
                await page.context.add_cookies(cookie_manager.get_browser_cookies())
                
                # Wait for cookies to be processed
                await asyncio.sleep(2.0)
                logger.info("Authentication cookies set successfully")
                
                # Get and log the updated cookies (for verification)
                updated_cookies = await page.context.cookies()
                logger.info(f"Browser has {len(updated_cookies)} cookies after setup")
            
            # Navigate to the tweet
            logger.info(f"Navigating to tweet with authentication")
            await page.goto(
                f"https://x.com/{username}/status/{tweet_id}",
                wait_until="domcontentloaded"
            )
            
            # 3. CHANGE SCROLLING TO NATURAL MOUSE MOVEMENTS
            # Mouse movement utility functions
            async def natural_mouse_curve(start_x, start_y, end_x, end_y, control_points=1):
                """Generate and follow a natural mouse movement curve"""
                # Create control points for the curve
                points = [(start_x, start_y)]
                
                # Add random control points to make the curve more natural
                for i in range(control_points):
                    # Calculate a point that deviates from the straight line
                    progress = (i + 1) / (control_points + 1)
                    line_x = start_x + (end_x - start_x) * progress
                    line_y = start_y + (end_y - start_y) * progress
                    
                    # Add randomness to the control point
                    ctrl_x = line_x + random.uniform(-80, 80) * (1 - progress * progress)
                    ctrl_y = line_y + random.uniform(-50, 50) * (1 - progress * progress)
                    
                    points.append((ctrl_x, ctrl_y))
                
                # Add destination
                points.append((end_x, end_y))
                
                # Follow the curve
                steps = random.randint(15, 25)  # More steps for smoother movement
                
                # Calculate points along the curve using Bézier curve algorithm
                # This is an approximation for a curve with arbitrary control points
                for i in range(steps + 1):
                    t = i / steps
                    
                    # Use De Casteljau's algorithm for the curve
                    current_points = points.copy()
                    while len(current_points) > 1:
                        new_points = []
                        for j in range(len(current_points) - 1):
                            x = current_points[j][0] * (1 - t) + current_points[j + 1][0] * t
                            y = current_points[j][1] * (1 - t) + current_points[j + 1][1] * t
                            new_points.append((x, y))
                        current_points = new_points
                    
                    # Move to point
                    point_x, point_y = current_points[0]
                    
                    # Create easing effect - slower at start and end
                    delay = 0.01 + 0.03 * (1 - abs(2 * t - 1))
                    
                    await page.mouse.move(point_x, point_y)
                    await asyncio.sleep(delay)
                
                return end_x, end_y  # Return the final position
            
            async def natural_scroll_with_mouse():
                """Scroll the page using natural mouse movements instead of synthetic scrolling"""
                # Get page dimensions
                dimensions = await page.evaluate('''() => {
                    return {
                        scrollHeight: document.documentElement.scrollHeight,
                        clientHeight: window.innerHeight,
                        scrollTop: document.documentElement.scrollTop
                    }
                }''')
                
                # Get a scrollbar position on the right side
                viewport = await page.viewport_size()
                scrollbar_x = viewport['width'] - random.randint(5, 15)
                
                # Current scroll position
                current_scroll_top = dimensions['scrollTop']
                current_y = current_scroll_top / dimensions['scrollHeight'] * viewport['height']
                
                # Number of scroll operations
                scroll_operations = random.randint(3, 5)
                
                for i in range(scroll_operations):
                    # Decide how far to scroll (more realistic to scroll in chunks)
                    scroll_amount = random.randint(300, 700)
                    
                    # Calculate new scroll position
                    new_scroll_top = min(
                        current_scroll_top + scroll_amount,
                        dimensions['scrollHeight'] - dimensions['clientHeight']
                    )
                    
                    # Calculate corresponding y position on scrollbar
                    new_y = (new_scroll_top / dimensions['scrollHeight']) * viewport['height']
                    
                    # Move mouse to scrollbar
                    await natural_mouse_curve(
                        viewport['width'] / 2, current_y,  # Start from middle of current view
                        scrollbar_x, current_y  # Move to scrollbar at same height
                    )
                    
                    # Move down along scrollbar (with mouse button pressed)
                    await page.mouse.down()
                    await natural_mouse_curve(
                        scrollbar_x, current_y,
                        scrollbar_x, new_y,
                        control_points=2  # More control points for more natural drag
                    )
                    await page.mouse.up()
                    
                    # Update current position
                    current_scroll_top = new_scroll_top
                    current_y = new_y
                    
                    # Pause like a human reading content
                    await asyncio.sleep(random.uniform(1.0, 2.5))
                    
                    # Occasionally move mouse to an interesting element
                    if random.random() < 0.7:
                        interesting_selectors = [
                            'article', 'a', 'button', 'img', 'video',
                            '[role="button"]', '[data-testid]'
                        ]
                        
                        selector = random.choice(interesting_selectors)
                        elements = await page.query_selector_all(selector)
                        
                        if elements and len(elements) > 0:
                            random_element = random.choice(elements)
                            try:
                                bbox = await random_element.bounding_box()
                                if bbox:
                                    element_x = bbox['x'] + bbox['width'] / 2
                                    element_y = bbox['y'] + bbox['height'] / 2
                                    
                                    # Only move to element if it's in viewport
                                    if (element_y > current_scroll_top and 
                                        element_y < current_scroll_top + dimensions['clientHeight']):
                                        await natural_mouse_curve(
                                            scrollbar_x, current_y,
                                            element_x, element_y - current_scroll_top + current_y,
                                            control_points=1
                                        )
                                        
                                        # Briefly hover
                                        await asyncio.sleep(random.uniform(0.3, 0.7))
                                        
                                        # Maybe move the mouse a bit while hovering
                                        if random.random() < 0.3:
                                            await natural_mouse_curve(
                                                element_x, element_y - current_scroll_top + current_y,
                                                element_x + random.uniform(-20, 20),
                                                element_y - current_scroll_top + current_y + random.uniform(-10, 10)
                                            )
                            except Exception as e:
                                logger.debug(f"Error interacting with element: {e}")
            
            # Perform natural scrolling with mouse instead of synthetic scrolling
            try:
                # Wait for initial content load
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                # Perform natural mouse-based scrolling
                await natural_scroll_with_mouse()
                
                # Handle dialogs that might appear during interaction
                dialog_selectors = [
                    'div[role="dialog"]',
                    '[data-testid="sheetDialog"]',
                    'div[data-testid="app-bar-close"]',
                    'div[aria-modal="true"]'
                ]
                
                close_button_texts = ['Not now', 'Cancel', 'Close', 'Skip', 'No thanks']
                
                for selector in dialog_selectors:
                    dialogs = await page.query_selector_all(selector)
                    if dialogs and len(dialogs) > 0:
                        logger.info(f"Found dialog with selector: {selector}")
                        
                        dialog = dialogs[0]
                        dialog_box = await dialog.bounding_box()
                        
                        if dialog_box:
                            # Move mouse to dialog naturally
                            center_x = dialog_box['x'] + dialog_box['width'] / 2
                            center_y = dialog_box['y'] + dialog_box['height'] / 2
                            
                            # Get current mouse position
                            mouse_position = await page.evaluate('() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })')
                            current_x = mouse_position['x'] or center_x - 100
                            current_y = mouse_position['y'] or center_y - 100
                            
                            # Move to dialog
                            await natural_mouse_curve(current_x, current_y, center_x, center_y)
                            
                            # Try to find buttons with specific text
                            for text in close_button_texts:
                                try:
                                    button = await dialog.query_selector(f'text="{text}"')
                                    if button:
                                        button_box = await button.bounding_box()
                                        if button_box:
                                            button_x = button_box['x'] + button_box['width'] / 2
                                            button_y = button_box['y'] + button_box['height'] / 2
                                            
                                            # Move to button
                                            await natural_mouse_curve(center_x, center_y, button_x, button_y)
                                            
                                            # Click naturally with delay between down and up
                                            await page.mouse.down()
                                            await asyncio.sleep(random.uniform(0.05, 0.15))
                                            await page.mouse.up()
                                            
                                            logger.info(f"Clicked button with text: {text}")
                                            await asyncio.sleep(1.0)
                                            break
                                except Exception as e:
                                    logger.warning(f"Error clicking text button: {e}")
                
            except Exception as e:
                logger.warning(f"Natural scrolling or dialog handling failed: {e}")
            
            # The rest of the code continues as before...
            
            # Extract video sources after interaction
            try:
                logger.info("Attempting to extract video sources after human-like interaction")
                
                # Use JavaScript to find all video sources in the page
                video_sources = None  # Initialize first
                try:
                    video_sources = await page.evaluate('''() => {
                        try {
                            const sources = [];
                            const videos = document.querySelectorAll('video');
                            
                            if (!videos || videos.length === 0) return [];
                            
                            videos.forEach(video => {
                                // Get basic info
                                const info = {
                                    src: video.src || null,
                                    currentSrc: video.currentSrc || null,
                                    sources: [],
                                    poster: video.poster || null,
                                    width: video.offsetWidth,
                                    height: video.offsetHeight,
                                    paused: video.paused,
                                    parentNode: null
                                };
                                
                                // Get sources from child elements
                                const sourceElements = video.querySelectorAll('source');
                                sourceElements.forEach(source => {
                                    info.sources.push({
                                        src: source.src || null,
                                        type: source.type || null
                                    });
                                });
                                
                                // Get parent info
                                if (video.parentNode) {
                                    const parent = video.parentNode;
                                    info.parentNode = {
                                        tagName: parent.tagName,
                                        className: parent.className,
                                        id: parent.id
                                    };
                                }
                                
                                sources.push(info);
                            });
                            
                            return sources;
                        } catch (e) {
                            return [{error: e.toString()}];
                        }
                    }''')
                except Exception as js_eval_error:
                    logger.error(f"JavaScript evaluation failed: {js_eval_error}")
                
                if video_sources is not None:
                    logger.info(f"Found {len(video_sources)} video sources via JavaScript")
                    
                    # Extract URLs from the data
                    for video_info in video_sources:
                        if video_info.get('error'):
                            logger.error(f"JavaScript error: {video_info['error']}")
                            continue
                            
                        # Check direct src attribute
                        if video_info.get('src') and video_info['src'].endswith('.mp4'):
                            media_urls.append(video_info['src'])
                            logger.info(f"Found video URL from src: {video_info['src']}")
                        
                        # Check currentSrc attribute
                        elif video_info.get('currentSrc') and video_info['currentSrc'].endswith('.mp4'):
                            media_urls.append(video_info['currentSrc'])
                            logger.info(f"Found video URL from currentSrc: {video_info['currentSrc']}")
                        
                        # Check child source elements
                        elif video_info.get('sources') and len(video_info['sources']) > 0:
                            for source in video_info['sources']:
                                if source.get('src') and source['src'].endswith('.mp4'):
                                    media_urls.append(source['src'])
                                    logger.info(f"Found video URL from source element: {source['src']}")
                else:
                    logger.warning("No video sources found or JavaScript evaluation returned None")
                
                # If we still don't have any media URLs, try alternative approaches
                if not media_urls:
                    logger.info("No video URLs found, trying network requests inspection")
                    
                    # Look for video URLs in page content
                    content = await page.content()
                    mp4_patterns = [
                        r'https://video\.twimg\.com/[^"\']+\.mp4[^"\']*',
                        r'https://pbs\.twimg\.com/[^"\']+/video/[^"\']+\.mp4[^"\']*',
                        r'https://pbs\.twimg\.com/[^"\']+\.mp4[^"\']*',
                        r'https://video\.twimg\.com/ext_tw_video/[^"\']+/[^"\']+/[^"\']+\.mp4[^"\']*',
                        # Add new patterns for X domain if they change
                        r'https://video\.x\.com/[^"\']+\.mp4[^"\']*',
                        r'https://pbs\.x\.com/[^"\']+/video/[^"\']+\.mp4[^"\']*',
                        r'https://pbs\.x\.com/[^"\']+\.mp4[^"\']*'
                    ]
                    
                    for pattern in mp4_patterns:
                        matches = re.findall(pattern, content)
                        for url in matches:
                            if url not in media_urls:
                                media_urls.append(url)
                                logger.info(f"Found video URL in HTML content: {url}")
                    
                    # If still no results, try monitoring network requests
                    if not media_urls:
                        logger.info("Monitoring network requests for video content")
                        
                        # Create a listener for video responses
                        video_urls = []
                        
                        async def handle_response(response):
                            if response.url.endswith('.mp4') or '.mp4?' in response.url:
                                if response.url not in video_urls:
                                    video_urls.append(response.url)
                                    logger.info(f"Detected video response: {response.url}")
                        
                        # Set up the event listener
                        page.on('response', handle_response)
                        
                        # Reload the page to trigger network requests
                        await page.reload(wait_until="networkidle")
                        
                        # Wait for potential network requests to complete
                        await asyncio.sleep(10.0)
                        
                        # Add any found URLs
                        for url in video_urls:
                            if url not in media_urls:
                                media_urls.append(url)
            
            except Exception as e:
                logger.error(f"Error extracting video sources: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Final screenshot
            final_path = os.path.join('.temp', 'screenshots', f"final_{username}_{tweet_id}_{int(time.time())}.png")
            await page.screenshot(path=final_path)
            
            # Extract tweet text
            tweet_text = None
            try:
                # Try multiple selectors
                selectors = [
                    'article div[data-testid="tweetText"]',
                    'div[data-testid="tweet"] div[data-testid="tweetText"]',
                    'div[data-testid="tweet"] div.css-901oao'
                ]
                
                for selector in selectors:
                    element = await page.query_selector(selector)
                    if element:
                        tweet_text = await element.inner_text()
                        logger.info(f"Found tweet text with selector: {selector}")
                        break
            except Exception as e:
                logger.error(f"Error during text extraction: {e}")
            
            # Before closing, capture any updated cookies
            final_cookies = await page.context.cookies()
            cookie_manager.update_from_response_cookies(final_cookies)
            cookie_manager.save_cookies()
            
            result = {
                'text': tweet_text,
                'media_urls': media_urls,
                'source': f"https://x.com/{username}/status/{tweet_id}"
            }
            
            logger.info(f"Enhanced human-like extraction complete: Text found: {bool(tweet_text)}, Media items: {len(media_urls)}")
            return result
    
    except Exception as e:
        logger.error(f"Fatal Playwright error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'text': f"Error extracting tweet: {str(e)}",
            'media_urls': [],
            'source': f"https://x.com/{username}/status/{tweet_id}"
        }

# Update the wrapper function
def get_tweet_content_with_playwright(username, tweet_id, auth_token=None, cookies=None):
    """
    Wrapper that runs the async Playwright function from synchronous code
    
    Parameters:
        username (str): The X username
        tweet_id (str): The tweet ID
        auth_token (str, optional): Legacy auth token 
        cookies (Dict[str, str], optional): Dictionary of cookies for authentication
    """
    try:
        # Get or create an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Run the async function with parameters
        return loop.run_until_complete(
            get_tweet_content_with_playwright_async(username, tweet_id, auth_token, cookies)
        )
    except Exception as e:
        logger.error(f"Error in async wrapper: {e}")
        return {
            'text': f"Error running async extraction: {str(e)}",
            'media_urls': [],
            'source': f"https://x.com/{username}/status/{tweet_id}"
        }

def ensure_playwright_browsers():
    """Ensure Playwright browsers are installed"""
    import subprocess
    import sys
    
    try:
        logger.info("Checking Playwright browser installation...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        logger.info("Playwright browser installation completed")
    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {e}")
        logger.warning("You may need to manually run: python -m playwright install chromium")

# At the end of the file
ensure_playwright_browsers() 