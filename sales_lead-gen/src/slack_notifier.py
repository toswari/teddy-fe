"""
Slack Notification Module
Sends notifications to Slack when new messages are generated
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    """Handles Slack notifications for new lead generation results"""
    
    def __init__(self, config=None):
        """Initialize Slack client with bot token from environment"""
        self.bot_token = os.getenv('SLACK_BOT_TOKEN')
        self.channel = os.getenv('SLACK_CHANNEL')
        self.client = None
        self.config = config or {}
        
        # Check if notifications are enabled in config
        slack_config = self.config.get('slack', {})
        self.enabled = slack_config.get('enabled', True)
        self.notification_type = slack_config.get('notification_type', 'detailed')
        self.mention_on_high_value = slack_config.get('mention_on_high_value', False)
        
        if self.bot_token and self.channel and self.enabled:
            self.client = WebClient(token=self.bot_token)
            logging.info("Slack notifier initialized successfully")
        else:
            if not self.enabled:
                logging.info("Slack notifications disabled in configuration")
            else:
                logging.warning("Slack credentials not found in environment variables")
    
    def is_enabled(self) -> bool:
        """Check if Slack notifications are properly configured"""
        return (self.enabled and 
                self.client is not None and 
                self.bot_token and 
                self.channel)
    
    def send_summary_notification(self, messages: List[Dict], output_file: str, run_stats: Dict) -> bool:
        """
        Send a summary notification about the lead generation run
        
        Args:
            messages: List of generated messages
            output_file: Path to the output file
            run_stats: Dictionary with run statistics
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.is_enabled():
            logging.warning("Slack notifications not configured - skipping notification")
            return False
        
        try:
            # Build the summary message
            summary_text = self._build_summary_message(messages, output_file, run_stats)
            
            # Send the main message
            response = self.client.chat_postMessage(
                channel=self.channel,
                text=summary_text,
                unfurl_links=False,
                unfurl_media=False
            )
            
            # Get the timestamp for threading
            thread_ts = response['ts']
            
            # Send individual prospect messages as threaded replies
            self._send_prospect_threads(messages[:5], thread_ts)
            
            logging.info(f"Slack notification sent successfully to {self.channel}")
            return True
            
        except SlackApiError as e:
            logging.error(f"Failed to send Slack notification: {e.response['error']}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error sending Slack notification: {str(e)}")
            return False
    
    def send_detailed_notification(self, messages: List[Dict], output_file: str, run_stats: Dict) -> bool:
        """
        Send a detailed notification with top companies and their reasoning
        
        Args:
            messages: List of generated messages
            output_file: Path to the output file
            run_stats: Dictionary with run statistics
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.is_enabled():
            logging.warning("Slack notifications not configured - skipping notification")
            return False
        
        try:
            # Build the main notification message
            main_text = self._build_main_notification(messages, output_file, run_stats)
            
            # Send the main message
            response = self.client.chat_postMessage(
                channel=self.channel,
                text=main_text,
                unfurl_links=False,
                unfurl_media=False
            )
            
            # Get the timestamp for threading
            thread_ts = response['ts']
            
            # Send individual prospect messages as threaded replies
            self._send_prospect_threads(messages, thread_ts)
            
            logging.info(f"Detailed Slack notification sent successfully to {self.channel}")
            return True
            
        except SlackApiError as e:
            logging.error(f"Failed to send detailed Slack notification: {e.response['error']}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error sending detailed Slack notification: {str(e)}")
            return False
    
    def _build_summary_message(self, messages: List[Dict], output_file: str, run_stats: Dict) -> str:
        """Build a concise summary message for Slack"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get top companies
        top_companies = [msg['company_name'] for msg in messages[:5]]
        companies_text = ", ".join(top_companies)
        if len(messages) > 5:
            companies_text += f" and {len(messages) - 5} more"
        
        # Get event type distribution
        event_types = {}
        for msg in messages:
            event_type = msg.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        top_events = sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:3]
        events_text = ", ".join([f"{event}: {count}" for event, count in top_events])
        
        summary = f"""**New Lead Generation Results**

**Summary:**
• {len(messages)} new messages generated
• {run_stats.get('articles_processed', 0)} articles processed
• Top companies: {companies_text}
• Event types: {events_text}

**Output file:** `{os.path.basename(output_file)}`
**Generated at:** {timestamp}

Individual prospect details will be posted as replies to this message."""
        
        return summary
    
    def _build_main_notification(self, messages: List[Dict], output_file: str, run_stats: Dict) -> str:
        """Build the main notification message (without individual prospect details)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Count high-priority prospects based on AI assessment
        high_value_count = 0
        for msg in messages:
            priority = (msg.get('priority') or '').lower()
            if priority == 'high':
                high_value_count += 1
        
        # Add mention if high-value prospects found and configured
        mention_text = ""
        if high_value_count > 0 and self.mention_on_high_value:
            mention_text = " <!channel>"
        
        main_message = f"""**Lead Generation - Daily Results**{mention_text}
**Summary:**
• {len(messages)} messages generated from {run_stats.get('articles_processed', 0)} articles
• {high_value_count} high-value prospects identified
• Generated: {timestamp}

Individual prospect details with reasoning posted as replies below."""
        
        return main_message
    
    def _send_prospect_threads(self, messages: List[Dict], thread_ts: str) -> None:
        """Send individual prospect messages as threaded replies"""
        # Sort prospects by AI-determined priority
        high_value_prospects = []
        regular_prospects = []
        
        for msg in messages:
            priority = (msg.get('priority') or '').lower()
            if priority == 'high':
                high_value_prospects.append(msg)
            else:
                regular_prospects.append(msg)
        
        # Send high-value prospects first, then regular ones (limit to top 10 total)
        prospects_to_send = (high_value_prospects + regular_prospects)[:10]
        
        for i, msg in enumerate(prospects_to_send, 1):
            try:
                prospect_text = self._build_prospect_message(msg, i)
                
                self.client.chat_postMessage(
                    channel=self.channel,
                    text=prospect_text,
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False
                )
                
            except SlackApiError as e:
                logging.error(f"Failed to send prospect thread {i}: {e.response['error']}")
            except Exception as e:
                logging.error(f"Unexpected error sending prospect thread {i}: {str(e)}")
    
    def _build_prospect_message(self, msg: Dict, index: int) -> str:
        """Build a message for an individual prospect"""
        company = msg['company_name']
        event_type = msg.get('event_type', 'unknown')
        reasoning = msg.get('reasoning', 'No reasoning available')
        linkedin_message = msg.get('linkedin_message', 'No message available')
        article_title = msg.get('article_title', 'No title')
        article_url = msg.get('article_url', '')
        source = msg.get('source', 'Unknown source')
        priority = (msg.get('priority') or 'standard').lower()
        
        # Truncate reasoning if too long
        if len(reasoning) > 40000:
            reasoning = reasoning[:40000] + "..."

        # Truncate LinkedIn message if too long
        if len(linkedin_message) > 30000:
            linkedin_message = linkedin_message[:30000] + "..."

        # Create visual separator and priority styling based on AI assessment
        is_high_priority = priority == 'high'
        priority_text = "HIGH PRIORITY" if is_high_priority else "Standard Priority"
        priority_indicator = "[HIGH]" if is_high_priority else "[STD]"
        separator = "━" * 40
        priority_icon_color = "🔴" if is_high_priority else "🔵"

        # Format article link
        article_link = f"<{article_url}|{article_title}>" if article_url else f'"{article_title}"'

        prospect_message = f""" {priority_icon_color}
**PROSPECT #{index}: {company.upper()}**
{priority_indicator} *{priority_text}* | Event: `{event_type}`


**Strategic Reasoning:**
> {reasoning}

**Suggested LinkedIn Message:**
```
{linkedin_message}
```

**Source:** {source}
**Article:** {article_link}"""
        
        return prospect_message
    
    def test_connection(self) -> bool:
        """Test the Slack connection and permissions"""
        if not self.is_enabled():
            print("ERROR: Slack not configured - missing SLACK_BOT_TOKEN or SLACK_CHANNEL")
            return False
        
        try:
            # Test API connection
            response = self.client.auth_test()
            print(f"SUCCESS: Slack connection successful - Bot: {response['user']}")
            
            # Test channel access
            test_response = self.client.chat_postMessage(
                channel=self.channel,
                text="Slack integration test successful! Lead generation notifications are now active.",
                unfurl_links=False
            )
            
            print(f"SUCCESS: Test message sent to {self.channel}")
            return True
            
        except SlackApiError as e:
            print(f"ERROR: Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error: {str(e)}")
            return False


def test_slack_integration():
    """Test function to verify Slack integration"""
    notifier = SlackNotifier()
    return notifier.test_connection()


if __name__ == "__main__":
    # Test the Slack integration when run directly
    test_slack_integration()