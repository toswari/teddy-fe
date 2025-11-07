"""
Article Processor Module
Fetches article content and uses Clarifai to extract information and generate messages
"""

import requests
import logging
import json
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from clarifai.client.model import Model


def fetch_article_content(url: str, timeout: int = 5) -> Optional[str]:
    """
    Fetch full article content from URL

    Args:
        url: Article URL
        timeout: Request timeout in seconds

    Returns:
        Article text content or None if failed
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()

        # Get text content
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Limit to first 3000 characters to avoid token limits
        return text[:3000]

    except Exception as e:
        logging.warning(f"Error fetching article content from {url}: {e}")
        return None


def process_with_clarifai(article: Dict, config: Dict) -> Optional[Dict]:
    """
    Process article with Clarifai to extract information and generate message

    Args:
        article: Article dictionary with title, url, summary
        config: Configuration dictionary with Clarifai settings

    Returns:
        Dictionary with extracted information and generated message, or None if failed
    """
    try:
        # Initialize Clarifai model
        model_url = config['clarifai']['url']
        pat = config['clarifai']['pat']

        if not pat:
            raise ValueError("Clarifai PAT token not provided")

        model = Model(url=model_url, pat=pat)

        # Fetch article content (use summary as fallback)
        content = fetch_article_content(article['url'])
        if not content:
            content = article.get('summary', article.get('title', ''))

        # Get background info about our company/product
        background_info = ""
        background_file = config['clarifai'].get('background_info_file', '')
        if background_file:
            try:
                with open(background_file, 'r', encoding='utf-8') as f:
                    background_info = f.read().strip()
            except FileNotFoundError:
                logging.warning(f"Background info file not found: {background_file}")
            except Exception as e:
                logging.warning(f"Error reading background info file: {e}")

        # Get targeting instructions from config
        targeting_instructions = config['clarifai'].get('targeting_instructions', '')
        if not targeting_instructions:
            # Fallback to default instructions if not in config
            targeting_instructions = """INSTRUCTIONS:
1. EXCLUDE these types of companies (NOT good targets):
   - Major AI/ML platform providers (OpenAI, Anthropic, Google AI, Microsoft AI, AWS AI, Meta AI, etc.)
   - Large cloud/infrastructure providers (CoreWeave, Lambda Labs, RunPod, etc.)
   - Pure cybersecurity companies (unless they need computer vision/AI for security applications)
   - Clarifai's direct competitors (other computer vision API providers)
   - Major tech giants (Google, Microsoft, Apple, Meta, Amazon) unless specific business unit with clear use case

2. INCLUDE these types of companies (good targets):
   - Mid-market companies adopting AI for business operations
   - Retail/e-commerce companies needing visual search, content moderation, or product recognition
   - Healthcare/medical companies using AI for imaging or diagnostics
   - Manufacturing companies implementing visual inspection or quality control
   - Media/entertainment companies needing content analysis or automated tagging
   - Startups building AI-powered applications (especially computer vision)
   - Government agencies or contractors with AI initiatives
   - Financial services implementing AI for document processing or fraud detection
   - Companies announcing AI initiatives but lacking the infrastructure

3. Focus on companies with these qualifying events:
   - Funding rounds ($1M-$100M range - not mega-rounds by giants)
   - New AI product launches (especially involving images/video/text processing)
   - Digital transformation initiatives
   - New hires for AI/ML teams
   - Partnerships to build AI capabilities
   - Expansion into new markets requiring AI

4. If no relevant target company is found, set company_name to null"""

        # Build prompt for extraction and message generation
        prompt = f"""You are analyzing news articles to find potential B2B sales opportunities for Clarifai's AI platform. Analyze this article and determine if it mentions a company that could be a good prospect for our computer vision, NLP, and AI inference solutions.

Context - Our Company/Product:
{background_info}

Article Title: {article['title']}
Article Content: {content[:2000]}

{targeting_instructions}

REQUIRED JSON RESPONSE FORMAT (respond with ONLY valid JSON):
{{
    "company_name": "Exact company name mentioned in article OR null if no relevant target",
    "event_type": "funding/product_launch/partnership/acquisition/expansion/hiring OR null",
    "event_details": "Brief 1-2 sentence summary of the event OR null",
    "priority": "high/standard - HIGH for companies with $5M+ funding, clear computer vision needs, or strategic partnerships. STANDARD for smaller opportunities",
    "reasoning": "2-3 sentences explaining why Clarifai should reach out and what specific computer vision/AI capabilities we could provide OR null",
    "linkedin_message": "Professional 2-3 sentence LinkedIn message congratulating them and mentioning relevant Clarifai capabilities (computer vision, AI inference, model hosting) OR null"
}}

CRITICAL: Respond with ONLY the JSON object, no extra text before or after."""

        # Call Clarifai model
        logging.debug(f"Calling Clarifai for: {article['title']}")

        response = model.predict_by_bytes(
            input_bytes=prompt.encode('utf-8'),
            input_type="text"
        )

        # Extract response text
        response_text = ""
        if hasattr(response, 'outputs') and response.outputs:
            output = response.outputs[0]
            if hasattr(output, 'data') and hasattr(output.data, 'text'):
                if hasattr(output.data.text, 'raw'):
                    response_text = output.data.text.raw
                elif isinstance(output.data.text, str):
                    response_text = output.data.text

        if not response_text:
            logging.warning(f"No response text from Clarifai for: {article['title']}")
            return None

        # Parse JSON response
        # Try to extract JSON from response (in case there's extra text)
        response_text = response_text.strip()
        
        # Try multiple approaches to extract JSON
        result = None
        
        # Approach 1: Try parsing the entire response as JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Approach 2: Find JSON object in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON parsing failed for: {article['title']} - {e}")
                    logging.debug(f"Attempted to parse: {json_str[:200]}...")
                    return None
            else:
                logging.warning(f"Could not find JSON in response for: {article['title']}")
                logging.debug(f"Response text: {response_text[:300]}...")
                return None
        
        if not isinstance(result, dict):
            logging.warning(f"Response is not a JSON object for: {article['title']}")
            return None

        # Validate required fields - company_name can be null, but we need the other fields if there's a company
        company_name = result.get('company_name')
        linkedin_message = result.get('linkedin_message')
        reasoning = result.get('reasoning')
        
        # Debug logging to see what we got
        logging.debug(f"Response fields - Company: {company_name}, Message: {bool(linkedin_message)}, Reasoning: {bool(reasoning)}")
        
        # If no company identified, that's valid (not relevant to us)
        if not company_name or company_name == "null" or company_name.lower() == "null":
            logging.debug(f"No relevant company identified for: {article['title']}")
            return None
            
        # If company identified, we need message and reasoning
        if not linkedin_message or not reasoning:
            logging.warning(f"Missing message or reasoning for company '{company_name}' in: {article['title']}")
            logging.debug(f"Full response: {json.dumps(result, indent=2)}")
            return None

        # Add article metadata
        result['article_url'] = article['url']
        result['article_title'] = article['title']
        result['published'] = article['published']
        result['source'] = article['source']

        logging.info(f"✓ Processed: {result.get('company_name', 'Unknown')} - {result.get('event_type', 'Unknown')}")

        return result

    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error for {article['title']}: {e}")
        logging.debug(f"Response was: {response_text}")
        return None
    except Exception as e:
        logging.error(f"Error processing article with Clarifai: {e}")
        return None


def process_articles(articles: List[Dict], config: Dict) -> List[Dict]:
    """
    Process multiple articles and generate messages

    Args:
        articles: List of article dictionaries
        config: Configuration dictionary

    Returns:
        List of message dictionaries
    """
    messages = []
    message_limit = config.get('message_limit', 20)

    logging.info(f"Processing up to {len(articles)} articles (limit: {message_limit} messages)")

    for idx, article in enumerate(articles, 1):
        if len(messages) >= message_limit:
            logging.info(f"Reached message limit ({message_limit}). Stopping processing.")
            break

        logging.info(f"[{idx}/{len(articles)}] Processing: {article['title'][:60]}...")

        try:
            result = process_with_clarifai(article, config)

            if result:
                messages.append(result)
                logging.info(f"✓ Added message for {result.get('company_name')} ({result.get('event_type', 'Unknown')})")
            else:
                logging.debug(f"Skipping article (no relevant company): {article['title'][:80]}...")

            # Small delay to avoid rate limiting
            time.sleep(0.2)

        except Exception as e:
            logging.error(f"Error processing article {idx}: {e}")
            continue

    logging.info(f"Successfully generated {len(messages)} messages from {len(articles)} articles")

    return messages
