import logging
import os
import random
import time
import asyncio
from datetime import datetime
from ..playwright.browser import create_browser_context as create_standard_browser
from .auth import TwitterAuth
from ...config import BROWSER_ARGS, POPULAR_RESOLUTIONS, AUTH_USER_AGENT, SCREENSHOTS_DIR

logger = logging.getLogger('tweet_fetcher')

# Create video recordings directory
VIDEO_DIR = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

# Global browser session manager
class BrowserSessionManager:
    """Manages persistent browser sessions across multiple tweet extractions"""
    
    # Class variables to hold the shared browser resources
    _instance = None
    _lock = asyncio.Lock()
    _active_sessions = {}  # Maps username to (playwright, context, auth_manager, last_used_time, in_use)
    _session_timeout = 1800  # 30 minutes in seconds - session expires after this time of inactivity
    _cleanup_interval = 3600  # 1 hour in seconds - how often to check for expired sessions
    _storage_save_interval = 300  # 5 minutes in seconds - how often to save storage state
    _last_cleanup = 0
    _last_storage_save = {}  # Maps username to last storage save time
    _storage_size_check_interval = 86400  # 24 hours in seconds - how often to check storage size
    _storage_size_limit = 10 * 1024 * 1024 * 1024  # 10GB in bytes
    _last_storage_size_check = {}  # Maps username to last storage size check time
    
    @classmethod
    async def get_instance(cls):
        """Get the singleton instance of the session manager"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    # Start background cleanup task
                    asyncio.create_task(cls._instance._cleanup_loop())
        return cls._instance
    
    @classmethod
    async def get_browser_session(cls, username=None, password=None, phone_number=None, record_video=False):
        """
        Get an authenticated browser session for a specific user
        
        Args:
            username: Twitter/X username
            password: Twitter/X password
            phone_number: Phone number for verification (with country code)
            record_video: Whether to record video of the login process
            
        Returns:
            tuple: (playwright, context, auth_manager)
        """
        manager = await cls.get_instance()
        return await manager._get_or_create_session(username, password, phone_number, record_video)
    
    @classmethod
    async def release_session(cls, username=None):
        """
        Mark a session as no longer in use (but don't close it)
        
        Args:
            username: Twitter/X username
        """
        session_key = username or "default"
        if session_key in cls._active_sessions:
            playwright, context, auth_manager, last_used, in_use = cls._active_sessions[session_key]
            cls._active_sessions[session_key] = (playwright, context, auth_manager, time.time(), False)
            
            # Save storage state when releasing the session
            await cls._save_session_storage(session_key)
            logger.info(f"Released browser session for {username or 'default user'}")
    
    @classmethod
    async def _save_session_storage(cls, session_key):
        """Save storage state for a specific session if needed"""
        current_time = time.time()
        last_save_time = cls._last_storage_save.get(session_key, 0)
        
        # Only save if it's been long enough since the last save
        if current_time - last_save_time > cls._storage_save_interval:
            if session_key in cls._active_sessions:
                _, context, auth_manager, _, _ = cls._active_sessions[session_key]
                try:
                    # Periodically check storage size
                    last_size_check = cls._last_storage_size_check.get(session_key, 0)
                    if current_time - last_size_check > cls._storage_size_check_interval:
                        await cls._check_storage_size(session_key, context, auth_manager)
                        cls._last_storage_size_check[session_key] = current_time
                    
                    await save_storage_state(context, auth_manager)
                    cls._last_storage_save[session_key] = current_time
                    logger.info(f"Saved storage state for {session_key}")
                except Exception as e:
                    logger.error(f"Error saving storage state for {session_key}: {e}")
    
    @classmethod
    async def _check_storage_size(cls, session_key, context, auth_manager):
        """Check and manage storage size for a browser session"""
        try:
            # Get profile directory
            profile_dir = auth_manager.get_auth_profile_dir()
            
            # Check storage size on disk
            storage_size = 0
            for root, dirs, files in os.walk(profile_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        storage_size += os.path.getsize(file_path)
            
            # Log current storage size
            storage_mb = storage_size / (1024 * 1024)
            logger.info(f"Current storage size for {session_key}: {storage_mb:.2f}MB")
            
            # If approaching limit (90%), trigger cleaning
            if storage_size > cls._storage_size_limit * 0.9:
                logger.warning(f"Storage for {session_key} approaching limit ({storage_mb:.2f}MB / 10GB), cleaning up...")
                
                # Create a page and run cleanup script
                page = await context.new_page()
                await page.goto("https://x.com", timeout=10000, wait_until="domcontentloaded")
                
                # Run JavaScript cleanup
                await page.evaluate("window._twitterStorageCleanup && window._twitterStorageCleanup()")
                
                # Clean browser cache files
                await page.evaluate("""
                    if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
                        navigator.serviceWorker.getRegistrations().then(registrations => {
                            for (let registration of registrations) {
                                registration.unregister();
                                console.log('Unregistered service worker');
                            }
                        });
                    }
                    
                    if (window.caches) {
                        caches.keys().then(cacheNames => {
                            for (let cacheName of cacheNames) {
                                if (cacheName.includes('twitter') || cacheName.includes('x.com')) {
                                    caches.delete(cacheName);
                                    console.log('Deleted cache:', cacheName);
                                }
                            }
                        });
                    }
                """)
                
                await page.close()
                
                # If we're still over 95% of limit, delete oldest cache files directly
                if storage_size > cls._storage_size_limit * 0.95:
                    await cls._clean_storage_files(profile_dir)
                
        except Exception as e:
            logger.error(f"Error checking storage size for {session_key}: {e}")
    
    @classmethod
    async def _clean_storage_files(cls, profile_dir):
        """Clean up oldest storage files to free space"""
        try:
            # Cache directories to check
            cache_dirs = [
                os.path.join(profile_dir, "Cache"),
                os.path.join(profile_dir, "Code Cache"),
                os.path.join(profile_dir, "GPUCache"),
                os.path.join(profile_dir, "Service Worker", "CacheStorage"),
                os.path.join(profile_dir, "IndexedDB")
            ]
            
            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
                    logger.info(f"Cleaning cache directory: {cache_dir}")
                    
                    # Get all files with their modification times
                    files = []
                    for root, _, filenames in os.walk(cache_dir):
                        for filename in filenames:
                            file_path = os.path.join(root, filename)
                            try:
                                if os.path.isfile(file_path):
                                    mtime = os.path.getmtime(file_path)
                                    size = os.path.getsize(file_path)
                                    files.append((file_path, mtime, size))
                            except (PermissionError, FileNotFoundError):
                                # Skip files we can't access
                                pass
                    
                    # Sort by modification time (oldest first)
                    files.sort(key=lambda x: x[1])
                    
                    # Delete oldest files up to 20% of the cache
                    if files:
                        total_size = sum(size for _, _, size in files)
                        delete_target = total_size * 0.2  # Delete 20% of the cache
                        
                        deleted_size = 0
                        deleted_count = 0
                        
                        for file_path, _, size in files:
                            try:
                                os.remove(file_path)
                                deleted_size += size
                                deleted_count += 1
                                
                                # Stop if we've deleted enough
                                if deleted_size >= delete_target:
                                    break
                            except (PermissionError, FileNotFoundError):
                                # Skip files we can't delete
                                pass
                        
                        logger.info(f"Deleted {deleted_count} cache files totaling {deleted_size / (1024 * 1024):.2f}MB")
                        
        except Exception as e:
            logger.error(f"Error cleaning storage files: {e}")
    
    @classmethod
    async def close_all_sessions(cls):
        """Close all active browser sessions"""
        for session_key, (playwright, context, auth_manager, _, _) in cls._active_sessions.items():
            try:
                # Save storage state before closing
                await save_storage_state(context, auth_manager)
                await playwright.stop()
                logger.info(f"Closed browser session for {session_key}")
            except Exception as e:
                logger.error(f"Error closing browser session for {session_key}: {e}")
        
        cls._active_sessions = {}
        cls._last_storage_save = {}
    
    async def _get_or_create_session(self, username=None, password=None, phone_number=None, record_video=False):
        """Get existing session or create a new one"""
        session_key = username or "default"
        current_time = time.time()
        
        # First check if we need to run cleanup
        if current_time - self.__class__._last_cleanup > self.__class__._cleanup_interval:
            await self._cleanup_expired_sessions()
            self.__class__._last_cleanup = current_time
        
        # Check if we have an active session for this user
        if session_key in self.__class__._active_sessions:
            playwright, context, auth_manager, last_used, in_use = self.__class__._active_sessions[session_key]
            
            # Update the last used time and mark as in-use
            self.__class__._active_sessions[session_key] = (playwright, context, auth_manager, current_time, True)
            
            # Check if session is still valid
            if current_time - last_used < self.__class__._session_timeout:
                logger.info(f"Reusing existing browser session for {username or 'default user'}")
                
                # Create a test page to check if the browser is still responsive
                try:
                    test_page = await context.new_page()
                    await test_page.close()
                    
                    # If it's been a while since our last storage save, do it now
                    if session_key not in self.__class__._last_storage_save or \
                       current_time - self.__class__._last_storage_save.get(session_key, 0) > self.__class__._storage_save_interval:
                        await self.__class__._save_session_storage(session_key)
                    
                    # Attempt to restore any additional storage state
                    await restore_storage_state(context, auth_manager)
                    
                    return playwright, context, auth_manager
                except Exception as e:
                    logger.warning(f"Existing session is not responsive: {e}. Creating new session.")
                    # Session is not responsive, close it and create a new one
                    try:
                        await playwright.stop()
                    except Exception as close_err:
                        logger.warning(f"Error closing browser: {close_err}")
            else:
                logger.info(f"Session for {username or 'default user'} expired, creating new one")
                try:
                    # Save storage before closing
                    await save_storage_state(context, auth_manager)
                    await playwright.stop()
                except Exception as close_err:
                    logger.warning(f"Error closing browser: {close_err}")
        
        # Create a new session with proper error handling
        max_retries = 2
        for retry in range(max_retries):
            try:
                playwright, context, auth_manager = await create_authenticated_browser(
                    username, 
                    password,
                    phone_number,
                    record_video=record_video
                )
                self.__class__._active_sessions[session_key] = (playwright, context, auth_manager, current_time, True)
                self.__class__._last_storage_save[session_key] = current_time  # Consider initial creation as a storage save
                logger.info(f"Created new browser session for {username or 'default user'}")
                return playwright, context, auth_manager
            except Exception as e:
                logger.error(f"Failed to create browser session (attempt {retry+1}/{max_retries}): {e}")
                if retry == max_retries - 1:
                    # Last retry failed, falling back to non-authenticated approach
                    logger.error("All attempts to create browser session failed")
                    # Fall back to non-authenticated browser
                    try:
                        from ..playwright.browser import create_browser_context
                        logger.info("Creating fallback unauthenticated browser instance")
                        playwright, fallback_context = await create_browser_context()
                        logger.info("Created fallback browser instance")
                        # We can't properly use the BrowserSessionManager with this fallback
                        # Just return it directly and let the caller handle authentication separately
                        return playwright, fallback_context, auth_manager
                    except Exception as fallback_err:
                        logger.error(f"Failed to create fallback browser: {fallback_err}")
                        raise RuntimeError(f"Failed to create any browser: {e}, fallback error: {fallback_err}")
        
        # This should never be reached due to the raise above
        raise RuntimeError("Failed to create browser session")
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired browser sessions"""
        current_time = time.time()
        expired_users = []
        
        for session_key, (playwright, context, auth_manager, last_used, in_use) in self.__class__._active_sessions.items():
            # Don't close sessions that are in use
            if in_use:
                continue
                
            # Close sessions that haven't been used for a while
            if current_time - last_used > self.__class__._session_timeout:
                try:
                    # Save storage state before closing
                    await save_storage_state(context, auth_manager)
                    await playwright.stop()
                    expired_users.append(session_key)
                    logger.info(f"Closed expired browser session for {session_key}")
                except Exception as e:
                    logger.error(f"Error closing expired browser session for {session_key}: {e}")
                    expired_users.append(session_key)
        
        # Remove expired sessions from tracking
        for session_key in expired_users:
            del self.__class__._active_sessions[session_key]
            if session_key in self.__class__._last_storage_save:
                del self.__class__._last_storage_save[session_key]
    
    async def _cleanup_loop(self):
        """Background task to periodically clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(self.__class__._cleanup_interval)
                await self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}")
                # Continue running even if there's an error

async def create_authenticated_browser(username=None, password=None, phone_number=None, record_video=False):
    """
    Create an authenticated browser session for Twitter/X with advanced anti-detection
    
    Args:
        username: Twitter username or email
        password: Twitter password
        phone_number: Phone number for verification (with country code)
        record_video: Whether to record video of the login process
        
    Returns:
        tuple: (playwright instance, browser_context, auth_manager)
    """
    # Create auth manager with user credentials
    auth_manager = TwitterAuth(username, password, phone_number)
    
    # Get auth profile directory (persistent between sessions)
    user_data_dir = auth_manager.get_auth_profile_dir()
    
    # Get persistent profile settings for consistent browser fingerprinting
    profile_settings = auth_manager.get_profile_settings()
    
    # Use persistent settings instead of random values
    viewport = profile_settings['viewport']
    user_agent = AUTH_USER_AGENT  # Use fixed user agent for authentication
    device_scale_factor = profile_settings['device_scale_factor'] 
    color_scheme = profile_settings['color_scheme']
    locale = profile_settings['locale']
    timezone_id = profile_settings['timezone_id']
    has_touch = profile_settings['has_touch']
    fingerprint_seed = profile_settings['fingerprint_seed']
    cpu_count = profile_settings['cpu_count']
    platform = profile_settings['platform']
    
    # Log the profile settings being used
    logger.info(f"Using persistent profile settings: {viewport['width']}x{viewport['height']}, {locale}, {timezone_id}")
    
    # Create advanced browser with enhanced capabilities and anti-detection
    from playwright.async_api import async_playwright
    
    playwright = None
    context = None
    
    try:
        playwright = await async_playwright().start()
        browser_type = playwright.chromium
        
        # Enhanced browser fingerprint randomization
        # Use the persistent fingerprint seed for consistent fingerprinting
        random.seed(fingerprint_seed)
        
        # Set up video recording path if enabled
        recording_options = {}
        video_path = None
        if record_video:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_id = username or "default"
            safe_user_id = ''.join(c if c.isalnum() else '_' for c in user_id)
            video_path = os.path.join(VIDEO_DIR, f"login_{safe_user_id}_{timestamp}.webm")
            
            # Configure recording options - make compatible with older Playwright versions
            # In older versions, record_video_dir is used instead of record_video.dir
            recording_options = {
                "record_video_dir": os.path.dirname(video_path),
                "record_video_size": {"width": viewport["width"], "height": viewport["height"]}
            }
            logger.info(f"Recording login process to: {video_path}")
        
        # Launch browser with full capabilities - essential for X's anti-bot measures
        context = await browser_type.launch_persistent_context(
            user_data_dir,
            headless=True,
            viewport=viewport,
            user_agent=user_agent,
            locale=locale,
            timezone_id=timezone_id,
            color_scheme=color_scheme,
            device_scale_factor=device_scale_factor,
            bypass_csp=True,  # Allow scripts to execute
            java_script_enabled=True,
            has_touch=has_touch,
            is_mobile=False,
            ignore_https_errors=True,
            # Note: persistent_storage_path is implied by user_data_dir in Playwright
            **recording_options,  # Add video recording if enabled
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
                # Add realistic headers that browsers typically send
                "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": platform,
                "Upgrade-Insecure-Requests": "1"
            },
            args=BROWSER_ARGS + [
                # Additional anti-fingerprinting arguments
                '--disable-features=IsolateOrigins',
                '--disable-site-isolation-trials',
                '--disable-web-security',
                f'--window-size={viewport["width"]},{viewport["height"]}',
                # Use consistent CPU count for hardware concurrency
                f'--js-flags=--cpu-count={cpu_count}',
                # Use consistent user ID based on fingerprint seed
                f'--guest-user-id={fingerprint_seed % 10000}',
                # Additional args for storage persistence
                '--enable-features=PersistentOriginTrials',
                '--enable-local-storage',
                # Set the storage quota to 10GB (10 * 1024 * 1024 * 1024 = 10,737,418,240 bytes)
                '--quota-for-storage-per-host=10737418240',
                # Additional storage quota parameters
                '--per-origin-storage-quota=10737418240',
                '--unlimited-storage',
                '--enable-features=PrivacySandboxSettings3',
                # Enable necessary storage
                '--enable-features=StorageAccessAPI',
                '--enable-features=CookieStoreAccess',
                '--enable-features=PrivateStateTokens',
                '--enable-features=TrustTokens',
                # Ensure localStorage is available and writable
                '--disable-features=BlockThirdPartyCookies',
            ]
        )
        
        # Reset the random seed to avoid affecting other randomization
        random.seed()
        
        # Get fingerprinting script
        browser_fingerprint_script = """// ... fingerprinting script ... """
        
        # Add fingerprinting script
        await context.add_init_script(browser_fingerprint_script)
        
        # Grant permissions
        await context.grant_permissions(['notifications'])
        
        # Create a page for authentication
        page = await context.new_page()
        
        # Initialize mouse tracking
        await page.evaluate("""
            window.mousex = 0;
            window.mousey = 0;
            document.addEventListener('mousemove', function(e) {
                window.mousex = e.clientX;
                window.mousey = e.clientY;
            });
        """)
        
        # Try to authenticate if username and password are provided
        if username and password:
            # Take a screenshot of the initial state
            screenshot_path = os.path.join(SCREENSHOTS_DIR, "login", f"initial_state_{int(time.time())}.png")
            await page.screenshot(path=screenshot_path)
            
            # First check if we're already authenticated from a previous session
            is_auth = await auth_manager.is_authenticated(page)
            
            # Only try to authenticate if not already authenticated
            if not is_auth:
                logger.info("Attempting to authenticate with username and password")
                auth_success = await auth_manager.authenticate(page)
                
                if auth_success:
                    # Explicitly save storage state to ensure it's persisted
                    await save_storage_state(context, auth_manager)
            else:
                logger.info("Using existing authenticated session")
            
            # Navigate to Twitter/X home page to ensure we're logged in
            await page.goto("https://x.com/home", timeout=30000, wait_until="domcontentloaded")
            
            # Take a screenshot of the final state after authentication
            screenshot_path = os.path.join(SCREENSHOTS_DIR, "login", f"final_state_{int(time.time())}.png")
            await page.screenshot(path=screenshot_path)
            
            # Close the page used for login
            await page.close()
            
            # If video recording was enabled, save the video with a meaningful name
            if record_video and video_path:
                # Get the actual video file (Playwright saves with a random name)
                try:
                    # Older Playwright versions might have different video access methods
                    video = None
                    if hasattr(page, 'video'):
                        video = page.video
                    
                    if video:
                        # Wait for the recording to finish
                        try:
                            # Different ways to access the video path depending on version
                            recorded_video_path = None
                            if hasattr(video, 'path'):
                                recorded_video_path = await video.path()
                            elif hasattr(page, 'video_path'):
                                recorded_video_path = await page.video_path()
                            else:
                                # Fallback for older versions - try to find latest video in directory
                                video_dir = os.path.dirname(video_path)
                                if os.path.exists(video_dir):
                                    video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith('.webm')]
                                    if video_files:
                                        # Get most recent video file
                                        recorded_video_path = max(video_files, key=os.path.getmtime)
                            
                            # Rename to our desired path
                            if recorded_video_path and os.path.exists(recorded_video_path):
                                # Make sure target directory exists
                                os.makedirs(os.path.dirname(video_path), exist_ok=True)
                                # Rename file if it doesn't already exist at target path
                                if not os.path.exists(video_path):
                                    os.rename(recorded_video_path, video_path)
                                    logger.info(f"Login video saved to: {video_path}")
                                else:
                                    logger.warning(f"Target video file already exists: {video_path}")
                            else:
                                logger.warning("Could not find recorded video file")
                        except Exception as e:
                            logger.error(f"Error saving video recording: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                except Exception as e:
                    logger.error(f"Error accessing video: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        else:
            logger.warning("No username/password provided, will try to use existing session if available")
            # Close the page and return the context
            await page.close()
        
        # Return the browser context and auth manager
        return playwright, context, auth_manager
        
    except Exception as e:
        # Make sure to clean up on error
        if playwright:
            await playwright.stop()
        logger.error(f"Failed to create authenticated browser: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Re-raise with a clear error message
        raise RuntimeError(f"Failed to create authenticated browser: {e}")

async def save_storage_state(context, auth_manager):
    """
    Explicitly save the browser's storage state to ensure persistence
    
    Args:
        context: Playwright browser context
        auth_manager: TwitterAuth instance
    """
    try:
        # Get storage state path
        storage_state_path = os.path.join(auth_manager.get_auth_profile_dir(), "storage_state.json")
        
        # Save the storage state (cookies, localStorage, sessionStorage)
        await context.storage_state(path=storage_state_path)
        
        # Save a timestamp to track when the storage state was last saved
        auth_manager.save_auth_state(True)
        
        logger.info(f"Saved browser storage state for {auth_manager.username or 'default user'}")
        
        # Create a page to explicitly persist localStorage and sessionStorage
        page = await context.new_page()
        await page.goto("https://x.com/home", timeout=10000, wait_until="domcontentloaded")
        
        # Extract and save localStorage and sessionStorage contents
        storage_data = await page.evaluate("""
            () => {
                const data = {
                    localStorage: {},
                    sessionStorage: {}
                };
                
                // Capture localStorage
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    data.localStorage[key] = localStorage.getItem(key);
                }
                
                // Capture sessionStorage
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    data.sessionStorage[key] = sessionStorage.getItem(key);
                }
                
                return data;
            }
        """)
        
        # Save storage data to a file
        storage_data_path = os.path.join(auth_manager.get_auth_profile_dir(), "extra_storage.json")
        import json
        with open(storage_data_path, 'w') as f:
            json.dump(storage_data, f)
        
        await page.close()
        
    except Exception as e:
        logger.error(f"Error saving storage state: {e}")

async def restore_storage_state(context, auth_manager):
    """
    Explicitly restore storage state from saved files
    
    Args:
        context: Playwright browser context
        auth_manager: TwitterAuth instance
    """
    try:
        # Check for extra storage data
        extra_storage_path = os.path.join(auth_manager.get_auth_profile_dir(), "extra_storage.json")
        if os.path.exists(extra_storage_path):
            # Create a page to restore the storage
            page = await context.new_page()
            await page.goto("https://x.com", timeout=10000, wait_until="domcontentloaded")
            
            # Load the storage data
            import json
            with open(extra_storage_path, 'r') as f:
                storage_data = json.load(f)
            
            # Restore localStorage and sessionStorage
            await page.evaluate("""
                (data) => {
                    // Restore localStorage
                    for (const key in data.localStorage) {
                        try {
                            localStorage.setItem(key, data.localStorage[key]);
                        } catch (e) {
                            console.error(`Error restoring localStorage key ${key}:`, e);
                        }
                    }
                    
                    // Restore sessionStorage
                    for (const key in data.sessionStorage) {
                        try {
                            sessionStorage.setItem(key, data.sessionStorage[key]);
                        } catch (e) {
                            console.error(`Error restoring sessionStorage key ${key}:`, e);
                        }
                    }
                    
                    return true;
                }
            """, storage_data)
            
            await page.close()
            logger.info(f"Restored extra storage state for {auth_manager.username or 'default user'}")
        
    except Exception as e:
        logger.error(f"Error restoring storage state: {e}") 