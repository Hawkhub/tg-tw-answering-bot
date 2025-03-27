import logging
import os
import asyncio
import re
from urllib.parse import urlparse

from ...config import (
    HTML_DIR, 
    SCREENSHOTS_DIR, 
    TWEET_TEXT_SELECTORS, 
    IMAGE_SELECTORS, 
    VIDEO_SELECTORS,
    DEFAULT_TIMEOUT
)
from ...utils.media import extract_media_from_page
from ..base import BaseExtractor
from .browser import create_browser_context

logger = logging.getLogger('tweet_fetcher')

class PlaywrightExtractor(BaseExtractor):
    """Extract tweet content using Playwright without auth"""
    
    def __init__(self, username, tweet_id, record_video=False, record_quality='medium'):
        """
        Initialize the extractor
        
        Args:
            username (str): Twitter/X username for the tweet
            tweet_id (str): Tweet ID
            record_video (bool): Whether to record the extraction process
            record_quality (str): Recording quality (low: 480p, medium: 720p, high: 1080p)
        """
        super().__init__(username, tweet_id)
        self.record_video = record_video
        self.record_quality = record_quality
    
    async def extract(self):
        """Extract tweet content using Playwright automation"""
        playwright = None
        browser_context = None
        
        try:
            # Create browser context with stealth measures
            playwright, browser_context = await create_browser_context(record_video=self.record_video, record_quality=self.record_quality)
            
            # Create a new page
            page = await browser_context.new_page()
            
            # Navigate to tweet
            logger.info(f"Navigating to tweet: {self.source_url}")
            await page.goto(self.source_url, wait_until="networkidle", timeout=DEFAULT_TIMEOUT)
            
            # Wait for tweet to load
            await page.wait_for_load_state("domcontentloaded")
            
            # Extract content from page
            return await self._extract_content_from_page(page)
            
        except Exception as e:
            logger.error(f"Error extracting tweet with Playwright: {str(e)}")
            return self.get_empty_result(f"Error extracting tweet: {str(e)}")
            
        finally:
            # Clean up resources
            if browser_context:
                await browser_context.close()
            if playwright:
                await playwright.stop()
    
    async def _extract_tweet_text(self, page):
        """Extract text content from tweet"""
        for selector in TWEET_TEXT_SELECTORS:
            try:
                text_element = await page.query_selector(selector)
                if text_element:
                    text = await text_element.inner_text()
                    if text:
                        return text
            except Exception as e:
                logger.warning(f"Failed extracting with selector {selector}: {e}")
                
        # Return empty string instead of error message
        return ""

    async def _extract_content_from_page(self, page):
        """Extract all content from a page"""
        from ...utils.media import extract_media_from_page
        from ...config import IMAGE_SELECTORS, VIDEO_SELECTORS, SCREENSHOTS_DIR, HTML_DIR
        
        # Extract text
        text = await self._extract_tweet_text(page)
        
        # Extract media URLs
        media_urls = await extract_media_from_page(page, IMAGE_SELECTORS, VIDEO_SELECTORS)
        
        # Take screenshot
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{self.username}_{self.tweet_id}.png")
        await page.screenshot(path=screenshot_path)
        
        # Save HTML
        html_path = os.path.join(HTML_DIR, f"{self.username}_{self.tweet_id}.html")
        html_content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        result = {
            'text': text,
            'media_urls': media_urls,
            'source': self.source_url,
            'screenshot': screenshot_path,
            'html': html_path,
            'error': None  # No error
        }
        
        # If we couldn't extract text or media, add an error but keep text field empty
        if not text and not media_urls:
            result['error'] = f"Could not extract content from tweet"
            
        return result 