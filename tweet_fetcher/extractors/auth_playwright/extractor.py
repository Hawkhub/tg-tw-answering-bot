import logging
import asyncio
import random
import math
import time
import os
from datetime import datetime
from ...config import DEFAULT_TIMEOUT, HTML_DIR, SCREENSHOTS_DIR, AUTH_USER_AGENT
from ..playwright.extractor import PlaywrightExtractor
from .browser import BrowserSessionManager, create_authenticated_browser

logger = logging.getLogger('tweet_fetcher')

class AuthPlaywrightExtractor(PlaywrightExtractor):
    """Extract tweet content using authenticated Playwright session"""
    
    def __init__(self, username, tweet_id, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
        """
        Initialize the extractor
        
        Args:
            username (str): Twitter/X username for the tweet
            tweet_id (str): Tweet ID
            auth_username (str): Username for authentication
            auth_password (str): Password for authentication
            auth_phone (str): Phone number for verification
            record_video (bool): Whether to record the extraction process
            record_quality (str): Recording quality (low: 480p, medium: 720p, high: 1080p)
        """
        super().__init__(username, tweet_id)
        self.auth_username = auth_username
        self.auth_password = auth_password
        self.auth_phone = auth_phone
        self.record_video = record_video
        self.record_quality = record_quality
        
        # If phone is not provided, try to get from environment
        if not self.auth_phone:
            self.auth_phone = os.environ.get('X_PHONE_NUMBER')
            
        self.browser_owned = False  # Flag to track if we own the browser instance
    
    async def extract(self):
        """Extract tweet content using authenticated Twitter/X session"""
        try:
            # Get a browser session from the session manager instead of creating a new one each time
            logger.info("Getting authenticated browser instance from session manager")
            try:
                self.playwright, self.context, self.auth_manager = await BrowserSessionManager.get_browser_session(
                    username=self.auth_username,
                    password=self.auth_password,
                    phone_number=self.auth_phone,
                    record_video=self.record_video,
                    record_quality=self.record_quality
                )
            except Exception as e:
                logger.error(f"Failed to get browser session: {e}")
                logger.info("Falling back to unauthenticated mode")
                # Fall back to unauthenticated extraction
                return await super().extract()
            
            # Create a new page in the existing browser context
            self.page = await self.context.new_page()
            
            # Apply human behavior settings to the page
            await self._setup_human_behavior(self.page)
            
            # Navigate to the tweet URL
            tweet_url = f"https://x.com/{self.username}/status/{self.tweet_id}"
            logger.info(f"Navigating to tweet with auth: {tweet_url}")
            
            await self.page.goto(tweet_url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
            
            # Wait for page to load - try article selector which contains tweets
            try:
                await self.page.wait_for_selector("article", timeout=15000)
            except Exception as e:
                logger.info(f"Network not fully idle or element not found, but continuing: {e}")
            
            # Simulate realistic human behavior for reading a tweet
            await self._simulate_realistic_tweet_interaction()
            
            # Extract tweet content
            content = await self._extract_tweet_content()
            
            # Take final screenshot for debugging if needed
            timestamp = int(time.time())
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"tweet_{self.tweet_id}_{timestamp}.png")
            await self.page.screenshot(path=screenshot_path)
            
            # Return extracted content
            has_text = bool(content.get('text', ''))
            media_count = len(content.get('media_urls', []))
            logger.info(f"Auth extraction complete: Text found: {has_text}, Media items: {media_count}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting tweet content: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Try fallback to unauthenticated extraction
            logger.info("Attempting fallback to unauthenticated extraction")
            try:
                return await super().extract()
            except Exception as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")
                return {"error": str(e)}
            
        finally:
            # Close the page but don't close the browser
            if hasattr(self, 'page') and self.page:
                try:
                    await self.page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")
            
            # Release the browser session back to the pool
            if hasattr(self, 'auth_username'):
                try:
                    await BrowserSessionManager.release_session(self.auth_username)
                except Exception as e:
                    logger.warning(f"Error releasing browser session: {e}")
    
    async def _setup_human_behavior(self, page):
        """Set up initial human-like browser behavior"""
        try:
            # Set a realistic viewport size - use common resolutions with slight variations
            # This makes fingerprinting harder
            common_widths = [1366, 1440, 1536, 1680, 1920, 2560]
            common_heights = [768, 900, 864, 1050, 1080, 1440]
            
            # Choose base resolution then add slight variation
            base_width = random.choice(common_widths)
            base_height = random.choice(common_heights)
            
            # Add slight variations to make fingerprinting harder
            width = base_width + random.randint(-10, 10)
            height = base_height + random.randint(-8, 8)
            
            await page.set_viewport_size({
                'width': width,
                'height': height
            })
            
            # Set a consistent but realistic user agent
            # We're using the AUTH_USER_AGENT from config but could implement rotation
            await page.set_extra_http_headers({
                'User-Agent': AUTH_USER_AGENT,
                'Accept-Language': random.choice([
                    'en-US,en;q=0.9', 
                    'en-GB,en;q=0.9,en-US;q=0.8', 
                    'en-CA,en;q=0.9,fr-CA;q=0.8',
                    'en;q=0.9'
                ])
            })
            
            # Add JavaScript to track mouse position globally
            await page.evaluate("""
                window.mousex = 0;
                window.mousey = 0;
                document.addEventListener('mousemove', function(e) {
                    window.mousex = e.clientX;
                    window.mousey = e.clientY;
                });
            """)
            
            # Set timezone should match your proxy location
            # Already handled in browser.py when creating the context
            
            logger.info(f"Human behavior setup complete: {width}x{height} viewport")
            
        except Exception as e:
            logger.error(f"Error setting up human behavior: {e}")

    async def _get_mouse_position(self, page, axis="x"):
        """Get current mouse position from page"""
        try:
            if axis.lower() == "x":
                return await page.evaluate("window.mousex")
            else:
                return await page.evaluate("window.mousey")
        except:
            # Default values if script fails
            return 0 if axis.lower() == "x" else 0
    
    async def _simulate_realistic_tweet_interaction(self):
        """Simulate a human interacting with a tweet in a naturalistic way"""
        try:
            # Get page dimensions
            page_dimensions = await self.page.evaluate("""
                () => {
                    return {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        scrollHeight: document.documentElement.scrollHeight
                    }
                }
            """)
            
            page_width = page_dimensions['width']
            page_height = page_dimensions['height']
            scroll_height = page_dimensions['scrollHeight']
            
            # 1. Simulate human reading behavior
            # Calculate a realistic reading time based on tweet length (between 2-8 seconds)
            # Reduced from original 10-20 seconds to be more efficient
            reading_time = random.uniform(2.0, 8.0)
            logger.info(f"Simulating reading for {reading_time:.1f} seconds")
            
            # 2.1 Initial scroll behavior - most people scroll down a bit to see the whole tweet
            scroll_positions = []
            max_scroll = min(scroll_height - page_height, 1200)  # Don't scroll too far
            
            # Generate a natural scrolling pattern
            current_position = 0
            while current_position < max_scroll:
                # Move in chunks of varying size
                step = random.randint(100, 300)
                current_position += step
                if current_position > max_scroll:
                    current_position = max_scroll
                scroll_positions.append(current_position)
            
            # Scroll down in a natural pattern
            for position in scroll_positions:
                await self.page.evaluate(f"window.scrollTo(0, {position})")
                # Short pause between scrolls
                await asyncio.sleep(random.uniform(0.1, 0.6))
            
            # Wait a moment at the bottom
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back up in a more direct manner
            scroll_back_steps = min(3, len(scroll_positions))
            for _ in range(scroll_back_steps):
                up_position = random.randint(0, int(max_scroll * 0.6))
                await self.page.evaluate(f"window.scrollTo(0, {up_position})")
                await asyncio.sleep(random.uniform(0.2, 0.8))
            
            # Final position near the top for content extraction
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 3. Interact with the tweet - find and look for the article
            article = await self.page.query_selector("article")
            
            if article:
                # Get article position
                article_box = await article.bounding_box()
                if article_box:
                    article_center_x = article_box['x'] + article_box['width'] / 2
                    article_center_y = article_box['y'] + article_box['height'] / 2
                    
                    # Move mouse to a random position in the article
                    await self._natural_mouse_move(
                        self.page,
                        await self._get_mouse_position(self.page, "x"),
                        await self._get_mouse_position(self.page, "y"),
                        article_center_x + random.randint(-article_box['width']//4, article_box['width']//4),
                        article_center_y + random.randint(-article_box['height']//4, article_box['height']//4),
                        random.uniform(0.3, 0.8)
                    )
                    
                    # 1 in 4 chance of clicking on the tweet text itself
                    if random.random() < 0.25:
                        # Find tweet text area
                        tweet_text = await self.page.query_selector("article div[data-testid='tweetText']")
                        if tweet_text:
                            text_box = await tweet_text.bounding_box()
                            if text_box:
                                # Move to and click on text
                                text_x = text_box['x'] + random.randint(10, int(text_box['width'] - 10))
                                text_y = text_box['y'] + random.randint(10, int(text_box['height'] - 10))
                                
                                await self._natural_mouse_move(
                                    self.page,
                                    await self._get_mouse_position(self.page, "x"),
                                    await self._get_mouse_position(self.page, "y"),
                                    text_x,
                                    text_y,
                                    random.uniform(0.2, 0.5)
                                )
                                
                                await self.page.mouse.click(text_x, text_y)
                                await asyncio.sleep(random.uniform(0.3, 0.8))
                    
                    # Check for media content to interact with
                    media = await self.page.query_selector("article div[data-testid='tweetPhoto']")
                    if media:
                        media_box = await media.bounding_box()
                        if media_box:
                            media_center_x = media_box['x'] + media_box['width'] / 2
                            media_center_y = media_box['y'] + media_box['height'] / 2
                            
                            # Move to media
                            await self._natural_mouse_move(
                                self.page,
                                await self._get_mouse_position(self.page, "x"),
                                await self._get_mouse_position(self.page, "y"),
                                media_center_x + random.randint(-30, 30),
                                media_center_y + random.randint(-30, 30),
                                random.uniform(0.3, 0.7)
                            )
                            
                            # 1 in 3 chance to click on media to see it in higher res
                            if random.random() < 0.3:
                                await self.page.mouse.click(
                                    media_center_x + random.randint(-10, 10),
                                    media_center_y + random.randint(-10, 10)
                                )
                                
                                # Wait for modal to appear
                                await asyncio.sleep(random.uniform(1.0, 2.0))
                                
                                # Click to close modal (usually anywhere outside or on X)
                                close_x = random.randint(int(page_width * 0.8), int(page_width * 0.95))
                                close_y = random.randint(30, 80)
                                
                                # Natural move to close button area
                                await self._natural_mouse_move(
                                    self.page,
                                    media_center_x,
                                    media_center_y,
                                    close_x,
                                    close_y,
                                    random.uniform(0.5, 0.8)
                                )
                                
                                await self.page.mouse.click(close_x, close_y)
                                await asyncio.sleep(random.uniform(0.3, 0.6))
                    
                    # Final random mouse movement to a neutral position
                    await self._natural_mouse_move(
                        self.page,
                        await self._get_mouse_position(self.page, "x"),
                        await self._get_mouse_position(self.page, "y"),
                        random.randint(int(page_width * 0.4), int(page_width * 0.6)),
                        random.randint(int(page_height * 0.4), int(page_height * 0.6)),
                        random.uniform(0.3, 0.7)
                    )
            else:
                logger.warning("Tweet article not found for interaction")
                
        except Exception as e:
            logger.warning(f"Error during realistic tweet interaction: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            
    async def _natural_mouse_move(self, page, start_x, start_y, end_x, end_y, duration_seconds):
        """
        Move the mouse in a natural, bezier-curve-like path
        
        Args:
            page: Playwright page
            start_x, start_y: Starting coordinates
            end_x, end_y: Ending coordinates
            duration_seconds: How long the movement should take
        """
        try:
            # Validate inputs
            if not all(isinstance(x, (int, float)) for x in [start_x, start_y, end_x, end_y, duration_seconds]):
                return
                
            # Convert any float coordinates to integers
            start_x, start_y = int(start_x), int(start_y)
            end_x, end_y = int(end_x), int(end_y)
            
            # Calculate distance
            distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            
            # If distance is too small, just move directly
            if distance < 5:
                await page.mouse.move(end_x, end_y)
                return
                
            # Create a natural curve with control points
            # Add randomized control points for natural curve
            control_point_1_x = start_x + (end_x - start_x) * random.uniform(0.1, 0.4)
            control_point_1_y = start_y + (end_y - start_y) * random.uniform(0.1, 0.4) + random.randint(-50, 50)
            
            control_point_2_x = start_x + (end_x - start_x) * random.uniform(0.6, 0.9)
            control_point_2_y = start_y + (end_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
            
            # Calculate number of steps based on distance and duration
            steps = max(5, min(25, int(distance / 10)))
            
            # Easing function to make movement more natural
            def ease_in_out(t):
                return 0.5 * (math.sin((t - 0.5) * math.pi) + 1)
            
            # Cubic Bezier curve function
            def cubic_bezier(t, p0, p1, p2, p3):
                u = 1 - t
                return u*u*u*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t*t*t*p3
            
            # Move along the curve with natural timing
            start_time = time.time()
            for step in range(steps + 1):
                # Calculate progress with easing
                t = step / steps
                eased_t = ease_in_out(t)
                
                # Calculate position along the curve
                x = cubic_bezier(eased_t, start_x, control_point_1_x, control_point_2_x, end_x)
                y = cubic_bezier(eased_t, start_y, control_point_1_y, control_point_2_y, end_y)
                
                # Add tiny random noise for ultra-realism
                x += random.uniform(-2, 2)
                y += random.uniform(-2, 2)
                
                # Move mouse to the position
                await page.mouse.move(int(x), int(y))
                
                # Adaptive wait time between steps - slower at start and end
                sleep_time = duration_seconds / steps
                
                # Add variation in speed (slower at beginning and end)
                if t < 0.2 or t > 0.8:
                    sleep_time *= random.uniform(1.0, 1.5)  # Slower at start/end
                else:
                    sleep_time *= random.uniform(0.5, 1.0)  # Faster in the middle
                    
                # Make sure we don't exceed total duration
                elapsed = time.time() - start_time
                remaining = duration_seconds - elapsed
                sleep_time = min(sleep_time, remaining / (steps - step)) if steps > step else 0
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
        except Exception as e:
            logger.warning(f"Error during natural mouse movement: {e}")
    
    async def _extract_tweet_content(self):
        """Extract the content from the loaded tweet page"""
        try:
            # Initialize result with default values
            result = {
                'text': '',
                'media_urls': [],
                'source': f"https://x.com/{self.username}/status/{self.tweet_id}",
                'auth_used': True,
                'username': self.username,
                'tweet_id': self.tweet_id,
                'timestamp': datetime.now().isoformat()
            }
            
            # Extract tweet text
            tweet_text_element = await self.page.query_selector("article div[data-testid='tweetText']")
            if tweet_text_element:
                result['text'] = await tweet_text_element.inner_text()
                logger.info("Found tweet text with selector: article div[data-testid='tweetText']")
            else:
                # Try alternative selectors
                alt_text_element = await self.page.query_selector("article div[lang]")
                if alt_text_element:
                    result['text'] = await alt_text_element.inner_text()
                    logger.info("Found tweet text with alternative selector: article div[lang]")
                else:
                    logger.warning("Could not find tweet text")
            
            # Extract media URLs (images, videos)
            try:
                # Look for images
                image_elements = await self.page.query_selector_all("article img[src*='https://pbs.twimg.com/media/']")
                if image_elements:
                    for img in image_elements:
                        src = await img.get_attribute('src')
                        if src and src not in result['media_urls']:
                            # Convert to original size image if possible
                            if '&name=small' in src or '&name=thumb' in src or '&name=medium' in src:
                                src = src.split('&name=')[0] + '&name=orig'
                            result['media_urls'].append(src)
                            
                # Look for videos
                video_elements = await self.page.query_selector_all("article video[src]")
                if video_elements:
                    for video in video_elements:
                        src = await video.get_attribute('src')
                        if src and src not in result['media_urls']:
                            result['media_urls'].append(src)
                            
                # Try to find poster images for videos
                poster_elements = await self.page.query_selector_all("article video[poster]")
                if poster_elements:
                    for poster in poster_elements:
                        src = await poster.get_attribute('poster')
                        if src and src not in result['media_urls']:
                            # Convert to original size if applicable
                            if '&name=' in src:
                                src = src.split('&name=')[0] + '&name=orig'
                            result['media_urls'].append(src)
                            
            except Exception as e:
                logger.warning(f"Error extracting media URLs: {e}")
            
            # Save HTML content for debugging
            timestamp = int(time.time())
            html_path = os.path.join(HTML_DIR, f"tweet_{self.tweet_id}_{timestamp}.html")
            html_content = await self.page.content()
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # If text is empty but we have media, set a default message
            if not result['text'] and result['media_urls']:
                result['text'] = f"Tweet by @{self.username} with media content."
            elif not result['text']:
                result['text'] = f"Tweet by @{self.username} - Text content could not be extracted."
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting tweet content: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'text': f"Error extracting tweet: {str(e)}",
                'media_urls': [],
                'source': f"https://x.com/{self.username}/status/{self.tweet_id}",
                'auth_used': True,
                'error': str(e)
            } 