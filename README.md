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
   ````

## Usage

Run the main application:
```
source .env
source venv/bin/activate
python bot.py
``` 