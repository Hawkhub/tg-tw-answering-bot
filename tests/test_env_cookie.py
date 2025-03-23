#!/usr/bin/env python3
import os
from config import X_COOKIE_TABLE
from tweet_fetcher import get_tweet_content

def main():
    """Test the X_COOKIE_TABLE environment variable integration"""
    # Check if X_COOKIE_TABLE is set
    if not X_COOKIE_TABLE:
        print("WARNING: X_COOKIE_TABLE environment variable is not set!")
        print("Please add it to your .env file and then 'source .env'")
        return
    
    print(f"X_COOKIE_TABLE is set with {len(X_COOKIE_TABLE)} characters")
    
    # Example Twitter/X post
    username = "Twitter"
    tweet_id = "1683301293655388160"  # Example tweet ID
    
    # This will automatically use X_COOKIE_TABLE
    print(f"Fetching tweet from @{username}/status/{tweet_id} using environment cookie table...")
    tweet_content = get_tweet_content(username, tweet_id)
    
    print("\nRESULTS:")
    print(f"Text: {tweet_content.get('text', 'No text found')}")
    print(f"Media items: {len(tweet_content.get('media_urls', []))}")
    print(f"Auth used: {tweet_content.get('auth_used', False)}")
    
    return tweet_content

if __name__ == "__main__":
    main() 