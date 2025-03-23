import logging
import os
import aiohttp
import asyncio
import re
from urllib.parse import urlparse

from ..config import MEDIA_DIR

logger = logging.getLogger('tweet_fetcher')

async def download_media(url, output_dir=MEDIA_DIR):
    """
    Download media from URL
    
    Args:
        url (str): Media URL
        output_dir (str): Download directory or specific file path
        
    Returns:
        str: Path to downloaded file or None if failed
    """
    try:
        # Check if output_dir is actually a full file path
        if os.path.splitext(output_dir)[1]:  # If it has an extension, it's likely a file path
            output_path = output_dir
            output_dir = os.path.dirname(output_path)
            use_custom_filename = True
        else:
            use_custom_filename = False
            # Parse URL to get filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            # Clean filename
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            
            # Ensure filename has an extension
            if not os.path.splitext(filename)[1]:
                filename += ".jpg"  # Default to jpg for URLs without extension
            
            # Create output path
            output_path = os.path.join(output_dir, filename)
        
        # Ensure directory exists
        logger.info(f"Ensuring directory exists: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Download file
        logger.info(f"Downloading media from URL: {url}")
        logger.info(f"Will save to: {output_path}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        f.write(await response.read())
                    logger.info(f"Downloaded {url} to {output_path}")
                    return output_path
                else:
                    logger.error(f"Failed to download {url}: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def extract_media_from_page(page, image_selectors, video_selectors):
    """
    Extract media URLs from a Playwright page
    
    Args:
        page: Playwright page
        image_selectors (list): Selectors for image elements
        video_selectors (list): Selectors for video elements
        
    Returns:
        list: Media URLs
    """
    media_urls = []
    
    # Extract images
    for selector in image_selectors:
        try:
            images = await page.query_selector_all(selector)
            for img in images:
                src = await img.get_attribute('src')
                if src and src not in media_urls:
                    # Get highest resolution image by removing query params
                    clean_src = src.split('?')[0]
                    media_urls.append(clean_src)
        except Exception as e:
            logger.warning(f"Error extracting images with selector {selector}: {e}")
    
    # Extract videos
    for selector in video_selectors:
        try:
            videos = await page.query_selector_all(selector)
            for video in videos:
                src = await video.get_attribute('src')
                if src and src not in media_urls:
                    media_urls.append(src)
                
                # Also check for poster attribute (thumbnail)
                poster = await video.get_attribute('poster')
                if poster and poster not in media_urls:
                    media_urls.append(poster)
        except Exception as e:
            logger.warning(f"Error extracting videos with selector {selector}: {e}")
    
    return media_urls

async def download_all_media(urls, output_dir=MEDIA_DIR):
    """
    Download all media from URLs
    
    Args:
        urls (list): Media URLs
        output_dir (str): Download directory
        
    Returns:
        list: Paths to downloaded files
    """
    if not urls:
        return []
    
    tasks = [download_media(url, output_dir) for url in urls]
    results = await asyncio.gather(*tasks)
    
    # Filter out None results
    return [path for path in results if path]

async def fetch_video_from_downloader(tweet_url):
    """
    Fetch video URL using dedicated tweet API services
    
    This function implements multiple API-based approaches to extract video URLs from tweets:
    1. Using the vxtwitter.com API (primary method)
    2. Using the fxtwitter.com API (backup method)
    3. Direct extraction from Twitter's website as a fallback
    
    Args:
        tweet_url (str): Tweet URL
        
    Returns:
        str: Best quality video URL or None if not found
    """
    try:
        import tempfile
        import os
        import time
        import re
        import json
        import aiohttp
        
        logger.info(f"Fetching video for tweet: {tweet_url}")
        
        # Create temp dir for storing debug files
        recordings_dir = os.path.join(tempfile.gettempdir(), "tweet_video_debug")
        os.makedirs(recordings_dir, exist_ok=True)
        
        # Extract tweet ID from URL
        tweet_id_match = re.search(r'status/(\d+)', tweet_url)
        if not tweet_id_match:
            logger.error(f"Could not extract tweet ID from URL: {tweet_url}")
            return None
        
        tweet_id = tweet_id_match.group(1)
        logger.info(f"Extracted tweet ID: {tweet_id}")
        
        # Strategy 1: Use vxtwitter.com API (most reliable)
        logger.info("Trying vxtwitter.com API...")
        vx_url = f"https://api.vxtwitter.com/status/{tweet_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(vx_url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Save full response for debugging
                        vx_response_file = os.path.join(recordings_dir, "vxtwitter_response.json")
                        with open(vx_response_file, "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved vxtwitter API response to: {vx_response_file}")
                        
                        # Check if the response has video data
                        if data.get('media_extended') and len(data['media_extended']) > 0:
                            for media in data['media_extended']:
                                if media.get('type') == 'video':
                                    variants = media.get('variants', [])
                                    if variants:
                                        # Sort by bitrate if available
                                        variants.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                                        video_url = variants[0].get('url')
                                        
                                        if video_url:
                                            logger.info(f"Found high quality video URL from vxtwitter API: {video_url}")
                                            # Save URL to file
                                            with open(os.path.join(recordings_dir, "video_urls.txt"), "w") as f:
                                                f.write(f"{video_url}\n")
                                            return video_url
                        
                        # Check for legacy media format
                        if not data.get('media_extended') and data.get('media') and data['media'].get('videos'):
                            videos = data['media']['videos']
                            if isinstance(videos, list) and videos:
                                # Sort by bitrate if available
                                videos.sort(key=lambda x: x.get('bitrate', 0) if 'bitrate' in x else 0, reverse=True)
                                video_url = videos[0].get('url')
                                
                                if video_url:
                                    logger.info(f"Found video URL from vxtwitter API (legacy format): {video_url}")
                                    # Save URL to file
                                    with open(os.path.join(recordings_dir, "video_urls.txt"), "w") as f:
                                        f.write(f"{video_url}\n")
                                    return video_url
        except Exception as e:
            logger.warning(f"Error using vxtwitter.com API: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        # Strategy 2: Try fxtwitter.com API as fallback
        logger.info("Trying fxtwitter.com API...")
        fx_url = f"https://api.fxtwitter.com/status/{tweet_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(fx_url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Save full response for debugging
                        fx_response_file = os.path.join(recordings_dir, "fxtwitter_response.json")
                        with open(fx_response_file, "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved fxtwitter API response to: {fx_response_file}")
                        
                        if data.get('code') == 200 and data.get('media') and data['media'].get('videos'):
                            videos = data['media']['videos']
                            if isinstance(videos, list) and videos:
                                # Sort by bitrate if available, otherwise by resolution
                                if 'bitrate' in videos[0]:
                                    videos.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                                elif 'width' in videos[0]:
                                    videos.sort(key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
                                
                                video_url = videos[0].get('url')
                                if video_url:
                                    logger.info(f"Found video URL from fxtwitter API: {video_url}")
                                    # Save URL to file
                                    with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                        f.write(f"{video_url}\n")
                                    return video_url
                            elif isinstance(videos, dict) and videos.get('url'):
                                video_url = videos.get('url')
                                logger.info(f"Found video URL from fxtwitter API: {video_url}")
                                # Save URL to file
                                with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                    f.write(f"{video_url}\n")
                                return video_url
        except Exception as e:
            logger.warning(f"Error using fxtwitter.com API: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        # Strategy 3: Try another variation - fixvx.com
        logger.info("Trying fixvx.com API...")
        fixvx_url = f"https://api.fixvx.com/status/{tweet_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(fixvx_url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Save full response for debugging
                        fixvx_response_file = os.path.join(recordings_dir, "fixvx_response.json")
                        with open(fixvx_response_file, "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved fixvx API response to: {fixvx_response_file}")
                        
                        # Check various potential formats
                        for key in ['media', 'mediaURLs', 'media_urls']:
                            if key in data and data[key]:
                                media_data = data[key]
                                
                                # Handle different response formats
                                if isinstance(media_data, list):
                                    for item in media_data:
                                        if isinstance(item, dict) and 'url' in item and ('video' in item.get('type', '').lower() or item.get('url', '').endswith('.mp4')):
                                            video_url = item['url']
                                            logger.info(f"Found video URL from fixvx API: {video_url}")
                                            # Save URL to file
                                            with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                                f.write(f"{video_url}\n")
                                            return video_url
                                        elif isinstance(item, str) and (item.endswith('.mp4') or 'video' in item):
                                            video_url = item
                                            logger.info(f"Found video URL from fixvx API: {video_url}")
                                            # Save URL to file
                                            with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                                f.write(f"{video_url}\n")
                                            return video_url
                                elif isinstance(media_data, dict):
                                    if media_data.get('videos'):
                                        videos = media_data['videos']
                                        if isinstance(videos, list) and videos:
                                            # Sort by quality
                                            if 'bitrate' in videos[0]:
                                                videos.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                                            
                                            video_url = videos[0].get('url')
                                            if video_url:
                                                logger.info(f"Found video URL from fixvx API: {video_url}")
                                                # Save URL to file
                                                with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                                    f.write(f"{video_url}\n")
                                                return video_url
        except Exception as e:
            logger.warning(f"Error using fixvx.com API: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        # Strategy 4: Make one last attempt by directly visiting the vxtwitter URL in a browser
        from playwright.async_api import async_playwright
        
        logger.info("Trying direct browser visit to vxtwitter...")
        recording_path = os.path.join(recordings_dir, f"debug_{int(asyncio.get_event_loop().time())}.webm")
        logger.info(f"Recording debug video to: {recording_path}")
        
        async with async_playwright() as p:
            # Launch browser with video recording
            browser = await p.chromium.launch(headless=True)
            
            context = await browser.new_context(
                record_video_dir=recordings_dir,
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            try:
                # Visit vxtwitter directly
                vxtwitter_url = tweet_url.replace("twitter.com", "vxtwitter.com").replace("x.com", "vxtwitter.com")
                logger.info(f"Navigating to: {vxtwitter_url}")
                await page.goto(vxtwitter_url, timeout=30000)
                
                # Take screenshot
                vx_screenshot = os.path.join(recordings_dir, "vxtwitter_page.png")
                await page.screenshot(path=vx_screenshot)
                logger.info(f"Saved vxtwitter page screenshot to: {vx_screenshot}")
                
                # Save HTML
                vx_html = await page.content()
                vx_html_path = os.path.join(recordings_dir, "vxtwitter_html.txt")
                with open(vx_html_path, "w") as f:
                    f.write(vx_html)
                
                # Look for video elements
                try:
                    await page.wait_for_selector("video", timeout=10000)
                    
                    # Extract video URLs
                    video_elements = await page.evaluate('''() => {
                        const videos = Array.from(document.querySelectorAll('video'));
                        return videos.map(video => {
                            return {
                                src: video.src,
                                sources: Array.from(video.querySelectorAll('source')).map(source => source.src)
                            };
                        });
                    }''')
                    
                    for video in video_elements:
                        if video.get('src') and video['src'].startswith('http'):
                            video_url = video['src']
                            logger.info(f"Found video URL from vxtwitter page: {video_url}")
                            # Save URL to file
                            with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                f.write(f"{video_url}\n")
                            return video_url
                        
                        for source in video.get('sources', []):
                            if source and source.startswith('http'):
                                logger.info(f"Found video source URL from vxtwitter page: {source}")
                                # Save URL to file
                                with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                                    f.write(f"{source}\n")
                                return source
                except Exception as e:
                    logger.warning(f"Error extracting video from vxtwitter page: {e}")
                
                # Use regex to find video URLs in the HTML
                video_urls = re.findall(r'https?://[^\s"\']+\.mp4[^\s"\']*', vx_html)
                if video_urls:
                    video_url = video_urls[0]  # Use the first one found
                    logger.info(f"Found video URL from vxtwitter HTML: {video_url}")
                    # Save URL to file
                    with open(os.path.join(recordings_dir, "video_urls.txt"), "a") as f:
                        f.write(f"{video_url}\n")
                    return video_url
                
            except Exception as e:
                logger.error(f"Error during vxtwitter browser access: {e}")
            finally:
                # Close browser
                await context.close()
                await browser.close()
                logger.info(f"Debug recording saved to: {recording_path}")
        
        logger.warning("No video URLs found after trying all strategies")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching video: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_debug_directory():
    """
    Get the directory where debug recordings and screenshots are saved
    
    Returns:
        str: Path to debug directory
    """
    import tempfile
    import os
    
    recordings_dir = os.path.join(tempfile.gettempdir(), "tweet_video_debug")
    os.makedirs(recordings_dir, exist_ok=True)
    return recordings_dir

# Add to __all__ if it exists
try:
    __all__.extend(['fetch_video_from_downloader', 'get_debug_directory'])
except NameError:
    __all__ = ['download_media', 'download_all_media', 'extract_media_from_page', 
               'fetch_video_from_downloader', 'get_debug_directory'] 