import logging
import os
import json
import time
import asyncio
import random
from datetime import datetime, timedelta

from ...config import PROFILES_DIR, POPULAR_RESOLUTIONS, SCREENSHOTS_DIR

logger = logging.getLogger('tweet_fetcher')

class TwitterAuth:
    """Handle Twitter/X authentication with username/password"""
    
    def __init__(self, username=None, password=None, phone_number=None):
        """
        Initialize Twitter auth manager
        
        Args:
            username (str): Twitter/X username or email
            password (str): Twitter/X password
            phone_number (str): Phone number for verification (with country code)
        """
        self.username = username
        self.password = password
        self.phone_number = phone_number
        
        # If phone number isn't provided, try to get it from environment variable
        if not self.phone_number:
            self.phone_number = os.environ.get('X_PHONE_NUMBER')
        
        self.auth_state = {}
        self.profile_dir = None
        
        # Create a unique profile identifier
        if username:
            # Create a safer version of the username for file paths
            safe_username = username.replace('@', '').replace('.', '_').lower()
            self.profile_dir = os.path.join(PROFILES_DIR, f"auth_{safe_username}")
        else:
            self.profile_dir = os.path.join(PROFILES_DIR, "auth_default")
        
        # Ensure profile directory exists
        os.makedirs(self.profile_dir, exist_ok=True)
        
        # Create screenshots directory for login debugging
        os.makedirs(os.path.join(SCREENSHOTS_DIR, "login"), exist_ok=True)
    
    def get_auth_profile_dir(self):
        """Get path to authenticated browser profile directory"""
        return self.profile_dir
    
    def get_profile_settings(self):
        """Get or create persistent profile settings for consistent browser fingerprinting"""
        settings_path = os.path.join(self.get_auth_profile_dir(), 'profile_settings.json')
        
        if os.path.exists(settings_path):
            # Load existing settings
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    logger.info(f"Loaded persistent profile settings for {os.path.basename(self.profile_dir)}")
                    return settings
            except Exception as e:
                logger.error(f"Failed to load profile settings: {e}")
                # If loading fails, continue to create new settings
        
        # Create new settings if none exist
        logger.info(f"Creating new persistent profile settings for {os.path.basename(self.profile_dir)}")
        settings = {
            'viewport': random.choice(POPULAR_RESOLUTIONS),
            'device_scale_factor': random.choice([1, 1.25, 1.5, 2]),
            'color_scheme': random.choice(["light", "dark"]),
            'locale': random.choice(["en-US", "en-GB", "en-CA", "en-AU"]),
            'timezone_id': random.choice([
                "America/New_York", "Europe/London", "America/Los_Angeles", 
                "Asia/Tokyo", "Europe/Berlin", "Australia/Sydney"
            ]),
            'platform': random.choice(['"Windows"', '"macOS"', '"Linux"']),
            'cpu_count': random.choice([2, 4, 6, 8, 12, 16]),
            'has_touch': random.choice([True, False]),
            'fingerprint_seed': random.randint(1, 1000000)
        }
        
        # Save the settings
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profile settings: {e}")
        
        return settings
    
    async def is_authenticated(self, page):
        """
        Check if the browser is authenticated to Twitter/X
        
        Args:
            page: Playwright page object
            
        Returns:
            bool: True if authenticated, False otherwise
        """
        try:
            # Take a screenshot for debugging
            timestamp = int(time.time())
            screenshot_path = os.path.join(SCREENSHOTS_DIR, "login", f"auth_check_{timestamp}.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Saved authentication check screenshot to {screenshot_path}")
            
            # Try to find elements that indicate we're logged in
            home_link = await page.query_selector('a[data-testid="AppTabBar_Home_Link"]')
            profile_icon = await page.query_selector('div[data-testid="SideNav_AccountSwitcher_Button"]')
            
            # If we found either element, we're logged in
            if home_link or profile_icon:
                logger.info("Browser is authenticated to Twitter/X")
                return True
            
            # Check for login form elements which indicate we're not logged in
            login_form = await page.query_selector('form[data-testid="LoginForm"]')
            login_button = await page.query_selector('a[href="/login"]')
            
            if login_form or login_button:
                logger.info("Browser is not authenticated to Twitter/X")
                return False
                
            # If none of the above, try another approach
            current_url = page.url
            if "/home" in current_url:
                logger.info("Browser appears authenticated (on home page)")
                return True
                
            logger.warning("Unable to determine authentication status definitively")
            return False
            
        except Exception as e:
            logger.error(f"Error checking authentication status: {e}")
            return False
    
    async def take_login_screenshot(self, page, step_name):
        """Take a screenshot during the login process for debugging"""
        timestamp = int(time.time())
        screenshot_path = os.path.join(SCREENSHOTS_DIR, "login", f"login_{step_name}_{timestamp}.png")
        await page.screenshot(path=screenshot_path)
        logger.info(f"Saved {step_name} screenshot to {screenshot_path}")
    
    async def human_type(self, page, selector, text, error_probability=0.03):
        """
        Type text in a human-like way with random delays and occasional errors
        
        Args:
            page: Playwright page object
            selector: CSS selector for the input field
            text: Text to type
            error_probability: Probability of making a typing error (0-1)
        """
        # First click the input field
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Clear any existing text (just in case)
        await page.fill(selector, "")
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        # Get initial typing speed based on text length
        # Longer text = faster typing (humans do this)
        base_delay = 0.1 if len(text) > 20 else 0.15
        
        # Create a typing pattern profile
        # This will make typing speed consistent for this user
        # Some users type faster than others but each user is consistent
        typing_profile = random.uniform(0.7, 1.3)  # Typing speed multiplier
        burst_chance = random.uniform(0.05, 0.2)  # Chance of typing bursts
        pause_chance = random.uniform(0.02, 0.1)  # Chance of pausing
        
        # Calculate actual typing delay for this user
        typing_delay = base_delay / typing_profile
        
        current_text = ""
        i = 0
        
        while i < len(text):
            # Occasional longer pause (like thinking)
            if random.random() < pause_chance:
                await asyncio.sleep(random.uniform(0.5, 1.2))
            
            # Decide if making a typo
            making_error = random.random() < error_probability
            
            if making_error and i < len(text) - 2:  # Only make errors if not near the end
                # Type wrong character
                wrong_char = chr(ord(text[i]) + random.randint(-2, 2))
                current_text += wrong_char
                await page.fill(selector, current_text)
                
                # Brief pause to "notice" the error
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Delete the error
                current_text = current_text[:-1]
                await page.fill(selector, current_text)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Now type correct character
                current_text += text[i]
                await page.fill(selector, current_text)
                i += 1
            else:
                # Type correct character
                current_text += text[i]
                await page.fill(selector, current_text)
                i += 1
            
            # Calculate delay for next character
            if random.random() < burst_chance:
                # Occasionally type a burst of characters quickly
                delay = typing_delay * random.uniform(0.3, 0.5)
            else:
                # Normal typing with slight randomness
                delay = typing_delay * random.uniform(0.8, 1.2)
                
            await asyncio.sleep(delay)
            
        # Natural pause after finishing typing
        await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Sometimes people click somewhere else after typing
        if random.random() < 0.3:
            # Get the bounding box of the input
            box = await page.evaluate(f"""
                (selector) => {{
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    return {{
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    }};
                }}
            """, selector)
            
            if box:
                # Click somewhere outside the input box
                await page.mouse.click(
                    box['x'] + box['width'] + random.randint(10, 30),
                    box['y'] + random.randint(-10, box['height'] + 10)
                )
                await asyncio.sleep(random.uniform(0.2, 0.5))
    
    async def natural_click(self, page, selector, take_screenshot=False, screenshot_name=None):
        """
        Click on an element in a natural human-like way
        
        Args:
            page: Playwright page object
            selector: CSS selector to click
            take_screenshot: Whether to take a screenshot before and after clicking
            screenshot_name: Base name for the screenshot
        
        Returns:
            bool: True if clicked successfully, False otherwise
        """
        try:
            # Wait for the element to be visible
            element = await page.wait_for_selector(selector, state="visible", timeout=5000)
            if not element:
                logger.warning(f"Element not found for clicking: {selector}")
                return False
                
            # Get the bounding box for the element
            box = await element.bounding_box()
            if not box:
                logger.warning(f"Could not get bounding box for element: {selector}")
                return False
                
            # Take screenshot before click if requested
            if take_screenshot and screenshot_name:
                await self.take_login_screenshot(page, f"{screenshot_name}_before_click")
                
            # Move mouse to a random position within the element
            target_x = box['x'] + random.uniform(box['width'] * 0.2, box['width'] * 0.8) 
            target_y = box['y'] + random.uniform(box['height'] * 0.2, box['height'] * 0.8)
            
            # Get current mouse position
            current_position = await page.evaluate("""
                () => { 
                    return {
                        x: window.mousex || window.innerWidth / 2,
                        y: window.mousey || window.innerHeight / 2
                    }
                }
            """)
            
            # Move mouse with a natural curve
            steps = random.randint(5, 10)
            
            # Use a simple quadratic curve for mouse movement
            for i in range(steps + 1):
                t = i / steps
                # Ease in-out interpolation
                progress = t * t * (3.0 - 2.0 * t)  # Smoother quadratic curve
                
                x = current_position['x'] + (target_x - current_position['x']) * progress
                y = current_position['y'] + (target_y - current_position['y']) * progress
                
                # Add a slight noise to the path
                x += random.uniform(-2, 2)
                y += random.uniform(-2, 2)
                
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
                
            # Slight pause before clicking
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Click the element
            await page.mouse.click(target_x, target_y)
            
            # Take screenshot after click if requested
            if take_screenshot and screenshot_name:
                await asyncio.sleep(random.uniform(0.5, 1.0))
                await self.take_login_screenshot(page, f"{screenshot_name}_after_click")
                
            return True
            
        except Exception as e:
            logger.error(f"Error performing natural click on {selector}: {e}")
            return False
    
    async def authenticate(self, page):
        """
        Authenticate to Twitter/X using username and password
        
        Args:
            page: Playwright page object
            
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if not self.username or not self.password:
            logger.error("Username and password are required for authentication")
            return False
        
        # First check if we're already authenticated
        logger.info("Checking if already authenticated")
        is_auth = await self.is_authenticated(page)
        if is_auth:
            logger.info("Already authenticated, no login needed")
            return True
        
        logger.info(f"Starting login process for {self.username}...")
        
        try:
            # Navigate to login page
            logger.info("Navigating to login page")
            await page.goto("https://x.com/login", wait_until="domcontentloaded")
            await self.take_login_screenshot(page, "login_page")
            
            # Wait for login form to appear and initial page interaction
            try:
                logger.info("Waiting for username input field")
                await page.wait_for_selector('input[autocomplete="username"]', timeout=10000)
                # Short wait like a human would
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.warning(f"Username input not found: {e}")
                # Try to find any input on the page
                inputs = await page.query_selector_all('input')
                if not inputs:
                    logger.error("No input fields found on login page")
                    return False
                else:
                    logger.info(f"Found {len(inputs)} input fields, will try to use them")
            
            # Type username with human-like typing
            logger.info(f"Entering username: {self.username}")
            await self.human_type(page, 'input[autocomplete="username"]', self.username)
            
            # Take a screenshot after entering username
            await self.take_login_screenshot(page, "username_entered")
            
            # Find and click the Next button
            next_button_clicked = False
            
            # Try different selectors for the Next button
            logger.info("Looking for Next button")
            next_selectors = [
                'div[role="button"][tabindex="0"]:has-text("Next")',
                'div[data-testid="LoginForm_Forward_Button"]',
                'div[role="button"]:has-text("Next")',
                'button:has-text("Next")'
            ]
            
            for selector in next_selectors:
                logger.info(f"Trying Next button selector: {selector}")
                if await self.natural_click(page, selector, True, "next_button"):
                    next_button_clicked = True
                    logger.info(f"Clicked 'Next' button using selector: {selector}")
                    break
            
            if not next_button_clicked:
                logger.error("Unable to find Next button")
                await self.take_login_screenshot(page, "next_button_not_found")
                
                # Dump the HTML for debugging
                html_content = await page.content()
                debug_path = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "debug")
                os.makedirs(debug_path, exist_ok=True)
                with open(os.path.join(debug_path, f"login_html_{int(time.time())}.html"), "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("Saved login page HTML for debugging")
                
                return False
            
            # Wait for password input with a human-like pause
            logger.info("Waiting for password input field")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await self.take_login_screenshot(page, "password_page")
            
            try:
                await page.wait_for_selector('input[name="password"]', timeout=10000)
                # Short pause before typing password
                await asyncio.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                logger.error(f"Password input not found: {e}")
                await self.take_login_screenshot(page, "password_input_not_found")
                
                # Try to find any password input
                password_inputs = await page.query_selector_all('input[type="password"]')
                if password_inputs:
                    logger.info(f"Found {len(password_inputs)} password inputs with type=password")
                else:
                    all_inputs = await page.query_selector_all('input')
                    logger.info(f"No password inputs found. Total inputs: {len(all_inputs)}")
                    
                    # Dump the HTML for debugging
                    html_content = await page.content()
                    debug_path = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "debug")
                    os.makedirs(debug_path, exist_ok=True)
                    with open(os.path.join(debug_path, f"password_page_html_{int(time.time())}.html"), "w", encoding="utf-8") as f:
                        f.write(html_content)
                    logger.info("Saved password page HTML for debugging")
                    
                return False
                
            # Type password with human-like typing
            # Use lower error probability for password (people are more careful with passwords)
            logger.info("Entering password")
            await self.human_type(page, 'input[name="password"]', self.password, error_probability=0.01)
            
            # Take a screenshot after entering password
            await self.take_login_screenshot(page, "password_entered")
            
            # Find and click the Login button
            login_button_clicked = False
            
            # Try different selectors for the Login button
            logger.info("Looking for Login button")
            login_selectors = [
                'div[data-testid="LoginForm_Login_Button"]',
                'div[role="button"]:has-text("Log in")',
                'button:has-text("Log in")',
                'input[type="submit"]'
            ]
            
            for selector in login_selectors:
                logger.info(f"Trying Login button selector: {selector}")
                if await self.natural_click(page, selector, True, "login_button"):
                    login_button_clicked = True
                    logger.info(f"Clicked 'Log in' button using selector: {selector}")
                    break
            
            if not login_button_clicked:
                logger.error("Unable to find Login button")
                await self.take_login_screenshot(page, "login_button_not_found")
                
                # Dump the HTML for debugging
                html_content = await page.content()
                debug_path = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "debug")
                os.makedirs(debug_path, exist_ok=True)
                with open(os.path.join(debug_path, f"login_button_html_{int(time.time())}.html"), "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("Saved login button page HTML for debugging")
                
                return False
                
            # Check for two-factor authentication challenge
            try:
                # Wait a moment to see if 2FA appears
                logger.info("Checking for two-factor authentication prompt")
                await asyncio.sleep(random.uniform(2.0, 3.0))
                two_factor = await page.query_selector('input[inputmode="numeric"]')
                if two_factor:
                    logger.error("Two-factor authentication detected - not supported")
                    await self.take_login_screenshot(page, "two_factor_auth")
                    return False
            except Exception:
                pass  # Ignore errors checking for 2FA
                
            # Check for phone verification modal
            # This could appear with different text, so we'll check multiple patterns
            # Common text: "Let's add your phone number", "Keep your account safe", "Confirm your phone"
            logger.info("Checking for phone verification prompt")
            
            # Take a screenshot to help with debugging
            await self.take_login_screenshot(page, "after_password")
            
            # Check for phone verification modal by looking for various indicators
            phone_verification_needed = False
            
            # Look for phone input field
            phone_input = await page.query_selector('input[type="tel"], input[aria-label*="Phone"], input[placeholder*="Phone"]')
            
            # Look for text indicators in the page
            verification_texts = [
                'phone number',
                'keep your account safe',
                'add your phone',
                'verify your identity',
                'confirm your phone'
            ]
            
            # Check page content for verification text
            page_content = await page.content()
            page_content_lower = page_content.lower()
            for text in verification_texts:
                if text in page_content_lower:
                    logger.info(f"Phone verification prompt detected: '{text}'")
                    phone_verification_needed = True
                    break
            
            # If we found a phone input or verification text
            if phone_input or phone_verification_needed:
                logger.info("Phone verification required during login")
                
                # Ensure we have a phone number
                if not self.phone_number:
                    logger.error("Phone verification required but X_PHONE_NUMBER not provided")
                    await self.take_login_screenshot(page, "phone_required_no_number")
                    return False
                
                # Take a screenshot of the phone verification screen
                await self.take_login_screenshot(page, "phone_verification")
                
                # Look for the phone number input field - try different selectors
                phone_selectors = [
                    'input[type="tel"]',
                    'input[aria-label*="Phone"]',
                    'input[placeholder*="Phone"]',
                    'input[name*="phone"]'
                ]
                
                phone_input_found = False
                for selector in phone_selectors:
                    logger.info(f"Looking for phone input with selector: {selector}")
                    phone_input = await page.query_selector(selector)
                    if phone_input:
                        logger.info(f"Phone input found with selector: {selector}")
                        # Type phone number with human-like typing
                        await self.human_type(page, selector, self.phone_number, error_probability=0.01)
                        phone_input_found = True
                        break
                
                if not phone_input_found:
                    logger.error("Could not find phone input field")
                    await self.take_login_screenshot(page, "phone_input_not_found")
                    
                    # Save the HTML for debugging
                    debug_path = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "debug")
                    os.makedirs(debug_path, exist_ok=True)
                    with open(os.path.join(debug_path, f"phone_page_html_{int(time.time())}.html"), "w", encoding="utf-8") as f:
                        f.write(page_content)
                    logger.info("Saved phone verification page HTML for debugging")
                    
                    return False
                
                # Take a screenshot after entering phone number
                await self.take_login_screenshot(page, "phone_entered")
                
                # Look for and click the Next/Verify/Continue button
                verification_button_selectors = [
                    'div[role="button"]:has-text("Next")',
                    'div[role="button"]:has-text("Continue")',
                    'div[role="button"]:has-text("Verify")',
                    'div[role="button"]:has-text("Submit")',
                    'button:has-text("Next")',
                    'button:has-text("Continue")',
                    'button:has-text("Verify")',
                    'button:has-text("Submit")'
                ]
                
                button_clicked = False
                for selector in verification_button_selectors:
                    logger.info(f"Looking for verification button with selector: {selector}")
                    if await self.natural_click(page, selector, True, "phone_verification_button"):
                        button_clicked = True
                        logger.info(f"Clicked phone verification button using selector: {selector}")
                        break
                
                if not button_clicked:
                    logger.error("Could not find phone verification button")
                    await self.take_login_screenshot(page, "phone_button_not_found")
                    return False
                
                # Wait for processing
                logger.info("Waiting for phone verification processing")
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await self.take_login_screenshot(page, "after_phone_verification")
                
                # Check for SMS verification code input
                # If Twitter sends a verification code to the phone
                sms_code_input = await page.query_selector('input[inputmode="numeric"], input[placeholder*="code"], input[aria-label*="code"]')
                if sms_code_input:
                    logger.error("SMS verification code required - not supported")
                    await self.take_login_screenshot(page, "sms_code_required")
                    return False
            
            # Wait for login to complete with a reasonable timeout
            logger.info("Waiting for login to complete")
            await asyncio.sleep(random.uniform(3.0, 5.0))
            await self.take_login_screenshot(page, "after_login")
            
            # Verify that we're logged in
            logger.info("Verifying login status")
            is_auth = await self.is_authenticated(page)
            if is_auth:
                logger.info("Successfully logged in to Twitter/X")
                # Save login success state to the profile directory
                self.save_auth_state(True)
                return True
            else:
                logger.error("Login attempt failed - still not authenticated")
                await self.take_login_screenshot(page, "login_failed")
                
                # Take additional debugging steps
                logger.info("Checking for error messages")
                error_messages = await page.query_selector_all('div[role="alert"], .error-message, [data-testid="error"]')
                if error_messages:
                    for error in error_messages:
                        error_text = await error.inner_text()
                        logger.error(f"Login error message found: {error_text}")
                
                # Dump the final HTML for debugging
                html_content = await page.content()
                debug_path = os.path.join(os.path.dirname(SCREENSHOTS_DIR), "debug")
                os.makedirs(debug_path, exist_ok=True)
                with open(os.path.join(debug_path, f"login_failed_html_{int(time.time())}.html"), "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("Saved failed login page HTML for debugging")
                
                return False
                
        except Exception as e:
            logger.error(f"Error during login process: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self.take_login_screenshot(page, "login_error")
            return False
    
    def save_auth_state(self, is_authenticated):
        """Save authentication state to profile directory"""
        state_file = os.path.join(self.get_auth_profile_dir(), "auth_state.json")
        try:
            state = {
                "authenticated": is_authenticated,
                "timestamp": int(time.time()),
                "username": self.username
            }
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save auth state: {e}")
    
    def get_auth_state(self):
        """Get saved authentication state from profile directory"""
        state_file = os.path.join(self.get_auth_profile_dir(), "auth_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load auth state: {e}")
        return {"authenticated": False, "timestamp": 0} 