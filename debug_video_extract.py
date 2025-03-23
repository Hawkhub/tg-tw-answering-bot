#!/usr/bin/env python3
"""
Debug Twitter Video Extraction Script

This script attempts to extract videos from Twitter/X posts using real human mouse movement
patterns to bypass Twitter's bot detection measures.
"""

import os
import sys
import asyncio
import argparse
import logging
import json
import time
import math
import random
import urllib.request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tweet_video_extract')

# Links to real mouse movement datasets
MOUSE_MOVEMENT_DATASETS = [
    "https://raw.githubusercontent.com/ZehuaJia/gesture-interaction-data/master/mouse/data-1/mouse-1-1.json",
    "https://raw.githubusercontent.com/ZehuaJia/gesture-interaction-data/master/mouse/data-1/mouse-1-2.json",
    "https://raw.githubusercontent.com/ZehuaJia/gesture-interaction-data/master/mouse/data-2/mouse-2-1.json",
    "https://raw.githubusercontent.com/ZehuaJia/gesture-interaction-data/master/mouse/data-2/mouse-2-2.json"
]

class RealMouseMovements:
    """Handles loading and replaying real human mouse movements"""
    
    def __init__(self):
        self.movements_cache = {}
        self.current_dataset = None
    
    async def load_movements(self, url=None):
        """Load a mouse movement dataset from a URL or randomly select one"""
        if not url:
            url = random.choice(MOUSE_MOVEMENT_DATASETS)
        
        try:
            if url in self.movements_cache:
                logger.info(f"Using cached mouse movements from {url}")
                self.current_dataset = self.movements_cache[url]
                return True
                
            logger.info(f"Loading mouse movements from {url}")
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                
                # Store the mouse tracks
                self.movements_cache[url] = data
                self.current_dataset = data
                logger.info(f"Loaded {len(data) if isinstance(data, list) else 'unknown'} mouse movement points")
                return True
        except Exception as e:
            logger.error(f"Error loading mouse movements: {e}")
            return False
    
    def get_movement_track(self):
        """Get a random segment of movement data"""
        if not self.current_dataset:
            return []
            
        # Format depends on the dataset structure
        # If it's a list of movement records
        if isinstance(self.current_dataset, list):
            # Take a random segment of the data (20-100 points)
            if len(self.current_dataset) > 100:
                start_idx = random.randint(0, len(self.current_dataset) - 100)
                end_idx = start_idx + random.randint(20, 100)
                return self.current_dataset[start_idx:end_idx]
            return self.current_dataset
        
        # If it's in a different format, handle accordingly
        # This is a placeholder for other dataset formats
        return []
        
    def get_scaled_movements(self, start_x, start_y, max_width, max_height, points=None):
        """
        Scale the mouse movements to fit within the desired area and
        start from the specified position
        """
        if not points:
            points = self.get_movement_track()
            
        if not points:
            logger.warning("No mouse movement data available")
            return []
            
        # Extract x, y coordinates based on dataset format
        # This assumes points are in a format with 'x' and 'y' keys or indices
        try:
            # Try to get first point coordinates
            if isinstance(points[0], dict) and 'x' in points[0] and 'y' in points[0]:
                # Format: [{'x': 123, 'y': 456}, ...]
                x_coords = [p['x'] for p in points]
                y_coords = [p['y'] for p in points]
                timestamps = [p.get('timestamp', i * 20) for i, p in enumerate(points)]
            elif isinstance(points[0], list) and len(points[0]) >= 2:
                # Format: [[123, 456], ...]
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                timestamps = [p[2] if len(p) > 2 else i * 20 for i, p in enumerate(points)]
            else:
                logger.warning(f"Unknown mouse data format: {points[0]}")
                return []
                
            # Calculate min/max values to scale properly
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Calculate scaling factors
            x_range = max_x - min_x
            y_range = max_y - min_y
            
            # Avoid division by zero
            x_scale = max_width / x_range if x_range > 0 else 1
            y_scale = max_height / y_range if y_range > 0 else 1
            
            # Scale factor to maintain aspect ratio
            scale = min(x_scale, y_scale) * 0.8  # 80% to keep it within bounds
            
            # Scale and translate points
            result = []
            prev_time = timestamps[0]
            
            for i in range(len(x_coords)):
                # Scale the point
                scaled_x = int(start_x + (x_coords[i] - min_x) * scale)
                scaled_y = int(start_y + (y_coords[i] - min_y) * scale)
                
                # Calculate time delay (in ms)
                delay = (timestamps[i] - prev_time) if i > 0 else 0
                # Cap delay to reasonable values (0-100ms)
                delay = max(0, min(100, delay))
                
                result.append({
                    'x': scaled_x,
                    'y': scaled_y,
                    'delay': delay / 1000.0  # Convert to seconds
                })
                
                prev_time = timestamps[i]
                
            return result
        except Exception as e:
            logger.error(f"Error processing mouse movements: {e}")
            return []

async def extract_tweet_video(tweet_url, output_dir=None, headless=False):
    """
    Extract video from a tweet using real human mouse movements
    
    Args:
        tweet_url: URL of the tweet with video
        output_dir: Directory to save the extracted video
        headless: Whether to run in headless mode
    """
    try:
        from playwright.async_api import async_playwright
        from tweet_fetcher.config import VIDEO_SELECTORS, SCREENSHOTS_DIR
        
        # Create output directories
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "videos")
        os.makedirs(output_dir, exist_ok=True)
        
        # Create screenshots directory for this run
        timestamp = int(time.time())
        screenshots_dir = os.path.join(SCREENSHOTS_DIR, f"video_extract_{timestamp}")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        logger.info(f"Starting video extraction for tweet: {tweet_url}")
        logger.info(f"Output directory: {output_dir}")
        
        # Initialize mouse movements
        mouse_tracker = RealMouseMovements()
        await mouse_tracker.load_movements()
        
        # Start Playwright
        async with async_playwright() as playwright:
            # Create browser with anti-bot measures
            browser = await playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--enable-features=NetworkService,NetworkServiceInProcess2',
                    '--enable-webgl',
                    '--use-gl=angle', 
                    '--enable-webassembly',
                    '--disable-web-security'
                ]
            )
            
            # Create context with realistic viewport and user agent
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                has_touch=False,
                locale="en-US",
                timezone_id="America/New_York",
                accept_downloads=True
            )
            
            # Create page and setup anti-bot measures
            page = await context.new_page()
            
            # Randomize navigation timing
            await page.route("**/*", lambda route: asyncio.create_task(
                route.continue_(
                    headers={
                        **route.request.headers,
                        "Accept-Language": "en-US,en;q=0.9"
                    }
                )
            ))
            
            # Track mouse position on the page
            await page.evaluate("""
                window.mousex = 0;
                window.mousey = 0;
                document.addEventListener('mousemove', function(e) {
                    window.mousex = e.clientX;
                    window.mousey = e.clientY;
                });
            """)
            
            # Initial page load
            logger.info(f"Navigating to tweet: {tweet_url}")
            await page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            # Take initial screenshot
            screenshot_path = os.path.join(screenshots_dir, "01_initial_load.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Saved initial screenshot to {screenshot_path}")
            
            # Get page dimensions
            page_dimensions = await page.evaluate("""
                () => {
                    return {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        scrollHeight: document.documentElement.scrollHeight
                    }
                }
            """)
            
            width, height = page_dimensions['width'], page_dimensions['height']
            
            # ======= Realistic Human Behavior Sequence =======
            
            # 1. Perform initial random scrolling
            logger.info("Performing initial natural scrolling")
            scrolls = random.randint(3, 6)
            for i in range(scrolls):
                # Random scroll amount
                scroll_amount = random.randint(200, 400)
                await page.mouse.wheel(0, scroll_amount)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # 2. Realistic wait time (like reading)
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # 3. Now perform mouse movements using real human data
            logger.info("Performing realistic mouse movements")
            
            # Get current mouse position
            current_x, current_y = await page.evaluate("() => { return {x: window.mousex || 100, y: window.mousey || 100}; }")
            
            # Get first set of movements
            movements = mouse_tracker.get_scaled_movements(
                current_x, current_y, 
                width * 0.8, height * 0.6
            )
            
            # Perform the movements
            for move in movements:
                await page.mouse.move(move['x'], move['y'])
                await asyncio.sleep(move['delay'])
            
            # 4. Scroll down a bit more
            logger.info("Scrolling to reveal media")
            for i in range(2):
                await page.mouse.wheel(0, random.randint(100, 300))
                await asyncio.sleep(random.uniform(0.3, 1.0))
            
            # Take screenshot at this point
            screenshot_path = os.path.join(screenshots_dir, "02_after_scroll.png")
            await page.screenshot(path=screenshot_path)
            
            # 5. Look for the tweet article
            article = await page.query_selector("article[data-testid='tweet']")
            
            if article:
                # Check if we can locate the video
                logger.info("Looking for video elements")
                
                # Try each video selector
                for selector in VIDEO_SELECTORS:
                    video_elements = await page.query_selector_all(selector)
                    
                    if video_elements:
                        logger.info(f"Found {len(video_elements)} video elements with selector: {selector}")
                        
                        # 6. For each video element, try to interact with it
                        for idx, video in enumerate(video_elements):
                            try:
                                # Get video element position
                                box = await video.bounding_box()
                                if box:
                                    # Center of the video
                                    video_x = box['x'] + box['width'] / 2
                                    video_y = box['y'] + box['height'] / 2
                                    
                                    # Get current mouse position
                                    current_position = await page.evaluate("() => { return {x: window.mousex || 100, y: window.mousey || 100}; }")
                                    current_x = current_position['x']
                                    current_y = current_position['y']
                                    
                                    # 7. Use another set of real human movements to approach the video
                                    logger.info(f"Moving mouse to video element {idx+1}")
                                    
                                    # Get new movement dataset
                                    await mouse_tracker.load_movements(random.choice(MOUSE_MOVEMENT_DATASETS))
                                    
                                    # Get movements toward the video
                                    movements = mouse_tracker.get_scaled_movements(
                                        current_x, current_y,
                                        box['width'] * 2, box['height'] * 2
                                    )
                                    
                                    # Ensure the movements end near the video
                                    if movements:
                                        # Adjust last few movements to get closer to video
                                        for i in range(min(5, len(movements))):
                                            idx = len(movements) - i - 1
                                            movements[idx]['x'] = int(video_x + random.randint(-20, 20))
                                            movements[idx]['y'] = int(video_y + random.randint(-20, 20))
                                    
                                    # Perform the movements
                                    for move in movements:
                                        await page.mouse.move(move['x'], move['y'])
                                        await asyncio.sleep(move['delay'])
                                    
                                    # 8. Click on the video
                                    logger.info("Clicking on video")
                                    final_x = video_x + random.randint(-10, 10)
                                    final_y = video_y + random.randint(-10, 10)
                                    await page.mouse.click(final_x, final_y)
                                    
                                    # Take screenshot after click
                                    screenshot_path = os.path.join(screenshots_dir, f"03_after_video_click_{idx+1}.png")
                                    await page.screenshot(path=screenshot_path)
                                    
                                    # 9. Wait for video to start playing
                                    await asyncio.sleep(random.uniform(2.0, 3.0))
                                    
                                    # 10. Check for video source
                                    video_src = await video.get_attribute('src')
                                    poster_src = await video.get_attribute('poster')
                                    
                                    if video_src:
                                        logger.info(f"Found video source: {video_src}")
                                        
                                        # Save video URL to file
                                        url_file_path = os.path.join(output_dir, f"video_url_{timestamp}.txt")
                                        with open(url_file_path, 'w') as f:
                                            f.write(f"Tweet: {tweet_url}\nVideo URL: {video_src}\n")
                                            if poster_src:
                                                f.write(f"Poster URL: {poster_src}\n")
                                        
                                        logger.info(f"Video URL saved to {url_file_path}")
                                        
                                        # Try to get video data from page resources
                                        await asyncio.sleep(1)
                                        resources = await page.evaluate("""
                                            () => {
                                                const resources = performance.getEntriesByType('resource')
                                                    .filter(r => r.name.includes('video') || 
                                                           r.name.includes('mp4') || 
                                                           r.name.includes('.ts') ||
                                                           r.name.includes('media'))
                                                    .map(r => r.name);
                                                return resources;
                                            }
                                        """)
                                        
                                        if resources:
                                            logger.info(f"Found {len(resources)} potential video resources")
                                            with open(url_file_path, 'a') as f:
                                                f.write("\nPotential video resources:\n")
                                                for res in resources:
                                                    f.write(f"- {res}\n")
                            except Exception as e:
                                logger.error(f"Error interacting with video element {idx+1}: {e}")
                    
                # 11. Try one more approach - try to find any media in the tweet
                logger.info("Searching for any media elements in the tweet")
                media_selectors = [
                    "div[data-testid='tweetPhoto']",
                    "div[data-testid='videoComponent']",
                    "div[data-testid='videoPlayer']"
                ]
                
                for selector in media_selectors:
                    media_elements = await page.query_selector_all(selector)
                    if media_elements:
                        logger.info(f"Found {len(media_elements)} media elements with selector: {selector}")
                        
                        # Get another random real mouse movement dataset
                        await mouse_tracker.load_movements(random.choice(MOUSE_MOVEMENT_DATASETS))
                        
                        # Interact with first media element
                        media = media_elements[0]
                        box = await media.bounding_box()
                        
                        if box:
                            # Get current mouse position
                            current_position = await page.evaluate("() => { return {x: window.mousex || 100, y: window.mousey || 100}; }")
                            
                            # Move mouse to media element with real movements
                            movements = mouse_tracker.get_scaled_movements(
                                current_position['x'], current_position['y'],
                                width * 0.7, height * 0.7
                            )
                            
                            # Ensure movements end near the media element
                            if movements:
                                media_x = box['x'] + box['width'] / 2
                                media_y = box['y'] + box['height'] / 2
                                
                                for i in range(min(5, len(movements))):
                                    idx = len(movements) - i - 1
                                    movements[idx]['x'] = int(media_x + random.randint(-20, 20))
                                    movements[idx]['y'] = int(media_y + random.randint(-20, 20))
                            
                            # Perform the movements
                            for move in movements:
                                await page.mouse.move(move['x'], move['y'])
                                await asyncio.sleep(move['delay'])
                            
                            # Click on the media
                            logger.info("Clicking on media element")
                            final_x = box['x'] + box['width'] / 2 + random.randint(-10, 10)
                            final_y = box['y'] + box['height'] / 2 + random.randint(-10, 10)
                            await page.mouse.click(final_x, final_y)
                            
                            # Take screenshot
                            screenshot_path = os.path.join(screenshots_dir, "04_after_media_click.png")
                            await page.screenshot(path=screenshot_path)
                            
                            # Wait for any modal or video to appear
                            await asyncio.sleep(random.uniform(2.0, 3.0))
                            
                            # Final screenshot
                            screenshot_path = os.path.join(screenshots_dir, "05_final_state.png")
                            await page.screenshot(path=screenshot_path)
                
                # 12. Check one more time for videos that might have appeared
                logger.info("Final check for video elements")
                videos_found = []
                
                for selector in VIDEO_SELECTORS:
                    video_elements = await page.query_selector_all(selector)
                    for video in video_elements:
                        src = await video.get_attribute('src')
                        if src and src not in videos_found:
                            videos_found.append(src)
                
                if videos_found:
                    logger.info(f"Found {len(videos_found)} video sources in final check")
                    url_file_path = os.path.join(output_dir, f"all_videos_{timestamp}.txt")
                    with open(url_file_path, 'w') as f:
                        f.write(f"Tweet: {tweet_url}\n\nVideo URLs:\n")
                        for url in videos_found:
                            f.write(f"- {url}\n")
                    logger.info(f"All video URLs saved to {url_file_path}")
                else:
                    logger.warning("No video sources found in final check")
            else:
                logger.warning("Could not find tweet article element")
            
            # Close browser
            await context.close()
            await browser.close()
            
            logger.info(f"Video extraction attempt completed. Check {screenshots_dir} for screenshots.")
            logger.info(f"Check {output_dir} for any extracted video URLs.")
            
            return True
            
    except Exception as e:
        logger.error(f"Error extracting video: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Twitter Video Extraction Script')
    parser.add_argument('--url', required=True, help='URL of the tweet containing video')
    parser.add_argument('--output', help='Directory to save extracted videos')
    parser.add_argument('--visible', action='store_true', help='Run in visible mode (not headless)')
    args = parser.parse_args()
    
    # Run the async function
    asyncio.run(extract_tweet_video(args.url, args.output, not args.visible))

if __name__ == "__main__":
    main() 