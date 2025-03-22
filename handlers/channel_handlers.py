from config import CHANNEL
from storage import save_message
import os
from tweet_fetcher import download_media, get_tweet_content, extract_tweet_info
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

def parse_cookie_table(cookie_table_text):
    """
    Parse a cookie table text (copied from browser dev tools) into a dictionary
    
    Args:
        cookie_table_text (str): Tab-separated cookie table text from browser
        
    Returns:
        dict: Dictionary of cookie name-value pairs
    """
    cookies = {}
    
    # Skip the header row
    lines = cookie_table_text.strip().split('\n')
    if not lines:
        return cookies
        
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 2:  # Need at least name and value
            continue
            
        name = parts[0].strip()
        value = parts[1].strip()
        
        # Only include non-empty cookies
        if name and value:
            cookies[name] = value
            
    return cookies

async def handle_x_tweet(message, client):
    """Handler for X/Twitter tweet links"""
    
    # Your X authentication cookies - this could be stored in config or environment
    x_cookies_text = """__cf_bm	Jmnk7_X0Q7RQuF_8dQdDurVovwH3G.HcZdCUlGLoXYI-1742641461-1.0.1.1-tXPuyuO7BbngM8E04Ow9v5fY7k0rgw78DbUzdrAGzf4dMEdeCJ5Kf1ZsQgF1kqj0VDjn1HPI6ibPIP9JxlenDlAYOARL18sq53_jTv3fxxQ	.x.com	/	2025-03-22T11:34:21.856Z	177	✓	✓	None			Medium	
__cf_bm	A9CE_Cs5HPML1a4cQ9EbhnYamCPkLZ.qKm68uhW7n.A-1742640699-1.0.1.1-cs3CvAjBB5iSFnjtamUt6MHMom1MN9iK.nsq3_AwTr.kKLV.aHGvTYS_3cuHuOYXfcd2LJlEJGFoqongajGb08.rBDIDcD5dpSOcI1CDVrg	.twitter.com	/	2025-03-22T11:21:39.370Z	177	✓	✓	None			Medium	
auth_multi	"136618804:755a6669542eb0cb257839435447015b65b5ad9a|811128179884781568:ac7ab9a86798794ad5e0cdd4258bf9cdf78b503b"	.x.com	/	2026-04-22T10:52:25.699Z	122	✓	✓	Lax			Medium	
auth_token	a1f73b6cc7fefbd4466df9a4d651740c100bda65	.x.com	/	2026-04-22T10:11:12.855Z	50	✓	✓	None			Medium	
ct0	4a6dffb4c9220de970a2d15c760de0ad95198863f09e61690c3701898bf9c6414437935d5cd9132d2256f80ca03e1dd819b804e3bcef0dfd3925f6fabbcc1ddc93a039e5679d739afd488f0c179607b4	.x.com	/	2026-04-22T10:11:13.306Z	163		✓	Lax			Medium	
d_prefs	MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw	.x.com	/	2025-07-09T14:39:48.194Z	59		✓				Medium	
dnt	1	.x.com	/	2026-04-22T10:11:12.855Z	4		✓	None			Medium	
guest_id	v1%3A174263827279062459	.x.com	/	2026-04-22T10:11:13.306Z	31		✓	None			Medium	
guest_id_ads	v1%3A169549221149633047	.x.com	/	2026-02-10T14:39:48.651Z	35		✓	None			Medium	
guest_id_marketing	v1%3A169549221149633047	.x.com	/	2026-02-10T14:39:48.651Z	41		✓	None			Medium	
kdt	SjKe4XI7Zdlsl4R4iRX5KgG8KGLD78jNpBW04OwZ	.x.com	/	2026-04-22T10:11:12.855Z	43	✓	✓				Medium	
lang	en	x.com	/	Session	6						Medium	
personalization_id	"v1_0T0QSTka1kLapeR2HhYJTg=="	.x.com	/	2026-03-17T20:04:28.481Z	47		✓	None			Medium	
twid	u%3D1306736056985948162	.x.com	/	2026-03-22T10:52:28.894Z	27		✓	None			Medium"""
    
    # Parse cookies from the text table
    x_cookies = parse_cookie_table(x_cookies_text)
    
    # Extract username and tweet_id from the URL
    url = message.content.strip()
    username, tweet_id = extract_tweet_info(url)
    
    if not username or not tweet_id:
        await message.channel.send("Unable to extract tweet information from the URL.")
        return
    
    # Inform user we're processing
    await message.channel.send(f"Fetching tweet from @{username}. This may take a moment...")
    
    # Get tweet content with full cookie authentication
    result = get_tweet_content(username, tweet_id, cookies=x_cookies)
    
    # Handle the result - share text and media
    if result['text']:
        await message.channel.send(f"**@{username}**: {result['text']}")
    
    # Send media files if any
    for media_url in result['media_urls'][:4]:  # Limit to 4 media items
        try:
            await message.channel.send(media_url)
        except Exception as e:
            await message.channel.send(f"Error sending media: {str(e)}")
    
    if not result['text'] and not result['media_urls']:
        await message.channel.send("Unable to retrieve tweet content.") 