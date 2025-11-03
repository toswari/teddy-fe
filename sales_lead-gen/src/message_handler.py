"""
Message Handler Module
Formats and saves generated messages to output files
"""

import json
import csv
import os
import logging
from datetime import datetime
from typing import List, Dict


def save_messages(messages: List[Dict], output_config: Dict) -> str:
    """
    Save generated messages to file in specified format

    Args:
        messages: List of message dictionaries
        output_config: Output configuration (format, filename, etc.)

    Returns:
        Path to the output file
    """
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_template = output_config.get('filename', 'generated_messages_{date}.json')
    filename = filename_template.format(date=timestamp)
    filepath = os.path.join('output', filename)

    output_format = output_config.get('format', 'json').lower()
    include_metadata = output_config.get('include_metadata', True)

    logging.info(f"Saving {len(messages)} messages to {filepath} (format: {output_format})")

    try:
        if output_format == 'json':
            save_as_json(messages, filepath, include_metadata)
        elif output_format == 'csv':
            save_as_csv(messages, filepath)
        elif output_format == 'txt':
            save_as_txt(messages, filepath)
        else:
            logging.warning(f"Unknown format '{output_format}', defaulting to JSON")
            save_as_json(messages, filepath, include_metadata)

        logging.info(f"✓ Messages saved successfully to {filepath}")
        return filepath

    except Exception as e:
        logging.error(f"Error saving messages: {e}")
        raise


def save_as_json(messages: List[Dict], filepath: str, include_metadata: bool = True):
    """Save messages as JSON file"""
    output_data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_messages': len(messages),
            'version': '1.0'
        } if include_metadata else {},
        'messages': messages
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def save_as_csv(messages: List[Dict], filepath: str):
    """Save messages as CSV file"""
    if not messages:
        logging.warning("No messages to save to CSV")
        return

    # Define CSV columns
    fieldnames = [
        'company_name',
        'event_type',
        'event_details',
        'reasoning',
        'linkedin_message',
        'article_title',
        'article_url',
        'published',
        'source'
    ]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(messages)


def save_as_txt(messages: List[Dict], filepath: str):
    """Save messages as formatted text file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("GENERATED OUTREACH MESSAGES\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Messages: {len(messages)}\n")
        f.write("=" * 80 + "\n\n")

        for idx, msg in enumerate(messages, 1):
            f.write(f"MESSAGE #{idx}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Company: {msg.get('company_name', 'N/A')}\n")
            f.write(f"Event Type: {msg.get('event_type', 'N/A')}\n")
            f.write(f"Event Details: {msg.get('event_details', 'N/A')}\n")
            f.write(f"Source: {msg.get('article_title', 'N/A')}\n")
            f.write(f"URL: {msg.get('article_url', 'N/A')}\n")
            f.write(f"Published: {msg.get('published', 'N/A')}\n")
            f.write("\nREASONING FOR OUTREACH:\n")
            f.write("-" * 80 + "\n")
            f.write(msg.get('reasoning', 'N/A'))
            f.write("\n\nLINKEDIN MESSAGE:\n")
            f.write("-" * 80 + "\n")
            f.write(msg.get('linkedin_message', 'N/A'))
            f.write("\n\n" + "=" * 80 + "\n\n")


def generate_summary_report(messages: List[Dict]) -> Dict:
    """
    Generate a summary report of the messages

    Args:
        messages: List of message dictionaries

    Returns:
        Summary statistics dictionary
    """
    companies = set()
    event_types = {}
    sources = {}

    for msg in messages:
        # Track companies
        company = msg.get('company_name', 'Unknown')
        if company:
            companies.add(company)

        # Track event types
        event_type = msg.get('event_type', 'Unknown')
        event_types[event_type] = event_types.get(event_type, 0) + 1

        # Track sources
        source = msg.get('source', 'Unknown')
        sources[source] = sources.get(source, 0) + 1

    summary = {
        'total_messages': len(messages),
        'unique_companies': len(companies),
        'companies': sorted(list(companies)),
        'event_types': event_types,
        'sources': sources,
        'generated_at': datetime.now().isoformat()
    }

    return summary
