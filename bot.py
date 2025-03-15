import os
import re
import json
import time
import signal
import sys
from datetime import datetime
import requests
import telebot

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL = os.environ.get('CHANNEL')  # The channel we're monitoring
# Parse comma-separated list of authorized users
AUTHORIZED_USERS = [username.strip() for username in os.environ.get('AUTHORIZED_USERS', '').split(',') if username.strip()]
MESSAGE_STORAGE_FILE = 'channel_messages.json'  # File to store messages
UPDATE_INTERVAL = 10  # Check every 10 seconds instead of 60
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB in bytes

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")

# Initialize storage file if it doesn't exist
def initialize_storage():
    if not os.path.exists(MESSAGE_STORAGE_FILE):
        with open(MESSAGE_STORAGE_FILE, 'w') as f:
            json.dump([], f)
        print(f"Created message storage file: {MESSAGE_STORAGE_FILE}")

# Save a new message to the storage file
def save_message(message):
    try:
        # Extract only the fields we need
        message_data = {
            'message_id': getattr(message, 'message_id', None),
            'text': getattr(message, 'text', ''),
            'date': getattr(message, 'date', int(time.time())),
            'caption': getattr(message, 'caption', None),  # For media messages with captions
        }
        
        # Add sender info if available (for channel posts, this might be None)
        if hasattr(message, 'from_user') and message.from_user:
            message_data['from'] = {
                'id': message.from_user.id,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name
            }
        
        # Add chat info
        if hasattr(message, 'chat'):
            message_data['chat'] = {
                'id': message.chat.id,
                'type': message.chat.type,
                'title': getattr(message.chat, 'title', None),
                'username': getattr(message.chat, 'username', None)
            }
        
        # Add entities if available (for links, mentions, etc.)
        if hasattr(message, 'entities') and message.entities:
            message_data['entities'] = []
            for entity in message.entities:
                message_data['entities'].append({
                    'type': entity.type,
                    'offset': entity.offset,
                    'length': entity.length,
                    'url': getattr(entity, 'url', None)
                })
        
        # Read existing messages
        with open(MESSAGE_STORAGE_FILE, 'r') as f:
            messages = json.load(f)
        
        # Check if this message is already stored (by message_id)
        if any(msg.get('message_id') == message_data.get('message_id') for msg in messages):
            return  # Message already exists, no need to save
        
        # Add timestamp for when we stored it
        message_data['_stored_at'] = datetime.now().isoformat()
        messages.append(message_data)
        
        # Check if the file would exceed the size limit
        temp_file = f"{MESSAGE_STORAGE_FILE}.temp"
        with open(temp_file, 'w') as f:
            json.dump(messages, f, indent=2)
        
        # Get size of the temp file
        file_size = os.path.getsize(temp_file)
        
        # If too large, remove oldest messages until under limit
        if file_size > MAX_FILE_SIZE_BYTES:
            print(f"Storage file would exceed size limit ({file_size} > {MAX_FILE_SIZE_BYTES})")
            
            # Sort messages by date, oldest first
            messages.sort(key=lambda x: x.get("date", 0))
            
            # Remove oldest messages until we're under the limit
            # Use binary search approach to find how many we need to remove
            start = 0
            end = len(messages) - 1  # Keep at least the newest message
            
            while start < end:
                mid = (start + end) // 2
                # Try with messages[mid:] (keeping newer messages)
                with open(temp_file, 'w') as f:
                    json.dump(messages[mid:], f, indent=2)
                
                if os.path.getsize(temp_file) <= MAX_FILE_SIZE_BYTES:
                    end = mid
                else:
                    start = mid + 1
            
            # Now start contains the index where we should cut
            messages = messages[start:]
            print(f"Removed {start} oldest messages to maintain size limit")
        
        # Write back to file
        with open(MESSAGE_STORAGE_FILE, 'w') as f:
            json.dump(messages, f, indent=2)
        
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        print(f"Saved new message with ID: {message_data.get('message_id')}, "
              f"Storage now contains {len(messages)} messages")
    
    except Exception as e:
        print(f"Error saving message: {e}")
        # Clean up temp file in case of error
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)


# Search for messages in the stored file
def search_stored_messages(query):
    """
    Search for messages containing the query in our stored messages.
    Returns the most recent message containing the query.
    """
    try:
        with open(MESSAGE_STORAGE_FILE, 'r') as f:
            messages = json.load(f)
        
        # Filter messages containing the query
        matching_messages = []
        for msg in messages:
            if "text" in msg and query.lower() in msg["text"].lower():
                matching_messages.append(msg)
        
        # Sort by date, newest first
        if matching_messages:
            # Use message date for sorting
            matching_messages.sort(key=lambda x: x.get("date", 0), reverse=True)
            return matching_messages[0]
        
        return None
    except Exception as e:
        print(f"Error searching stored messages: {e}")
        return None

@bot.message_handler(commands=['status'])
def status_check(message):
    try:
        # Get stats about stored messages
        with open(MESSAGE_STORAGE_FILE, 'r') as f:
            messages = json.load(f)
        
        # Calculate some stats
        message_count = len(messages)
        newest_message = max(messages, key=lambda x: x.get("date", 0)) if messages else None
        oldest_message = min(messages, key=lambda x: x.get("date", 0)) if messages else None
        
        # Format the response
        if message_count > 0:
            newest_date = datetime.fromtimestamp(newest_message.get("date", 0))
            oldest_date = datetime.fromtimestamp(oldest_message.get("date", 0))
            
            response = (
                f"📊 Storage Status:\n"
                f"- Total messages: {message_count}\n"
                f"- Newest message: {newest_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- Oldest message: {oldest_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- Storage file: {MESSAGE_STORAGE_FILE}"
            )
        else:
            response = "No messages stored yet. Waiting for channel updates."
            
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"Error checking status: {str(e)}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(AUTHORIZED_USERS, message.from_user.username)
    # Check if the message is from an authorized user first
    if message.from_user.username not in AUTHORIZED_USERS:
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    
    # Extract the word that comes before '/status/'
    pattern = r'/(\w+)/status/'
    match = re.search(pattern, message.text)
    
    if match:
        extracted_text = match.group(1)
        bot.reply_to(message, f"Searching for '{extracted_text}' in stored channel messages...")
    else:
        # No match, echo as before
        bot.reply_to(message, 'Not a twitter post link')

# Add a handler for channel posts
@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    """Handle posts from channels"""
    # Check if this is from our target channel
    chat = message.chat
    chat_id = chat.id
    chat_username = getattr(chat, 'username', '')
    chat_title = getattr(chat, 'title', '')
    
    # Try to match based on ID, username, or title
    channel_identifier = CHANNEL.lstrip('@') if CHANNEL.startswith('@') else CHANNEL
    
    if (str(chat_id) == channel_identifier or 
        (chat_username and chat_username.lower() == channel_identifier.lower()) or
        (chat_title and chat_title.lower() == channel_identifier.lower())):
        
        # Save this channel message - pass the message object directly
        save_message(message)
        print(f"✅ Saved message {message.message_id} from channel {chat_title}")

# Simplified signal handler - no thread management needed
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