#!/usr/bin/env python3
"""
Automated Sales Outreach System - Main Entry Point
Fetches news from RSS feeds and generates personalized outreach messages
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

# Import modules
from src.news_scraper import scrape_news
from src.article_processor import process_articles
from src.message_handler import save_messages
from src.deduplicator import deduplicate_messages
from src.slack_notifier import SlackNotifier


def load_config():
    """Load configuration with environment variable support"""
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        # Override with environment variables
        if os.getenv('CLARIFAI_PAT'):
            config['clarifai']['pat'] = os.getenv('CLARIFAI_PAT')

        # Validate required fields
        if not config['clarifai']['pat']:
            raise ValueError("CLARIFAI_PAT not found in environment variables or config")

        return config
    except FileNotFoundError:
        logging.error("config.yaml not found. Please create one from the template.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)


def setup_logging(local_mode=False):
    """Setup logging for local or production mode"""
    level = logging.DEBUG if local_mode else logging.INFO
    format_str = '%(asctime)s - %(levelname)s - %(message)s'

    handlers = [logging.StreamHandler()]

    if not local_mode:
        # Add file handler for production
        os.makedirs('logs', exist_ok=True)
        log_file = f"logs/outreach_{datetime.now().strftime('%Y%m%d')}.log"
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers
    )


def generate_summary(articles, messages):
    """Generate summary report of the run"""
    summary = {
        'timestamp': datetime.now().isoformat(),
        'articles_processed': len(articles),
        'messages_generated': len(messages),
        'companies': list(set([m.get('company_name', 'Unknown') for m in messages])),
        'event_types': {}
    }

    # Count event types
    for msg in messages:
        event_type = msg.get('event_type', 'Unknown')
        summary['event_types'][event_type] = summary['event_types'].get(event_type, 0) + 1

    return summary


def main():
    """Main execution flow"""
    # Load environment variables from .env file if it exists
    load_dotenv()

    # Detect if running locally
    local_mode = os.path.exists('.env') or os.getenv('LOCAL_DEV') == 'true'

    # Setup logging
    setup_logging(local_mode)

    logging.info("=" * 60)
    logging.info("Starting Automated Sales Outreach System")
    logging.info(f"Mode: {'Local Development' if local_mode else 'Production'}")
    logging.info("=" * 60)

    try:
        # Load configuration
        config = load_config()
        logging.info(f"Configuration loaded successfully")
        logging.info(f"RSS Feeds configured: {len(config['rss_feeds'])}")

        # Step 1: Scrape news from RSS feeds
        logging.info("\n--- Phase 1: Scraping News Feeds ---")
        articles = scrape_news(config)
        logging.info(f"Found {len(articles)} recent articles")

        if not articles:
            logging.warning("No articles found. Exiting.")
            return

        # Step 2: Process articles and generate messages
        logging.info("\n--- Phase 2: Processing Articles ---")
        messages = process_articles(articles, config)
        logging.info(f"Generated {len(messages)} messages")

        if not messages:
            logging.warning("No messages generated. Exiting.")
            return

        # Step 2.5: Deduplicate messages for same company/event (if enabled)
        if config.get('deduplicate_events', True):
            logging.info("\n--- Phase 2.5: Deduplicating Messages ---")
            messages_before = len(messages)
            messages = deduplicate_messages(messages, config)
            if len(messages) < messages_before:
                logging.info(f"Removed {messages_before - len(messages)} duplicate event(s)")
            logging.info(f"Final message count: {len(messages)}")
        else:
            logging.info("\n--- Phase 2.5: Deduplication disabled ---")

        # Step 3: Save messages to output file
        logging.info("\n--- Phase 3: Saving Messages ---")
        output_file = save_messages(messages, config['output'])
        logging.info(f"Messages saved to: {output_file}")

        # Generate and log summary
        summary = generate_summary(articles, messages)
        logging.info("\n" + "=" * 60)
        logging.info("RUN SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Timestamp: {summary['timestamp']}")
        logging.info(f"Articles Processed: {summary['articles_processed']}")
        logging.info(f"Messages Generated: {summary['messages_generated']}")
        logging.info(f"Companies Found: {', '.join(summary['companies'][:5])}")
        if len(summary['companies']) > 5:
            logging.info(f"  ... and {len(summary['companies']) - 5} more")
        logging.info(f"Event Types: {summary['event_types']}")
        logging.info(f"Output File: {output_file}")
        logging.info("=" * 60)

        # Step 4: Send Slack notification (if configured)
        logging.info("\n--- Phase 4: Sending Notifications ---")
        slack_notifier = SlackNotifier(config)
        if slack_notifier.is_enabled():
            # Send notification based on configuration
            notification_type = config.get('slack', {}).get('notification_type', 'detailed')
            if notification_type == 'summary':
                success = slack_notifier.send_summary_notification(messages, output_file, summary)
            else:
                success = slack_notifier.send_detailed_notification(messages, output_file, summary)
            
            if success:
                logging.info(f"✓ Slack {notification_type} notification sent successfully")
            else:
                logging.warning("✗ Failed to send Slack notification")
        else:
            logging.info("Slack notifications not configured or disabled - skipping")

        logging.info("\n✓ Outreach generation completed successfully!")

    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
