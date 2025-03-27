import signal
import sys
import asyncio
import telebot
import argparse
from config import BOT_TOKEN, X_USERNAME, X_PASSWORD
from storage import initialize_storage
from handlers.user_handlers import handle_welcome, handle_status_check, handle_twitter_link
from handlers.channel_handlers import handle_channel_post
from tweet_fetcher.extractors.auth_playwright.browser import BrowserSessionManager

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Twitter to Telegram Bot')
parser.add_argument('--record', action='store_true', help='Enable screen recording for all Playwright actions')
parser.add_argument('--record-quality', choices=['low', 'medium', 'high'], default='medium', 
                    help='Recording quality (low: 480p, medium: 720p, high: 1080p)')
args = parser.parse_args()

# Store recording settings globally
ENABLE_RECORDING = args.record
RECORDING_QUALITY = args.record_quality

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Register command handlers
@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    handle_welcome(bot, message)

@bot.message_handler(commands=['status'])
def status_check(message):
    handle_status_check(bot, message)

# Register general message handler
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    handle_twitter_link(bot, message)

# Add a handler for channel posts
@bot.channel_post_handler(func=lambda message: True)
def channel_post_handler(message):
    handle_channel_post(bot, message)

# Initialize Twitter browser session
def initialize_twitter_session():
    """Initialize Twitter browser session at startup"""
    print("Initializing Twitter browser session...")
    
    # Create a new event loop for initialization
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    session = None
    
    try:
        # Get a browser session - this will authenticate if needed
        session = loop.run_until_complete(BrowserSessionManager.get_browser_session(
            username=X_USERNAME,
            password=X_PASSWORD,
            phone_number=None,  # Will use environment variable if needed
            record_video=ENABLE_RECORDING,  # Use the recording flag
            record_quality=RECORDING_QUALITY  # Pass recording quality
        ))
        
        # Release the session to the pool (don't close it)
        loop.run_until_complete(BrowserSessionManager.release_session(X_USERNAME))
        print("✅ Twitter browser session initialized successfully")
        if ENABLE_RECORDING:
            print("🎥 Screen recording is enabled with", RECORDING_QUALITY, "quality")
        
        result = True
    except Exception as e:
        print(f"❌ Failed to initialize Twitter browser session: {e}")
        import traceback
        print(traceback.format_exc())
        result = False
    finally:
        # Run pending tasks before closing the loop
        try:
            # Get all pending tasks except the current one
            pending = [task for task in asyncio.all_tasks(loop) 
                      if not task.done() and task != asyncio.current_task(loop)]
            
            if pending:
                print(f"Waiting for {len(pending)} pending tasks to complete...")
                # Give pending tasks a chance to complete
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            print(f"Error during cleanup of pending tasks: {e}")
        
        # Close the loop only after all tasks have completed
        loop.close()
        
    return result

# Shutdown Twitter browser sessions explicitly
def shutdown_twitter_session():
    """Explicitly close all Twitter browser sessions"""
    print("Closing Twitter browser sessions...")
    
    # Create a new event loop for shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Close all browser sessions
        loop.run_until_complete(BrowserSessionManager.close_all_sessions())
        print("All Twitter sessions closed")
    except Exception as e:
        print(f"Error closing Twitter sessions: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        try:
            # Run any pending tasks before closing
            pending = [task for task in asyncio.all_tasks(loop)
                      if not task.done() and task != asyncio.current_task(loop)]
            
            if pending:
                print(f"Waiting for {len(pending)} pending tasks to complete...")
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            print(f"Error during cleanup of pending tasks: {e}")
            
        # Close the loop
        loop.close()

# Enhanced signal handler that properly closes resources
def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Shutting down gracefully...')
    # Explicitly close all browser sessions
    shutdown_twitter_session()
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Initialize the storage
    initialize_storage()
    
    # Initialize Twitter session before starting the bot
    twitter_ready = initialize_twitter_session()
    if not twitter_ready:
        print("Warning: Twitter session initialization failed. Will try again when processing tweets.")
    
    try:
        # Start the bot with allowed_updates to include channel_post
        print("Bot started. Press Ctrl+C to exit.")
        bot.infinity_polling(timeout=60, long_polling_timeout=30, allowed_updates=['message', 'channel_post'])
    except KeyboardInterrupt:
        # This may still happen if Ctrl+C is pressed during bot initialization
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"Bot error: {e}")
        signal_handler(signal.SIGTERM, None)