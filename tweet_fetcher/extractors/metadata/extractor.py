import logging
import aiohttp
import re
from bs4 import BeautifulSoup

from ...config import USER_AGENTS
from ..base import BaseExtractor

logger = logging.getLogger('tweet_fetcher')

class MetadataExtractor(BaseExtractor):
    """Extract minimal tweet data from metadata"""
    
    async def extract(self):
        """Extract tweet content from HTML metadata"""
        try:
            # Setup HTTP session
            headers = {
                'User-Agent': USER_AGENTS[0],
                'Accept': 'text/html,application/xhtml+xml,application/xml',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://x.com/',
                'dnt': '1'
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.source_url, allow_redirects=True) as response:
                    if response.status != 200:
                        return self.get_empty_result(f"HTTP Error: {response.status}")
                    
                    html = await response.text()
                    
                    # Extract metadata
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Try to extract from meta tags
                    text = self._extract_meta_description(soup)
                    image_urls = self._extract_meta_images(soup)
                    
                    return {
                        'text': text,
                        'media_urls': image_urls,
                        'source': self.source_url
                    }
                    
        except Exception as e:
            logger.error(f"Error extracting tweet metadata: {str(e)}")
            return self.get_empty_result(f"Error extracting tweet metadata: {str(e)}")
    
    def _extract_meta_description(self, soup):
        """Extract tweet text from meta description"""
        # Try different meta tags that might contain the tweet content
        for meta_property in ['og:description', 'twitter:description', 'description']:
            meta_tag = soup.find('meta', property=meta_property) or soup.find('meta', attrs={'name': meta_property})
            if meta_tag and meta_tag.get('content'):
                content = meta_tag.get('content')
                # Clean up the text - remove URL suffixes like "https://t.co/abc123"
                content = re.sub(r'https://t\.co/\w+$', '', content).strip()
                return content
        
        # If we couldn't find content, return placeholder
        return f"Tweet by @{self.username} - Text content could not be extracted from metadata."
    
    def _extract_meta_images(self, soup):
        """Extract image URLs from meta tags"""
        image_urls = []
        
        # Look for image in og:image and twitter:image meta tags
        for meta_property in ['og:image', 'twitter:image']:
            meta_tag = soup.find('meta', property=meta_property) or soup.find('meta', attrs={'name': meta_property})
            if meta_tag and meta_tag.get('content'):
                image_url = meta_tag.get('content')
                if image_url and image_url not in image_urls:
                    image_urls.append(image_url)
        
        return image_urls 