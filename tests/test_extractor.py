#!/usr/bin/env python3
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tweet_fetcher.extractors.auth_playwright.extractor import AuthPlaywrightExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_extractor')

async def test_extractor():
    """
    Test the AuthPlaywrightExtractor to verify it works without runtime errors.
    This test doesn't actually execute the extraction, it just checks for initialization issues.
    """
    try:
        # Create an instance of the extractor
        extractor = AuthPlaywrightExtractor(
            username="ImjustPage",
            tweet_id="1855969758681972736",
            auth_username="test_user",
            auth_password="test_password"
        )
        
        print("Successfully created AuthPlaywrightExtractor instance")
        print("Class attributes:")
        print(f"- username: {extractor.username}")
        print(f"- tweet_id: {extractor.tweet_id}")
        print(f"- auth_username: {extractor.auth_username}")
        print(f"- auth_password: {extractor.auth_password}")
        
        # Test if methods exist
        methods = [
            "_setup_human_behavior",
            "_get_mouse_position",
            "_simulate_realistic_tweet_interaction",
            "_natural_mouse_move",
            "_extract_tweet_content",
            "extract"
        ]
        
        print("\nChecking methods:")
        for method in methods:
            if hasattr(extractor, method) and callable(getattr(extractor, method)):
                print(f"- Method {method} exists")
            else:
                print(f"- Method {method} MISSING")
        
        return True
    except Exception as e:
        logger.error(f"Error testing extractor: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_extractor())
    if result:
        print("\nTest completed successfully")
    else:
        print("\nTest failed")
        sys.exit(1) 