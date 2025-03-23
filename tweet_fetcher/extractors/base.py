import logging
from abc import ABC, abstractmethod

logger = logging.getLogger('tweet_fetcher')

class BaseExtractor(ABC):
    """Base class for all tweet extractors"""
    
    def __init__(self, username, tweet_id):
        """
        Initialize the extractor
        
        Args:
            username (str): Twitter/X username
            tweet_id (str): Tweet ID
        """
        self.username = username
        self.tweet_id = tweet_id
        self.source_url = f"https://x.com/{username}/status/{tweet_id}"
        
    @abstractmethod
    async def extract(self):
        """
        Extract tweet content
        
        Returns:
            dict: Tweet content with keys:
                - text: Tweet text content
                - media_urls: List of media URLs
                - source: Source URL
        """
        pass
    
    def get_empty_result(self, error_message=None):
        """Get empty result with optional error message"""
        text = error_message
        if not text:
            text = f"Tweet by @{self.username} - Content could not be retrieved automatically."
            
        return {
            'text': text,
            'media_urls': [],
            'source': self.source_url
        } 