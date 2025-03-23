#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
import json
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import X_USERNAME, X_PASSWORD
from tweet_fetcher.extractors.auth_playwright.extractor import AuthPlaywrightExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_extractor_extraction')

async def test_extraction():
    """
    Test the actual extraction process by fetching a tweet.
    This will test the full functionality of the AuthPlaywrightExtractor.
    """
    if not X_USERNAME or not X_PASSWORD:
        print("ERROR: X_USERNAME and X_PASSWORD are required for this test")
        print("Please set them in your .env file and run 'source .env'")
        return False

    try:
        print(f"Testing tweet extraction using credentials for: {X_USERNAME}")
        print("Creating extractor instance...")
        
        # Create an instance of the extractor
        extractor = AuthPlaywrightExtractor(
            username="ImjustPage",
            tweet_id="1855969758681972736",
            auth_username=X_USERNAME,
            auth_password=X_PASSWORD
        )
        
        print("Starting extraction process (this will take some time)...")
        start_time = time.time()
        
        # Actually extract the tweet content
        # We'll only run this for 30 seconds maximum to avoid hanging
        content = await asyncio.wait_for(extractor.extract(), timeout=120)
        
        elapsed_time = time.time() - start_time
        print(f"Extraction completed in {elapsed_time:.2f} seconds")
        
        # Display the results
        print("\nExtraction results:")
        print(f"Text content: {content.get('text', 'None')}")
        print(f"Media URLs: {len(content.get('media_urls', []))}")
        print(f"Authentication used: {content.get('auth_used', False)}")
        
        # Save results to a file for inspection
        results_dir = os.path.join(".temp", "test_results")
        os.makedirs(results_dir, exist_ok=True)
        
        result_file = os.path.join(results_dir, f"extraction_result_{int(time.time())}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2)
            
        print(f"\nResults saved to: {result_file}")
        
        return True
    except asyncio.TimeoutError:
        logger.error("Extraction timed out after 120 seconds")
        return False
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting extraction test...")
    print("Note: This test will create a real browser and attempt to log in to X/Twitter")
    print("The test might take up to 2 minutes to complete")
    
    try:
        result = asyncio.run(test_extraction())
        if result:
            print("\nExtraction test completed successfully")
        else:
            print("\nExtraction test failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1) 