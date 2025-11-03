"""
Message Deduplicator Module
Groups messages by company and event to avoid duplicate outreach
"""

import logging
from typing import List, Dict
from collections import defaultdict


def group_messages_by_company(messages: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group messages by company name

    Args:
        messages: List of message dictionaries

    Returns:
        Dictionary mapping company names to lists of messages
    """
    grouped = defaultdict(list)

    for msg in messages:
        company = msg.get('company_name', 'Unknown')
        grouped[company].append(msg)

    return dict(grouped)


def deduplicate_messages(messages: List[Dict], config: Dict) -> List[Dict]:
    """
    Deduplicate messages for the same company/event

    Groups messages by company, then uses AI to determine if multiple articles
    are about the same event. Keeps the best/most comprehensive message.

    Args:
        messages: List of message dictionaries
        config: Configuration dictionary with Clarifai settings

    Returns:
        Deduplicated list of messages
    """
    if len(messages) <= 1:
        return messages

    logging.info(f"Deduplicating {len(messages)} messages...")

    # Group by company
    company_groups = group_messages_by_company(messages)

    deduplicated = []

    for company, company_messages in company_groups.items():
        if len(company_messages) == 1:
            # Only one message for this company, keep it
            deduplicated.append(company_messages[0])
            logging.debug(f"  {company}: 1 message, keeping")
        else:
            # Multiple messages for same company - check if same event
            logging.info(f"  {company}: {len(company_messages)} messages, checking for duplicates...")

            # Use AI to determine if they're the same event
            kept_messages = deduplicate_company_messages(company_messages, config)
            deduplicated.extend(kept_messages)

            if len(kept_messages) < len(company_messages):
                removed = len(company_messages) - len(kept_messages)
                logging.info(f"  {company}: Merged {removed} duplicate event(s), keeping {len(kept_messages)}")

    logging.info(f"Deduplication complete: {len(messages)} → {len(deduplicated)} messages")

    return deduplicated


def deduplicate_company_messages(company_messages: List[Dict], config: Dict) -> List[Dict]:
    """
    Deduplicate messages for the same company using AI

    Args:
        company_messages: List of messages for the same company
        config: Configuration with Clarifai settings

    Returns:
        Deduplicated list of messages for this company
    """
    from clarifai.client.model import Model
    import json

    # Get Clarifai model
    model_url = config['clarifai']['url']
    pat = config['clarifai']['pat']

    if not pat:
        logging.warning("No Clarifai PAT - skipping AI-based deduplication")
        # Fallback: simple deduplication by event_type
        return simple_deduplicate(company_messages)

    try:
        model = Model(url=model_url, pat=pat)

        # Build comparison prompt
        events_summary = []
        for idx, msg in enumerate(company_messages):
            events_summary.append({
                'id': idx,
                'event_type': msg.get('event_type'),
                'event_details': msg.get('event_details'),
                'article_title': msg.get('article_title'),
                'published': msg.get('published'),
                'source': msg.get('source')
            })

        prompt = f"""Analyze these {len(events_summary)} articles about the same company and determine which ones are covering the SAME event vs DIFFERENT events.

Articles:
{json.dumps(events_summary, indent=2)}

Instructions:
1. Group articles that are about the SAME event (same announcement, just from different sources)
2. Keep articles that are about DIFFERENT events separate
3. For each unique event, pick the article ID with the most comprehensive details

Return JSON with this structure:
{{
    "unique_events": [
        {{
            "event_description": "Brief description of the event",
            "keep_article_id": 0,  // ID of the best article for this event
            "duplicate_ids": [1, 2]  // IDs of other articles covering same event
        }}
    ]
}}

Respond ONLY with valid JSON."""

        # Call Clarifai
        response = model.predict_by_bytes(
            input_bytes=prompt.encode('utf-8'),
            input_type="text"
        )

        # Extract response
        response_text = ""
        if hasattr(response, 'outputs') and response.outputs:
            output = response.outputs[0]
            if hasattr(output, 'data') and hasattr(output.data, 'text'):
                if hasattr(output.data.text, 'raw'):
                    response_text = output.data.text.raw
                elif isinstance(output.data.text, str):
                    response_text = output.data.text

        if not response_text:
            logging.warning("No response from Clarifai for deduplication")
            return simple_deduplicate(company_messages)

        # Parse JSON response
        response_text = response_text.strip()
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')

        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx + 1]
            result = json.loads(json_str)

            # Extract unique messages based on AI decision
            keep_ids = set()
            for event in result.get('unique_events', []):
                keep_id = event.get('keep_article_id')
                if keep_id is not None and 0 <= keep_id < len(company_messages):
                    keep_ids.add(keep_id)

            if keep_ids:
                kept_messages = [company_messages[i] for i in sorted(keep_ids)]
                return kept_messages

        # Fallback if parsing failed
        logging.warning("Could not parse deduplication response, using simple deduplication")
        return simple_deduplicate(company_messages)

    except Exception as e:
        logging.warning(f"Error in AI deduplication: {e}")
        return simple_deduplicate(company_messages)


def simple_deduplicate(company_messages: List[Dict]) -> List[Dict]:
    """
    Simple deduplication fallback - compare event details to find similar events

    Args:
        company_messages: List of messages for same company

    Returns:
        Deduplicated list
    """
    if len(company_messages) == 1:
        return company_messages

    # Group by event type first
    event_type_groups = defaultdict(list)
    for msg in company_messages:
        event_type = msg.get('event_type', 'unknown')
        event_type_groups[event_type].append(msg)

    deduplicated = []

    for event_type, messages in event_type_groups.items():
        if len(messages) == 1:
            deduplicated.append(messages[0])
        else:
            # Multiple messages of same type - compare event details
            # Look for similar events by checking if event_details overlap
            kept = []
            for msg in messages:
                details = msg.get('event_details', '').lower()
                title = msg.get('article_title', '').lower()

                # Check if this is similar to any already kept event
                is_duplicate = False
                for kept_msg in kept:
                    kept_details = kept_msg.get('event_details', '').lower()
                    kept_title = kept_msg.get('article_title', '').lower()

                    # Simple similarity check - if details share key phrases
                    detail_words = set(details.split())
                    kept_words = set(kept_details.split())

                    # If >50% word overlap, consider it the same event
                    if detail_words and kept_words:
                        overlap = len(detail_words & kept_words) / min(len(detail_words), len(kept_words))
                        if overlap > 0.5:
                            is_duplicate = True
                            logging.debug(f"    Found duplicate: '{title[:50]}...' similar to '{kept_title[:50]}...'")
                            break

                if not is_duplicate:
                    kept.append(msg)

            deduplicated.extend(kept)

    return deduplicated
