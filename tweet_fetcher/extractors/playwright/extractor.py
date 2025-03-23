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
    
    async def extract(self):
        """Extract tweet content using Playwright automation"""
        playwright = None
        browser_context = None
        
        try:
            # Create browser context with stealth measures
            playwright, browser_context = await create_browser_context()
            
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
                
        return f"Tweet by @{self.username} - Text content could not be extracted."

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
        
        return {
            'text': text,
            'media_urls': media_urls,
            'source': self.source_url,
            'screenshot': screenshot_path,
            'html': html_path
        } 