import requests
from bs4 import BeautifulSoup
import random
import re
import logging
import asyncio
from playwright.async_api import async_playwright
import os

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

def get_tweet_content(username, tweet_id):
    """
    Multi-tiered approach to get tweet content:
    1. Use Playwright as primary method for reliable extraction
    2. Fall back to minimal metadata extraction
    3. (Placeholder) Future token-based authenticated approach
    
    Returns dict with text, media_urls, and source
    """
    logger.info(f"Starting tweet content fetch for @{username}/status/{tweet_id}")
    
    # Create base result with at least the X URL
    result = {'text': None, 'media_urls': [], 'source': f"https://x.com/{username}/status/{tweet_id}"}
    
    # First tier: Use Playwright (most reliable)
    try:
        logger.info("Attempting Playwright extraction as primary method...")
        content = get_tweet_content_with_playwright(username, tweet_id)
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
    
    # Third tier: Placeholder for future token-based approach
    # Currently just creates a minimal result with what we know
    try:
        logger.info("All fetching approaches failed, creating minimal result")
        result['text'] = f"Tweet by @{username} - Content could not be retrieved automatically. Please view directly on X.com"
        
        # TODO: Future enhancement - Authenticated token approach
        # This placeholder is for a future implementation that would:
        # 1. Use authentication with a user token
        # 2. Access Twitter's API or authenticated pages
        # 3. Extract content using authenticated session cookies
        # 4. Handle rate limiting and token management
        
        return result
    except Exception as e:
        logger.error(f"All methods failed: {e}")
    
    # If all approaches fail, return the basic result
    logger.warning(f"All tweet content retrieval methods failed")
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

async def get_tweet_content_with_playwright_async(username, tweet_id):
    """
    Async Playwright implementation with stealth techniques.
    This allows for more efficient handling of network operations.
    """
    logger.info(f"Starting async Playwright extraction for @{username}/status/{tweet_id}")
    
    try:
        async with async_playwright() as p:
            # Use persistent context approach instead of args
            browser_type = p.chromium
            
            # Define the user data directory - updated to use .temp folder
            user_data_dir = os.path.join(os.getcwd(), ".temp", "profiles", f"profile_{random.randint(1, 5)}")
            
            # More robust error handling when launching browser
            try:
                # Use launch_persistent_context instead of launch + new_context
                context = await browser_type.launch_persistent_context(
                    user_data_dir,
                    headless=True,
                    viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                    locale=random.choice(["en-US", "en-GB", "en-CA"]),
                    timezone_id=random.choice(["America/New_York", "Europe/London", "Asia/Tokyo"]),
                    color_scheme=random.choice(["light", "dark"]),
                    device_scale_factor=random.choice([1, 2]),
                    has_touch=random.choice([True, False]),
                    is_mobile=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-web-security',
                        '--disable-site-isolation-trials'
                    ]
                )
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                return {
                    'text': f"Error launching browser: {str(e)}",
                    'media_urls': [],
                    'source': f"https://x.com/{username}/status/{tweet_id}"
                }
                
            if not context:
                logger.error("Browser context creation failed")
                return {
                    'text': "Browser context couldn't be created",
                    'media_urls': [],
                    'source': f"https://x.com/{username}/status/{tweet_id}"
                }
                
            # Add fingerprint evasion with error handling
            try:
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
            except Exception as e:
                logger.warning(f"Failed to add stealth script: {e}, continuing anyway")
            
            # Create page with error handling
            try:
                page = await context.new_page()
                if not page:
                    raise Exception("Failed to create page")
            except Exception as e:
                logger.error(f"Failed to create page: {e}")
                await context.close()
                return {
                    'text': f"Error creating browser page: {str(e)}",
                    'media_urls': [],
                    'source': f"https://x.com/{username}/status/{tweet_id}"
                }
            
            # Set timeout with error handling
            try:
                await page.set_default_timeout(30000)
            except Exception as e:
                logger.warning(f"Failed to set timeout: {e}, continuing anyway")
            
            # Navigate to Twitter with error handling
            try:
                logger.info("Visiting Twitter homepage first")
                response = await page.goto("https://x.com/", wait_until="domcontentloaded")
                if not response:
                    logger.warning("No response from initial page load, but continuing")
            except Exception as e:
                logger.error(f"Failed to load Twitter homepage: {e}")
                # We'll continue anyway to try the tweet directly
            
            # Human-like delay
            human_delay = random.uniform(1.5, 4.0)
            logger.info(f"Adding human-like delay of {human_delay:.2f} seconds")
            await asyncio.sleep(human_delay)
            
            # Go to tweet URL with better error handling
            try:
                logger.info(f"Navigating to tweet URL")
                response = await page.goto(
                    f"https://x.com/{username}/status/{tweet_id}", 
                    wait_until="networkidle",
                    timeout=60000
                )
                if not response:
                    logger.warning("No response object from tweet page load, but continuing")
                if response and not response.ok:
                    logger.warning(f"Tweet page loaded with status {response.status}")
            except Exception as e:
                logger.error(f"Failed to load tweet page: {e}")
                await context.close()
                return {
                    'text': f"Error loading tweet page: {str(e)}",
                    'media_urls': [],
                    'source': f"https://x.com/{username}/status/{tweet_id}"
                }
            
            # Extra wait for JS to execute
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Take screenshot with error handling
            try:
                screenshot_path = os.path.join('.temp', 'screenshots', f"tweet_{username}_{tweet_id}_screenshot.png")
                await page.screenshot(path=screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {e}, continuing anyway")
            
            # Extract tweet text with better error handling
            tweet_text = None
            retries = 3
            while retries > 0 and tweet_text is None:
                try:
                    # Try multiple selectors
                    selectors = [
                        'article div[data-testid="tweetText"]',
                        'div[data-testid="tweet"] div[data-testid="tweetText"]',
                        'div[data-testid="tweet"] div.css-901oao'
                    ]
                    
                    for selector in selectors:
                        element = await page.query_selector(selector)
                        if element:  # Make sure element exists before trying to get text
                            tweet_text = await element.inner_text()
                            logger.info(f"Found tweet text with selector: {selector}")
                            break
                    
                    if not tweet_text:
                        logger.warning(f"Text extraction failed, retrying ({retries} left)")
                        await asyncio.sleep(1)
                        # Sometimes scrolling helps render content
                        await page.mouse.wheel(0, 50)
                except Exception as e:
                    logger.error(f"Error during text extraction: {e}")
                
                retries -= 1
            
            # Extract media with better error handling
            media_urls = []
            try:
                # Try different selectors for images
                image_selectors = [
                    'article img[src*="media"]',
                    'div[data-testid="tweetPhoto"] img',
                    'a[href*="/photo/"] img'
                ]
                
                for selector in image_selectors:
                    images = await page.query_selector_all(selector)
                    if images and len(images) > 0:  # Make sure we have images
                        logger.info(f"Found {len(images)} images with selector: {selector}")
                        for img in images:
                            if img:  # Make sure each image exists
                                src = await img.get_attribute('src')
                                if src and not any(x in src.lower() for x in ['profile', 'icon', 'logo']):
                                    # Get highest resolution
                                    high_res_src = re.sub(r'&name=\w+', '&name=large', src)
                                    media_urls.append(high_res_src)
                        if media_urls:  # If we found media, no need to try other selectors
                            break
                
                # Check for videos only if we didn't find images
                if not media_urls:
                    video_selectors = [
                        'video[preload="auto"]',
                        'div[data-testid="videoPlayer"] video',
                        'div[data-testid="videoComponent"] video'
                    ]
                    
                    for selector in video_selectors:
                        videos = await page.query_selector_all(selector)
                        if videos and len(videos) > 0:  # Make sure we have videos
                            logger.info(f"Found {len(videos)} videos with selector: {selector}")
                            for video in videos:
                                if video:  # Make sure each video exists
                                    src = await video.get_attribute('src')
                                    if src:
                                        media_urls.append(src)
                            if media_urls:  # If we found media, no need to try other selectors
                                break
            except Exception as e:
                logger.error(f"Error during media extraction: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Clean up - close the context instead of a browser
            await context.close()
            
            result = {
                'text': tweet_text,
                'media_urls': media_urls,
                'source': f"https://x.com/{username}/status/{tweet_id}"
            }
            
            logger.info(f"Async Playwright extraction complete: Text found: {bool(tweet_text)}, Media items: {len(media_urls)}")
            return result
            
    except Exception as e:
        logger.error(f"Async Playwright extraction failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'text': f"Error extracting tweet: {str(e)}",
            'media_urls': [],
            'source': f"https://x.com/{username}/status/{tweet_id}"
        }

# Wrapper to call async function from sync code
def get_tweet_content_with_playwright(username, tweet_id):
    """Wrapper that runs the async Playwright function from synchronous code"""
    try:
        # Get or create an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If there's no event loop in current thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Run the async function
        return loop.run_until_complete(get_tweet_content_with_playwright_async(username, tweet_id))
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