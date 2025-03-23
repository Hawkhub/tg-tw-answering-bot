import logging
import os
import re
import atexit
import asyncio

from .utils.directories import ensure_temp_dirs
from .config import TWEET_URL_PATTERN
from .extractors import extract_tweet_sync, ExtractorType
from .utils.media import download_media, download_all_media  # Import media functions
# Import X credentials from main config
from config import X_USERNAME, X_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tweet_fetcher')

# Ensure temp directories exist
ensure_temp_dirs()

# Create a shutdown function to properly close all browser sessions
async def _shutdown_browser_sessions():
    """Close all browser sessions properly"""
    try:
        # Import here to avoid circular imports
        from .extractors.auth_playwright.browser import BrowserSessionManager
        
        logger.info("Shutting down all browser sessions...")
        await BrowserSessionManager.close_all_sessions()
        logger.info("All browser sessions closed successfully")
    except Exception as e:
        logger.error(f"Error during browser shutdown: {e}")

def shutdown():
    """Cleanup function to ensure all resources are properly released"""
    logger.info("Performing tweet_fetcher shutdown...")
    
    # Run the async shutdown in an event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context already
            future = asyncio.ensure_future(_shutdown_browser_sessions())
            # We could wait but this might block - depends on your application
        else:
            # If we're not in an async context, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_shutdown_browser_sessions())
            loop.close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Register shutdown function to be called on exit
atexit.register(shutdown)

def extract_tweet_info(url):
    """Extract username and tweet ID from Twitter/X URL"""
    match = re.match(TWEET_URL_PATTERN, url)
    if match:
        username = match.group(2)
        tweet_id = match.group(3)
        return username, tweet_id
    return None, None

def get_tweet_content(username, tweet_id, use_auth=False, auth_username=None, auth_password=None, auth_phone=None):
    """
    Multi-tiered approach to get tweet content
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Tweet ID
        use_auth (bool): Whether to try authenticated approach
        auth_username (str): X/Twitter username for authentication
        auth_password (str): X/Twitter password for authentication
        auth_phone (str): X/Twitter phone number for verification
        
    Returns:
        dict: Tweet content with text, media_urls and source
    """
    methods = [ExtractorType.PLAYWRIGHT, ExtractorType.METADATA]
    
    # Use environment credentials if not provided directly
    if auth_username is None and X_USERNAME:
        auth_username = X_USERNAME
    
    if auth_password is None and X_PASSWORD:
        auth_password = X_PASSWORD
    
    if auth_phone is None and os.environ.get('X_PHONE_NUMBER'):
        auth_phone = os.environ.get('X_PHONE_NUMBER')
    
    # If authentication is requested and we have credentials
    if use_auth and auth_username and auth_password:
        # Add auth method as first priority
        methods.insert(0, ExtractorType.AUTH_PLAYWRIGHT)
        
    # Pass authentication details to the extractor
    return extract_tweet_sync(
        username, 
        tweet_id, 
        methods, 
        auth_username=auth_username, 
        auth_password=auth_password,
        auth_phone=auth_phone
    )

def get_tweet_from_url(url, use_auth=False, auth_username=None, auth_password=None, auth_phone=None):
    """
    Extract tweet content from a URL
    
    Args:
        url (str): Twitter/X URL
        use_auth (bool): Whether to try authenticated approach
        auth_username (str): X/Twitter username for authentication
        auth_password (str): X/Twitter password for authentication
        auth_phone (str): X/Twitter phone number for verification
        
    Returns:
        dict: Tweet content with text, media_urls and source
    """
    username, tweet_id = extract_tweet_info(url)
    if username and tweet_id:
        return get_tweet_content(
            username, 
            tweet_id, 
            use_auth=use_auth, 
            auth_username=auth_username, 
            auth_password=auth_password,
            auth_phone=auth_phone
        )
    else:
        logger.error(f"Invalid tweet URL: {url}")
        return {
            'text': f"Invalid tweet URL: {url}",
            'media_urls': [],
            'source': url
        }

# Export media functions so they can be imported directly from tweet_fetcher
__all__ = [
    'get_tweet_content',
    'get_tweet_from_url',
    'download_media',
    'download_all_media',
    'ExtractorType',
    'shutdown'
]

# Testing function - use this to debug specific tweet fetching
def test_tweet_fetch(username, tweet_id, use_auth=False, auth_username=None, auth_password=None, auth_phone=None):
    """
    Test function to fetch a tweet and print the results for debugging
    """
    print(f"Testing tweet fetch for @{username}/status/{tweet_id}")
    
    # Use environment credentials if not provided directly
    if auth_username is None and X_USERNAME:
        auth_username = X_USERNAME
    
    if auth_password is None and X_PASSWORD:
        auth_password = X_PASSWORD
        
    if auth_phone is None and os.environ.get('X_PHONE_NUMBER'):
        auth_phone = os.environ.get('X_PHONE_NUMBER')
    
    # Force authentication if credentials are available
    if auth_username and auth_password:
        use_auth = True
        
    result = get_tweet_content(
        username, 
        tweet_id, 
        use_auth=use_auth, 
        auth_username=auth_username, 
        auth_password=auth_password,
        auth_phone=auth_phone
    )
    
    print("\nRESULT:")
    print(f"Text: {result.get('text')}")
    print(f"Media URLs: {result.get('media_urls')}")
    print(f"Source: {result.get('source')}")
    
    return result 