import feedparser
import logging
import requests
import email.utils
from datetime import datetime, timedelta
from typing import List, Dict
import urllib3

# Silence noisy SSL warnings when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _first(*candidates):
    """Return the first non-None, non-empty value (strips strings)."""
    for c in candidates:
        if c:
            return c.strip() if isinstance(c, str) else c
    return ""


def fetch_rss_feed(
    feed_config: Dict,
    limit_per_feed: int = 10,
    article_age_hours: int = 24,
    verify_ssl: bool = True,
    timeout: int = 15,
) -> List[Dict]:
    """
    Fetch a single feed with full control over headers and SSL.
    Handles every known variation of missing tags.
    """
    url = feed_config["url"]
    feed_name = feed_config["name"]
    feed_type = feed_config.get("type", "custom_rss")

    logging.info(f"Fetching RSS feed: {feed_name} ({feed_type})")

    # ----- browser headers -----
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, application/atom+xml, "
            "application/xml, text/xml, application/json;q=0.9, */*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }

    session = requests.Session()
    session.headers.update(headers)

    # ----- HTTP request -----
    try:
        resp = session.get(
            url, timeout=timeout, verify=verify_ssl, allow_redirects=True
        )
        resp.raise_for_status()
    except requests.exceptions.SSLError as ssl_err:
        logging.error(f"SSL error for {feed_name}: {ssl_err}")
        if not verify_ssl:
            logging.info(f"Retrying {feed_name} with verify=False")
            return fetch_rss_feed(
                feed_config,
                limit_per_feed,
                article_age_hours,
                verify_ssl=False,
                timeout=timeout,
            )
        return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for {feed_name}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected HTTP error for {feed_name}: {e}")
        return []

    # ----- feed parsing -----
    try:
        # Check if response looks like HTML instead of RSS/XML
        content_str = resp.content.decode('utf-8', errors='ignore')[:1000]
        if content_str.strip().lower().startswith('<!doctype html') or \
           content_str.strip().lower().startswith('<html') or \
           'RSS feeds are disabled on this site' in content_str:
            logging.error(f"Feed URL returned HTML content instead of RSS for {feed_name}")
            return []
        
        # Try to parse with different encoding options to handle malformed XML
        feed = None
        try:
            # First try with original content
            feed = feedparser.parse(resp.content)
        except Exception:
            try:
                # Try with UTF-8 encoding and error handling
                content_utf8 = resp.content.decode('utf-8', errors='replace')
                feed = feedparser.parse(content_utf8)
            except Exception:
                try:
                    # Try with latin-1 encoding as fallback
                    content_latin1 = resp.content.decode('latin-1', errors='replace')
                    feed = feedparser.parse(content_latin1)
                except Exception:
                    # Last resort: clean up common problematic characters
                    content_clean = resp.content.decode('utf-8', errors='replace')
                    # Remove common problematic characters
                    content_clean = content_clean.replace('\x00', '').replace('\x08', '').replace('\x0b', '').replace('\x0c', '')
                    # Remove non-printable characters except newlines and tabs
                    content_clean = ''.join(char for char in content_clean if ord(char) >= 32 or char in '\n\r\t')
                    feed = feedparser.parse(content_clean)
        
        if not feed:
            logging.error(f"feedparser failed on {feed_name}: Could not parse with any encoding")
            return []
            
    except Exception as e:
        logging.error(f"feedparser failed on {feed_name}: {e}")
        return []

    # Handle malformed XML warnings (common with RSS feeds)
    if feed.bozo and hasattr(feed, "bozo_exception"):
        error_msg = str(feed.bozo_exception)
        
        # Check if we still got some entries despite XML issues
        if hasattr(feed, 'entries') and len(feed.entries) > 0:
            # We got entries despite XML issues - just log as warning and continue
            if "not well-formed" in error_msg or "invalid token" in error_msg:
                logging.warning(f"Feed has XML parsing warnings but extracted {len(feed.entries)} entries from {feed_name}: {error_msg}")
            else:
                logging.warning(f"Feed parsing warning for {feed_name}: {error_msg}")
        else:
            # No entries extracted - this is a real problem
            if "RSS feeds are disabled" in error_msg:
                logging.error(f"RSS feeds disabled for {feed_name}: {error_msg}")
            elif "not well-formed" in error_msg or "invalid token" in error_msg:
                logging.error(f"Feed has severe XML parsing errors for {feed_name}: {error_msg}")
            else:
                logging.error(f"Feed parsing failed for {feed_name}: {error_msg}")
            return []

    cutoff = datetime.now() - timedelta(hours=article_age_hours)
    recent_articles: List[Dict] = []
    older = 0

    # ----- walk entries -----
    for entry in feed.entries[: limit_per_feed * 3]:
        try:
            # ---- TITLE ----
            title = _first(
                entry.get("title"),
                entry.get("title_detail", {}).get("value"),
                entry.get("media_title"),
                "[No Title]",
            )

            # ---- URL ----
            url = _first(
                entry.get("link"),
                entry.get("id"),
                entry.get("guid"),
                entry.get("url"),
                entry.get("links", [{}])[0].get("href"),
                "",
            )

            # ---- SUMMARY / CONTENT ----
            summary = _first(
                entry.get("summary"),
                entry.get("description"),
                entry.get("content", [{}])[0].get("value"),
                entry.get("media_description"),
                entry.get("subtitle"),
                "",
            )

            # ---- DATE ----
            pub_date = None
            for key in ("published_parsed", "updated_parsed", "created_parsed"):
                parsed = entry.get(key)
                if parsed and len(parsed) >= 6:
                    try:
                        pub_date = datetime(*parsed[:6])
                        break
                    except Exception:
                        continue

            # ISO string fallback
            if not pub_date:
                iso = _first(
                    entry.get("published"),
                    entry.get("updated"),
                    entry.get("created"),
                    entry.get("date"),
                )
                if iso:
                    try:
                        pub_date = datetime.fromisoformat(
                            iso.replace("Z", "+00:00")
                        )
                    except Exception:
                        try:
                            # RFC-2822
                            ts = email.utils.parsedate_to_datetime(iso).timestamp()
                            pub_date = datetime.fromtimestamp(ts)
                        except Exception:
                            pass

            if not pub_date:
                pub_date = datetime.now()

            # ---- AGE FILTER ----
            if pub_date <= cutoff:
                older += 1
                continue

            article = {
                "title": title,
                "url": url,
                "summary": summary,
                "published": pub_date.isoformat(),
                "source": feed_name,
                "feed_type": feed_type,
            }
            recent_articles.append(article)

            if len(recent_articles) >= limit_per_feed:
                break

        except Exception as e:
            logging.debug(f"Entry parsing error in {feed_name}: {e}")
            continue

    logging.info(
        f"{feed_name}: {len(recent_articles)} recent "
        f"(filtered {older} older than {article_age_hours}h)"
    )
    return recent_articles


def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """Remove duplicate articles based on URL."""
    seen = set()
    uniq: List[Dict] = []
    for a in articles:
        url = a["url"]
        if url and url not in seen:
            seen.add(url)
            uniq.append(a)
        else:
            logging.debug(f"Skipping duplicate: {a.get('title', 'No title')}")
    return uniq


def scrape_news(config: Dict, verify_ssl: bool = True) -> List[Dict]:
    """
    Main entry point – processes all configured feeds.
    """
    all_articles: List[Dict] = []
    rss_feeds = config.get("rss_feeds", [])
    search_limit = config.get("search_limit", 10)
    article_age_hours = config.get("article_age_hours", 24)

    if not rss_feeds:
        logging.warning("No RSS feeds configured")
        return []

    limit_per_feed = max(1, search_limit // len(rss_feeds))
    logging.info(
        f"Processing {len(rss_feeds)} feed(s) | "
        f"Target: {search_limit} (~{limit_per_feed}/feed) | "
        f"Age filter: {article_age_hours}h | SSL verify: {verify_ssl}"
    )

    for feed_cfg in rss_feeds:
        articles = fetch_rss_feed(
            feed_cfg,
            limit_per_feed=limit_per_feed,
            article_age_hours=article_age_hours,
            verify_ssl=verify_ssl,
        )
        all_articles.extend(articles)

    all_articles = deduplicate_articles(all_articles)
    all_articles.sort(key=lambda x: x["published"], reverse=True)
    result = all_articles[:search_limit]

    logging.info(f"Final result: {len(result)} article(s)")
    return result
