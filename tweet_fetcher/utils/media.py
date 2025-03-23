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
        output_dir (str): Download directory
        
    Returns:
        str: Path to downloaded file or None if failed
    """
    try:
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
        os.makedirs(output_dir, exist_ok=True)
        
        # Download file
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