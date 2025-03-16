import os

# Bot configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL = os.environ.get('CHANNEL')  # The channel we're monitoring
# Parse comma-separated list of authorized users
AUTHORIZED_USERS = [username.strip() for username in os.environ.get('AUTHORIZED_USERS', '').split(',') if username.strip()]

# File storage settings
MESSAGE_STORAGE_FILE = 'channel_messages.json'  # File to store messages
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB in bytes 