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
import concurrent.futures

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
            
        # Get list of managed tasks for debugging
        managed_tasks = loop.run_until_complete(BrowserSessionManager.list_managed_tasks())
        if managed_tasks:
            print(f"Browser session manager is tracking {len(managed_tasks)} tasks:")
            for i, task in enumerate(managed_tasks):
                print(f"  Task {i+1}: {task['name']} ({task['type']}), age: {task['age_seconds']:.1f}s, done: {task['done']}")
        
        result = True
    except Exception as e:
        print(f"❌ Failed to initialize Twitter browser session: {e}")
        import traceback
        print(traceback.format_exc())
        
        # Explicitly try to clean up any browser sessions that might be left open
        try:
            print("Attempting to clean up any partial browser sessions...")
            loop.run_until_complete(BrowserSessionManager.cancel_all_managed_tasks())
            loop.run_until_complete(BrowserSessionManager.clear_pending_tasks(loop))
            loop.run_until_complete(BrowserSessionManager.close_all_sessions())
        except Exception as cleanup_err:
            print(f"Error during emergency cleanup: {cleanup_err}")
            
        result = False
    finally:
        # Run pending tasks before closing the loop
        try:
            # Get all pending tasks except the current one
            pending = [task for task in asyncio.all_tasks(loop) 
                      if not task.done() and task != asyncio.current_task(loop)]
            
            if pending:
                print(f"Waiting for {len(pending)} pending tasks to complete...")
                
                # DEBUG: Print detailed information about pending tasks
                for i, task in enumerate(pending):
                    task_name = task.get_name() if hasattr(task, 'get_name') else "Unknown"
                    task_info = str(task)
                    print(f"Task {i+1}: {task_name}")
                    print(f"  Details: {task_info}")
                    print(f"  Done: {task.done()}, Cancelled: {task.cancelled()}")
                    
                    # Check if it's in managed tasks
                    managed_tasks = loop.run_until_complete(BrowserSessionManager.list_managed_tasks())
                    matched_tasks = [t for t in managed_tasks if id(task) == t['id']]
                    if matched_tasks:
                        print(f"  Managed task: {matched_tasks[0]['type']}")
                        print(f"  Stack trace:\n{''.join(matched_tasks[0]['stack'])}")
                    
                    # Try to get task stack
                    try:
                        task_stack = task.get_stack() if hasattr(task, 'get_stack') else None
                        if task_stack:
                            stack_trace = ''.join(traceback.format_stack(task_stack[0]))
                            print(f"  Task stack:\n{stack_trace}")
                    except Exception as stack_err:
                        print(f"  Could not get task stack: {stack_err}")
                
                # First try to cancel managed tasks
                print("Cancelling browser managed tasks...")
                cancelled = loop.run_until_complete(BrowserSessionManager.cancel_all_managed_tasks())
                print(f"Cancelled {cancelled} managed tasks")
                
                # Check if any are cleanup tasks from BrowserSessionManager
                browser_cleanup_tasks = [t for t in pending if 
                                       hasattr(t, 'get_name') and 
                                       t.get_name() == "BrowserSessionManager_cleanup"]
                if browser_cleanup_tasks:
                    print(f"Found {len(browser_cleanup_tasks)} browser cleanup tasks - cancelling...")
                    for task in browser_cleanup_tasks:
                        task.cancel()
                
                # Give pending tasks a short time to complete
                wait_done, wait_pending = loop.run_until_complete(
                    asyncio.wait(pending, timeout=5, return_when=asyncio.ALL_COMPLETED)
                )
                
                # If some tasks are still pending, cancel them forcefully
                if wait_pending:
                    print(f"Forcibly cancelling {len(wait_pending)} tasks that didn't complete")
                    for task in wait_pending:
                        task.cancel()
                        
                    # Give them a moment to acknowledge cancellation
                    try:
                        loop.run_until_complete(asyncio.wait(wait_pending, timeout=1))
                    except Exception:
                        pass  # Ignore errors during final cancellation
                        
                    # Check if any tasks are still not done
                    still_running = [t for t in wait_pending if not t.done()]
                    if still_running:
                        print(f"WARNING: {len(still_running)} tasks still running after cancellation")
                        # Print final information about stuck tasks
                        for i, task in enumerate(still_running):
                            task_name = task.get_name() if hasattr(task, 'get_name') else "Unknown"
                            print(f"Stuck task {i+1}: {task_name}")
        except Exception as e:
            print(f"Error during cleanup of pending tasks: {e}")
            import traceback
            print(traceback.format_exc())
        
        # Close the loop only after all tasks have completed or been cancelled
        loop.close()
        
    return result

# Shutdown Twitter browser sessions explicitly
def shutdown_twitter_session():
    """Explicitly close all Twitter browser sessions"""
    print("Closing Twitter browser sessions...")
    
    try:
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_event_loop()
            is_running = loop.is_running()
        except RuntimeError:
            # No event loop in current thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            is_running = False
            
        if is_running:
            # If we're already in a running event loop (like during signal handling while polling),
            # we can't create a new one. Use run_coroutine_threadsafe instead.
            print("Using threadsafe call for cleanup in running event loop")
            future = asyncio.run_coroutine_threadsafe(BrowserSessionManager.close_all_sessions(), loop)
            try:
                # Wait for the future to complete with a timeout
                future.result(timeout=10)
                print("All Twitter sessions closed")
            except concurrent.futures.TimeoutError:
                print("Timeout while closing sessions")
            except Exception as e:
                print(f"Error in threadsafe session closure: {e}")
        else:
            # If no loop is running, we can use the standard approach
            loop.run_until_complete(BrowserSessionManager.close_all_sessions())
            print("All Twitter sessions closed")
            
            # Close the loop if we created it
            if not hasattr(loop, '_is_telebot_loop'):
                loop.close()
    except Exception as e:
        print(f"Error closing Twitter sessions: {e}")
        import traceback
        print(traceback.format_exc())

# Enhanced signal handler that properly closes resources
def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Shutting down gracefully...')
    
    # Mark termination flags
    global _is_shutting_down
    _is_shutting_down = True
    
    # Explicitly close all browser sessions
    shutdown_twitter_session()
    
    # Force exit after a short delay if we're still running
    import threading
    def force_exit():
        print("Forcing exit...")
        import os
        os._exit(0)
    
    # Schedule a force exit after 5 seconds in case normal shutdown fails
    timer = threading.Timer(5.0, force_exit)
    timer.daemon = True
    timer.start()
    
    print("Exiting...")
    sys.exit(0)

# Global termination flag
_is_shutting_down = False

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Initialize the storage
    initialize_storage()
    
    # Create a separate event loop for pre-bot initialization
    cleanup_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(cleanup_loop)
    
    # First, ensure any existing tasks are cleaned up
    try:
        print("Cleaning up any lingering tasks from previous runs...")
        cleanup_loop.run_until_complete(BrowserSessionManager.clear_pending_tasks(cleanup_loop))
        cleanup_loop.run_until_complete(BrowserSessionManager.close_all_sessions())
    except Exception as e:
        print(f"Error during initial cleanup: {e}")
    finally:
        cleanup_loop.close()
    
    # Initialize Twitter session before starting the bot
    twitter_ready = initialize_twitter_session()
    if not twitter_ready:
        print("Warning: Twitter session initialization failed. Will try again when processing tweets.")
    
    try:
        # Create a new event loop for the bot
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        
        # Mark this loop as belonging to telebot (for our own tracking)
        bot_loop._is_telebot_loop = True
        
        # Start the bot with allowed_updates to include channel_post
        print("Bot started. Press Ctrl+C to exit.")
        bot.infinity_polling(timeout=60, long_polling_timeout=30, allowed_updates=['message', 'channel_post'])
    except KeyboardInterrupt:
        # This may still happen if Ctrl+C is pressed during bot initialization
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"Bot error: {e}")
        signal_handler(signal.SIGTERM, None)