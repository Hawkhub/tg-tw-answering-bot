import os
import re
import json
from bs4 import BeautifulSoup
from config import MESSAGE_STORAGE_FILE

# Search for messages in the stored file
def search_stored_messages(query):
    """
    Search for messages containing the query in our stored messages.
    Returns the most recent message containing the query.
    """
    try:
        with open(MESSAGE_STORAGE_FILE, 'r') as f:
            messages = json.load(f)
        
        # Filter messages containing the query
        matching_messages = []
        for msg in messages:
            if "text" in msg and query.lower() in msg["text"].lower():
                matching_messages.append(msg)
        
        # Sort by date, newest first
        if matching_messages:
            # Use message date for sorting
            matching_messages.sort(key=lambda x: x.get("date", 0), reverse=True)
            return matching_messages[0]
        
        return None
    except Exception as e:
        print(f"Error searching stored messages: {e}")
        return None

def search_exported_html(query):
    """
    Search for the query in all exported HTML files in .channel_data folder.
    Returns a list of matching message IDs and their contexts.
    """
    results = []
    channel_data_dir = '.channel_data'
    
    if not os.path.exists(channel_data_dir):
        print(f"Warning: {channel_data_dir} directory not found")
        return results
    
    print(f"Searching for '{query}' in exported HTML files...")
    
    # Walk through all directories in .channel_data
    for root, dirs, files in os.walk(channel_data_dir):
        # Filter for HTML message files
        html_files = [f for f in files if re.match(r'messages\d*\.html', f)]
        
        for html_file in html_files:
            file_path = os.path.join(root, html_file)
            print(f"Checking file: {file_path}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Find all message divs
                message_divs = soup.find_all('div', id=re.compile(r'message\d+'))
                
                for div in message_divs:
                    # Extract message ID
                    message_id_match = re.match(r'message(\d+)', div.get('id', ''))
                    if not message_id_match:
                        continue
                    
                    message_id = message_id_match.group(1)
                    
                    # Find text div within this message
                    text_div = div.find('div', class_='text')
                    if not text_div:
                        continue
                    
                    # Get text content
                    text_content = text_div.get_text(strip=True)
                    
                    # Check if query is in text content
                    if query.lower() in text_content.lower():
                        # Get date information if available
                        date_div = div.find('div', class_='pull_right date details')
                        date_text = date_div.get('title', '') if date_div else ''
                        
                        # Get sender information if available
                        from_div = div.find('div', class_='from_name')
                        from_name = from_div.get_text(strip=True) if from_div else ''
                        
                        # Extract Twitter links if present
                        twitter_links = []
                        links = text_div.find_all('a')
                        for link in links:
                            href = link.get('href', '')
                            if 'twitter.com' in href or 'x.com' in href:
                                twitter_links.append(href)
                        
                        # Gather result information
                        result = {
                            'message_id': message_id,
                            'text': text_content,
                            'date': date_text,
                            'from': from_name,
                            'file_path': file_path,
                            'twitter_links': twitter_links
                        }
                        
                        results.append(result)
                        print(f"Found match in message {message_id}: {text_content[:50]}...")
            
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    # Sort results by message_id (as a numeric value)
    results.sort(key=lambda x: int(x['message_id']))
    
    print(f"Found {len(results)} matching messages for query '{query}'")
    return results 