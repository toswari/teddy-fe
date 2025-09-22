# Intercom Metrics & Slack Reporting

This repository extracts Intercom conversation, response, and other metrics and (optionally) publishes a formatted report to Slack.

## Components
- `intercom_metrics.py` – Fetches data from Intercom (admins, conversations with pagination, tags, segments) and produces a timestamped JSON metrics file.
- `slack_reporter.py` – Consumes a metrics JSON file and sends a structured report + escalation alerts to Slack.
