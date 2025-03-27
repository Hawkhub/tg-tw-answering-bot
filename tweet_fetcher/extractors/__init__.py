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
    VIDEO_DOWNLOADER = auto() # For fetching videos from downloader service
    

async def extract_tweet(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Extract tweet content using specified methods in priority order
    
    Note: This function stops at the first successful method. 
    Consider using extract_tweet_combined for more comprehensive results.
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try in order
        auth_username (str): Username for authentication 
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        record_video (bool): Whether to record the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Tweet content with text and media_urls
    """
    logger.info(f"Starting tweet extraction for @{username}/status/{tweet_id}")
    if record_video:
        logger.info(f"Screen recording enabled with {record_quality} quality")
    
    # Try each method in order
    for method in methods:
        try:
            logger.info(f"Trying extraction method: {method.name.lower()}")
            
            if method == ExtractorType.AUTH_PLAYWRIGHT:
                from .auth_playwright.extractor import AuthPlaywrightExtractor
                extractor = AuthPlaywrightExtractor(
                    username, 
                    tweet_id, 
                    auth_username, 
                    auth_password, 
                    auth_phone,
                    record_video=record_video,
                    record_quality=record_quality
                )
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
                extractor = PlaywrightExtractor(
                    username, 
                    tweet_id,
                    record_video=record_video,
                    record_quality=record_quality
                )
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
    
    # If all methods failed, return empty result with error field only, not in text field
    logger.error("All extraction methods failed")
    return {
        'text': "",  # Keep text empty, no error messages in text field
        'media_urls': [],
        'source': f"https://x.com/{username}/status/{tweet_id}",
        'error': "All extraction methods failed"
    }

def extract_tweet_sync(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Synchronous wrapper for extract_tweet
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try in order
        auth_username (str): Username for authentication
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        record_video (bool): Whether to record the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Tweet content with text and media_urls
    """
    return asyncio.run(
        extract_tweet(
            username, 
            tweet_id, 
            methods, 
            auth_username, 
            auth_password, 
            auth_phone,
            record_video,
            record_quality
        )
    )

async def extract_tweet_combined(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Extract tweet content using all specified methods and combine the results
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try
        auth_username (str): Username for authentication 
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        record_video (bool): Whether to record the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Combined tweet content with text and media_urls from all sources
    """
    logger.info(f"Starting combined tweet extraction for @{username}/status/{tweet_id}")
    if record_video:
        logger.info(f"Screen recording enabled with {record_quality} quality")
    
    # Initialize the combined result
    combined_result = {
        'text': '',
        'media_urls': [],
        'source': f"https://x.com/{username}/status/{tweet_id}",
        'error': None
    }
    
    # Keep track of methods that were successful
    successful_methods = []
    
    # Try each method and collect all available data
    for method in methods:
        try:
            logger.info(f"Trying extraction method: {method.name.lower()}")
            
            if method == ExtractorType.AUTH_PLAYWRIGHT:
                from .auth_playwright.extractor import AuthPlaywrightExtractor
                extractor = AuthPlaywrightExtractor(
                    username, 
                    tweet_id, 
                    auth_username, 
                    auth_password, 
                    auth_phone,
                    record_video=record_video,
                    record_quality=record_quality
                )
                result = await extractor.extract()
                
            elif method == ExtractorType.PLAYWRIGHT:
                from .playwright.extractor import PlaywrightExtractor
                extractor = PlaywrightExtractor(
                    username, 
                    tweet_id,
                    record_video=record_video,
                    record_quality=record_quality
                )
                result = await extractor.extract()
                
            elif method == ExtractorType.METADATA:
                from .metadata.extractor import MetadataExtractor
                extractor = MetadataExtractor(username, tweet_id)
                result = await extractor.extract()
                
            elif method == ExtractorType.VIDEO_DOWNLOADER:
                # This method works with the full tweet URL
                from ..utils.media import fetch_video_from_downloader
                tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                video_url = await fetch_video_from_downloader(tweet_url)
                
                # Create a result object similar to other extractors
                if video_url:
                    result = {
                        'text': combined_result['text'],  # Keep existing text
                        'media_urls': [video_url],
                        'source': tweet_url,
                        'error': None
                    }
                else:
                    result = None
                
            # Check if we got meaningful content
            if result and not result.get('error'):
                successful_methods.append(method.name)
                
                # Add text if it's new and not empty
                if result.get('text') and result['text'] not in combined_result['text']:
                    if combined_result['text']:
                        combined_result['text'] += "\n\n" + result['text']
                    else:
                        combined_result['text'] = result['text']
                
                # Add media URLs that are not already in the list
                if result.get('media_urls'):
                    for url in result['media_urls']:
                        if url not in combined_result['media_urls']:
                            combined_result['media_urls'].append(url)
            
        except Exception as e:
            logger.error(f"{method.name.lower()} approach failed with error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # Check if we have any successful results
    if successful_methods:
        logger.info(f"Successfully extracted tweet content with methods: {', '.join(successful_methods)}")
        logger.info(f"Found {len(combined_result['media_urls'])} media URLs")
        combined_result['error'] = None
        return combined_result
    else:
        # If all methods failed, return error result - keep text empty, error only in error field
        logger.error("All extraction methods failed")
        combined_result['text'] = ""  # Ensure no error messages in text field
        combined_result['error'] = "All extraction methods failed"
        return combined_result

def extract_tweet_combined_sync(username, tweet_id, methods, auth_username=None, auth_password=None, auth_phone=None, record_video=False, record_quality='medium'):
    """
    Synchronous wrapper for extract_tweet_combined
    
    Args:
        username (str): Twitter/X username
        tweet_id (str): Twitter/X tweet ID
        methods (list): List of ExtractorType to try
        auth_username (str): Username for authentication
        auth_password (str): Password for authentication
        auth_phone (str): Phone number for verification
        record_video (bool): Whether to record the extraction process
        record_quality (str): Recording quality ('low', 'medium', 'high')
        
    Returns:
        dict: Combined tweet content with text and media_urls from all sources
    """
    try:
        # First try to get the current event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            new_loop_created = True
        else:
            new_loop_created = False
        
        # Run the extraction task
        if loop.is_running():
            # If the loop is already running (we're in an async context)
            # Create a future and run the extraction in a task
            future = asyncio.run_coroutine_threadsafe(
                extract_tweet_combined(username, tweet_id, methods, auth_username, auth_password, auth_phone, record_video, record_quality),
                loop
            )
            result = future.result(timeout=120)  # 2-minute timeout
        else:
            # If the loop is not running, use run_until_complete
            result = loop.run_until_complete(
                extract_tweet_combined(username, tweet_id, methods, auth_username, auth_password, auth_phone, record_video, record_quality)
            )
        
        # Close the loop if we created it
        if new_loop_created:
            loop.close()
            
        return result
    except Exception as e:
        import logging
        logger = logging.getLogger('tweet_fetcher')
        logger.error(f"Error in extract_tweet_combined_sync: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Return an error result
        return {
            'text': "",  # Keep text empty, no error messages in text field
            'media_urls': [],
            'source': f"https://twitter.com/{username}/status/{tweet_id}",
            'error': f"Extraction error: {str(e)}"
        } 