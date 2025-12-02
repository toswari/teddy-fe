#!/usr/bin/env python
"""
Combined extraction and Slack notification
Extracts OpenRouter stats and sends to Slack in one operation
No intermediate file writes
"""

import sys
import asyncio
from extract_stats import OpenRouterStatsExtractor
from slack_notifier import SlackStatsNotifier
from config import load_models
from datetime import datetime, timezone


async def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <model_slug>")
        print(f"   or: {sys.argv[0]} --all")
        return 1

    if sys.argv[1] == "--all":
        # Process all configured models
        models = load_models()
        print(f"Processing {len(models)} models...\n")

        for model in models:
            print("=" * 60)
            result = await extract_and_notify_model(model["slug"])
            if result != 0:
                print(f"[ERROR] Failed to process {model['slug']}")

        return 0
    else:
        # Process single model
        return await extract_and_notify_model(sys.argv[1])


async def extract_and_notify_model(model_slug: str) -> int:
    """Extract and notify for a single model"""
    try:
        # Extract
        print(f"Extracting stats for {model_slug}...")

        extractor = OpenRouterStatsExtractor(model_slug)
        providers = await extractor.extract()

        # Build report
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model_slug,
            "url": extractor.url,
            "providers": providers,
        }

        # Print extracted data
        print(extractor.generate_report(providers))

        # Send to Slack
        print("\nSending to Slack...")
        notifier = SlackStatsNotifier(model_slug)
        message = notifier.format_message(report)

        if notifier.send(message):
            print("[OK] Complete\n")
            return 0
        else:
            print("[ERROR] Failed to send\n")
            return 1

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
