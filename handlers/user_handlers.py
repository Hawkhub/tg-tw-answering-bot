import re
import os
from datetime import datetime
import tempfile
from config import AUTHORIZED_USERS, MESSAGE_STORAGE_FILE, CHANNEL
from storage import save_message
from search import search_stored_messages, search_exported_html
from tweet_fetcher import get_tweet_content, download_media

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
    
    # Search for mentions of the Twitter username
    bot.reply_to(message, f"Searching for '{twitter_username}' in channel history...")
    
    # First search in our JSON storage (recent messages)
    json_result = search_stored_messages(twitter_username)
    
    # Only search in HTML files if nothing found in JSON
    html_results = []
    channel_id = CHANNEL  # Default to the configured channel
    reply_message_id = None  # Will remain None if no results found
    
    if not json_result:
        bot.reply_to(message, "Not found in recent messages. Searching in older exported history...")
        html_results = search_exported_html(twitter_username)
    
    # If we found results, format a response with the match details
    if json_result or html_results:
        # Format the response with search results
        response = f"✅ Found mentions of '{twitter_username}':\n\n"
        
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
            
            # If channel_id is a string (username), we need to get the numeric ID
            if isinstance(channel_id, str) and channel_id.startswith('@'):
                try:
                    channel_info = bot.get_chat(channel_id)
                    channel_id = channel_info.id
                except Exception as e:
                    print(f"Error getting channel ID: {e}")
                    bot.reply_to(message, "Found results but couldn't determine channel ID.")
                    return
        
        # Send response to the user
        bot.reply_to(message, response)
    else:
        bot.reply_to(message, f"ℹ️ No previous mentions of '{twitter_username}' found. Will post as a new message.")
        # If channel_id is a string (username), we need to get the numeric ID
        if isinstance(channel_id, str) and channel_id.startswith('@'):
            try:
                channel_info = bot.get_chat(channel_id)
                channel_id = channel_info.id
            except Exception as e:
                print(f"Error getting channel ID: {e}")
                bot.reply_to(message, "Couldn't determine channel ID.")
                return
    
    # Get tweet content (do this regardless of whether we found previous mentions)
    bot.send_message(message.chat.id, "📥 Fetching tweet content...")
    tweet_content = get_tweet_content(twitter_username, tweet_id)
    
    if tweet_content and (tweet_content.get('text') or tweet_content.get('media_urls')):
        # Send tweet content to user
        content_msg = f"📝 Tweet content:\n\n"
        if tweet_content.get('text'):
            content_msg += f"{tweet_content['text']}\n\n"
        content_msg += f"Source: {tweet_content['source']}"
        
        user_msg = bot.send_message(message.chat.id, content_msg)
        
        # Send media if available
        media_sent = False
        if tweet_content.get('media_urls'):
            for idx, media_url in enumerate(tweet_content['media_urls'][:4]):  # Limit to 4 media items
                try:
                    # Create temp file for the media
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(media_url)[1]) as tmp:
                        tmp_path = tmp.name
                    
                    # Download the media
                    if download_media(media_url, tmp_path):
                        # Determine type and send
                        if any(media_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            with open(tmp_path, 'rb') as photo:
                                bot.send_photo(message.chat.id, photo)
                                media_sent = True
                        elif any(media_url.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi']):
                            with open(tmp_path, 'rb') as video:
                                bot.send_video(message.chat.id, video)
                                media_sent = True
                        else:
                            with open(tmp_path, 'rb') as doc:
                                bot.send_document(message.chat.id, doc)
                                media_sent = True
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Error sending media: {e}")
            
            if not media_sent:
                bot.send_message(message.chat.id, "⚠️ Could not download or send media files.")
    else:
        bot.send_message(message.chat.id, "⚠️ Could not retrieve tweet content.")
    
    # Post to the channel (either as a reply or new message)
    if channel_id:
        try:
            # Build channel message with tweet content if available
            channel_msg = reconstructed_link
            
            if tweet_content and tweet_content.get('text'):
                # Add tweet text if available (limit to ~200 chars)
                text = tweet_content['text']
                if len(text) > 200:
                    text = text[:197] + "..."
                channel_msg = f"{text}\n\n{channel_msg}"
            
            # Post the X link to the channel (as a reply if we have a message_id)
            sent_message = bot.send_message(
                chat_id=channel_id,
                text=channel_msg,
                reply_to_message_id=reply_message_id  # This will be None if no previous mentions found
            )
            
            # If we have media and it's an image, send it as a reply to our message
            if tweet_content and tweet_content.get('media_urls'):
                for idx, media_url in enumerate(tweet_content['media_urls'][:1]):  # Just send first image
                    try:
                        # Create temp file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(media_url)[1]) as tmp:
                            tmp_path = tmp.name
                        
                        # Download and send
                        if download_media(media_url, tmp_path):
                            if any(media_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                                with open(tmp_path, 'rb') as photo:
                                    bot.send_photo(
                                        chat_id=channel_id,
                                        photo=photo,
                                        reply_to_message_id=sent_message.message_id
                                    )
                        
                        # Clean up
                        os.unlink(tmp_path)
                    except Exception as e:
                        print(f"Error sending media to channel: {e}")
            
            # Manually save the message the bot just sent
            save_message(sent_message)
            print(f"✅ Sent and saved message {sent_message.message_id} to channel")
            
            if reply_message_id:
                bot.reply_to(message, f"✅ Posted the tweet to the channel as a reply to message {reply_message_id}")
            else:
                bot.reply_to(message, f"✅ Posted the tweet to the channel as a new message")
        except Exception as e:
            print(f"Error posting to channel: {e}")
            bot.reply_to(message, f"❌ Error posting to channel: {str(e)}")
    else:
        bot.reply_to(message, "⚠️ Couldn't post to channel: missing channel ID.") 