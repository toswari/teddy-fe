import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
from bs4 import BeautifulSoup

# Configs
# NOTE: It's best practice to use environment variables for sensitive data.
BEARER_TOKEN = os.environ.get("INTERCOM_BEARER_TOKEN", "dG9rOjhmN2IzOWU2XzVmNjdfNDc1ZV9iZDU2XzdjOGRlNWJlNmExYzoxOjA=")
BASE_URL = "https://api.intercom.io/conversations"
DAYS_BACK = 30
TAG_NAME = "Marketing-SEO"

# Headers
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Accept": "application/json"
}

# Helper: Extract plain text from HTML blocks
def extract_text_from_html(html):
    """Parses HTML to extract clean, readable text."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n").strip()

# Helper: Find the tag ID for the tag name
def get_tag_id(tag_name):
    """
    Fetches the ID of a tag from the Intercom API by its name.

    Args:
        tag_name (str): The name of the tag to search for.

    Returns:
        str or None: The ID of the tag if found, otherwise None.
    """
    url = "https://api.intercom.io/tags"
    print(f"🔄 Looking up tag ID for '{tag_name}'...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tags_data = response.json().get("data", [])
        for tag in tags_data:
            if tag.get("name") == tag_name:
                print(f"✅ Found tag '{tag_name}' with ID: {tag['id']}")
                return tag['id']
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch tags: {e}")
    return None

# ---
## Core Functions

def fetch_conversations_by_tag_and_date(tag_id):
    """
    Fetches conversations from Intercom filtered by tag ID and date range.

    Args:
        tag_id (str): The ID of the tag to filter by.

    Returns:
        list: A list of filtered conversation dictionaries.
    """
    print("📥 Fetching conversations from Intercom...")

    all_conversations = []

    # Intercom's API supports filtering by tag ID and creation date range.
    cutoff_timestamp = int((datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).timestamp())
    url = f"{BASE_URL}?tag_ids={tag_id}&state=all&created_after={cutoff_timestamp}"

    while url:
      try:
          resp = requests.get(url, headers=headers)
          resp.raise_for_status()
          data = resp.json()
          conversations = data.get("conversations", [])
          all_conversations.extend(conversations)

          # Correct pagination logic to handle both string URLs and dicts
          next_page = data.get("pages", {}).get("next")
          if isinstance(next_page, str):
              url = next_page
          elif isinstance(next_page, dict):
              # Intercom's dict-based pagination uses a cursor.
              cursor = next_page.get("starting_after")
              # We need to construct the full URL, including all original parameters.
              if cursor:
                  url = f"{BASE_URL}?tag_ids={tag_id}&state=all&created_after={cutoff_timestamp}&starting_after={cursor}"
              else:
                  url = None
          else:
              url = None

      except requests.exceptions.RequestException as e:
          print(f"❌ Request failed: {e}")
          break

    print(f"✅ Retrieved {len(all_conversations)} conversations matching the criteria.")
    return all_conversations

def process_conversation_data(conversations):
    """
    Processes raw conversation data into a clean, structured list.

    Args:
        conversations (list): A list of raw conversation dictionaries.

    Returns:
        list: A list of processed conversation dictionaries ready for DataFrame.
    """
    processed_conversations = []
    for conv in tqdm(conversations, desc="Processing"):
        try:
            conv_id = conv.get("id")

            # Use the "source" object to get the initial message sender info
            source = conv.get("source", {})
            author = source.get("author", {})

            name = author.get("name", "Unknown")
            email = author.get("email", "Unknown")

            # Get the body of the initial message
            initial_message = extract_text_from_html(source.get("body", "No message body found."))

            # Format the date
            created_at = datetime.fromtimestamp(conv.get("created_at", 0), tz=timezone.utc)
            formatted_date = created_at.strftime("%d-%m-%Y")

            # The API response sometimes contains multiple tags for one conversation.
            # We must filter again to ensure only conversations with the desired tag are included.
            tag_list = conv.get("tags", {}).get("tags", [])
            tag_names = [tag["name"] for tag in tag_list]
            if TAG_NAME not in tag_names:
                continue

            processed_conversations.append({
                "Conversation ID": conv_id,
                "Client Name": name,
                "Client Email": email,
                "Initial Message": initial_message,
                "Date": formatted_date
            })

        except Exception as e:
            print(f"❌ Error processing conversation {conv_id}: {e}")

    return processed_conversations

# ---
## Main Execution

def main():
    """Main function to run the script."""
    tag_id = get_tag_id(TAG_NAME)
    if not tag_id:
        print(f"❌ Could not find tag with name '{TAG_NAME}'. Exiting.")
        return

    conversations = fetch_conversations_by_tag_and_date(tag_id)
    if not conversations:
        print("⚠️ No conversations found with the specified criteria.")
        return

    processed_data = process_conversation_data(conversations)

    if processed_data:
        df = pd.DataFrame(processed_data)
        file_name = f"{TAG_NAME.lower().replace(' ', '_')}_conversations.xlsx"
        df.to_excel(file_name, index=False)
        print(f"✅ Exported {len(processed_data)} conversations to {file_name}")
    else:
        print("⚠️ No conversations were processed successfully.")

if __name__ == "__main__":
    main()