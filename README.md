# Python Project

This is a Python project for a telegram bot that monitors a channel and saves new messages to a file.
When user sends a twitter (X) link to the bot, it first checks exported channel history that is stored alongside the bot's file holding the updates, and if it finds the message in one or another history containing the author of a tweet, it uses the found message to reply to it and then compiles new post for the channel with the provided link.

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   ```

2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables in the `.env` file:
   ```
   BOT_TOKEN=your_telegram_bot_token
   CHANNEL=@your_channel_name
   AUTHORIZED_USERS=user1,user2,user3
   X_USERNAME=your_twitter_username
   X_PASSWORD=your_twitter_password
   ```
   
   The `X_USERNAME` and `X_PASSWORD` variables should contain your X/Twitter login credentials for authentication.

## X/Twitter Authentication

This application uses username/password authentication to interact with X/Twitter. For detailed instructions on:
- How to set up X/Twitter authentication
- Understanding the persistent browser profile system
- Troubleshooting authentication issues

Please refer to the [Twitter Authentication Guide](TWITTER_AUTH_GUIDE.md).

## Usage

Run the main application:
```
source .env
source venv/bin/activate
python bot.py
```