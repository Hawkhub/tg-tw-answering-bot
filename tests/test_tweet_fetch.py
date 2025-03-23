#!/usr/bin/env python3
import os
import sys
import time
import argparse

# Add parent directory to path to import from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import X_USERNAME, X_PASSWORD
from tweet_fetcher import get_tweet_content

def main():
    """Test the tweet fetcher with different authentication options"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test tweet fetching with authentication')
    parser.add_argument('--username', '-u', help='Twitter username of the tweet author')
    parser.add_argument('--tweet_id', '-t', help='Tweet ID to fetch')
    parser.add_argument('--no-auth', action='store_true', help='Skip authentication')
    args = parser.parse_args()
    
    # Default to example tweet if none provided
    username = args.username or "ImjustPage"
    tweet_id = args.tweet_id or "1855969758681972736"
    use_auth = not args.no_auth
    
    print(f"Testing tweet fetch for @{username}/status/{tweet_id}")
    
    # Check authentication credentials if using auth
    if use_auth:
        if not X_USERNAME or not X_PASSWORD:
            print("WARNING: X_USERNAME or X_PASSWORD not set in environment")
            print("Please set them in your .env file and run 'source .env'")
            print("Continuing without authentication...")
            use_auth = False
        else:
            print(f"Will attempt authentication as {X_USERNAME}")
    
    # Record start time to measure performance
    start_time = time.time()
    
    # Fetch the tweet content
    tweet_content = get_tweet_content(
        username, 
        tweet_id, 
        use_auth=use_auth, 
        auth_username=X_USERNAME,
        auth_password=X_PASSWORD
    )
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Display results
    print("\nRESULTS:")
    print(f"Text: {tweet_content.get('text', 'No text found')}")
    print(f"Media items: {len(tweet_content.get('media_urls', []))}")
    
    if tweet_content.get('media_urls'):
        print("Media URLs:")
        for url in tweet_content.get('media_urls', []):
            print(f"  - {url}")
    
    print(f"Authentication used: {tweet_content.get('auth_used', False)}")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    
    # Check for errors
    if 'error' in tweet_content:
        print(f"Error encountered: {tweet_content['error']}")
    
    # Return the content for potential further processing
    return tweet_content

if __name__ == "__main__":
    main() 