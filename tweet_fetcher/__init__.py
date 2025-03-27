import logging
import os
import re
import atexit
import asyncio

from .utils.directories import ensure_temp_dirs
from .config import TWEET_URL_PATTERN
from .extractors import extract_tweet_sync, extract_tweet_combined_sync, ExtractorType
from .utils.media import download_media as async_download_media, download_all_media, get_debug_directory  # Import media functions
# Import X credentials from main config
from config import X_USERNAME, X_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tweet_fetcher')

# Ensure temp directories exist
ensure_temp_dirs()

# Create a synchronous wrapper for the async download_media function
def download_media(url, output_path):
    """
    Synchronous wrapper for async download_media function
    
    Args:
        url (str): Media URL to download
        output_path (str): Full path where to save the file
        
    Returns:
        str: Path to downloaded file or None if failed
    """
    try:
        # Get directory from output_path
        output_dir = os.path.dirname(output_path)
        
        # Ensure directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a completely separate event loop for this download to avoid conflicts
        loop = asyncio.new_event_loop()
        try:
            # Set as the current event loop for this thread
            asyncio.set_event_loop(loop)
            
            # Run the async function in this isolated loop
            result = loop.run_until_complete(async_download_media(url, output_dir))
            
            # If the download was successful, rename the file to the expected output_path
            if result:
                # Rename only if the result path is different from the expected path
                if result != output_path and os.path.exists(result):
                    # If target file already exists, remove it
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                        
                    # Rename/move the file
                    os.rename(result, output_path)
                    logger.info(f"Renamed {result} to {output_path}")
                    return output_path
                return result
            return None
        finally:
            # Always clean up and close the loop, even if there was an error
            try:
                # Get all pending tasks in this loop
                pending = asyncio.all_tasks(loop)
                if pending:
                    # Cancel all tasks and give them a chance to clean up
                    for task in pending:
                        task.cancel()
                    # Wait with a timeout for tasks to acknowledge cancellation
                    done, pending = loop.run_until_complete(
                        asyncio.wait(pending, timeout=5, return_when=asyncio.ALL_COMPLETED)
                    )
            except Exception as cleanup_err:
                logger.warning(f"Error cleaning up tasks during download: {cleanup_err}")
            finally:
                # Close the loop
                loop.close()
    except Exception as e:
        logger.error(f"Error in synchronous download_media: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

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
        import traceback
        logger.error(traceback.format_exc())

def shutdown():
    """Cleanup function to ensure all resources are properly released"""
    logger.info("Performing tweet_fetcher shutdown...")
    
    # Run the async shutdown in an event loop
    try:
        # Create a completely new event loop for shutdown to avoid conflicts
        shutdown_loop = asyncio.new_event_loop()
        try:
            # Set as the current event loop for this thread
            asyncio.set_event_loop(shutdown_loop)
            
            # Run the browser shutdown task
            shutdown_loop.run_until_complete(_shutdown_browser_sessions())
            logger.info("Browser sessions shutdown completed")
            
            # Get any pending tasks
            pending = asyncio.all_tasks(shutdown_loop)
            if pending:
                logger.info(f"Waiting for {len(pending)} pending tasks to complete...")
                
                # Use wait with timeout to avoid hanging
                done, pending = shutdown_loop.run_until_complete(
                    asyncio.wait(pending, timeout=5, return_when=asyncio.ALL_COMPLETED)
                )
                
                # Cancel any tasks that didn't finish
                if pending:
                    logger.warning(f"Forcibly cancelling {len(pending)} tasks that didn't complete")
                    for task in pending:
                        task.cancel()
                    
                    # Give a short grace period for cancellation to be processed
                    try:
                        shutdown_loop.run_until_complete(asyncio.wait(pending, timeout=1))
                    except Exception as e:
                        logger.warning(f"Error during final task cancellation: {e}")
            
        finally:
            # Always close the loop
            shutdown_loop.close()
            
        logger.info("Tweet fetcher shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        import traceback
        logger.error(traceback.format_exc())

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

def get_tweet_content(username, tweet_id, use_auth=False, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Multi-tiered approach to get tweet content
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Tweet ID
        use_auth (bool): Whether to try authenticated approach
        auth_username (str): X/Twitter username for authentication
        auth_password (str): X/Twitter password for authentication
        auth_phone (str): X/Twitter phone number for verification
        record_video (bool): Whether to record video of the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Tweet content with text, media_urls and source
    """
    # Create a list of all extraction methods to try
    # Make AUTH_PLAYWRIGHT the primary method, followed by others
    # methods = [ExtractorType.AUTH_PLAYWRIGHT, ExtractorType.PLAYWRIGHT, ExtractorType.METADATA, ExtractorType.VIDEO_DOWNLOADER]
    methods = [ExtractorType.AUTH_PLAYWRIGHT]

    # Use environment credentials if not provided directly
    if auth_username is None and X_USERNAME:
        auth_username = X_USERNAME
    
    if auth_password is None and X_PASSWORD:
        auth_password = X_PASSWORD
    
    if auth_phone is None and os.environ.get('X_PHONE_NUMBER'):
        auth_phone = os.environ.get('X_PHONE_NUMBER')
    
    # Pass authentication details to the combined extractor
    return extract_tweet_combined_sync(
        username, 
        tweet_id, 
        methods, 
        auth_username=auth_username, 
        auth_password=auth_password,
        auth_phone=auth_phone,
        record_video=record_video,
        record_quality=record_quality
    )

def get_tweet_from_url(url, use_auth=False, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Extract tweet content from a URL
    
    Args:
        url (str): Twitter/X URL
        use_auth (bool): Whether to try authenticated approach
        auth_username (str): X/Twitter username for authentication
        auth_password (str): X/Twitter password for authentication
        auth_phone (str): X/Twitter phone number for verification
        record_video (bool): Whether to record video of the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Tweet content with text, media_urls and source
    """
    username, tweet_id = extract_tweet_info(url)
    if username and tweet_id:
        result = get_tweet_content(
            username, 
            tweet_id, 
            use_auth=use_auth, 
            auth_username=auth_username, 
            auth_password=auth_password,
            auth_phone=auth_phone,
            record_video=record_video,
            record_quality=record_quality
        )
        
        # Make sure the original source URL is included
        result['source'] = url
        return result
    else:
        logger.error(f"Invalid tweet URL: {url}")
        return {
            'text': "",  # Keep text empty, don't include error messages in text field
            'media_urls': [],
            'source': url,
            'error': "Invalid tweet URL"
        }

# Export media functions so they can be imported directly from tweet_fetcher
__all__ = [
    'get_tweet_content',
    'get_tweet_from_url',
    'download_media',
    'download_all_media',
    'ExtractorType',
    'extract_tweet_combined_sync',
    'get_debug_directory',
    'test_video_download',
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
    
    # AUTH_PLAYWRIGHT is now the primary method by default
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
    print(f"Media URLs ({len(result.get('media_urls', []))}): {result.get('media_urls')}")
    print(f"Source: {result.get('source')}")
    print(f"Error: {result.get('error')}")
    
    return result

def test_video_download(url):
    """
    Test function to download video from tweet URL
    
    Args:
        url (str): Tweet URL
        
    Returns:
        None
    """
    # Run the test script with the provided URL
    import subprocess
    import sys
    import os
    
    script_path = os.path.join(os.path.dirname(__file__), 'test_video.py')
    
    print(f"Testing video download from {url}")
    print(f"Debug files will be saved to {get_debug_directory()}")
    
    subprocess.run([sys.executable, script_path, url]) 