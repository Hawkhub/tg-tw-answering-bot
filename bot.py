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
    # Check if the message is from an authorized user first
    if message.from_user.username not in AUTHORIZED_USERS:
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    
    # Extract the word that comes before '/status/'
    pattern = r'/(\w+)/status/'
    match = re.search(pattern, message.text)
    
    if match:
        twitter_username = match.group(1)
        bot.reply_to(message, f"Searching for '{twitter_username}' in channel history...")
        
        # First search in our JSON storage (recent messages)
        json_result = search_stored_messages(twitter_username)
        
        # Only search in HTML files if nothing found in JSON
        html_results = []
        channel_id = None
        if not json_result:
            bot.reply_to(message, "Not found in recent messages. Searching in older exported history...")
            html_results = search_exported_html(twitter_username)
            
            # For HTML results, we need to determine the channel ID
            if html_results:
                # Use the configured channel ID since we're searching that channel's history
                channel_id = CHANNEL
                # If channel starts with @, we need to get its ID
                if channel_id.startswith('@'):
                    try:
                        channel_info = bot.get_chat(channel_id)
                        channel_id = channel_info.id
                    except Exception as e:
                        print(f"Error getting channel ID: {e}")
                        bot.reply_to(message, "Found results but couldn't determine channel ID to reply.")
                        return
        
        if json_result or html_results:
            # Format the response with search results
            response = f"✅ Found mentions of '{twitter_username}':\n\n"
            
            # Variable to store the message ID we'll reply to
            reply_message_id = None
            
            # Add JSON result if found (prioritize this as it's most recent)
            if json_result:
                response += f"📩 Recent message:\n"
                if 'text' in json_result:
                    response += f"{json_result['text'][:200]}...\n\n"
                
                # Get message ID and chat ID for replying
                reply_message_id = json_result.get('message_id')
                if 'chat' in json_result:
                    channel_id = json_result['chat'].get('id')
            
            # Add HTML results (up to 3) only if we didn't find a JSON result
            elif html_results:
                response += f"📚 From history ({len(html_results)} found):\n"
                for idx, result in enumerate(html_results[:3]):
                    response += f"{idx+1}. {result['text'][:100]}...\n"
                
                if len(html_results) > 3:
                    response += f"...and {len(html_results) - 3} more results\n"
                
                # Use the first result for replying
                reply_message_id = int(html_results[0]['message_id'])
            
            # Send response to the user
            bot.reply_to(message, response)
            
            # Now post the Twitter link to the channel as a reply to the found message
            if channel_id and reply_message_id:
                try:
                    # Post the Twitter link to the channel as a reply
                    sent_message = bot.send_message(
                        chat_id=channel_id,
                        text=f"New update from {twitter_username}:\n{message.text}",
                        reply_to_message_id=reply_message_id
                    )
                    
                    # Manually save the message the bot just sent
                    save_message(sent_message)
                    print(f"✅ Sent and saved message {sent_message.message_id} to channel")
                    
                    bot.reply_to(message, f"✅ Posted your Twitter link to the channel as a reply to message {reply_message_id}")
                except Exception as e:
                    print(f"Error posting to channel: {e}")
                    bot.reply_to(message, f"❌ Error posting to channel: {str(e)}")
            else:
                bot.reply_to(message, "⚠️ Couldn't post to channel: missing channel ID or message ID.")
        else:
            bot.reply_to(message, f"❌ No mentions of '{twitter_username}' found in any channel history.")
    else:
        # No match, echo as before
        bot.reply_to(message, 'Not a Twitter post link.')

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

def search_exported_html(query):
    """
    Search for the query in all exported HTML files in .channel_data folder.
    Returns a list of matching message IDs and their contexts.
    """
    results = []
    channel_data_dir = '.channel_data'
    
    if not os.path.exists(channel_data_dir):
        print(f"Warning: {channel_data_dir} directory not found")
        return results
    
    print(f"Searching for '{query}' in exported HTML files...")
    
    # Walk through all directories in .channel_data
    for root, dirs, files in os.walk(channel_data_dir):
        # Filter for HTML message files
        html_files = [f for f in files if re.match(r'messages\d*\.html', f)]
        
        for html_file in html_files:
            file_path = os.path.join(root, html_file)
            print(f"Checking file: {file_path}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Find all message divs
                message_divs = soup.find_all('div', id=re.compile(r'message\d+'))
                
                for div in message_divs:
                    # Extract message ID
                    message_id_match = re.match(r'message(\d+)', div.get('id', ''))
                    if not message_id_match:
                        continue
                    
                    message_id = message_id_match.group(1)
                    
                    # Find text div within this message
                    text_div = div.find('div', class_='text')
                    if not text_div:
                        continue
                    
                    # Get text content
                    text_content = text_div.get_text(strip=True)
                    
                    # Check if query is in text content
                    if query.lower() in text_content.lower():
                        # Get date information if available
                        date_div = div.find('div', class_='pull_right date details')
                        date_text = date_div.get('title', '') if date_div else ''
                        
                        # Get sender information if available
                        from_div = div.find('div', class_='from_name')
                        from_name = from_div.get_text(strip=True) if from_div else ''
                        
                        # Extract Twitter links if present
                        twitter_links = []
                        links = text_div.find_all('a')
                        for link in links:
                            href = link.get('href', '')
                            if 'twitter.com' in href or 'x.com' in href:
                                twitter_links.append(href)
                        
                        # Gather result information
                        result = {
                            'message_id': message_id,
                            'text': text_content,
                            'date': date_text,
                            'from': from_name,
                            'file_path': file_path,
                            'twitter_links': twitter_links
                        }
                        
                        results.append(result)
                        print(f"Found match in message {message_id}: {text_content[:50]}...")
            
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    # Sort results by message_id (as a numeric value)
    results.sort(key=lambda x: int(x['message_id']))
    
    print(f"Found {len(results)} matching messages for query '{query}'")
    return results

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