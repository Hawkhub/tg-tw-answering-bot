from config import CHANNEL
from storage import save_message
import os
from tweet_fetcher import download_media
import telebot

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
    Post a tweet and its media to a channel in a single message when possible
    """
    result = {
        'success': False,
        'message': None,
        'error': None
    }
    
    try:
        # Build the X.com URL and caption text
        reconstructed_link = f"https://x.com/{twitter_username}/status/{tweet_id}"
        
        # Build message caption
        caption = ""
        if tweet_content and tweet_content.get('text'):
            # Add tweet text if available (limit to ~1000 chars for caption)
            text = tweet_content['text']
            if len(text) > 1000:
                text = text[:997] + "..."
            caption = f"\"{text}\"\n\n{reconstructed_link}"
        else:
            caption = reconstructed_link
        
        # Check if we have media to send
        if tweet_content and tweet_content.get('media_urls'):
            media_files = []
            temp_files = []  # Track temp files for cleanup
            
            try:
                # Prepare media group
                for idx, media_url in enumerate(tweet_content['media_urls'][:10]):  # Telegram allows up to 10 items
                    # Determine file type
                    file_ext = os.path.splitext(media_url)[1].lower()
                    if not file_ext:
                        file_ext = '.jpg'  # Default to jpg if no extension
                    
                    # Create temp file path
                    tmp_path = os.path.join('.temp', 'media', f"media_channel_{tweet_id}_{idx}{file_ext}")
                    
                    # Download the media
                    if download_media(media_url, tmp_path):
                        temp_files.append(tmp_path)  # Track for cleanup
                        
                        # Create appropriate media object based on file type
                        if idx == 0:
                            # First media gets the caption
                            if file_ext in ['.jpg', '.jpeg', '.png']:
                                media_files.append(telebot.types.InputMediaPhoto(
                                    open(tmp_path, 'rb'), 
                                    caption=caption
                                ))
                            elif file_ext == '.gif':
                                # Gifs get converted to videos in media groups
                                media_files.append(telebot.types.InputMediaVideo(
                                    open(tmp_path, 'rb'), 
                                    caption=caption,
                                    supports_streaming=True
                                ))
                            elif file_ext in ['.mp4', '.mov', '.avi', '.webm']:
                                media_files.append(telebot.types.InputMediaVideo(
                                    open(tmp_path, 'rb'), 
                                    caption=caption,
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
                    sent_messages = bot.send_media_group(
                        chat_id=channel_id,
                        media=media_files,
                        reply_to_message_id=reply_message_id
                    )
                    
                    # Save all sent messages
                    for msg in sent_messages:
                        save_message(msg)
                    
                    print(f"✅ Sent media group with {len(media_files)} items to channel")
                    result['success'] = True
                    result['message'] = sent_messages[0]  # Return first message as reference
                
            except Exception as e:
                print(f"Error sending media group: {e}")
                import traceback
                print(traceback.format_exc())
                
                # Fall back to text-only message if media group fails
                if not result['success']:
                    sent_message = bot.send_message(
                        chat_id=channel_id,
                        text=caption,
                        reply_to_message_id=reply_message_id
                    )
                    save_message(sent_message)
                    result['success'] = True
                    result['message'] = sent_message
            
            finally:
                # Clean up temp files
                for tmp_path in temp_files:
                    if os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception as e:
                            print(f"Error removing temp file {tmp_path}: {e}")
        
        else:
            # No media, just send text message
            sent_message = bot.send_message(
                chat_id=channel_id,
                text=caption,
                reply_to_message_id=reply_message_id
            )
            save_message(sent_message)
            result['success'] = True
            result['message'] = sent_message
        
    except Exception as e:
        import traceback
        error_tb = traceback.format_exc()
        print(f"Error posting to channel: {e}")
        print(error_tb)
        result['error'] = str(e)
    
    return result 