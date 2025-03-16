import re
from datetime import datetime
from config import AUTHORIZED_USERS, MESSAGE_STORAGE_FILE, CHANNEL
from storage import save_message
from search import search_stored_messages, search_exported_html

def handle_welcome(bot, message):
    """Handle /start and /hello commands"""
    bot.reply_to(message, "Howdy, how are you doing?")

def handle_status_check(bot, message):
    """Handle /status command to check storage statistics"""
    try:
        import json
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

def handle_twitter_link(bot, message):
    """Handle Twitter/X links from authorized users"""
    # Check if the message is from an authorized user first
    if message.from_user.username not in AUTHORIZED_USERS:
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    
    # Extract both the Twitter username and tweet ID
    pattern = r'/(\w+)/status/(\d+)'
    match = re.search(pattern, message.text)
    
    if not match:
        # No match, echo as before
        bot.reply_to(message, 'Not a Twitter post link.')
        return
    
    twitter_username = match.group(1)
    tweet_id = match.group(2)
    
    # Create the clean x.com URL format
    reconstructed_link = f"https://x.com/{twitter_username}/status/{tweet_id}"
    
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
        
        # Now post the reconstructed Twitter link to the channel as a reply
        if channel_id and reply_message_id:
            try:
                # Post the reconstructed X link to the channel as a reply
                sent_message = bot.send_message(
                    chat_id=channel_id,
                    text=reconstructed_link,
                    reply_to_message_id=reply_message_id
                )
                
                # Manually save the message the bot just sent
                save_message(sent_message)
                print(f"✅ Sent and saved message {sent_message.message_id} to channel")
                
                bot.reply_to(message, f"✅ Posted the link to the channel as a reply to message {reply_message_id}")
            except Exception as e:
                print(f"Error posting to channel: {e}")
                bot.reply_to(message, f"❌ Error posting to channel: {str(e)}")
        else:
            bot.reply_to(message, "⚠️ Couldn't post to channel: missing channel ID or message ID.")
    else:
        bot.reply_to(message, f"❌ No mentions of '{twitter_username}' found in any channel history.") 