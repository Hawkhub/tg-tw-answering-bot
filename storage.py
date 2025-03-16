import os
import json
import time
from datetime import datetime
from config import MESSAGE_STORAGE_FILE, MAX_FILE_SIZE_BYTES

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