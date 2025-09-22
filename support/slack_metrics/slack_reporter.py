#!/usr/bin/env python3
"""
Slack Reporter for Intercom Metrics

This script reads Intercom metrics data and posts formatted reports to Slack.
Supports both webhook URLs and Slack API tokens.
"""

import requests
import json
import sys
import glob
import os
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv
from statistics import mean, median

# Load environment variables
load_dotenv()
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

class SlackReporter:
    def __init__(self, webhook_url: str = None, bot_token: str = None):
        """Initialize the Slack reporter.
        
        Args:
            webhook_url: Slack webhook URL for posting messages
            bot_token: Slack bot token for API access
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        
        if not webhook_url and not bot_token:
            raise ValueError("Either webhook_url or bot_token must be provided")
    
    def send_webhook_message(self, message: str, channel: str = None) -> bool:
        """Send message via Slack webhook.
        
        Args:
            message: Message text to send
            channel: Channel to send to (optional for webhooks)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            print("No webhook URL configured")
            return False
            
        payload = {"text": message}
        if channel:
            payload["channel"] = channel
            
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending webhook message: {e}")
            return False
    
    def test_bot_permissions(self) -> Dict:
        """Test bot permissions and scopes."""
        if not self.bot_token:
            return {"error": "No bot token"}
            
        url = "https://slack.com/api/auth.test"
        headers = {'Authorization': f'Bearer {self.bot_token}'}
        
        try:
            response = requests.get(url, headers=headers)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def resolve_channel_id(self, channel: str) -> str:
        """Convert channel name or user handle to proper channel/user ID."""
        try:
            # If it starts with @ it's a user, we need to handle DM specially
            if channel.startswith('@'):
                # For file uploads to users, we need to use conversations.open to get DM channel
                # But since that's complex and the user likely wants DM functionality,
                # let's try a simple approach: remove @ and see if it works
                return channel[1:]  # Remove @ symbol
            # If it starts with # it's a channel, convert to channel ID  
            elif channel.startswith('#'):
                channel_name = channel[1:]
                print(f"Looking up channel: {channel_name}")
                response = requests.get(
                    "https://slack.com/api/conversations.list",
                    headers={'Authorization': f'Bearer {self.bot_token}'}
                )
                if response.ok:
                    data = response.json()
                    print(f"Conversations API response: {data.get('ok', False)}")
                    if data.get('ok'):
                        channels = data.get('channels', [])
                        print(f"Found {len(channels)} channels")
                        for ch in channels:
                            ch_name = ch.get('name', '')
                            ch_id = ch.get('id', '')
                            print(f"Checking channel: #{ch_name} -> {ch_id}")
                            if ch_name == channel_name:
                                print(f"Found match: #{channel_name} -> {ch_id}")
                                return ch_id
                    else:
                        print(f"Conversations API error: {data.get('error', 'unknown')}")
                print(f"No match found for channel: {channel_name}")
            return channel
        except Exception as e:
            print(f"Channel resolution error: {e}")
            return channel

    def upload_file_to_slack(self, file_path: str, channel: str, title: str = None, initial_comment: str = None) -> bool:
        """Upload a file to Slack via API.
        
        Args:
            file_path: Path to file to upload
            channel: Channel to upload to
            title: Title for the file
            initial_comment: Comment to post with file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token:
            print("No bot token configured for file upload")
            return False
            
        # Resolve channel to proper ID
        resolved_channel = self.resolve_channel_id(channel)
        print(f"Resolved channel '{channel}' to ID '{resolved_channel}'")
            
        # Use the modern 3-step file upload process
        try:
            # Step 1: Get upload URL
            print("Step 1: Getting upload URL...")
            
            # Get file info
            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            
            get_url_response = requests.post(
                "https://slack.com/api/files.getUploadURLExternal",
                headers={'Authorization': f'Bearer {self.bot_token}'},
                data={
                    'filename': filename,
                    'length': file_size
                }
            )
            
            if not get_url_response.ok:
                print(f"Failed to get upload URL: {get_url_response.status_code}")
                return False
                
            url_result = get_url_response.json()
            if not url_result.get('ok', False):
                print(f"Get upload URL error: {url_result.get('error', 'Unknown error')}")
                return False
            
            upload_url = url_result['upload_url']
            file_id = url_result['file_id']
            
            # Step 2: Upload file to the URL
            print("Step 2: Uploading file...")
            with open(file_path, 'rb') as file:
                upload_response = requests.post(
                    upload_url,
                    files={'file': file}
                )
            
            if not upload_response.ok:
                print(f"File upload failed: {upload_response.status_code}")
                return False
            
            # Step 3: Complete the upload and share to channel
            print("Step 3: Completing upload...")
            complete_response = requests.post(
                "https://slack.com/api/files.completeUploadExternal",
                headers={'Authorization': f'Bearer {self.bot_token}'},
                data={
                    'files': json.dumps([{
                        'id': file_id,
                        'title': title or filename
                    }]),
                    'channel_id': resolved_channel,
                    'initial_comment': initial_comment or f"📈 {title or 'Chart'}"
                }
            )
            
            if not complete_response.ok:
                print(f"Complete upload failed: {complete_response.status_code}")
                return False
                
            complete_result = complete_response.json()
            if complete_result.get('ok', False):
                print("File uploaded successfully using modern API!")
                return True
            else:
                print(f"Complete upload error: {complete_result.get('error', 'Unknown error')}")
                print(f"Complete upload response: {complete_result}")
                print(f"Channel used: {resolved_channel}")
                print(f"File ID used: {file_id}")
                return False
                
        except Exception as e:
            print(f"Modern file upload error: {e}")
            return False

    def send_api_message(self, message: str, channel: str) -> bool:
        """Send message via Slack API.
        
        Args:
            message: Message text to send
            channel: Channel to send to (required for API)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token:
            print("No bot token configured")
            return False
            
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            'Authorization': f'Bearer {self.bot_token}',
            'Content-Type': 'application/json'
        }
        payload = {
            "channel": channel,
            "text": message
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            if not result.get('ok', False):
                print(f"Slack API error: {result.get('error', 'Unknown error')}")
                return False
                
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending API message: {e}")
            return False
    
    def send_message(self, message: str, channel: str = None) -> bool:
        """Send message using available method (webhook or API).
        
        Args:
            message: Message text to send
            channel: Channel to send to
            
        Returns:
            True if successful, False otherwise
        """
        if self.webhook_url:
            return self.send_webhook_message(message, channel)
        elif self.bot_token:
            if not channel:
                print("Channel required when using bot token")
                return False
            return self.send_api_message(message, channel)
        else:
            print("No Slack configuration available")
            return False

class IntercomMetricsFormatter:
    @staticmethod
    def _fmt_minutes(value_min: float) -> str:
        """Format minutes as a concise human string (m / h / d).
        Args:
            value_min: Minutes value
        Returns:
            Human readable string
        """
        if value_min is None:
            return "n/a"
        if value_min < 60:
            return f"{value_min:.0f}m"
        hours = value_min / 60
        if hours < 24:
            return f"{hours:.1f}h"
        days = hours / 24
        return f"{days:.1f}d"

    @staticmethod
    def _percentile(values, pct: float):
        if not values:
            return None
        if pct <= 0:
            return min(values)
        if pct >= 100:
            return max(values)
        vals = sorted(values)
        k = (len(vals) - 1) * (pct / 100)
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        if f == c:
            return vals[f]
        d0 = vals[f] * (c - k)
        d1 = vals[c] * (k - f)
        return d0 + d1

    @staticmethod
    def format_kpi_snapshot(data: Dict) -> str:
        """Produce a compact KPI snapshot for quick Slack consumption."""
        ws = data.get("workspace_data", {})
        conv_states = ws.get("conversation_states", {})
        open_convos = conv_states.get("open_conversations", {})
        summary = conv_states.get("summary", {})
        resp24 = ws.get("response_metrics_24h", {})

        open_total = open_convos.get("total_open", 0)
        need_response = summary.get("needs_attention", 0)

        fresh_times = resp24.get('fresh_response_times', [])
        backlog_count = resp24.get('backlog_responses_count', 0)
        fresh_avg = mean(fresh_times) if fresh_times else None
        fresh_p90 = IntercomMetricsFormatter._percentile(fresh_times, 90) if fresh_times else None
        first_resp = resp24.get('first_response_times', [])
        first_avg = mean(first_resp) if first_resp else None

        # Pagination metadata (if present)
        pagination = ws.get('pagination_metadata', {})
        if pagination:
            pages_fetched = pagination.get('pages_fetched')
            page_size = pagination.get('page_size')
            total = pagination.get('total_conversations')
            cap = pagination.get('capped', False)
            cap_note = " CAP" if cap else ""
            pagination_line = f"• Pages: {pages_fetched} x {page_size} (total {total}{cap_note})"
        else:
            pagination_line = None

        parts = [
            "🏁 *Support KPI Snapshot (Last 24h)*",
            f"• Open: {open_total} | Need response: {need_response}",
            f"• Fresh responses: {len(fresh_times)} | Backlog cleared: {backlog_count}",
            f"• First response avg (fresh): {IntercomMetricsFormatter._fmt_minutes(first_avg) if first_avg else 'n/a'}",
            f"• Response avg (fresh): {IntercomMetricsFormatter._fmt_minutes(fresh_avg) if fresh_avg else 'n/a'} | P90: {IntercomMetricsFormatter._fmt_minutes(fresh_p90) if fresh_p90 else 'n/a'}"
        ]
        if pagination_line:
            parts.insert(1, pagination_line)
        return "\n".join(parts)
    @staticmethod
    def format_metrics_summary(data: Dict) -> str:
        """Format the main metrics summary for Slack.
        
        Args:
            data: Intercom metrics data
            
        Returns:
            Formatted Slack message
        """
        workspace_data = data.get("workspace_data", {})
        extraction_date = data.get("extraction_date", "")
        
        # Parse extraction date
        try:
            date_obj = datetime.fromisoformat(extraction_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
        except:
            formatted_date = extraction_date
        
        message_parts = [
            f"📊 *Intercom Metrics Report* - {formatted_date}",
            "",
            "📈 *Overview:*"
        ]
        
        # Basic counts
        admin_count = len(workspace_data.get("admins", {}).get("admins", []))
        company_count = len(workspace_data.get("companies", {}).get("companies", []))
        contact_count = len(workspace_data.get("contacts", {}).get("contacts", []))
        conversation_count = len(workspace_data.get("conversations", {}).get("conversations", []))
        
        message_parts.extend([
            f"• Admins: {admin_count}",
            f"• Companies: {company_count}",
            f"• Contacts: {contact_count}",
            f"• Conversations: {conversation_count}"
        ])
        
        # Conversation counts
        counts = workspace_data.get("conversation_counts", {})
        if "conversation" in counts:
            conv_counts = counts["conversation"]
            message_parts.extend([
                "",
                "💬 *Conversation Status:*",
                f"• Open: {conv_counts.get('open', 'N/A')}",
                f"• Closed: {conv_counts.get('closed', 'N/A')}",
                f"• Assigned: {conv_counts.get('assigned', 'N/A')}",
                f"• Unassigned: {conv_counts.get('unassigned', 'N/A')}"
            ])
        
        # Comprehensive Conversation State Analysis
        conversation_states = workspace_data.get("conversation_states", {})
        state_breakdown = conversation_states.get("state_breakdown", {})
        summary = conversation_states.get("summary", {})
        current_convos = conversation_states.get("open_conversations", {})
        snoozed_convos = conversation_states.get("snoozed_conversations", {})
        
        # Show overall conversation state
        # Safe bool parsing for envs
        def env_bool(name: str, default: str = "false") -> bool:
            val = os.getenv(name, default)
            if val is None:
                return False
            return val.strip().lower() in ("1","true","yes","y","on")

        exclude_spam = env_bool("EXCLUDE_SPAM_CONVERSATIONS", "true")
        spam_note = " (spam filtered)" if exclude_spam else " (includes spam)"
        
        message_parts.extend([
            "",
            f"🔄 *Conversation States{spam_note}:*",
            f"• Open: {state_breakdown.get('open', 0)}",
            f"• Snoozed: {state_breakdown.get('snoozed', 0)}",
            f"• Recently Closed: {state_breakdown.get('closed', 0)}"
        ])
        
        if summary.get("total_active", 0) > 0:
            message_parts.extend([
                "",
                f"📊 *Active Conversations Summary:*",
                f"• Total Active: {summary.get('total_active', 0)} (open + snoozed)",
                f"• Need Response: {summary.get('needs_attention', 0)} urgent",
                f"• On Hold: {summary.get('on_hold', 0)} snoozed"
            ])
        
        # Open conversations details
        if current_convos.get("total_open", 0) > 0:
            message_parts.extend([
                "",
                f"🔄 *Open Conversations Details ({current_convos['total_open']} total):*"
            ])
            
            # Assignment breakdown
            assigned = current_convos.get("assignment_breakdown", {}).get("assigned", 0)
            unassigned = current_convos.get("assignment_breakdown", {}).get("unassigned", 0)
            message_parts.append(f"• Assignment: {assigned} assigned, {unassigned} unassigned")
            
            # Response status breakdown
            response_status = current_convos.get("response_status", {})
            awaiting_agent = response_status.get("awaiting_agent", 0)
            awaiting_customer = response_status.get("awaiting_customer", 0)
            unknown_status = response_status.get("unknown", 0)
            message_parts.append(f"• Response status: {awaiting_agent} awaiting agent, {awaiting_customer} awaiting customer, {unknown_status} unknown")
            
            # Waiting time breakdown
            waiting = current_convos.get("waiting_time_analysis", {})
            if any(waiting.values()):
                message_parts.append(f"• Wait times: <1h({waiting.get('under_1h', 0)}), 1-4h({waiting.get('1h_to_4h', 0)}), 4-24h({waiting.get('4h_to_24h', 0)}), >24h({waiting.get('over_24h', 0)})")
            
            # Priority breakdown
            priorities = current_convos.get("priority_breakdown", {})
            if any(priorities.values()):
                message_parts.append(f"• Priorities: High({priorities.get('high', 0)}), Medium({priorities.get('medium', 0)}), Low({priorities.get('low', 0)})")
            
            # Show top urgent conversations (longest waiting + high priority)
            conversations = current_convos.get("conversations", [])
            urgent_convos = []
            
            # Get conversations that need attention 
            # Prioritize conversations awaiting agent responses
            for convo in conversations:
                response_status = convo.get("response_status", "unknown")
                waiting_hours = convo.get("waiting_hours", 0)
                priority = convo.get("priority", "none")
                assigned_to = convo.get("assigned_to", "Unassigned")
                last_msg = (convo.get("last_message") or "").strip()
                customer_wait = response_status == "awaiting_agent"
                agent_wait = response_status == "awaiting_customer"
                unknown = response_status == "unknown"

                is_urgent = False

                # Core rule: only treat as urgent if customer is waiting OR it's clearly high priority & stale
                if customer_wait:
                    # Customer waiting thresholds
                    if priority == "high" and waiting_hours > 0.5:
                        is_urgent = True
                    elif priority == "medium" and waiting_hours > 1:
                        is_urgent = True
                    elif waiting_hours > 2:  # Any waiting >2h
                        is_urgent = True
                    # Unassigned accelerates
                    if assigned_to == "Unassigned" and waiting_hours > 0.75:
                        is_urgent = True
                elif agent_wait:
                    # Usually not urgent; only flag extreme cases
                    if priority == "high" and waiting_hours > 48:
                        is_urgent = True
                elif unknown:
                    # Much stricter: require both age and signal
                    if priority == "high" and waiting_hours > 4:
                        is_urgent = True
                    elif assigned_to == "Unassigned" and waiting_hours > 8 and last_msg:
                        is_urgent = True
                    # Deprioritize low/no priority unknowns under 24h
                    if waiting_hours < 12 and priority in ["none", "low"]:
                        is_urgent = False

                if is_urgent:
                    urgent_convos.append(convo)
            
            # Sort by priority, response status, and waiting time
            def urgency_score(convo):
                priority_scores = {"high": 100, "medium": 50, "low": 10, "none": 0}
                urgency = priority_scores.get(convo.get("priority", "none"), 0)
                
                # Major boost for conversations awaiting agent response
                response_status = convo.get("response_status", "unknown")
                if response_status == "awaiting_agent":
                    urgency += 200  # Highest urgency - customer waiting for us
                elif response_status == "unknown":
                    urgency += 50   # Medium urgency - unclear status
                elif response_status == "awaiting_customer":
                    urgency += 10   # Lower urgency - we're waiting for customer
                
                # Boost unassigned conversations (especially if customer is waiting)
                if convo.get("assigned_to") == "Unassigned":
                    if response_status == "awaiting_agent":
                        urgency += 100  # Much higher boost if customer is waiting and unassigned
                    else:
                        urgency += 25   # Regular boost for unassigned
                
                # Add waiting time (but less weight if awaiting customer)
                waiting_multiplier = 0.5 if response_status == "awaiting_customer" else 1.0
                urgency += min(convo.get("waiting_hours", 0), 48) * waiting_multiplier
                
                return urgency
            
            urgent_convos.sort(key=urgency_score, reverse=True)
            # Limit total urgent items to a sane number (avoid noise)
            urgent_convos = urgent_convos[:10]
            
            # Show top urgent conversations
            if urgent_convos:
                message_parts.extend([
                    "",
                    f"⚠️ *Currently ({len(urgent_convos)} conversations need attention):*"
                ])
                for i, convo in enumerate(urgent_convos[:5]):  # Show top 5
                    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(convo.get("priority"), "⚪")
                    
                    # Get clean subject/title
                    subject = convo.get("subject", "No subject").strip()
                    if not subject or subject == "No subject":
                        subject = "Untitled conversation"
                    
                    # Get customer name
                    customer = convo.get("customer", "Unknown Customer").strip()
                    
                    # Format assignment and response status
                    assigned_to = convo.get("assigned_to", "Unassigned")
                    response_status = convo.get("response_status", "unknown")
                    
                    # Status indicators
                    if assigned_to == "Unassigned":
                        assignment_status = "🚨 Unassigned"
                    else:
                        assignment_status = f"👤 {assigned_to}"
                    
                    # Response status indicators
                    if response_status == "awaiting_agent":
                        response_indicator = "⏳ Need to respond"
                    elif response_status == "awaiting_customer":
                        response_indicator = "⌛ Awaiting customer"
                    else:
                        response_indicator = "❓ Status unclear"
                    
                    # Create clean, readable format
                    message_parts.append(f"{i+1}. {priority_emoji} **{subject}**")
                    message_parts.append(f"   Customer: {customer} | Wait: {convo.get('waiting_time', '?')} | {assignment_status} | Status: {response_indicator}")
                    
                    # Add context from last message if available and meaningful
                    last_msg = convo.get("last_message", "").strip()
                    if last_msg and len(last_msg) > 3:  # Only show if there's meaningful content
                        if len(last_msg) > 120:
                            last_msg = last_msg[:120] + "..."
                        message_parts.append(f"   💬 \"{last_msg}\"")
                
                if len(urgent_convos) > 5:
                    message_parts.append(f"   ... and {len(urgent_convos) - 5} more urgent conversations")
            else:
                message_parts.extend([
                    "",
                    "✅ *No current conversations detected*"
                ])
        elif current_convos.get("total_open") == 0:
            message_parts.extend([
                "",
                "🔄 *Open Conversations: 0* ✅ All clear!"
            ])
        
        # Snoozed conversations monitoring
        if snoozed_convos.get("total_snoozed", 0) > 0:
            message_parts.extend([
                "",
                f"😴 *Snoozed Conversations ({snoozed_convos['total_snoozed']} total):*"
            ])
            
            # Snoozed status breakdown
            snoozed_response_status = snoozed_convos.get("response_status", {})
            awaiting_agent_snoozed = snoozed_response_status.get("awaiting_agent", 0)
            awaiting_customer_snoozed = snoozed_response_status.get("awaiting_customer", 0)
            
            if awaiting_agent_snoozed > 0 or awaiting_customer_snoozed > 0:
                message_parts.append(f"• Response status: {awaiting_agent_snoozed} awaiting agent, {awaiting_customer_snoozed} awaiting customer")
            
            # Show long-waiting snoozed conversations
            snoozed_conversations = snoozed_convos.get("conversations", [])
            long_snoozed = [c for c in snoozed_conversations if c.get("waiting_hours", 0) > 24]
            
            if long_snoozed:
                message_parts.extend([
                    "",
                    f"⚠️ *Long-Snoozed Conversations ({len(long_snoozed)} >24h):*"
                ])
                for i, convo in enumerate(long_snoozed[:3]):  # Show top 3
                    subject = convo.get("subject", "No subject")
                    customer = convo.get("customer", "Unknown")
                    waiting_time = convo.get("waiting_time", "?")
                    response_status = convo.get("response_status", "unknown")
                    
                    status_emoji = "⏳" if response_status == "awaiting_agent" else "⌛" if response_status == "awaiting_customer" else "❓"
                    
                    message_parts.append(f"{i+1}. {status_emoji} **{subject}**")
                    message_parts.append(f"   Customer: {customer} | Snoozed: {waiting_time}")
                
                if len(long_snoozed) > 3:
                    message_parts.append(f"   ... and {len(long_snoozed) - 3} more long-snoozed conversations")
        
        return "\n".join(message_parts)
    
    @staticmethod
    def format_daily_metrics(data: Dict) -> str:
        """Format daily metrics for Slack.
        
        Args:
            data: Intercom metrics data
            
        Returns:
            Formatted Slack message
        """
        daily_data = data.get("workspace_data", {}).get("daily_metrics", {})
        
        if not daily_data:
            return "📅 *Daily Metrics:* No data available"
        
        message_parts = [
            f"📊 *Historical Context ({daily_data.get('analysis_period_days', 'N/A')} days):*",
            f"• Average per day: {daily_data.get('overall_metrics', {}).get('conversations_per_day', 0):.1f}",
            f"• Busiest day: {daily_data.get('overall_metrics', {}).get('busiest_day', 'N/A')}"
        ]
        
        # Recent days breakdown
        daily_stats = daily_data.get('daily_stats', {})
        if daily_stats:
            message_parts.extend([
                "",
                "📈 *Volume Trends:*"
            ])
            
            sorted_days = sorted(daily_stats.items(), reverse=True)[:7]  # Last 7 days
            for date, stats in sorted_days:
                created = stats.get('conversations_created', 0)
                closed = stats.get('conversations_closed', 0)
                message_parts.append(f"• {date}: {created} created, {closed} closed")
        
        return "\n".join(message_parts)
    
    @staticmethod
    def format_response_times(data: Dict) -> str:
        """Format response time metrics for Slack.
        
        Args:
            data: Intercom metrics data
            
        Returns:
            Formatted Slack message
        """
        response_data = data.get("workspace_data", {}).get("response_metrics", {})
        
        if not response_data:
            return "⏱️ *Response Times:* No data available"
        
        convs_analyzed = response_data.get('conversations_analyzed', 0)
        message_parts = [
            "📈 *Recent Trends (Last 14 Days):*",
            f"• Conversations analyzed: {convs_analyzed}"
        ]

        first_response_times = response_data.get('first_response_times', []) or []
        all_response_times = response_data.get('avg_response_times', []) or []  # legacy field = every agent reply gap

        # Split into operational (<=24h) vs backlog (>24h) to avoid inflation from very old replies
        backlog_cutoff_min = 24 * 60
        op_first = [t for t in first_response_times if t <= backlog_cutoff_min]
        backlog_first = [t for t in first_response_times if t > backlog_cutoff_min]
        op_responses = [t for t in all_response_times if t <= backlog_cutoff_min]
        backlog_responses = [t for t in all_response_times if t > backlog_cutoff_min]

        from statistics import median
        def stats_line(label, arr):
            if not arr:
                return f"• {label}: n/a"
            avg_v = sum(arr)/len(arr)
            med_v = median(arr)
            # simple p90
            sorted_v = sorted(arr)
            if len(sorted_v) == 1:
                p90_v = sorted_v[0]
            else:
                k = (len(sorted_v)-1)*0.9
                f = int(k); c = min(f+1, len(sorted_v)-1)
                if f == c:
                    p90_v = sorted_v[f]
                else:
                    p90_v = sorted_v[f]*(c-k)+sorted_v[c]*(k-f)
            def fmt_min(m):
                if m < 60: return f"{m:.0f}m"
                h = m/60
                if h < 24: return f"{h:.1f}h"
                return f"{h/24:.1f}d"
            return (f"• {label}: avg {fmt_min(avg_v)} | median {fmt_min(med_v)} | p90 {fmt_min(p90_v)} (n={len(arr)})")

        # First response perspective
        message_parts.append(stats_line("First response (operational <=24h)", op_first))
        if backlog_first:
            message_parts.append(stats_line("First response (backlog >24h)", backlog_first))

        # All response gaps perspective
        message_parts.append(stats_line("Response gaps (operational <=24h)", op_responses))
        if backlog_responses:
            message_parts.append(stats_line("Response gaps (backlog >24h)", backlog_responses))

        # Legacy aggregate for backward comparison
        if all_response_times:
            message_parts.append(stats_line("All gaps (raw mix)", all_response_times))

        # Admin performance (still raw but add note if backlog heavy)
        admin_times = response_data.get('response_times_by_admin', {}) or {}
        if admin_times:
            message_parts.extend(["", "👥 *Team Trends (14d response gaps)*:"])
            for admin, times in admin_times.items():
                if not times:
                    continue
                op_admin = [t for t in times if t <= backlog_cutoff_min]
                backlog_admin = [t for t in times if t > backlog_cutoff_min]
                if op_admin:
                    avg_op = sum(op_admin)/len(op_admin)
                    message_parts.append(f"• {admin}: op avg {avg_op/60:.1f}h ({len(op_admin)} ops)" )
                if backlog_admin:
                    avg_b = sum(backlog_admin)/len(backlog_admin)
                    message_parts.append(f"  ↳ backlog avg {avg_b/60:.1f}h ({len(backlog_admin)} backlog)")

        # Small sample warning
        total_samples = len(first_response_times) + len(all_response_times)
        pagination_present = data.get('workspace_data', {}).get('conversations', {}).get('pagination') is not None
        if not pagination_present and (convs_analyzed < 10 or total_samples < 30):
            message_parts.append("\n⚠️ Limited sample (no pagination); figures may not cover all conversations. Set PAGINATE_CONVERSATIONS=true for full coverage.")

        message_parts.append("ℹ️ Operational metrics exclude delays >24h (treated as backlog) to avoid inflating day-to-day performance.")
        return "\n".join(message_parts)
    
    @staticmethod
    def format_full_report(data: Dict) -> str:
        """Format a complete report combining all metrics.
        
        Args:
            data: Intercom metrics data
            
        Returns:
            Formatted Slack message
        """
        sections = [
            IntercomMetricsFormatter.format_metrics_summary(data),
            "",
            IntercomMetricsFormatter.format_24h_response_times(data),
            "",
            IntercomMetricsFormatter.format_response_times(data),
            "",
            IntercomMetricsFormatter.format_daily_metrics(data),
            "", 
            IntercomMetricsFormatter.format_kpi_snapshot(data)
    
        ]
        
        return "\n".join(sections)
    
    @staticmethod
    def format_24h_response_times(data: Dict) -> str:
        """Format 24-hour response time metrics for Slack.
        
        Args:
            data: Intercom metrics data
            
        Returns:
            Formatted Slack message
        """
        response_data_24h = data.get("workspace_data", {}).get("response_metrics_24h", {})

        if not response_data_24h or response_data_24h.get('responses_count', 0) == 0:
            return "🔴 *Current Status (Last 24h):* No admin responses recorded"

        fresh = response_data_24h.get('fresh_response_times', [])
        backlog = response_data_24h.get('backlog_response_times', [])
        first_fresh = response_data_24h.get('first_response_times', [])  # Already fresh only

        def stats_block(label, arr):
            if not arr:
                return f"• {label}: n/a"
            avg_v = mean(arr)
            med_v = median(arr)
            p90_v = IntercomMetricsFormatter._percentile(arr, 90)
            return (f"• {label}: avg {IntercomMetricsFormatter._fmt_minutes(avg_v)} | "
                    f"median {IntercomMetricsFormatter._fmt_minutes(med_v)} | "
                    f"p90 {IntercomMetricsFormatter._fmt_minutes(p90_v)} (n={len(arr)})")

        parts = [
            "🔴 *Current Status (Last 24h):*",
            f"• Conversations with responses: {response_data_24h.get('conversations_analyzed', 0)}",
            f"• Responses: {response_data_24h.get('responses_count', 0)} (fresh: {response_data_24h.get('fresh_responses_count', 0)}, backlog: {response_data_24h.get('backlog_responses_count', 0)})",
            stats_block("First response (fresh)", first_fresh),
            stats_block("Responses (fresh)", fresh),
            stats_block("Responses (backlog)", backlog)
        ]

        # Admin performance (fresh only)
        admin_times = response_data_24h.get('response_times_by_admin', {})
        if admin_times:
            parts.append("")
            parts.append("👥 *Team Fresh Performance:*")
            for admin, times in admin_times.items():
                if times:
                    avg_time = mean(times)
                    med_time = median(times)
                    parts.append(
                        f"• {admin}: avg {IntercomMetricsFormatter._fmt_minutes(avg_time)} | median {IntercomMetricsFormatter._fmt_minutes(med_time)} (n={len(times)})"
                    )

        backlog_admin_times = response_data_24h.get('backlog_response_times_by_admin', {})
        if backlog_admin_times:
            parts.append("")
            parts.append("� *Backlog Clearance:*")
            for admin, times in backlog_admin_times.items():
                if times:
                    avg_time = mean(times)
                    parts.append(
                        f"• {admin}: cleared {len(times)} (avg age {IntercomMetricsFormatter._fmt_minutes(avg_time)})"
                    )

        parts.append("\nℹ️ Fresh = customer message and reply both within 24h. \nℹ️ Backlog = reply today to older customer message (excluded from fresh averages).")
        return "\n".join(parts)

class EscalationAnalyzer:
    """Analyze metrics for concerning trends and threshold breaches."""
    
    def __init__(self, config: Dict = None):
        """Initialize with escalation configuration."""
        self.config = config or self._default_config()
    
    def _default_config(self) -> Dict:
        """Default escalation thresholds and rules."""
        return {
            'response_time_thresholds': {
                'first_response_critical_hours': 24,     # First response > 24h = critical
                'first_response_warning_hours': 12,      # First response > 12h = warning
                'avg_response_critical_hours': 48,       # Average response > 48h = critical
                'avg_response_warning_hours': 24         # Average response > 24h = warning
            },
            'volume_thresholds': {
                'daily_increase_warning_pct': 50,        # Daily volume up 50% = warning
                'daily_decrease_warning_pct': 30,        # Daily volume down 30% = warning
                'weekly_increase_critical_pct': 100,     # Weekly volume up 100% = critical
                'backlog_critical_count': 20,            # 20+ open conversations = critical
                'backlog_warning_count': 10              # 10+ open conversations = warning
            },
            'trend_analysis_days': {
                'short_term': 3,   # Compare last 3 days
                'medium_term': 7,  # Compare last 7 days
                'long_term': 14    # Compare last 14 days
            },
            'notification_channels': {
                'warning': (os.getenv('INTERCOM_SLACK_ALERTS_CHANNEL') or os.getenv('SLACK_ALERTS_CHANNEL', '#alerts-support')),
                'critical': (os.getenv('INTERCOM_SLACK_ALERTS_CHANNEL') or os.getenv('SLACK_ALERTS_CHANNEL', '#alerts-support'))
            }
        }
    
    def analyze_response_times(self, response_data: Dict, response_data_24h: Dict = None) -> Dict:
        """Analyze response time metrics for escalations.

        Uses 14-day aggregates plus 24h fresh metrics (avoids backlog distortion).
        """
        alerts: List[Dict] = []

        # 14-day first response (operational <=24h subset for alert fairness)
        fr_all = response_data.get('first_response_times', [])
        fr_times = [t for t in fr_all if t <= 24*60]
        if fr_times:
            fr_avg_min = sum(fr_times)/len(fr_times)
            fr_avg_h = fr_avg_min/60
            crit_fr = self.config['response_time_thresholds']['first_response_critical_hours']
            warn_fr = self.config['response_time_thresholds']['first_response_warning_hours']
            if fr_avg_h > crit_fr:
                alerts.append({
                    'type':'critical','category':'response_time','metric':'first_response_time_14d',
                    'value':fr_avg_h,'threshold':crit_fr,
                    'message':f"🚨 CRITICAL: Average first response time (14d) is {fr_avg_h:.1f}h (threshold: {crit_fr}h)"})
            elif fr_avg_h > warn_fr:
                alerts.append({
                    'type':'warning','category':'response_time','metric':'first_response_time_14d',
                    'value':fr_avg_h,'threshold':warn_fr,
                    'message':f"⚠️ WARNING: Average first response time (14d) is {fr_avg_h:.1f}h (threshold: {warn_fr}h)"})

        # 14-day overall responses (operational subset)
        all_resp_all = response_data.get('avg_response_times', [])
        all_resp_times = [t for t in all_resp_all if t <= 24*60]
        if all_resp_times:
            avg_resp_min = sum(all_resp_times)/len(all_resp_times)
            avg_resp_h = avg_resp_min/60
            crit_r = self.config['response_time_thresholds']['avg_response_critical_hours']
            warn_r = self.config['response_time_thresholds']['avg_response_warning_hours']
            if avg_resp_h > crit_r:
                alerts.append({
                    'type':'critical','category':'response_time','metric':'avg_response_time_14d',
                    'value':avg_resp_h,'threshold':crit_r,
                    'message':f"🚨 CRITICAL: Average response time (14d) is {avg_resp_h:.1f}h (threshold: {crit_r}h)"})
            elif avg_resp_h > warn_r:
                alerts.append({
                    'type':'warning','category':'response_time','metric':'avg_response_time_14d',
                    'value':avg_resp_h,'threshold':warn_r,
                    'message':f"⚠️ WARNING: Average response time (14d) is {avg_resp_h:.1f}h (threshold: {warn_r}h)"})

        # 24h window (fresh preferred)
        if response_data_24h:
            fresh_first = response_data_24h.get('first_response_times', [])  # already fresh only
            # Only alert on 24h first response if we actually have at least 2 fresh first responses (avoid noise)
            if len(fresh_first) >= 2:
                fresh_first_avg_h = (sum(fresh_first)/len(fresh_first))/60
                crit_fr = self.config['response_time_thresholds']['first_response_critical_hours']
                warn_fr = self.config['response_time_thresholds']['first_response_warning_hours']
                if fresh_first_avg_h > crit_fr:
                    alerts.append({
                        'type':'critical','category':'response_time','metric':'first_response_time_24h',
                        'value':fresh_first_avg_h,'threshold':crit_fr,
                        'message':f"🚨 CRITICAL: Fresh first response avg (24h) {fresh_first_avg_h:.1f}h > {crit_fr}h (n={len(fresh_first)})"})
                elif fresh_first_avg_h > warn_fr:
                    alerts.append({
                        'type':'warning','category':'response_time','metric':'first_response_time_24h',
                        'value':fresh_first_avg_h,'threshold':warn_fr,
                        'message':f"⚠️ WARNING: Fresh first response avg (24h) {fresh_first_avg_h:.1f}h > {warn_fr}h (n={len(fresh_first)})"})

            fresh_resp = response_data_24h.get('fresh_response_times') or []
            # Require at least 3 fresh responses to alert on avg (stability)
            if len(fresh_resp) >= 3:
                fresh_resp_avg_h = (sum(fresh_resp)/len(fresh_resp))/60
                crit_r = self.config['response_time_thresholds']['avg_response_critical_hours']
                warn_r = self.config['response_time_thresholds']['avg_response_warning_hours']
                if fresh_resp_avg_h > crit_r:
                    alerts.append({
                        'type':'critical','category':'response_time','metric':'avg_response_time_24h',
                        'value':fresh_resp_avg_h,'threshold':crit_r,
                        'message':f"🚨 CRITICAL: Fresh response avg (24h) {fresh_resp_avg_h:.1f}h > {crit_r}h (n={len(fresh_resp)})"})
                elif fresh_resp_avg_h > warn_r:
                    alerts.append({
                        'type':'warning','category':'response_time','metric':'avg_response_time_24h',
                        'value':fresh_resp_avg_h,'threshold':warn_r,
                        'message':f"⚠️ WARNING: Fresh response avg (24h) {fresh_resp_avg_h:.1f}h > {warn_r}h (n={len(fresh_resp)})"})

            # If no fresh responses but backlog responses occurred, do NOT create "fresh" alerts.

        return {'alerts': alerts, 'analysis': 'response_time_analysis'}
    
    def analyze_conversation_volume(self, daily_data: Dict, conversation_counts: Dict) -> Dict:
        """Analyze conversation volume trends for escalations."""
        alerts = []
        
        # Check current backlog (open conversations)
        open_count = conversation_counts.get('conversation', {}).get('open', 0)
        unassigned_count = conversation_counts.get('conversation', {}).get('unassigned', 0)
        
        critical_backlog = self.config['volume_thresholds']['backlog_critical_count']
        warning_backlog = self.config['volume_thresholds']['backlog_warning_count']
        
        if open_count > critical_backlog:
            alerts.append({
                'type': 'critical',
                'category': 'volume',
                'metric': 'open_conversations',
                'value': open_count,
                'threshold': critical_backlog,
                'message': f"🚨 CRITICAL: {open_count} open conversations (threshold: {critical_backlog})"
            })
        elif open_count > warning_backlog:
            alerts.append({
                'type': 'warning',
                'category': 'volume',
                'metric': 'open_conversations',
                'value': open_count,
                'threshold': warning_backlog,
                'message': f"⚠️ WARNING: {open_count} open conversations (threshold: {warning_backlog})"
            })
        
        if unassigned_count > 5:  # More than 5 unassigned is concerning
            alerts.append({
                'type': 'warning',
                'category': 'volume',
                'metric': 'unassigned_conversations',
                'value': unassigned_count,
                'threshold': 5,
                'message': f"⚠️ WARNING: {unassigned_count} unassigned conversations need attention"
            })
        
        # Analyze daily trends
        daily_stats = daily_data.get('daily_stats', {})
        if daily_stats:
            recent_days = sorted(daily_stats.items(), reverse=True)[:7]  # Last 7 days
            
            if len(recent_days) >= 3:
                # Compare last 3 days to previous 3 days
                last_3_days = recent_days[:3]
                prev_3_days = recent_days[3:6] if len(recent_days) >= 6 else recent_days[3:]
                
                last_3_avg = sum(stats['conversations_created'] for _, stats in last_3_days) / len(last_3_days)
                prev_3_avg = sum(stats['conversations_created'] for _, stats in prev_3_days) / len(prev_3_days) if prev_3_days else last_3_avg
                
                if prev_3_avg > 0:  # Avoid division by zero
                    change_pct = ((last_3_avg - prev_3_avg) / prev_3_avg) * 100
                    
                    increase_threshold = self.config['volume_thresholds']['daily_increase_warning_pct']
                    decrease_threshold = self.config['volume_thresholds']['daily_decrease_warning_pct']
                    
                    if change_pct > increase_threshold:
                        alerts.append({
                            'type': 'warning',
                            'category': 'volume',
                            'metric': 'volume_increase',
                            'value': change_pct,
                            'threshold': increase_threshold,
                            'message': f"📈 WARNING: Conversation volume increased {change_pct:.0f}% over last 3 days"
                        })
                    elif change_pct < -decrease_threshold:
                        alerts.append({
                            'type': 'warning',
                            'category': 'volume',
                            'metric': 'volume_decrease',
                            'value': abs(change_pct),
                            'threshold': decrease_threshold,
                            'message': f"📉 WARNING: Conversation volume decreased {abs(change_pct):.0f}% over last 3 days"
                        })
        
        return {'alerts': alerts, 'analysis': 'volume_analysis'}
    
    def analyze_team_performance(self, response_data: Dict, daily_data: Dict, conversation_counts: Dict) -> Dict:
        """Analyze team performance for concerning patterns (clean)."""
        alerts: List[Dict] = []
        response_times_by_admin = response_data.get('response_times_by_admin', {})
        total_responses = sum(len(v) for v in response_times_by_admin.values())

        # Response imbalance
        if response_times_by_admin:
            admin_avg = {a: (sum(t)/len(t)) for a,t in response_times_by_admin.items() if t}
            if len(admin_avg) > 1:
                overall = sum(admin_avg.values())/len(admin_avg)
                for admin, avg_min in admin_avg.items():
                    hours = avg_min/60
                    if avg_min > overall*2 and hours > 24:
                        alerts.append({'type':'warning','category':'team_performance','metric':'individual_response_time','value':hours,'threshold':24,'message':f"⚠️ WARNING: {admin} response time {hours:.1f}h >2x team avg {overall/60:.1f}h"})
                    if hours > 72:
                        alerts.append({'type':'critical','category':'team_performance','metric':'extreme_response_time','value':hours,'threshold':72,'message':f"🚨 CRITICAL: {admin} extremely slow responses {hours:.1f}h"})

        # Workload distribution last 7 days
        admin_workload = {}
        total_conversations = 0
        daily_stats = daily_data.get('daily_stats', {}) if daily_data else {}
        if daily_stats:
            recent = sorted(daily_stats.items(), reverse=True)[:7]
            for _, stats in recent:
                by_admin = stats.get('conversations_by_admin', {})
                total_conversations += sum(by_admin.values())
                for admin, count in by_admin.items():
                    rec = admin_workload.setdefault(admin, {'total':0,'active_days':0,'daily':[]})
                    rec['total'] += count
                    rec['daily'].append(count)
                    if count>0:
                        rec['active_days'] += 1
        if total_conversations>0 and len(admin_workload)>1:
            for admin, rec in admin_workload.items():
                pct = (rec['total']/total_conversations)*100
                if pct>70:
                    alerts.append({'type':'warning','category':'team_performance','metric':'workload_imbalance','value':pct,'threshold':70,'message':f"⚠️ WARNING: {admin} handling {pct:.0f}% of volume"})
                if rec['active_days']==0:
                    alerts.append({'type':'warning','category':'team_performance','metric':'admin_inactive','value':0,'threshold':1,'message':f"⚠️ WARNING: {admin} inactive last 7 days"})
                if len(rec['daily'])>=5:
                    avg_daily = sum(rec['daily'])/len(rec['daily'])
                    if avg_daily>0:
                        var = sum((x-avg_daily)**2 for x in rec['daily'])/len(rec['daily'])
                        cv = (var**0.5)/avg_daily
                        if cv>1.5 and avg_daily>1:
                            alerts.append({'type':'warning','category':'team_performance','metric':'inconsistent_workload','value':cv,'threshold':1.5,'message':f"⚠️ WARNING: {admin} workload variability CV={cv:.2f}"})

        responding_admins = len([a for a,t in response_times_by_admin.items() if t])
        workload_active = len([a for a,r in admin_workload.items() if r.get('active_days',0)>0])
        active_admins = max(responding_admins, workload_active)
        if active_admins==1 and (total_conversations>20 or responding_admins>=1):
            primary = next(iter(response_times_by_admin.keys()), 'Unknown')
            alerts.append({'type':'critical','category':'team_performance','metric':'single_point_of_failure','value':1,'threshold':2,'message':f"🚨 CRITICAL: Only 1 active responder ({primary})"})
        elif active_admins==0 and total_responses>0:
            alerts.append({'type':'critical','category':'team_performance','metric':'no_active_admins','value':0,'threshold':1,'message':f"🚨 CRITICAL: No active admins despite {total_responses} responses"})

        return {'alerts': alerts, 'analysis': 'team_performance_analysis'}
    
    def generate_escalation_report(self, metrics_data: Dict) -> Dict:
        """Generate comprehensive escalation analysis."""
        workspace_data = metrics_data.get("workspace_data", {})
        
        # Analyze different aspects
        response_analysis = self.analyze_response_times(
            workspace_data.get("response_metrics", {}),
            workspace_data.get("response_metrics_24h", {})
        )
        volume_analysis = self.analyze_conversation_volume(
            workspace_data.get("daily_metrics", {}),
            workspace_data.get("conversation_counts", {})
        )
        team_analysis = self.analyze_team_performance(
            workspace_data.get("response_metrics", {}),
            workspace_data.get("daily_metrics", {}),
            workspace_data.get("conversation_counts", {})
        )
        
        # Combine all alerts
        all_alerts = []
        all_alerts.extend(response_analysis['alerts'])
        all_alerts.extend(volume_analysis['alerts'])
        all_alerts.extend(team_analysis['alerts'])
        
        # Categorize alerts
        critical_alerts = [alert for alert in all_alerts if alert['type'] == 'critical']
        warning_alerts = [alert for alert in all_alerts if alert['type'] == 'warning']
        
        return {
            'has_alerts': len(all_alerts) > 0,
            'critical_count': len(critical_alerts),
            'warning_count': len(warning_alerts),
            'critical_alerts': critical_alerts,
            'warning_alerts': warning_alerts,
            'all_alerts': all_alerts,
            'escalation_needed': len(critical_alerts) > 0
        }


def create_daily_trends_chart(data: Dict, output_file: str = "daily_trends.png") -> str:
    """Create a daily trends chart from Intercom metrics data.
    
    Args:
        data: Intercom metrics data
        output_file: Output filename for the chart
        
    Returns:
        Path to the created chart file
    """
    daily_data = data.get("workspace_data", {}).get("daily_metrics", {})
    daily_stats = daily_data.get('daily_stats', {})
    
    if not daily_stats:
        print("No daily stats available for chart")
        return None
    
    # Prepare data for the last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=29)
    
    dates = []
    created_counts = []
    closed_counts = []
    
    # Generate all dates in the range
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(current_date)
        
        if date_str in daily_stats:
            created_counts.append(daily_stats[date_str].get('conversations_created', 0))
            closed_counts.append(daily_stats[date_str].get('conversations_closed', 0))
        else:
            created_counts.append(0)
            closed_counts.append(0)
            
        current_date += timedelta(days=1)
    
    # Create the chart
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot lines
    ax.plot(dates, created_counts, marker='o', linewidth=2, markersize=4, 
            label='Conversations Created', color='#2E8B57', alpha=0.8)
    ax.plot(dates, closed_counts, marker='s', linewidth=2, markersize=4,
            label='Conversations Closed', color='#4682B4', alpha=0.8)
    
    # Fill areas under curves
    ax.fill_between(dates, created_counts, alpha=0.2, color='#2E8B57')
    ax.fill_between(dates, closed_counts, alpha=0.2, color='#4682B4')
    
    # Formatting
    ax.set_title('Daily Conversation Trends (30 Days)', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Number of Conversations', fontsize=12)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Grid and legend
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', frameon=True, shadow=True)
    
    # Set y-axis to start from 0
    ax.set_ylim(bottom=0)
    
    # Add summary statistics as text
    total_created = sum(created_counts)
    total_closed = sum(closed_counts)
    avg_created = total_created / 30
    avg_closed = total_closed / 30
    
    stats_text = f'30-Day Summary:\nTotal Created: {total_created}\nTotal Closed: {total_closed}\nAvg/Day Created: {avg_created:.1f}\nAvg/Day Closed: {avg_closed:.1f}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    # Tight layout and save
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Daily trends chart saved to {output_file}")
    return output_file

def find_latest_metrics_file(directory: str = ".") -> str:
    """Find the most recent Intercom metrics file.
    
    Args:
        directory: Directory to search in
        
    Returns:
        Path to the latest metrics file
    """
    pattern = os.path.join(directory, "intercom_metrics_*.json")
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError("No Intercom metrics files found")
    
    # Sort by modification time, newest first
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def run_intercom_metrics():
    """Run the intercom_metrics.py script and return the generated file path."""
    print("Running Intercom metrics extraction...")
    
    try:
        # Run the intercom metrics script
        result = subprocess.run(
            [sys.executable, "intercom_metrics.py"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        print("Intercom metrics extraction completed")
        
        # Find the newly created file
        metrics_file = find_latest_metrics_file()
        return metrics_file
        
    except subprocess.CalledProcessError as e:
        print(f"Error running intercom_metrics.py: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"Error running intercom metrics: {e}")
        raise

def main():
    # Get configuration from environment variables
    SLACK_WEBHOOK_URL = os.getenv("INTERCOM_SLACK_WEBHOOK_URL") or os.getenv("SLACK_WEBHOOK_URL")
    SLACK_BOT_TOKEN = os.getenv("INTERCOM_SLACK_BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL = os.getenv("INTERCOM_SLACK_CHANNEL") or os.getenv("SLACK_CHANNEL", "#layer-intercom")
    SLACK_ALERTS_CHANNEL = os.getenv("INTERCOM_SLACK_ALERTS_CHANNEL") or os.getenv("SLACK_ALERTS_CHANNEL", "#alerts-support")
    
    # Validate configuration
    if not SLACK_BOT_TOKEN and not SLACK_WEBHOOK_URL:
        print("ERROR: Either INTERCOM_SLACK_BOT_TOKEN (or legacy SLACK_BOT_TOKEN) or INTERCOM_SLACK_WEBHOOK_URL must be set!")
        print("Please create a .env file with your Slack configuration.")
        print("See .env.example for the required format.")
        sys.exit(1)
    
    try:
        # Run Intercom metrics extraction first
        metrics_file = run_intercom_metrics()
        print(f"Using metrics file: {metrics_file}")
        
        with open(metrics_file, 'r') as f:
            metrics_data = json.load(f)
        
        # Initialize Slack reporter
        slack_reporter = SlackReporter(
            webhook_url=SLACK_WEBHOOK_URL if SLACK_WEBHOOK_URL and SLACK_WEBHOOK_URL.startswith('https://') else None,
            bot_token=SLACK_BOT_TOKEN
        )
        
        # Test bot permissions
        print("Testing bot permissions...")
        auth_test = slack_reporter.test_bot_permissions()
        print(f"Bot auth test: {auth_test}")
        
        # Check bot scopes
        if slack_reporter.bot_token:
            print("Checking bot scopes...")
            try:
                # Check OAuth scopes
                scopes_response = requests.get(
                    "https://slack.com/api/auth.test",
                    headers={'Authorization': f'Bearer {slack_reporter.bot_token}'}
                )
                if scopes_response.ok:
                    scopes_data = scopes_response.json()
                    print(f"Bot info: {scopes_data}")
                
                # Try to get actual permissions
                perms_response = requests.post(
                    "https://slack.com/api/apps.permissions.info",
                    headers={'Authorization': f'Bearer {slack_reporter.bot_token}'}
                )
                if perms_response.ok:
                    perms_data = perms_response.json()
                    print(f"Bot permissions: {perms_data}")
            except Exception as e:
                print(f"Could not check scopes: {e}")
        
        # Format the report
        print("Formatting metrics for Slack...")
        full_report = IntercomMetricsFormatter.format_full_report(metrics_data)
        
        # Analyze for escalations
        print("Analyzing metrics for escalations...")
        escalation_analyzer = EscalationAnalyzer()
        escalation_report = escalation_analyzer.generate_escalation_report(metrics_data)
        
        # Chart generation removed per user request
        chart_file = None
        
        # Send to Slack
        print("Sending report to Slack...")
        success = slack_reporter.send_message(full_report, SLACK_CHANNEL)
        
        # Handle escalations if any alerts found
        if escalation_report['has_alerts']:
            print(f"Found {escalation_report['critical_count']} critical and {escalation_report['warning_count']} warning alerts")
            
            # Send critical alerts to alerts channel
            if escalation_report['critical_alerts']:
                critical_message = "🚨 *CRITICAL INTERCOM ALERTS* 🚨\n"
                for alert in escalation_report['critical_alerts']:
                    critical_message += f"• {alert['message']}\n"
                
                # Try to send to alerts channel, fallback to user if fails
                critical_success = slack_reporter.send_message(critical_message, SLACK_ALERTS_CHANNEL)
                if not critical_success:
                    print(f"Failed to send to {SLACK_ALERTS_CHANNEL} channel, sending to user instead")
                    slack_reporter.send_message(critical_message, SLACK_CHANNEL)
                else:
                    print(f"Critical alerts sent to {SLACK_ALERTS_CHANNEL} channel")
            
            # Send warning alerts to alerts-support channel
            if escalation_report['warning_alerts']:
                warning_message = "⚠️ *Intercom Warnings* ⚠️\n"
                for alert in escalation_report['warning_alerts']:
                    warning_message += f"• {alert['message']}\n"
                
                warning_message += f"\n*Total alerts: {escalation_report['critical_count']} critical, {escalation_report['warning_count']} warnings*"
                
                warning_success = slack_reporter.send_message(warning_message, SLACK_ALERTS_CHANNEL)
                if not warning_success:
                    print(f"Failed to send to {SLACK_ALERTS_CHANNEL} channel, sending to user instead")
                    slack_reporter.send_message(warning_message, SLACK_CHANNEL)
                else:
                    print(f"Warning alerts sent to {SLACK_ALERTS_CHANNEL} channel")
        else:
            print("No escalation alerts detected - all metrics within normal ranges")
        
        # Chart upload functionality removed per user request
        
        if success:
            print("Report sent successfully to Slack!")
            
            # Delete the metrics file and chart after successful posting
            try:
                os.remove(metrics_file)
                print(f"Deleted metrics file: {metrics_file}")
            except Exception as e:
                print(f"Warning: Could not delete metrics file: {e}")
                
            # Chart cleanup removed per user request
        else:
            print("Failed to send report to Slack")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()