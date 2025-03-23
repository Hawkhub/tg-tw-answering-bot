#!/usr/bin/env python3
"""
Simple test script for video downloader
"""

import sys
from tweet_fetcher import test_video_download

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_video_downloader.py <tweet-url>")
        sys.exit(1)
    
    tweet_url = sys.argv[1]
    test_video_download(tweet_url) 