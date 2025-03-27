#!/usr/bin/env python3
"""
Main entry point for the Twitter to Telegram bot.
"""
import sys
import os
import importlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main')

def main():
    """Main function to run the bot application."""
    logger.info("Starting Twitter to Telegram bot...")
    
    try:
        # Import bot module
        bot_module = importlib.import_module('bot')
        
        # Bot.py has its own __main__ block that will run automatically
        logger.info("Bot initialized successfully!")
        return True
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 