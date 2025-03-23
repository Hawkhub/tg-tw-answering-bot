import logging
import asyncio
from enum import Enum, auto

# Configure logging
logger = logging.getLogger('tweet_fetcher')

class ExtractorType(Enum):
    """Types of tweet extractors"""
    AUTH_PLAYWRIGHT = auto()  # Authenticated Playwright session
    PLAYWRIGHT = auto()       # Regular unauthenticated Playwright
    METADATA = auto()         # Simple metadata extraction without browser
    

async def extract_tweet(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None):
    """
    Extract tweet content using specified methods in priority order
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try in order
        auth_username (str): Username for authentication 
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        
    Returns:
        dict: Tweet content with text and media_urls
    """
    logger.info(f"Starting tweet extraction for @{username}/status/{tweet_id}")
    
    # Try each method in order
    for method in methods:
        try:
            logger.info(f"Trying extraction method: {method.name.lower()}")
            
            if method == ExtractorType.AUTH_PLAYWRIGHT:
                from .auth_playwright.extractor import AuthPlaywrightExtractor
                extractor = AuthPlaywrightExtractor(username, tweet_id, auth_username, auth_password, auth_phone)
                result = await extractor.extract()
                
                # Check if we got meaningful content
                if result and result.get('text') and not result.get('error'):
                    logger.info(f"Successfully extracted tweet content via {method.name.lower()}")
                    return result
                else:
                    logger.warning(f"{method.name.lower()} approach failed to find content")
                    continue
                    
            elif method == ExtractorType.PLAYWRIGHT:
                from .playwright.extractor import PlaywrightExtractor
                extractor = PlaywrightExtractor(username, tweet_id)
                result = await extractor.extract()
                
                if result and result.get('text') and not result.get('error'):
                    logger.info(f"Successfully extracted tweet content via {method.name.lower()}")
                    return result
                else:
                    logger.warning(f"{method.name.lower()} approach failed to find content")
                    continue
                    
            elif method == ExtractorType.METADATA:
                from .metadata.extractor import MetadataExtractor
                extractor = MetadataExtractor(username, tweet_id)
                result = await extractor.extract()
                
                if result and result.get('text') and not result.get('error'):
                    logger.info(f"Successfully extracted tweet content via {method.name.lower()}")
                    return result
                else:
                    logger.warning(f"{method.name.lower()} approach failed to find content")
                    continue
                
        except Exception as e:
            logger.error(f"{method.name.lower()} approach failed with error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # If all methods failed, return empty result
    logger.error("All extraction methods failed")
    return {
        'text': f"Failed to extract tweet from @{username}/status/{tweet_id}",
        'media_urls': [],
        'source': f"https://x.com/{username}/status/{tweet_id}",
        'error': "All extraction methods failed"
    }

def extract_tweet_sync(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None):
    """
    Synchronous wrapper for extract_tweet
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try in order
        auth_username (str): Username for authentication
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        
    Returns:
        dict: Tweet content with text and media_urls
    """
    return asyncio.run(extract_tweet(username, tweet_id, methods, auth_username, auth_password, auth_phone)) 