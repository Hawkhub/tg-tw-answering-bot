import os
import re
import json
import time
from datetime import datetime
import threading
import requests
import telebot

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL = os.environ.get('CHANNEL')  # The channel we're monitoring
MESSAGE_STORAGE_FILE = 'channel_messages.json'  # File to store messages
UPDATE_INTERVAL = 60  # Check for new messages every 60 seconds
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB in bytes

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize storage file if it doesn't exist
def initialize_storage():
    if not os.path.exists(MESSAGE_STORAGE_FILE):
        with open(MESSAGE_STORAGE_FILE, 'w') as f:
            json.dump([], f)
        print(f"Created message storage file: {MESSAGE_STORAGE_FILE}")

# Save a new message to the storage file
def save_message(message):
    try:
        # Read existing messages
        with open(MESSAGE_STORAGE_FILE, 'r') as f:
            messages = json.load(f)
        
        # Check if this message is already stored (by message_id)
        if any(msg.get('message_id') == message.get('message_id') for msg in messages):
            return  # Message already exists, no need to save
        
        # Add timestamp for when we stored it
        message['_stored_at'] = datetime.now().isoformat()
        messages.append(message)
        
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
            
        print(f"Saved new message with ID: {message.get('message_id')}, "
              f"Storage now contains {len(messages)} messages")
    
    except Exception as e:
        print(f"Error saving message: {e}")
        # Clean up temp file in case of error
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)

# Fetch and store new messages from the channel
def fetch_new_messages():
    # Format channel username
    channel_id = f"@{CHANNEL_USERNAME}" if not CHANNEL_USERNAME.startswith('@') else CHANNEL_USERNAME
    
    try:
        # Get last update_id from our storage to avoid duplicates
        last_update_id = 0
        try:
            with open(MESSAGE_STORAGE_FILE, 'r') as f:
                messages = json.load(f)
                # Find the max update_id if we have it stored
                for msg in messages:
                    if '_update_id' in msg and msg['_update_id'] > last_update_id:
                        last_update_id = msg['_update_id']
        except (json.JSONDecodeError, FileNotFoundError):
            pass  # Use default last_update_id = 0
            
        # Fetch updates from Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"offset": last_update_id + 1 if last_update_id else None}
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if not data.get("ok"):
            print(f"Error from Telegram API: {data.get('description')}")
            return
        
        # Process and store new messages
        for update in data.get("result", []):
            # Look for channel posts from our target channel
            if "channel_post" in update:
                post = update["channel_post"]
                chat = post.get("chat", {})
                
                # Check if this post is from our target channel
                if chat.get("username", "").lower() == CHANNEL_USERNAME.lower().lstrip('@'):
                    # Store update_id to avoid duplicates in future
                    post['_update_id'] = update.get('update_id')
                    save_message(post)
            
            # Also check for forwarded messages in regular chats
            elif "message" in update:
                msg = update["message"]
                # Check if it's a message forwarded from our channel
                forward_from_chat = msg.get("forward_from_chat", {})
                if forward_from_chat.get("username", "").lower() == CHANNEL_USERNAME.lower().lstrip('@'):
                    # Store this forwarded message
                    msg['_update_id'] = update.get('update_id')
                    msg['_forwarded'] = True
                    save_message(msg)
        
        print(f"Message fetch completed at {datetime.now().isoformat()}")
    except Exception as e:
        print(f"Error fetching new messages: {e}")

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

# Background task to fetch messages periodically
def message_fetcher():
    while True:
        try:
            fetch_new_messages()
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            print(f"Error in message fetcher thread: {e}")
            time.sleep(10)  # Shorter wait if there was an error

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")

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
    # Extract the word that comes before '/status/'
    pattern = r'/(\w+)/status/'
    match = re.search(pattern, message.text)
    
    if match:
        extracted_text = match.group(1)
        
        bot.reply_to(message, f"Searching for '{extracted_text}' in stored channel messages...")
        
        try:
            # Search for this text in our stored channel messages
            found_message = search_stored_messages(extracted_text)
            
            if found_message:
                # Format the response
                sender = "Channel Post"  # Channel posts don't have a "from" field like user messages
                if "_forwarded" in found_message:
                    sender = f"Forwarded by {found_message.get('from', {}).get('first_name', 'Unknown')}"
                
                msg_date = datetime.fromtimestamp(found_message.get("date", 0))
                msg_text = found_message.get("text", "No text")
                
                response = (
                    f"Found message with '{extracted_text}':\n"
                    f"Source: {sender}\n"
                    f"Date: {msg_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Message: {msg_text}"
                )
                bot.reply_to(message, response)
            else:
                bot.reply_to(message, f"No messages found containing '{extracted_text}'")
        except Exception as e:
            bot.reply_to(message, f"Error searching messages: {str(e)}")
            print(f"Exception details: {e}")
    else:
        # No match, echo as before
        bot.reply_to(message, message.text)

if __name__ == "__main__":
    # Initialize the storage
    initialize_storage()
    
    # Start the background thread to fetch messages
    fetcher_thread = threading.Thread(target=message_fetcher, daemon=True)
    fetcher_thread.start()
    
    # Start the bot
    print("Bot started. Press Ctrl+C to exit.")
    bot.infinity_polling()