import os
import logging
from tweet_fetcher.config import TEMP_DIRS

logger = logging.getLogger('tweet_fetcher')

def ensure_temp_dirs():
    """
    Ensure all temporary directories exist
    Returns information about created/existing directories
    """
    created = []
    existing = []
    failed = []
    
    for directory in TEMP_DIRS:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                created.append(directory)
                logger.info(f"Created directory: {directory}")
            else:
                # Verify the directory is writable
                if os.access(directory, os.W_OK):
                    existing.append(directory)
                    logger.info(f"Directory exists and is writable: {directory}")
                else:
                    logger.error(f"Directory exists but is NOT writable: {directory}")
                    failed.append(f"{directory} (not writable)")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            failed.append(f"{directory} ({str(e)})")
    
    # Print summary
    if created:
        logger.info(f"Created {len(created)} directories: {', '.join(created)}")
    if existing:
        logger.info(f"Found {len(existing)} existing directories: {', '.join(existing)}")
    if failed:
        logger.error(f"Failed to create/verify {len(failed)} directories: {', '.join(failed)}")
    
    return {
        "created": created,
        "existing": existing,
        "failed": failed
    } 