"""
Slack Bot Integration for OpenRouter Stats
Sends extracted stats to a Slack channel via bot token
Routes different models to different channels based on config
"""

import json
import sys
import os
from typing import Optional
import requests
from config import get_model_config


class SlackStatsNotifier:
    """Send OpenRouter stats to Slack."""

    def __init__(self, model_slug: str, bot_token: Optional[str] = None):
        """Initialize the notifier."""
        self.model_slug = model_slug
        self.config = get_model_config(model_slug)

        if not bot_token:
            bot_token = self._get_bot_token_from_env()

        self.bot_token = bot_token
        self.api_url = "https://slack.com/api/chat.postMessage"

        print("[DEBUG] Slack bot initialized")

    def _get_bot_token_from_env(self) -> str:
        """Get Slack bot token from environment variable."""
        bot_token = os.environ.get("OPENROUTER_SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError(
                "OPENROUTER_SLACK_BOT_TOKEN environment variable not set. "
                "Set it with your Slack bot token."
            )
        return bot_token

    def _get_status_emoji(self, uptime: Optional[float]) -> str:
        """Get emoji for uptime status."""
        if uptime is None:
            return "⚠️"
        elif uptime >= 99.9:
            return "🟢"
        elif uptime >= 99:
            return "🟡"
        elif uptime >= 95:
            return "🟠"
        else:
            return "🔴"

    def _get_alert_color(self, uptime: Optional[float]) -> str:
        """Get color for Slack message based on uptime level."""
        if uptime is None:
            return "#999999"  # Gray for unknown
        elif uptime >= 99.9:
            return "#36a64f"  # Green - excellent
        elif uptime >= 99:
            return "#ffd700"  # Gold - good
        elif uptime >= 95:
            return "#ff9900"  # Orange - warning
        else:
            return "#ff0000"  # Red - critical

    def _get_alert_title(self, uptime: Optional[float]) -> str:
        """Get alert title based on uptime level."""
        if uptime is None:
            return "Unknown Status"
        elif uptime >= 99.9:
            return "Excellent"
        elif uptime >= 99:
            return "Good"
        elif uptime >= 95:
            return "Warning"
        else:
            return "Critical"

    def format_message(self, report: dict) -> dict:
        """Format report data as a Slack message with uptime metrics and model link."""
        providers = report.get("providers", [])
        model = report.get("model", "Unknown")
        timestamp = report.get("timestamp", "Unknown")

        # Create provider blocks with color coding
        provider_blocks = []

        for provider in providers:
            uptime = provider.get("uptime_percent", "N/A")
            latency = provider.get("latency_s", "N/A")
            throughput = provider.get("throughput_tps", "N/A")
            timeline = provider.get("timeline", {})

            status_emoji = self._get_status_emoji(uptime)
            alert_title = self._get_alert_title(uptime)

            uptime_str = f"{uptime}%" if uptime != "N/A" else "N/A"
            latency_str = f"{latency}s" if latency != "N/A" else "N/A"
            throughput_str = f"{throughput} tps" if throughput != "N/A" else "N/A"

            # Build stats text with current stats
            stats_text = f"{status_emoji} {alert_title}\n"
            stats_text += f"Uptime {uptime_str} | Latency {latency_str} | Throughput {throughput_str}"

            provider_blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": stats_text}}
            )

            # Add degraded times if available (no separate title, just the times)
            if timeline and "degraded_count" in timeline:
                degraded = timeline.get("degraded_count", 0)
                if degraded > 0:
                    degraded_periods = timeline.get("degraded_periods", [])
                    if degraded_periods:
                        # Format the timestamps
                        times_text = ", ".join(degraded_periods[:5])  # Show first 5
                        if len(degraded_periods) > 5:
                            times_text += f", +{len(degraded_periods) - 5} more"
                        degraded_text = f"Degraded: {times_text}"
                    else:
                        degraded_text = f"Degraded: {degraded} hours"
                    provider_blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": degraded_text},
                        }
                    )

        # Build the full message with model-specific link (no preview)
        display_name = self.config.display_name
        model_url = f"openrouter.ai/{model}"
        message = {
            "channel": self.config.slack_channel,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{display_name}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Updated: {timestamp}\n<{model_url}>",
                    },
                },
                {"type": "divider"},
                *provider_blocks,
            ],
            "unfurl_links": False,
            "unfurl_media": False,
        }

        return message

    def send(self, message: dict) -> bool:
        """Send message to Slack using bot token."""
        try:
            # Extract channel from message
            channel = message.get("channel")
            if not channel:
                raise ValueError("Channel not specified in message")

            # Prepare message for API
            blocks = message.get("blocks", [])

            # Post the message
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "channel": channel,
                    "blocks": blocks,
                    "username": "OpenRouter Status",
                },
                timeout=10,
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                print(f"[ERROR] Slack API error: {error}")
                return False

            print(f"[OK] Message sent to {channel}")
            return True

        except requests.RequestException as e:
            print(f"[ERROR] Failed to send to Slack: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False


def send_stats_for_model(model_slug: str, report: dict) -> bool:
    """Send stats for a specific model to Slack."""
    try:
        notifier = SlackStatsNotifier(model_slug)
        message = notifier.format_message(report)
        return notifier.send(message)

    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    """Send stats to Slack from stdin."""
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python slack_notifier.py <model_slug>")
        print("Pass JSON report via stdin")
        return 1

    model_slug = sys.argv[1]

    try:
        # Read report from stdin
        report = json.load(sys.stdin)

        # Verify report is for the right model
        if report.get("model") != model_slug:
            print(f"[ERROR] Report is for {report.get('model')}, not {model_slug}")
            return 1

        print(f"Sending stats for {model_slug} to Slack...")
        success = send_stats_for_model(model_slug, report)
        return 0 if success else 1

    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


