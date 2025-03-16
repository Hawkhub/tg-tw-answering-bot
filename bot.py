import os
import re
import json
import time
import signal
import sys
from datetime import datetime
import requests
import telebot
from bs4 import BeautifulSoup
from config import BOT_TOKEN
from storage import initialize_storage, save_message
from handlers.user_handlers import handle_welcome, handle_status_check, handle_twitter_link
from handlers.channel_handlers import handle_channel_post

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

# Simplified signal handler
def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Shutting down gracefully...')
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Initialize the storage
    initialize_storage()
    
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