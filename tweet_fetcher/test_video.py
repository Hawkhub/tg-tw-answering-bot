#!/usr/bin/env python3
"""
Test script for debugging video extraction from tweets
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tweet_fetcher.utils.media import fetch_video_from_downloader, get_debug_directory
from tweet_fetcher import extract_tweet_info

async def test_video_extraction(tweet_url):
    """Test video extraction from a tweet URL"""
    print(f"Testing video extraction for: {tweet_url}")
    print(f"Debug directory: {get_debug_directory()}")
    
    # Extract username and tweet ID
    username, tweet_id = extract_tweet_info(tweet_url)
    if not username or not tweet_id:
        print(f"Invalid tweet URL: {tweet_url}")
        return
    
    print(f"Username: {username}")
    print(f"Tweet ID: {tweet_id}")
    
    # Try to extract video
    print("Fetching video URL...")
    video_url = await fetch_video_from_downloader(tweet_url)
    
    if video_url:
        print(f"Successfully found video URL: {video_url}")
    else:
        print("Failed to find video URL")
    
    # Display debug files
    debug_dir = get_debug_directory()
    print(f"\nDebug files in {debug_dir}:")
    files = os.listdir(debug_dir)
    for file in sorted(files):
        file_path = os.path.join(debug_dir, file)
        file_size = os.path.getsize(file_path) / 1024  # Size in KB
        print(f"  - {file} ({file_size:.2f} KB)")
    
    # Show how to find the video recording
    video_files = [f for f in files if f.endswith('.webm')]
    if video_files:
        print("\nTo watch the debug video recording, open the following file:")
        for video in video_files:
            print(f"  {os.path.join(debug_dir, video)}")
    
    # Show how to view HTML content
    html_files = [f for f in files if f.endswith('.txt')]
    if html_files:
        print("\nHTML content was saved and can be viewed in:")
        for html in html_files:
            print(f"  {os.path.join(debug_dir, html)}")
    
    # Show how to view screenshots
    screenshots = [f for f in files if f.endswith('.png')]
    if screenshots:
        print("\nScreenshots were saved and can be viewed:")
        for screenshot in screenshots:
            print(f"  {os.path.join(debug_dir, screenshot)}")

def main():
    """Main function to parse arguments and run test"""
    parser = argparse.ArgumentParser(description='Test video extraction from tweets')
    parser.add_argument('tweet_url', help='Twitter/X tweet URL')
    args = parser.parse_args()
    
    asyncio.run(test_video_extraction(args.tweet_url))

if __name__ == '__main__':
    main() 