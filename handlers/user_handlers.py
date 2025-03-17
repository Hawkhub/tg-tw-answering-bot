import re
import os
from datetime import datetime
from config import AUTHORIZED_USERS, MESSAGE_STORAGE_FILE, CHANNEL
from storage import save_message
from search import search_stored_messages, search_exported_html
from tweet_fetcher import get_tweet_content, download_media
from handlers.channel_handlers import post_tweet_to_channel
import telebot

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
        # Send tweet content and media to user in a consolidated message
        content_msg = ""
        if tweet_content.get('text'):
            content_msg += f"{tweet_content['text']}\n\n"
        content_msg += f"Source: {tweet_content['source']}"
        
        # Check if we have media
        if tweet_content.get('media_urls'):
            media_files = []
            temp_files = []  # Track temp files for cleanup
            
            try:
                # Process up to 10 media items (Telegram's limit for media groups)
                for idx, media_url in enumerate(tweet_content['media_urls'][:10]):
                    # Determine file type
                    file_ext = os.path.splitext(media_url)[1].lower()
                    if not file_ext:
                        file_ext = '.jpg'  # Default to jpg if no extension
                    
                    # Create temp file path
                    tmp_path = os.path.join('.temp', 'media', f"media_user_{tweet_id}_{idx}{file_ext}")
                    
                    # Download the media
                    if download_media(media_url, tmp_path):
                        temp_files.append(tmp_path)  # Track for cleanup
                        
                        # Create appropriate media object based on file type
                        if idx == 0:
                            # First media gets the caption
                            if file_ext in ['.jpg', '.jpeg', '.png']:
                                media_files.append(telebot.types.InputMediaPhoto(
                                    open(tmp_path, 'rb'), 
                                    caption=content_msg
                                ))
                            elif file_ext == '.gif':
                                # Note: GIFs will be converted to videos in media groups
                                media_files.append(telebot.types.InputMediaVideo(
                                    open(tmp_path, 'rb'), 
                                    caption=content_msg,
                                    supports_streaming=True
                                ))
                            elif file_ext in ['.mp4', '.mov', '.avi', '.webm']:
                                media_files.append(telebot.types.InputMediaVideo(
                                    open(tmp_path, 'rb'), 
                                    caption=content_msg,
                                    supports_streaming=True
                                ))
                        else:
                            # Additional media without caption
                            if file_ext in ['.jpg', '.jpeg', '.png']:
                                media_files.append(telebot.types.InputMediaPhoto(
                                    open(tmp_path, 'rb')
                                ))
                            elif file_ext in ['.mp4', '.mov', '.avi', '.webm', '.gif']:
                                media_files.append(telebot.types.InputMediaVideo(
                                    open(tmp_path, 'rb'),
                                    supports_streaming=True
                                ))
                
                # Send as media group if we have media
                if media_files:
                    bot.send_media_group(
                        chat_id=message.chat.id,
                        media=media_files
                    )
                    media_sent = True
                
            except Exception as e:
                print(f"Error sending media group to user: {e}")
                import traceback
                print(traceback.format_exc())
                
                # Fall back to text-only message
                if not media_sent:
                    bot.send_message(message.chat.id, content_msg)
            
            finally:
                # Clean up temp files
                for tmp_path in temp_files:
                    if os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception as e:
                            print(f"Error removing temp file {tmp_path}: {e}")
        else:
            # No media, just send text
            bot.send_message(message.chat.id, content_msg)
    else:
        bot.send_message(message.chat.id, "⚠️ Could not retrieve tweet content.")
    
    # Post to the channel (either as a reply or new message)
    if channel_id:
        # Use the channel handler function to post the tweet
        result = post_tweet_to_channel(
            bot=bot, 
            channel_id=channel_id, 
            tweet_content=tweet_content, 
            twitter_username=twitter_username, 
            tweet_id=tweet_id, 
            reply_message_id=reply_message_id
        )
        
        if result['success']:
            if reply_message_id:
                bot.reply_to(message, f"✅ Posted the tweet to the channel as a reply to message {reply_message_id}")
            else:
                bot.reply_to(message, f"✅ Posted the tweet to the channel as a new message")
        else:
            bot.reply_to(message, f"❌ Error posting to channel: {result['error']}")
    else:
        bot.reply_to(message, "⚠️ Couldn't post to channel: missing channel ID.") 