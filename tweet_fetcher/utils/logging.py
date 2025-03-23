import logging
import os
import sys
from datetime import datetime

def setup_logging(log_dir=None, log_level=logging.INFO):
    """
    Set up logging configuration for tweet_fetcher
    
    Args:
        log_dir (str): Optional directory for log files
        log_level: Logging level
    """
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Configure tweet_fetcher logger
    logger = logging.getLogger('tweet_fetcher')
    logger.setLevel(log_level)
    
    # Add file handler if log_dir is provided
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'tweet_fetcher_{timestamp}.log')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to {log_file}")
    
    return logger 