import os
import random
import logging

# Configure logging
logger = logging.getLogger('tweet_fetcher')

# URL pattern for matching Twitter/X links
TWEET_URL_PATTERN = r'https?://(?:www\.)?(twitter|x)\.com/(\w+)/status/(\d+)'

# Directories
TEMP_DIR = os.path.join(os.getcwd(), ".temp")
PROFILES_DIR = os.path.join(TEMP_DIR, "profiles")
SCREENSHOTS_DIR = os.path.join(TEMP_DIR, "screenshots")
HTML_DIR = os.path.join(TEMP_DIR, "html")
MEDIA_DIR = os.path.join(TEMP_DIR, "media")

# All temp directories
TEMP_DIRS = [
    TEMP_DIR,
    PROFILES_DIR,
    SCREENSHOTS_DIR,
    HTML_DIR,
    MEDIA_DIR
]

# Timeouts
DEFAULT_TIMEOUT = 60000  # 60 seconds

# Fixed user agent for authentication (do not randomize this one)
AUTH_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"

# User agents (for non-authenticated approaches)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15"
]

# Common screen resolutions
POPULAR_RESOLUTIONS = [
    {"width": 1920, "height": 1080},  # FHD
    {"width": 1366, "height": 768},   # Common laptop
    {"width": 1536, "height": 864},   # Common on modern laptops
    {"width": 1440, "height": 900},   # MacBook
    {"width": 2560, "height": 1440},  # 2K
    {"width": 1680, "height": 1050},  # Common desktop
]

# Browser launch arguments for enabling all features needed for X anti-bot measures
BROWSER_ARGS = [
    # Disable automation flags
    '--disable-blink-features=AutomationControlled',
    
    # Enable all possible features that a real browser would have
    '--enable-features=NetworkService,NetworkServiceInProcess2',
    '--enable-javascript',
    '--javascript-harmony',
    '--enable-webgl',
    '--enable-webgl2-compute-context',
    '--use-gl=angle', 
    '--use-angle=default',
    
    # Critical for X: WebAssembly support
    '--enable-webassembly',
    '--enable-wasm-baseline',
    '--enable-wasm-branch-hinting',
    '--enable-wasm-dynamic-tiering',
    '--enable-wasm-garbage-collection',
    '--enable-wasm-lazy-compilation',
    '--enable-wasm-relaxed-simd',
    '--enable-wasm-simd',
    '--enable-wasm-tiering',
    '--enable-wasm-threads',
    
    # Hardware acceleration and GPU features
    '--enable-gpu-rasterization',
    '--enable-zero-copy',
    '--enable-accelerated-2d-canvas',
    '--enable-accelerated-video-decode',
    '--enable-accelerated-video-encode',
    '--canvas-oop-rasterization',
    
    # Other browser capabilities
    '--enable-encrypted-media',
    '--enable-media-capabilities',
    '--enable-media-session',
    '--enable-picture-in-picture',
    '--enable-usermedia-screen-capturing',
    
    # Permissions
    '--autoplay-policy=no-user-gesture-required',
    
    # System features
    '--enable-audio-service-sandbox',
    '--enable-speech-service',
    
    # Flags that make the browser more stable
    '--disable-dev-shm-usage',
    '--disable-popup-blocking',
    '--no-sandbox',
    '--no-zygote',
    
    # Performance optimizations
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-background-timer-throttling',
    '--disable-ipc-flooding-protection',
    
    # Required for some OAuth flows
    '--disable-web-security',
    '--allow-running-insecure-content',
]

# Selectors for tweet content
TWEET_TEXT_SELECTORS = [
    'article div[data-testid="tweetText"]',
    'div[data-testid="tweet"] div[data-testid="tweetText"]',
    'div[data-testid="tweet"] div.css-901oao'
]

IMAGE_SELECTORS = [
    'article img[src*="media"]',
    'div[data-testid="tweetPhoto"] img',
    'a[href*="/photo/"] img'
]

VIDEO_SELECTORS = [
    'video[preload="auto"]',
    'div[data-testid="videoPlayer"] video',
    'div[data-testid="videoComponent"] video'
] 