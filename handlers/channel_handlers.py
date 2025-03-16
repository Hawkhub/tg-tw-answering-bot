from config import CHANNEL
from storage import save_message

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