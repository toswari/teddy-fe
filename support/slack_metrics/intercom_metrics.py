#!/usr/bin/env python3
"""
Intercom Metrics Extraction Script

This script pulls various metrics from Intercom using their REST API.
Supports conversation stats, admin metrics, and company data.
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv
from statistics import mean, median

# Load environment variables
load_dotenv()

class IntercomMetricsClient:
    def __init__(self, access_token: str, base_url: str = "https://api.intercom.io"):
        """Initialize the Intercom metrics client.
        
        Args:
            access_token: Your Intercom access token
            base_url: Base URL for Intercom API (defaults to US region)
        """
        self.access_token = access_token
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        # Simple in-memory cache for conversation details to reduce duplicate API calls
        self._conversation_cache = {}

    def _normalize_priority(self, raw_priority: Optional[str]) -> str:
        """Normalize various priority values from Intercom into high/medium/low/none.

        Intercom can sometimes return values like 'priority', 'not_priority', or None.
        Anything unrecognized collapses to 'none' so downstream breakdowns remain clean.
        """
        if not raw_priority:
            return "none"
        raw = str(raw_priority).lower().strip()
        mapping = {
            'high': 'high',
            'medium': 'medium',
            'low': 'low',
            'priority': 'none',       # unexpected generic value
            'not_priority': 'none',
            'none': 'none'
        }
        return mapping.get(raw, 'none')
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the Intercom API.
        
        Args:
            endpoint: API endpoint to call
            params: Optional query parameters
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def get_admins(self) -> Dict:
        """Get all admins in the workspace."""
        return self._make_request("/admins")
    
    def get_companies(self, page_size: int = 50) -> Dict:
        """Get companies data.
        
        Args:
            page_size: Number of companies per page
        """
        params = {'per_page': page_size}
        return self._make_request("/companies", params)
    
    def get_contacts(self, page_size: int = 50) -> Dict:
        """Get contacts/users data.
        
        Args:
            page_size: Number of contacts per page
        """
        params = {'per_page': page_size}
        return self._make_request("/contacts", params)
    
    def get_conversations(self, page_size: int = 50, state: str = None, exclude_spam: bool = True) -> Dict:
        """Get conversations data.
        
        Args:
            page_size: Number of conversations per page
            state: Filter by state (open, closed, snoozed)
            exclude_spam: Whether to exclude spam conversations (default: True)
        """
        params = {'per_page': page_size}
        if state:
            params['state'] = state
        
        response = self._make_request("/conversations", params)
        
        # Filter out spam conversations if requested
        if exclude_spam and response and 'conversations' in response:
            original_count = len(response['conversations'])
            filtered_conversations = []
            
            for convo in response['conversations']:
                # Check various spam indicators
                is_spam = self._is_spam_conversation(convo)
                if not is_spam:
                    filtered_conversations.append(convo)
            
            response['conversations'] = filtered_conversations
            
            if original_count > len(filtered_conversations):
                print(f"Filtered out {original_count - len(filtered_conversations)} spam conversations")
        
        return response

    def get_conversations_paginated(self, page_size: int = 50, state: str = None, exclude_spam: bool = True, max_pages: Optional[int] = None) -> Dict:
        """Fetch conversations across multiple pages.

        Intercom pagination typically returns a 'pages.next.starting_after' token.
        We'll follow that chain until exhausted or max_pages reached.

        Args:
            page_size: items per page
            state: optional conversation state filter
            exclude_spam: whether to filter spam locally
            max_pages: safety cap to avoid excessive API usage

        Returns:
            Dict with aggregated conversations and pagination metadata
        """
        params_base = {'per_page': page_size}
        if state:
            params_base['state'] = state
        all_conversations: List[Dict] = []
        pages_fetched = 0
        starting_after = None
        while True:
            params = dict(params_base)
            if starting_after:
                params['starting_after'] = starting_after
            try:
                resp = self._make_request('/conversations', params)
            except Exception:
                break
            convs = resp.get('conversations', []) or []
            if exclude_spam and convs:
                filtered = []
                for c in convs:
                    if not self._is_spam_conversation(c):
                        filtered.append(c)
                convs = filtered
            all_conversations.extend(convs)
            pages_fetched += 1
            # pagination token
            next_info = (resp.get('pages') or {}).get('next') or {}
            starting_after = next_info.get('starting_after')
            if not starting_after:
                break
            if max_pages and pages_fetched >= max_pages:
                break
        return {
            'type': 'list',
            'conversations': all_conversations,
            'pagination': {
                'pages_fetched': pages_fetched,
                'page_size': page_size,
                'total_conversations': len(all_conversations),
                'state': state,
                'capped': True if (max_pages and pages_fetched >= max_pages and starting_after) else False
            }
        }
    def _is_spam_conversation(self, convo: Dict) -> bool:
        """Heuristic spam detection (conservative)."""
        try:
            tags = convo.get('tags', {}).get('tags', [])
            spam_tags = ['spam', 'junk', 'bot', 'automated']
            for tag in tags:
                name = (tag.get('name') or '').lower()
                if any(st in name for st in spam_tags):
                    return True

            source = convo.get('source') or {}
            source_type = source.get('type', '')
            if source_type in ['email'] and source.get('delivered_as') == 'automated':
                return True

            subject = (source.get('subject') or '').lower()
            body = (source.get('body') or '').lower()
            spam_keywords = [
                'viagra','casino','lottery','winner','congratulations','free money','earn money',
                'click here','act now','limited time','special offer','weight loss','debt relief'
            ]
            content_to_check = f"{subject} {body}"
            spam_score = sum(1 for kw in spam_keywords if kw in content_to_check)
            if spam_score >= 2:
                return True

            contacts = convo.get('contacts', {}).get('contacts', [])
            if contacts:
                contact = contacts[0]
                email = (contact.get('email') or '').lower()
                name = (contact.get('name') or '').lower()
                suspicious_domains = ['tempmail','guerrillamail','10minutemail','mailinator','throwaway','spam','fake']
                if any(dom in email for dom in suspicious_domains):
                    return True
                if name and (name.isdigit() or len(name) < 2):
                    return True

            priority = convo.get('priority', '')
            if priority == 'not_priority':
                parts = convo.get('conversation_parts', {}).get('conversation_parts', [])
                if len(parts) <= 1:
                    return True

            assignee = convo.get('assignee', {})
            if assignee and assignee.get('name') == 'Spam Filter Bot':
                return True

            parts = convo.get('conversation_parts', {}).get('conversation_parts', [])
            for part in parts:
                author = part.get('author', {})
                if author.get('type') == 'bot' and (author.get('name') or '').lower() in ['spam','auto']:
                    return True
            return False
        except Exception:
            return False
    
    def get_conversation_counts(self) -> Dict:
        """Get conversation counts by type and state."""
        return self._make_request("/counts")
    
    def get_tags(self) -> Dict:
        """Get all tags."""
        return self._make_request("/tags")
    
    def get_segments(self) -> Dict:
        """Get all segments."""
        return self._make_request("/segments")
    
    def get_conversations_with_sla(self, page_size: int = 50) -> Dict:
        """Get conversations with SLA data.
        
        Args:
            page_size: Number of conversations per page
        """
        params = {'per_page': page_size, 'display_as': 'plaintext'}
        return self._make_request("/conversations", params)
    
    def get_sla_applied_conversations(self, conversation_ids: List[str] = None) -> List[Dict]:
        """Get SLA applied data for specific conversations.
        
        Args:
            conversation_ids: List of conversation IDs to check for SLA data
            
        Returns:
            List of conversations with SLA information
        """
        sla_data = []
        
        if conversation_ids:
            for conv_id in conversation_ids:
                try:
                    conv_data = self._make_request(f"/conversations/{conv_id}")
                    if 'sla_applied' in conv_data:
                        sla_data.append({
                            'conversation_id': conv_id,
                            'sla_applied': conv_data['sla_applied'],
                            'created_at': conv_data.get('created_at'),
                            'updated_at': conv_data.get('updated_at'),
                            'state': conv_data.get('state')
                        })
                except Exception as e:
                    print(f"Error getting SLA data for conversation {conv_id}: {e}")
                    continue
        
        return sla_data
    
    def analyze_sla_performance(self, conversations: Dict) -> Dict:
        """Analyze SLA performance from conversations data.
        
        Args:
            conversations: Conversations data from API
            
        Returns:
            SLA performance analysis
        """
        sla_stats = {
            'total_conversations': 0,
            'conversations_with_sla': 0,
            'slas_met': 0,
            'slas_breached': 0,
            'sla_types': {},
            'performance_by_admin': {}
        }
        
        if 'conversations' not in conversations:
            return sla_stats
            
        conversations_list = conversations['conversations']
        sla_stats['total_conversations'] = len(conversations_list)
        
        for conv in conversations_list:
            if 'sla_applied' in conv and conv['sla_applied']:
                sla_stats['conversations_with_sla'] += 1
                sla_applied = conv['sla_applied']
                
                # Track SLA types
                sla_name = sla_applied.get('sla_name', 'Unknown')
                if sla_name not in sla_stats['sla_types']:
                    sla_stats['sla_types'][sla_name] = {
                        'total': 0, 'met': 0, 'breached': 0
                    }
                
                sla_stats['sla_types'][sla_name]['total'] += 1
                
                # Check if SLA was met
                sla_status = sla_applied.get('sla_status', 'unknown')
                if sla_status == 'hit':
                    sla_stats['slas_met'] += 1
                    sla_stats['sla_types'][sla_name]['met'] += 1
                elif sla_status == 'missed':
                    sla_stats['slas_breached'] += 1
                    sla_stats['sla_types'][sla_name]['breached'] += 1
                
                # Track by admin/assignee
                assignee = conv.get('assignee', {})
                if assignee and 'name' in assignee:
                    admin_name = assignee['name']
                    if admin_name not in sla_stats['performance_by_admin']:
                        sla_stats['performance_by_admin'][admin_name] = {
                            'total': 0, 'met': 0, 'breached': 0
                        }
                    
                    sla_stats['performance_by_admin'][admin_name]['total'] += 1
                    if sla_status == 'hit':
                        sla_stats['performance_by_admin'][admin_name]['met'] += 1
                    elif sla_status == 'missed':
                        sla_stats['performance_by_admin'][admin_name]['breached'] += 1
        
        # Calculate percentages
        if sla_stats['conversations_with_sla'] > 0:
            sla_stats['sla_hit_rate'] = (sla_stats['slas_met'] / sla_stats['conversations_with_sla']) * 100
            sla_stats['sla_breach_rate'] = (sla_stats['slas_breached'] / sla_stats['conversations_with_sla']) * 100
        else:
            sla_stats['sla_hit_rate'] = 0
            sla_stats['sla_breach_rate'] = 0
            
        return sla_stats
    
    def get_conversation_parts(self, conversation_id: str) -> Dict:
        """Get conversation parts (messages) for a specific conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Conversation parts data
        """
        # Use cache if available
        if conversation_id in self._conversation_cache:
            return self._conversation_cache[conversation_id]
        detail = self._make_request(f"/conversations/{conversation_id}")
        self._conversation_cache[conversation_id] = detail
        return detail
    
    def calculate_daily_metrics(self, conversations: Dict, days_back: int = 30) -> Dict:
        """Calculate daily conversation metrics.
        
        Args:
            conversations: Conversations data from API
            days_back: Number of days to analyze (default 30)
            
        Returns:
            Daily metrics analysis
        """
        from collections import defaultdict
        
        daily_metrics = {
            'analysis_period_days': days_back,
            'daily_stats': defaultdict(lambda: {
                'conversations_created': 0,
                'conversations_closed': 0,
                'total_response_times': [],
                'first_response_times': [],
                'admin_responses': 0,
                'customer_messages': 0,
                'conversations_by_admin': defaultdict(int),
                'avg_waiting_time': []
            }),
            'overall_metrics': {
                'total_conversations': 0,
                'avg_first_response_time': 0,
                'avg_response_time': 0,
                'conversations_per_day': 0,
                'busiest_day': '',
                'response_time_by_admin': defaultdict(list)
            }
        }
        
        if 'conversations' not in conversations:
            return daily_metrics
            
        conversations_list = conversations['conversations']
        daily_metrics['overall_metrics']['total_conversations'] = len(conversations_list)
        
        cutoff_time = datetime.now().timestamp() - (days_back * 24 * 60 * 60)
        
        for conv in conversations_list:
            created_at = conv.get('created_at', 0)
            if created_at < cutoff_time:
                continue
                
            # Convert timestamp to date string
            created_date = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d')
            
            daily_stats = daily_metrics['daily_stats'][created_date]
            daily_stats['conversations_created'] += 1
            
            # Check if conversation is closed
            if conv.get('state') == 'closed':
                daily_stats['conversations_closed'] += 1
            
            # Calculate waiting time if available
            waiting_since = conv.get('waiting_since')
            if waiting_since and waiting_since > 0:
                waiting_time = (datetime.now().timestamp() - waiting_since) / 60  # minutes
                daily_stats['avg_waiting_time'].append(waiting_time)
            
            # Track conversations by admin
            assignee = conv.get('assignee', {})
            if assignee and 'name' in assignee:
                admin_name = assignee['name']
                daily_stats['conversations_by_admin'][admin_name] += 1
                
        # Calculate overall metrics
        total_days = len(daily_metrics['daily_stats'])
        if total_days > 0:
            daily_metrics['overall_metrics']['conversations_per_day'] = (
                daily_metrics['overall_metrics']['total_conversations'] / total_days
            )
            
            # Find busiest day
            max_conversations = 0
            busiest_day = ''
            for date, stats in daily_metrics['daily_stats'].items():
                if stats['conversations_created'] > max_conversations:
                    max_conversations = stats['conversations_created']
                    busiest_day = date
            daily_metrics['overall_metrics']['busiest_day'] = busiest_day
        
        # Convert defaultdicts to regular dicts for JSON serialization
        daily_metrics['daily_stats'] = dict(daily_metrics['daily_stats'])
        for date in daily_metrics['daily_stats']:
            daily_metrics['daily_stats'][date]['conversations_by_admin'] = dict(
                daily_metrics['daily_stats'][date]['conversations_by_admin']
            )
        daily_metrics['overall_metrics']['response_time_by_admin'] = dict(
            daily_metrics['overall_metrics']['response_time_by_admin']
        )
        
        return daily_metrics
    
    def get_detailed_response_metrics(self, conversation_ids: List[str] = None, sample_size: int = None) -> Dict:
        """Get detailed response time metrics from conversation parts.
        
        Args:
            conversation_ids: List of conversation IDs to analyze
            sample_size: Number of conversations to sample for detailed analysis (None = all)
            
        Returns:
            Detailed response metrics
        """
        from collections import defaultdict
        
        response_metrics = {
            'conversations_analyzed': 0,
            'first_response_times': [],
            'avg_response_times': [],
            'response_times_by_admin': defaultdict(list)
        }
        
        if not conversation_ids:
            return response_metrics
            
        # Sample conversations to avoid API rate limits (if sample_size specified)
        if sample_size is not None:
            sample_conversations = conversation_ids[:sample_size]
        else:
            sample_conversations = conversation_ids
        
        for conv_id in sample_conversations:
            try:
                conv_detail = self.get_conversation_parts(conv_id)
                if 'conversation_parts' not in conv_detail:
                    continue
                    
                response_metrics['conversations_analyzed'] += 1
                parts = conv_detail['conversation_parts']['conversation_parts']
                
                # Analyze response times between parts
                customer_message_time = None
                first_response_recorded = False
                
                for part in parts:
                    part_type = part.get('part_type', '')
                    created_at = part.get('created_at', 0)
                    author = part.get('author', {})
                    
                    if author.get('type') == 'user' and part_type == 'comment':
                        # Customer message
                        customer_message_time = created_at
                    elif author.get('type') == 'admin' and part_type == 'comment' and customer_message_time:
                        # Admin response
                        response_time = (created_at - customer_message_time) / 60  # minutes
                        
                        if not first_response_recorded:
                            response_metrics['first_response_times'].append(response_time)
                            first_response_recorded = True
                        
                        response_metrics['avg_response_times'].append(response_time)
                        
                        admin_name = author.get('name', 'Unknown')
                        response_metrics['response_times_by_admin'][admin_name].append(response_time)
                        
                        # Skip business hours tracking for 24/7 operations
                            
                        customer_message_time = None  # Reset for next customer message
                        
            except Exception as e:
                print(f"Error analyzing conversation {conv_id}: {e}")
                continue
        
        # Convert defaultdict to dict for JSON serialization
        response_metrics['response_times_by_admin'] = dict(response_metrics['response_times_by_admin'])
        
        return response_metrics
    
    def get_all_conversation_states(self, limit: int = 50, exclude_spam: bool = None) -> Dict:
        """Get comprehensive conversation state analysis across all states.
        
        Args:
            limit: Maximum number of conversations per state to analyze
            exclude_spam: Whether to exclude spam conversations (None = use env setting)
            
        Returns:
            Dict with complete conversation state breakdown
        """
        try:
            # Use environment setting if not specified
            if exclude_spam is None:
                val = os.getenv("EXCLUDE_SPAM_CONVERSATIONS", "true")
                if val is None:
                    val = "true"
                exclude_spam = str(val).lower() == "true"
            
            # Get conversations in all states
            open_convos = self.get_conversations(page_size=limit, state="open", exclude_spam=exclude_spam)
            closed_convos = self.get_conversations(page_size=min(limit, 10), state="closed", exclude_spam=exclude_spam)  # Sample recent closed
            snoozed_convos = self.get_conversations(page_size=limit, state="snoozed", exclude_spam=exclude_spam)
            
            conversation_analysis = {
                "state_breakdown": {
                    "open": 0,
                    "closed": 0, 
                    "snoozed": 0
                },
                "open_conversations": self._analyze_conversations_by_state(open_convos, "open", limit),
                "snoozed_conversations": self._analyze_conversations_by_state(snoozed_convos, "snoozed", limit),
                "closed_sample": self._analyze_conversations_by_state(closed_convos, "closed", min(limit, 10)),
                "summary": {
                    "total_active": 0,  # open + snoozed
                    "needs_attention": 0,  # urgent open conversations
                    "on_hold": 0  # snoozed conversations
                }
            }
            
            # Get state counts
            if open_convos and open_convos.get("conversations"):
                conversation_analysis["state_breakdown"]["open"] = len(open_convos["conversations"])
            if closed_convos and closed_convos.get("conversations"):
                conversation_analysis["state_breakdown"]["closed"] = len(closed_convos["conversations"])
            if snoozed_convos and snoozed_convos.get("conversations"):
                conversation_analysis["state_breakdown"]["snoozed"] = len(snoozed_convos["conversations"])
            
            # Calculate summary stats
            conversation_analysis["summary"]["total_active"] = (
                conversation_analysis["state_breakdown"]["open"] + 
                conversation_analysis["state_breakdown"]["snoozed"]
            )
            
            conversation_analysis["summary"]["needs_attention"] = len([
                c for c in conversation_analysis["open_conversations"]["conversations"] 
                if c.get("response_status") == "awaiting_agent"
            ])
            
            conversation_analysis["summary"]["on_hold"] = conversation_analysis["state_breakdown"]["snoozed"]
            
            return conversation_analysis
            
        except Exception as e:
            print(f"Error getting conversation states: {e}")
            return {
                "state_breakdown": {"open": 0, "closed": 0, "snoozed": 0},
                "open_conversations": {"total_open": 0, "conversations": []},
                "snoozed_conversations": {"total_snoozed": 0, "conversations": []},
                "closed_sample": {"total_closed": 0, "conversations": []},
                "summary": {"total_active": 0, "needs_attention": 0, "on_hold": 0}
            }

    def _analyze_conversations_by_state(self, convos_data: Dict, state: str, limit: int) -> Dict:
        """Analyze conversations for a specific state."""
        if not convos_data or not convos_data.get("conversations"):
            return {
                f"total_{state}": 0,
                "conversations": [],
                "priority_breakdown": {"high": 0, "medium": 0, "low": 0, "none": 0},
                "assignment_breakdown": {"assigned": 0, "unassigned": 0},
                "response_status": {"awaiting_agent": 0, "awaiting_customer": 0, "unknown": 0},
                "waiting_time_analysis": {"under_1h": 0, "1h_to_4h": 0, "4h_to_24h": 0, "over_24h": 0}
            }
        
        # Use existing analysis logic but adapt for any state
        conversations = convos_data["conversations"]
        analysis = {
            f"total_{state}": len(conversations),
            "conversations": [],
            "priority_breakdown": {"high": 0, "medium": 0, "low": 0, "none": 0},
            "assignment_breakdown": {"assigned": 0, "unassigned": 0},
            "response_status": {"awaiting_agent": 0, "awaiting_customer": 0, "unknown": 0},
            "waiting_time_analysis": {"under_1h": 0, "1h_to_4h": 0, "4h_to_24h": 0, "over_24h": 0}
        }
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        for convo in conversations[:limit]:
            # Use the existing conversation analysis logic
            convo_details = self._analyze_single_conversation(convo, now, analysis)
            if convo_details:
                analysis["conversations"].append(convo_details)
        
        # Sort by urgency for open conversations, by time for others
        if state == "open":
            analysis["conversations"].sort(key=lambda x: (
                x.get("response_status") == "awaiting_agent", 
                x.get("waiting_hours", 0)
            ), reverse=True)
        else:
            analysis["conversations"].sort(key=lambda x: x.get("waiting_hours", 0), reverse=True)
        
        return analysis

    def _analyze_single_conversation(self, convo: Dict, now: datetime, analysis: Dict) -> Dict:
        """Analyze a single conversation and update counters."""
        # Extract conversation details (using existing logic)
        convo_id = convo.get("id", "")
        subject = convo.get("source", {}).get("subject", "No Subject")
        if not subject or subject == "No Subject":
            body = convo.get("source", {}).get("body", "")
            if body:
                subject = body[:50] + "..." if len(body) > 50 else body
        
        # Clean up HTML tags and format subject
        if subject:
            import re
            subject = re.sub(r'<[^>]+>', '', subject)
            subject = ' '.join(subject.split())
            if len(subject) > 40:
                subject = subject[:40] + "..."
            if not subject.strip():
                subject = "No subject"

        state = convo.get("state", "unknown")
        priority = self._normalize_priority(convo.get("priority"))

        # Get assignee info
        assignee = convo.get("assignee")
        if assignee and assignee.get("type") == "admin":
            assigned_to = assignee.get("name", "Unknown Admin")
            analysis["assignment_breakdown"]["assigned"] += 1
        else:
            assigned_to = "Unassigned"
            analysis["assignment_breakdown"]["unassigned"] += 1

        # Calculate waiting time
        updated_at = convo.get("updated_at")
        waiting_hours = 0
        if updated_at:
            try:
                updated_time = datetime.fromtimestamp(updated_at, tz=timezone.utc)
                waiting_hours = (now - updated_time).total_seconds() / 3600
            except:
                pass

        # Categorize waiting time
        if waiting_hours < 1:
            analysis["waiting_time_analysis"]["under_1h"] += 1
        elif waiting_hours < 4:
            analysis["waiting_time_analysis"]["1h_to_4h"] += 1
        elif waiting_hours < 24:
            analysis["waiting_time_analysis"]["4h_to_24h"] += 1
        else:
            analysis["waiting_time_analysis"]["over_24h"] += 1
        
        # Count priorities
        if priority in analysis["priority_breakdown"]:
            analysis["priority_breakdown"][priority] += 1
        else:
            analysis["priority_breakdown"]["none"] += 1
        
        # Analyze conversation parts for response status
        parts = convo.get("conversation_parts", {}).get("conversation_parts", [])
        # Fallback: fetch full conversation detail if parts missing so we can classify status
        if not parts and convo.get("id"):
            try:
                detail = self.get_conversation_parts(convo["id"])
                parts = detail.get("conversation_parts", {}).get("conversation_parts", [])
                # Merge minimal fields (updated_at might be newer in detail)
                if detail.get("updated_at"):
                    convo["updated_at"] = detail.get("updated_at")
                # Inject fetched parts into original to avoid re-fetch later
                convo.setdefault("conversation_parts", {"conversation_parts": parts})
            except Exception as e:
                # Leave parts empty if fetch fails
                parts = []
        last_message = ""
        customer_name = "Unknown Customer"
        response_status = "unknown"
        last_message_author = None
        
        # Get customer info
        contacts = convo.get("contacts", {}).get("contacts", [])
        if contacts:
            contact = contacts[0]
            name = contact.get("name", "").strip()
            email = contact.get("email", "").strip()
            if name:
                customer_name = name
            elif email:
                customer_name = email.split("@")[0] + "@..."
            if len(customer_name) > 25:
                customer_name = customer_name[:25] + "..."
        
        # Analyze message history for response status
        # Traverse from newest to oldest to determine last message author accurately
        for part in sorted(parts, key=lambda p: p.get("created_at", 0), reverse=True):
            if part.get("part_type") != "comment":
                continue
            author = part.get("author", {})
            author_type = author.get("type", "")
            if not last_message_author:
                if author_type == "user":
                    response_status = "awaiting_agent"
                    last_message_author = "customer"
                elif author_type == "admin":
                    response_status = "awaiting_customer"
                    last_message_author = "agent"
            # Capture last customer message snippet for context even if not final author
            if not last_message and author_type == "user":
                msg = part.get("body", "")
                if msg:
                    import re
                    msg = re.sub(r'<[^>]+>', '', msg)
                    msg = ' '.join(msg.split())
                    if len(msg) > 80:
                        msg = msg[:80] + "..."
                    last_message = msg
            # Break early if we have determined status and have snippet
            if last_message_author and last_message:
                break
        
        # Update response status counts
        analysis["response_status"][response_status] += 1
        
        # Format waiting time
        if waiting_hours < 1:
            waiting_str = f"{int(waiting_hours * 60)}m"
        elif waiting_hours < 24:
            waiting_str = f"{waiting_hours:.1f}h"
        else:
            waiting_str = f"{waiting_hours/24:.1f}d"
        
        return {
            "id": convo_id,
            "subject": subject,
            "customer": customer_name,
            "assigned_to": assigned_to,
            "priority": priority,
            "waiting_time": waiting_str,
            "waiting_hours": waiting_hours,
            "last_message": last_message,
            "state": state,
            "response_status": response_status,
            "last_message_author": last_message_author
        }

    def get_current_open_conversations(self, limit: int = 20, exclude_spam: bool = None) -> Dict:
        """Get current open conversations with details.
        
        Args:
            limit: Maximum number of conversations to return
            exclude_spam: Whether to exclude spam conversations (None = use env setting)
            
        Returns:
            Dict with open conversation details
        """
        try:
            # Use environment setting if not specified
            if exclude_spam is None:
                val = os.getenv("EXCLUDE_SPAM_CONVERSATIONS", "true")
                if val is None:
                    val = "true"
                exclude_spam = str(val).lower() == "true"
            
            # Get open conversations
            open_convos = self.get_conversations(page_size=limit, state="open", exclude_spam=exclude_spam)
            
            current_status = {
                "total_open": 0,
                "conversations": [],
                "priority_breakdown": {"high": 0, "medium": 0, "low": 0, "none": 0},
                "assignment_breakdown": {"assigned": 0, "unassigned": 0},
                "response_status": {
                    "awaiting_agent": 0,      # Customer sent last message, waiting for agent
                    "awaiting_customer": 0,   # Agent sent last message, waiting for customer
                    "unknown": 0              # Can't determine last message author
                },
                "waiting_time_analysis": {
                    "under_1h": 0,
                    "1h_to_4h": 0,
                    "4h_to_24h": 0,
                    "over_24h": 0
                }
            }
            
            if not open_convos or not open_convos.get("conversations"):
                return current_status
                
            conversations = open_convos["conversations"]
            current_status["total_open"] = len(conversations)
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for convo in conversations[:limit]:
                # Extract conversation details
                convo_id = convo.get("id", "")
                subject = convo.get("source", {}).get("subject", "No Subject")
                if not subject or subject == "No Subject":
                    # Try to get subject from first message
                    body = convo.get("source", {}).get("body", "")
                    if body:
                        subject = body[:50] + "..." if len(body) > 50 else body
                
                # Clean up HTML tags and format subject
                if subject:
                    import re
                    # Remove HTML tags
                    subject = re.sub(r'<[^>]+>', '', subject)
                    # Remove extra whitespace
                    subject = ' '.join(subject.split())
                    # Remove CSS classes and style attributes
                    subject = re.sub(r'class="[^"]*"', '', subject)
                    subject = re.sub(r'style="[^"]*"', '', subject)
                    # Truncate if too long
                    if len(subject) > 40:
                        subject = subject[:40] + "..."
                    # Fallback if empty after cleaning
                    if not subject.strip():
                        subject = "No subject"
                        
                state = convo.get("state", "unknown")
                priority = self._normalize_priority(convo.get("priority"))
                
                # Get assignee info
                assignee = convo.get("assignee")
                if assignee and assignee.get("type") == "admin":
                    assigned_to = assignee.get("name", "Unknown Admin")
                    current_status["assignment_breakdown"]["assigned"] += 1
                else:
                    assigned_to = "Unassigned"
                    current_status["assignment_breakdown"]["unassigned"] += 1
                
                # Calculate waiting time
                updated_at = convo.get("updated_at")
                waiting_hours = 0
                if updated_at:
                    try:
                        updated_time = datetime.fromtimestamp(updated_at, tz=timezone.utc)
                        waiting_hours = (now - updated_time).total_seconds() / 3600
                    except:
                        pass
                
                # Categorize waiting time
                if waiting_hours < 1:
                    current_status["waiting_time_analysis"]["under_1h"] += 1
                elif waiting_hours < 4:
                    current_status["waiting_time_analysis"]["1h_to_4h"] += 1
                elif waiting_hours < 24:
                    current_status["waiting_time_analysis"]["4h_to_24h"] += 1
                else:
                    current_status["waiting_time_analysis"]["over_24h"] += 1
                
                # Count priorities
                if priority in current_status["priority_breakdown"]:
                    current_status["priority_breakdown"][priority] += 1
                else:
                    current_status["priority_breakdown"]["none"] += 1
                
                # Get conversation parts (messages) for context and determine response status
                parts = convo.get("conversation_parts", {}).get("conversation_parts", [])
                if not parts and convo.get("id"):
                    try:
                        detail = self.get_conversation_parts(convo["id"])
                        parts = detail.get("conversation_parts", {}).get("conversation_parts", [])
                        convo.setdefault("conversation_parts", {"conversation_parts": parts})
                        if detail.get("updated_at"):
                            convo["updated_at"] = detail.get("updated_at")
                    except Exception:
                        parts = []
                last_message = ""
                customer_name = "Unknown Customer"
                response_status = "unknown"  # awaiting_agent, awaiting_customer, or unknown
                last_message_author = None
                
                # Get customer info
                contacts = convo.get("contacts", {}).get("contacts", [])
                customer_name = "Unknown Customer"
                if contacts:
                    contact = contacts[0]
                    # Try name first, then email, then fallback
                    name = contact.get("name", "").strip()
                    email = contact.get("email", "").strip()
                    
                    if name and name != "":
                        customer_name = name
                    elif email and email != "":
                        # Use email but hide domain for privacy
                        customer_name = email.split("@")[0] + "@..."
                    
                    # Handle non-English names or special characters
                    if len(customer_name) > 25:
                        customer_name = customer_name[:25] + "..."
                
                # Analyze conversation parts to determine response status and get context
                # Look for the most recent meaningful message (comment type)
                # Iterate newest first
                for part in sorted(parts, key=lambda p: p.get("created_at", 0), reverse=True):
                    if part.get("part_type") != "comment":
                        continue
                    author = part.get("author", {})
                    author_type = author.get("type", "")
                    if not last_message_author:
                        if author_type == "user":
                            response_status = "awaiting_agent"
                            last_message_author = "customer"
                        elif author_type == "admin":
                            response_status = "awaiting_customer"
                            last_message_author = "agent"
                    if not last_message and author_type == "user":
                        msg = part.get("body", "")
                        if msg:
                            import re
                            msg = re.sub(r'<[^>]+>', '', msg)
                            msg = ' '.join(msg.split())
                            if len(msg) > 80:
                                msg = msg[:80] + "..."
                            last_message = msg
                    if last_message_author and last_message:
                        break
                
                # Update response status counts
                current_status["response_status"][response_status] += 1
                
                # Format waiting time
                if waiting_hours < 1:
                    waiting_str = f"{int(waiting_hours * 60)}m"
                elif waiting_hours < 24:
                    waiting_str = f"{waiting_hours:.1f}h"
                else:
                    waiting_str = f"{waiting_hours/24:.1f}d"
                
                convo_details = {
                    "id": convo_id,
                    "subject": subject,
                    "customer": customer_name,
                    "assigned_to": assigned_to,
                    "priority": priority,
                    "waiting_time": waiting_str,
                    "waiting_hours": waiting_hours,
                    "last_message": last_message,
                    "state": state,
                    "response_status": response_status,  # awaiting_agent, awaiting_customer, unknown
                    "last_message_author": last_message_author
                }
                
                current_status["conversations"].append(convo_details)
            
            # Sort by waiting time (longest first)
            current_status["conversations"].sort(key=lambda x: x["waiting_hours"], reverse=True)
            
            return current_status
            
        except Exception as e:
            print(f"Error getting current open conversations: {e}")
            return {
                "total_open": 0,
                "conversations": [],
                "priority_breakdown": {"high": 0, "medium": 0, "low": 0, "none": 0},
                "assignment_breakdown": {"assigned": 0, "unassigned": 0},
                "response_status": {"awaiting_agent": 0, "awaiting_customer": 0, "unknown": 0},
                "waiting_time_analysis": {"under_1h": 0, "1h_to_4h": 0, "4h_to_24h": 0, "over_24h": 0}
            }
    
    def get_detailed_response_metrics_24h(self, conversation_ids: List[str] = None, sample_size: int = None) -> Dict:
        """Get detailed response time metrics for responses in the last 24 hours.

        Clarifies the meaning of the window to avoid inflated averages:
        - A "fresh" response is when BOTH the customer message and the admin response occurred within the last 24 hours.
        - A "backlog" response is when the admin responded in the last 24 hours to a customer message that is older than 24 hours.

        This separation prevents very old unanswered conversations (answered today) from inflating
        the 24h average response time. We still expose backlog performance for transparency.

        Returns dict fields:
        conversations_analyzed: conversations that had at least one admin response in last 24h
        responses_count: total admin responses in last 24h (fresh + backlog)
        fresh_responses_count / backlog_responses_count: split counts
        first_response_times: first responses within 24h window where customer msg also inside window
        avg_response_times: all responses (fresh + backlog) for backward compatibility
        fresh_response_times / backlog_response_times: split arrays
        response_times_by_admin: only fresh responses (to reflect current-day performance)
        backlog_response_times_by_admin: backlog responses per admin
        """
        from collections import defaultdict

        response_metrics = {
            'conversations_analyzed': 0,
            'responses_count': 0,
            'fresh_responses_count': 0,
            'backlog_responses_count': 0,
            'first_response_times': [],              # only fresh first responses
            'avg_response_times': [],                # all (legacy field)
            'fresh_response_times': [],              # fresh only
            'backlog_response_times': [],            # backlog only
            'response_times_by_admin': defaultdict(list),            # fresh
            'backlog_response_times_by_admin': defaultdict(list)     # backlog
        }

        if not conversation_ids:
            return response_metrics

        # Sample conversations if requested
        sample_conversations = conversation_ids[:sample_size] if sample_size is not None else conversation_ids

        cutoff_time_24h = datetime.now().timestamp() - (24 * 60 * 60)

        for conv_id in sample_conversations:
            try:
                conv_detail = self.get_conversation_parts(conv_id)
                if 'conversation_parts' not in conv_detail:
                    continue

                parts = conv_detail['conversation_parts']['conversation_parts']
                if not parts:
                    continue

                conversation_had_recent_response = False
                customer_message_time = None
                first_fresh_response_recorded = False

                for part in parts:
                    if part.get('part_type') != 'comment':
                        continue

                    created_at = part.get('created_at', 0)
                    author = part.get('author', {})
                    author_type = author.get('type')

                    if author_type == 'user':
                        customer_message_time = created_at
                    elif author_type == 'admin' and customer_message_time:
                        # Only consider admin responses that happened in last 24h
                        if created_at >= cutoff_time_24h:
                            conversation_had_recent_response = True
                            response_time = (created_at - customer_message_time) / 60  # minutes

                            # Classify fresh vs backlog
                            is_fresh = customer_message_time >= cutoff_time_24h
                            admin_name = author.get('name', 'Unknown')

                            # Always maintain legacy aggregate list
                            response_metrics['avg_response_times'].append(response_time)
                            response_metrics['responses_count'] += 1

                            if is_fresh:
                                response_metrics['fresh_response_times'].append(response_time)
                                response_metrics['response_times_by_admin'][admin_name].append(response_time)
                                response_metrics['fresh_responses_count'] += 1
                                if not first_fresh_response_recorded:
                                    response_metrics['first_response_times'].append(response_time)
                                    first_fresh_response_recorded = True
                            else:
                                response_metrics['backlog_response_times'].append(response_time)
                                response_metrics['backlog_response_times_by_admin'][admin_name].append(response_time)
                                response_metrics['backlog_responses_count'] += 1

                        # Reset after an admin response regardless of window inclusion
                        customer_message_time = None

                if conversation_had_recent_response:
                    response_metrics['conversations_analyzed'] += 1

            except Exception as e:
                print(f"Error analyzing 24h conversation {conv_id}: {e}")
                continue

        # Convert defaultdicts for JSON serialization
        response_metrics['response_times_by_admin'] = dict(response_metrics['response_times_by_admin'])
        response_metrics['backlog_response_times_by_admin'] = dict(response_metrics['backlog_response_times_by_admin'])
        return response_metrics

def save_metrics_to_file(data: Dict, filename: str = None):
    """Save metrics data to a JSON file.
    
    Args:
        data: Dictionary containing metrics data
        filename: Optional filename, defaults to timestamp-based name
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intercom_metrics_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"Metrics saved to {filename}")

def main():
    def env_bool(name: str, default: str = "true") -> bool:
        val = os.getenv(name, default)
        if val is None:
            val = default
        return str(val).lower() == 'true'
    # Get Intercom access token from environment
    ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
    if not ACCESS_TOKEN:
        print("ERROR: INTERCOM_ACCESS_TOKEN environment variable not set!")
        print("Please create a .env file with your Intercom access token.")
        print("See .env.example for the required format.")
        sys.exit(1)
    
    # Initialize client
    client = IntercomMetricsClient(ACCESS_TOKEN)
    
    print("Pulling Intercom metrics...")
    
    try:
        # Collect all metrics
        metrics_data = {
            "extraction_date": datetime.now().isoformat(),
            "workspace_data": {}
        }
        
        print("- Getting admins...")
        metrics_data["workspace_data"]["admins"] = client.get_admins()
        
        print("- Getting conversation counts...")
        metrics_data["workspace_data"]["conversation_counts"] = client.get_conversation_counts()
        
        print("- Getting companies...")
        metrics_data["workspace_data"]["companies"] = client.get_companies()
        
        print("- Getting contacts...")
        metrics_data["workspace_data"]["contacts"] = client.get_contacts()

        print("- Getting conversations (with pagination if enabled)...")
        exclude_spam = env_bool("EXCLUDE_SPAM_CONVERSATIONS", "true")
        paginate = env_bool("PAGINATE_CONVERSATIONS", "true")
        page_size = int(os.getenv("CONVERSATION_PAGE_SIZE", "50"))
        max_pages = os.getenv("CONVERSATION_MAX_PAGES")
        max_pages_int = int(max_pages) if max_pages and max_pages.isdigit() else None
        if paginate:
            conversations_agg = client.get_conversations_paginated(page_size=page_size, exclude_spam=exclude_spam, max_pages=max_pages_int)
            metrics_data["workspace_data"]["conversations"] = conversations_agg
        else:
            metrics_data["workspace_data"]["conversations"] = client.get_conversations(page_size=page_size, exclude_spam=exclude_spam)
        
        print("- Getting tags...")
        metrics_data["workspace_data"]["tags"] = client.get_tags()
        
        print("- Getting segments...")
        metrics_data["workspace_data"]["segments"] = client.get_segments()
        
        print("- Analyzing SLA performance...")
        sla_analysis = client.analyze_sla_performance(metrics_data["workspace_data"]["conversations"])
        metrics_data["workspace_data"]["sla_analysis"] = sla_analysis
        
        print("- Calculating daily metrics...")
        daily_metrics = client.calculate_daily_metrics(metrics_data["workspace_data"]["conversations"], days_back=30)
        metrics_data["workspace_data"]["daily_metrics"] = daily_metrics
        
        print("- Analyzing response times (last 14 days)...")
        conversations_list = metrics_data["workspace_data"]["conversations"].get("conversations", [])
        
        # Filter conversations from last 14 days
        cutoff_time_14d = datetime.now().timestamp() - (14 * 24 * 60 * 60)
        recent_conversations_14d = [
            conv for conv in conversations_list 
            if conv.get("created_at", 0) >= cutoff_time_14d and "id" in conv
        ]
        recent_conversation_ids_14d = [conv["id"] for conv in recent_conversations_14d]
        
        response_metrics = client.get_detailed_response_metrics(recent_conversation_ids_14d, sample_size=None)
        metrics_data["workspace_data"]["response_metrics"] = response_metrics
        
        print("- Analyzing response times (last 24 hours)...")
        # For 24-hour analysis, use a larger sample of recent conversations
        # Since we need conversations that had responses in the last 24 hours, not just created
        # We'll analyze all recent conversations and filter responses by timestamp in the detailed analysis
        response_metrics_24h = client.get_detailed_response_metrics_24h(recent_conversation_ids_14d, sample_size=None)
        metrics_data["workspace_data"]["response_metrics_24h"] = response_metrics_24h
        
        print("- Analyzing all conversation states (paginated open/snoozed if enabled)...")
        if paginate:
            # Fetch broader sets for open and snoozed states separately to improve accuracy
            open_data = client.get_conversations_paginated(page_size=page_size, state="open", exclude_spam=exclude_spam, max_pages=max_pages_int)
            snoozed_data = client.get_conversations_paginated(page_size=page_size, state="snoozed", exclude_spam=exclude_spam, max_pages=max_pages_int)
            closed_sample = client.get_conversations(page_size=min(page_size, 20), state="closed", exclude_spam=exclude_spam)
            # Temporarily inject into client-style structure to reuse analyzer
            def wrapper(dataset):
                return {'conversations': dataset.get('conversations', [])}
            all_conversation_states = {
                **client.get_all_conversation_states(limit=page_size, exclude_spam=exclude_spam),
            }
            # Overwrite with full fetched lists for open/snoozed before re-analysis
            all_conversation_states['open_conversations'] = client._analyze_conversations_by_state(wrapper(open_data), 'open', limit=len(open_data.get('conversations', [])))
            all_conversation_states['snoozed_conversations'] = client._analyze_conversations_by_state(wrapper(snoozed_data), 'snoozed', limit=len(snoozed_data.get('conversations', [])))
            all_conversation_states['state_breakdown']['open'] = len(open_data.get('conversations', []))
            all_conversation_states['state_breakdown']['snoozed'] = len(snoozed_data.get('conversations', []))
            # closed retained
        else:
            all_conversation_states = client.get_all_conversation_states()
        metrics_data["workspace_data"]["conversation_states"] = all_conversation_states
        
        # Keep backward compatibility
        metrics_data["workspace_data"]["current_conversations"] = all_conversation_states["open_conversations"]
        
        # Save to file
        save_metrics_to_file(metrics_data)
        
        # Print summary
        print("\n=== Metrics Summary ===")
        admin_count = len(metrics_data["workspace_data"]["admins"].get("admins", []))
        print(f"Admins: {admin_count}")
        
        companies_data = metrics_data["workspace_data"]["companies"]
        company_count = len(companies_data.get("companies", []))
        print(f"Companies: {company_count}")
        
        contacts_data = metrics_data["workspace_data"]["contacts"]
        contact_count = len(contacts_data.get("contacts", []))
        print(f"Contacts: {contact_count}")
        
        conversations_data = metrics_data["workspace_data"]["conversations"]
        conversation_count = len(conversations_data.get("conversations", []))
        print(f"Conversations: {conversation_count}")
        # Pagination summary
        pagination_meta = metrics_data['workspace_data'].get('conversations', {}).get('pagination')
        if pagination_meta:
            capped_note = " (CAP REACHED)" if pagination_meta.get('capped') else ""
            print(f"Pagination: pages={pagination_meta.get('pages_fetched')} size={pagination_meta.get('page_size')} total={pagination_meta.get('total_conversations')}{capped_note}")
        
        tags_data = metrics_data["workspace_data"]["tags"]
        tag_count = len(tags_data.get("tags", []))
        print(f"Tags: {tag_count}")
        
        segments_data = metrics_data["workspace_data"]["segments"]
        segment_count = len(segments_data.get("segments", []))
        print(f"Segments: {segment_count}")
        
        counts = metrics_data["workspace_data"]["conversation_counts"]
        if "conversation" in counts:
            conv_counts = counts["conversation"]
            print(f"Open conversations: {conv_counts.get('open', 'N/A')}")
            print(f"Closed conversations: {conv_counts.get('closed', 'N/A')}")
            print(f"Assigned conversations: {conv_counts.get('assigned', 'N/A')}")
            print(f"Unassigned conversations: {conv_counts.get('unassigned', 'N/A')}")
        
        # Print daily metrics
        daily_data = metrics_data["workspace_data"]["daily_metrics"]
        print(f"\n=== Daily Metrics ({daily_data['analysis_period_days']} days) ===")
        print(f"Average conversations per day: {daily_data['overall_metrics']['conversations_per_day']:.1f}")
        print(f"Busiest day: {daily_data['overall_metrics']['busiest_day']}")
        
        if daily_data['daily_stats']:
            print(f"\n=== Recent Days Breakdown ===")
            sorted_days = sorted(daily_data['daily_stats'].items(), reverse=True)[:14]  # Last 14 days
            for date, stats in sorted_days:
                print(f"{date}: {stats['conversations_created']} created, {stats['conversations_closed']} closed")
                if stats['conversations_by_admin']:
                    admins_summary = ", ".join([f"{admin}({count})" for admin, count in stats['conversations_by_admin'].items()])
                    print(f"  By admin: {admins_summary}")
        
        # Print response time metrics
        response_data = metrics_data["workspace_data"]["response_metrics"]
        print(f"\n=== Response Time Analysis (last 14 days) ===")
        print(f"Conversations analyzed: {response_data['conversations_analyzed']}")
        
        if response_data['first_response_times']:
            avg_first_response = sum(response_data['first_response_times']) / len(response_data['first_response_times'])
            print(f"Average first response time: {avg_first_response:.1f} minutes")
        
        if response_data['avg_response_times']:
            avg_response = sum(response_data['avg_response_times']) / len(response_data['avg_response_times'])
            print(f"Average response time: {avg_response:.1f} minutes")
        
        # Removed business hours tracking for 24/7 operations
        
        if response_data['response_times_by_admin']:
            print(f"\n=== Response Times by Admin ===")
            for admin, times in response_data['response_times_by_admin'].items():
                if times:
                    avg_time = sum(times) / len(times)
                    print(f"{admin}: {avg_time:.1f} min avg ({len(times)} responses)")
        
        # Print 24-hour response time metrics (improved clarity)
        response_data_24h = metrics_data["workspace_data"]["response_metrics_24h"]
        print(f"\n=== Response Time Analysis (last 24 hours) ===")
        print(f"Conversations with any admin response in window: {response_data_24h['conversations_analyzed']}")
        print(f"Total responses: {response_data_24h['responses_count']} (fresh: {response_data_24h['fresh_responses_count']}, backlog: {response_data_24h['backlog_responses_count']})")

        def fmt_stats(label, arr):
            if not arr:
                print(f"{label}: n/a")
                return
            avg_v = mean(arr)
            med_v = median(arr)
            # Provide hours if large
            if avg_v >= 120:  # 2h threshold
                print(f"{label}: {avg_v:.1f} min (avg) / {med_v:.1f} min (median)  ~{avg_v/60:.2f}h avg")
            else:
                print(f"{label}: {avg_v:.1f} min (avg) / {med_v:.1f} min (median)")

        fmt_stats("Fresh responses (customer + agent within 24h)", response_data_24h['fresh_response_times'])
        fmt_stats("Backlog responses (customer msg older)", response_data_24h['backlog_response_times'])
        fmt_stats("All responses (legacy avg)", response_data_24h['avg_response_times'])
        fmt_stats("First responses (fresh only)", response_data_24h['first_response_times'])

        if response_data_24h['response_times_by_admin']:
            print(f"\n=== 24h Fresh Response Times by Admin ===")
            for admin, times in response_data_24h['response_times_by_admin'].items():
                if times:
                    avg_time = mean(times)
                    med_time = median(times)
                    if avg_time >= 120:
                        print(f"{admin}: {avg_time:.1f} min avg / {med_time:.1f} min median (~{avg_time/60:.2f}h) [{len(times)} fresh]")
                    else:
                        print(f"{admin}: {avg_time:.1f} min avg / {med_time:.1f} min median [{len(times)} fresh]")

        if response_data_24h['backlog_response_times_by_admin']:
            print(f"\n=== 24h Backlog Response Times by Admin (answered old msgs) ===")
            for admin, times in response_data_24h['backlog_response_times_by_admin'].items():
                if times:
                    avg_time = mean(times)
                    med_time = median(times)
                    print(f"{admin}: {avg_time/60:.2f}h avg / {med_time/60:.2f}h median ({len(times)} backlog)")
        print("Note: 'Backlog' responses are replies given today to messages older than 24h and are excluded from 'fresh' averages to avoid inflation.")
        
    except Exception as e:
        import traceback
        print(f"Error extracting metrics: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()