"""
News Scraper Module
Fetches news from RSS feeds and returns recent articles
"""

import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict


def fetch_rss_feed(feed_config: Dict, limit_per_feed: int = 10, article_age_hours: int = 24) -> List[Dict]:
    """
    Fetch news from a single RSS feed

    Args:
        feed_config: Dictionary containing feed name, url, and type
        limit_per_feed: Maximum articles to fetch from this feed
        article_age_hours: Maximum age of articles in hours (default: 24)

    Returns:
        List of article dictionaries
    """
    url = feed_config['url']
    feed_name = feed_config['name']
    feed_type = feed_config.get('type', 'custom_rss')

    logging.info(f"Fetching RSS feed: {feed_name} ({feed_type})")

    try:
        # Parse RSS feed with headers to avoid blocking
        feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        if feed.bozo and hasattr(feed, 'bozo_exception'):
            logging.warning(f"Feed parsing warning for {feed_name}: {feed.bozo_exception}")

        # Filter for recent articles based on configured age
        cutoff_date = datetime.now() - timedelta(hours=article_age_hours)
        recent_articles = []
        total_entries = len(feed.entries)
        filtered_count = 0

        for entry in feed.entries[:limit_per_feed * 3]:  # Fetch more entries to account for filtering
            try:
                # Parse publication date (handle different date formats)
                pub_date = None

                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6])
                else:
                    # Fallback to current time if no date available
                    pub_date = datetime.now()

                # Only include recent articles
                if pub_date > cutoff_date:
                    article = {
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'summary': entry.get('summary', entry.get('description', '')),
                        'published': pub_date.isoformat(),
                        'source': feed_name,
                        'feed_type': feed_type
                    }
                    recent_articles.append(article)

                    # Stop if we have enough recent articles
                    if len(recent_articles) >= limit_per_feed:
                        break
                else:
                    # Article too old, count it
                    filtered_count += 1

            except Exception as e:
                logging.warning(f"Error parsing entry from {feed_name}: {e}")
                continue

        # Log filtering statistics
        age_hours = article_age_hours
        logging.info(f"✓ Found {len(recent_articles)} recent articles from {feed_name} (filtered {filtered_count} older than {age_hours}h)")
        return recent_articles

    except Exception as e:
        logging.error(f"Error fetching feed {feed_name}: {e}")
        return []


def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """
    Remove duplicate articles based on URL

    Args:
        articles: List of article dictionaries

    Returns:
        Deduplicated list of articles
    """
    seen_urls = set()
    unique_articles = []

    for article in articles:
        url = article['url']
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
        else:
            logging.debug(f"Skipping duplicate article: {article['title']}")

    return unique_articles


def scrape_news(config: Dict) -> List[Dict]:
    """
    Main scraping function - processes all RSS feeds

    Args:
        config: Configuration dictionary with RSS feeds and limits

    Returns:
        List of article dictionaries sorted by publication date
    """
    all_articles = []
    rss_feeds = config.get('rss_feeds', [])
    search_limit = config.get('search_limit', 10)
    article_age_hours = config.get('article_age_hours', 24)

    if not rss_feeds:
        logging.warning("No RSS feeds configured")
        return []

    # Calculate limit per feed (distribute evenly)
    limit_per_feed = max(1, search_limit // len(rss_feeds))

    logging.info(f"Processing {len(rss_feeds)} RSS feed(s)")
    logging.info(f"Target: {search_limit} total articles (~{limit_per_feed} per feed)")
    logging.info(f"Article age filter: last {article_age_hours} hours")

    # Fetch from each feed
    for feed_config in rss_feeds:
        try:
            articles = fetch_rss_feed(feed_config, limit_per_feed, article_age_hours)
            all_articles.extend(articles)
        except Exception as e:
            logging.error(f"Error processing feed {feed_config.get('name', 'Unknown')}: {e}")
            continue

    # Deduplicate articles
    all_articles = deduplicate_articles(all_articles)

    # Sort by publication date (most recent first)
    all_articles.sort(key=lambda x: x['published'], reverse=True)

    # Return up to the configured limit
    result = all_articles[:search_limit]

    logging.info(f"Total articles after deduplication: {len(result)}")

    return result
