from config import CHANNEL
from storage import save_message
import os
from tweet_fetcher import download_media

def handle_channel_post(bot, message):
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
        return True
    
    return False

def post_tweet_to_channel(bot, channel_id, tweet_content, twitter_username, tweet_id, reply_message_id=None):
    """
    Post a tweet and its media to a channel
    
    Args:
        bot: The Telegram bot instance
        channel_id: ID of the channel to post to
        tweet_content: Dict containing tweet text and media URLs
        twitter_username: Twitter username
        tweet_id: Tweet ID
        reply_message_id: Optional message ID to reply to
        
    Returns:
        dict: Result with success status and sent message or error
    """
    result = {
        'success': False,
        'message': None,
        'error': None
    }
    
    try:
        # Build the X.com URL
        reconstructed_link = f"https://x.com/{twitter_username}/status/{tweet_id}"
        
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
            reply_to_message_id=reply_message_id
        )
        
        # If we have media, send it with proper type detection
        if tweet_content and tweet_content.get('media_urls'):
            for idx, media_url in enumerate(tweet_content['media_urls'][:4]):  # Limit to 4 media items
                try:
                    # Create temp file for the media
                    file_ext = os.path.splitext(media_url)[1].lower()
                    if not file_ext:
                        file_ext = '.jpg'  # Default to jpg if no extension
                    
                    tmp_path = os.path.join('.temp', 'media', f"media_channel_{tweet_id}_{idx}{file_ext}")
                    
                    # Download the media
                    if download_media(media_url, tmp_path):
                        # Enhanced media type detection for channel posts
                        if file_ext in ['.jpg', '.jpeg', '.png']:
                            # Static images
                            with open(tmp_path, 'rb') as photo:
                                bot.send_photo(
                                    chat_id=channel_id,
                                    photo=photo,
                                    reply_to_message_id=sent_message.message_id
                                )
                        elif file_ext == '.gif':
                            # Animated GIFs
                            with open(tmp_path, 'rb') as animation:
                                bot.send_animation(
                                    chat_id=channel_id,
                                    animation=animation,
                                    reply_to_message_id=sent_message.message_id
                                )
                        elif file_ext in ['.mp4', '.mov', '.avi', '.webm']:
                            # Videos
                            with open(tmp_path, 'rb') as video:
                                bot.send_video(
                                    chat_id=channel_id,
                                    video=video,
                                    reply_to_message_id=sent_message.message_id
                                )
                        # Don't send other file types to the channel
                    
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception as e:
                    print(f"Error sending media to channel: {e}")
                    import traceback
                    print(traceback.format_exc())
        
        # Manually save the message the bot just sent
        save_message(sent_message)
        print(f"✅ Sent and saved message {sent_message.message_id} to channel")
        
        result['success'] = True
        result['message'] = sent_message
        
    except Exception as e:
        import traceback
        error_tb = traceback.format_exc()
        print(f"Error posting to channel: {e}")
        print(error_tb)
        result['error'] = str(e)
    
    return result 