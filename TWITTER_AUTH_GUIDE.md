# X/Twitter Authentication Guide

This guide explains how to set up authentication for X/Twitter in this application using username and password.

## How Authentication Works

The application uses a browser automation approach to log into X/Twitter and maintain a persistent browser session. This approach is necessary as X has advanced anti-bot measures that make traditional API-based approaches unreliable.

Key features:
- Persistent browser profiles that maintain a consistent browser fingerprint
- Username/password authentication that mimics a real browser login
- Anti-detection measures to avoid being blocked
- Screenshots of the login process for debugging

## Setting Up Authentication

To use X/Twitter authentication in this application, follow these steps:

### 1. Update your .env file

Edit the `.env` file in your project directory and set the following variables:

```
export X_USERNAME='your_twitter_username'  # Your X/Twitter username or email
export X_PASSWORD='your_twitter_password'  # Your X/Twitter password
```

### 2. Activate the environment variables

Run the following command to apply the environment variables:

```bash
source .env
```

### 3. Test the authentication

Run the test script to verify your authentication works:

```bash
./tests/test_login.py
```

This will create a browser session, log into X/Twitter with your credentials, and navigate to a test tweet. The script will save screenshots of each step in the `.temp/screenshots/login` directory.

If successful, you should see:
- A message confirming that login was successful
- Screenshots showing the authenticated session
- Confirmation that the tweet content was found

## How Profile Persistence Works

When you first use X authentication:

1. The system creates a profile directory based on your username at `.temp/profiles/auth_yourusername`
2. It generates and stores persistent browser settings in this directory
3. Uses these settings consistently for all future requests
4. The browser session is saved, so subsequent authentications are faster

The persistent settings include:
- Viewport size
- Color scheme
- Locale and timezone
- Device characteristics 
- Fingerprint values

This ensures that your "browser profile" appears consistent to X's anti-bot detection systems, mimicking a real user who always uses the same device and settings.

## Troubleshooting

If you experience authentication issues:

1. **Check your credentials**: Make sure your username and password are correct
2. **Clear the profile**: Delete the `.temp/profiles/auth_yourusername` directory to start fresh
3. **Check screenshots**: Look at the login screenshots in `.temp/screenshots/login` to see where the process is failing
4. **2FA**: This system currently doesn't support accounts with Two-Factor Authentication enabled

## Security Notes

- The `.env` file contains your X/Twitter credentials and should never be committed to version control
- Keep your credentials private to prevent account compromise
- Auth profile directories contain your session data - keep them secure
- Consider creating a dedicated account for this application instead of using your personal account 