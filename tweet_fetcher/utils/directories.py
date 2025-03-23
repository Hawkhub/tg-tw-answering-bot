import os
from tweet_fetcher.config import TEMP_DIRS

def ensure_temp_dirs():
    """Ensure all temporary directories exist"""
    for directory in TEMP_DIRS:
        os.makedirs(directory, exist_ok=True) 