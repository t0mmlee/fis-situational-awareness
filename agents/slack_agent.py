"""
FIS Situational Awareness System - Slack Ingestion Agent

Ingests FIS-related data from Slack via Tribe MCP.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agents.base import BaseIngestionAgent, IngestionResult
from config import config


class SlackIngestionAgent(BaseIngestionAgent):
    """
    Ingests FIS-related Slack data via Tribe MCP.

    Uses slack_search_public_and_private to discover FIS mentions,
    then enriches with thread context and user profiles.
    """

    def __init__(self, mcp_session):
        super().__init__("slack", mcp_session)
        self.search_query = config.ingestion.slack_search_query

    async def ingest(self, since: Optional[datetime] = None) -> IngestionResult:
        """
        Ingest Slack data.

        Args:
            since: Only fetch messages since this timestamp

        Returns:
            IngestionResult with stats
        """
        start_time = datetime.now(timezone.utc)
        errors = []

        try:
            await self.log_ingestion_start()

            # Search for FIS mentions
            raw_messages = await self._search_slack(since)
            self.logger.info(f"Found {len(raw_messages)} FIS-related messages")

            # Enrich with thread context
            enriched_messages = await self._enrich_with_threads(raw_messages)

            # Normalize to FIS entities
            entities = await self.normalize(enriched_messages)
            self.logger.info(f"Extracted {len(entities)} entities from Slack")

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return IngestionResult(
                source=self.source_name,
                success=True,
                items_ingested=len(raw_messages),
                items_changed=len(entities),
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            self.logger.error(f"Slack ingestion failed: {e}")
            errors.append(str(e))
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return IngestionResult(
                source=self.source_name,
                success=False,
                items_ingested=0,
                items_changed=0,
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc)
            )

    async def _search_slack(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Search Slack for FIS mentions.

        Args:
            since: Only fetch messages since this timestamp

        Returns:
            List of raw message dictionaries
        """
        # Build search query with date filter
        query = self.search_query
        if since:
            query += f" after:{since.strftime('%Y-%m-%d')}"

        # Call Tribe MCP slack_search_public_and_private
        result_content = await self.call_mcp_tool(
            "slack_search_public_and_private",
            arguments={
                "query": query,
                "limit": 20,
                "sort": "timestamp",
                "sort_dir": "desc"
            }
        )

        # Parse search results
        messages = self._parse_slack_search_results(result_content)
        return messages

    def _parse_slack_search_results(self, content: Any) -> List[Dict[str, Any]]:
        """
        Parse Slack search results from MCP tool output.

        Args:
            content: Raw MCP tool result content

        Returns:
            List of message dictionaries
        """
        parsed = self.parse_json_content(content)

        messages = []

        # MCP slack_search returns formatted text, need to parse it
        if isinstance(parsed, dict) and "text" in parsed:
            text = parsed["text"]
            # Parse the formatted output
            # Example format: "### Result 1 of 2\nChannel: #dev\nFrom: Jane (U123)"
            result_blocks = re.split(r"### Result \d+ of \d+", text)
            for block in result_blocks[1:]:  # Skip first empty split
                msg = self._parse_message_block(block)
                if msg:
                    messages.append(msg)

        return messages

    def _parse_message_block(self, block: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single message block from search results.

        Args:
            block: Text block for one message

        Returns:
            Message dictionary or None if parsing fails
        """
        try:
            lines = block.strip().split("\n")
            msg = {}

            for line in lines:
                if line.startswith("Channel:"):
                    channel_match = re.search(r"#([\w-]+)\s*\((C[A-Z0-9]+)\)", line)
                    if channel_match:
                        msg["channel_name"] = channel_match.group(1)
                        msg["channel_id"] = channel_match.group(2)
                elif line.startswith("From:"):
                    user_match = re.search(r"From:\s*(.+?)\s*\(([UW][A-Z0-9]+)\)", line)
                    if user_match:
                        msg["user_name"] = user_match.group(1)
                        msg["user_id"] = user_match.group(2)
                elif line.startswith("Time:"):
                    time_str = line.replace("Time:", "").strip()
                    msg["timestamp"] = datetime.fromisoformat(time_str.replace(" UTC", "+00:00"))
                elif line.startswith("Message_ts:"):
                    msg["message_ts"] = line.replace("Message_ts:", "").strip()
                elif line.startswith("Text:"):
                    msg["text"] = line.replace("Text:", "").strip()
                elif line.startswith("🧵 Thread:"):
                    msg["has_thread"] = True

            if "text" in msg and "channel_id" in msg:
                return msg

        except Exception as e:
            self.logger.warning(f"Failed to parse message block: {e}")

        return None

    async def _enrich_with_threads(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich messages with thread context.

        Args:
            messages: List of message dictionaries

        Returns:
            Enriched messages with thread context
        """
        enriched = []

        for msg in messages:
            # If message has a thread, fetch thread context
            if msg.get("has_thread") and msg.get("message_ts"):
                try:
                    thread_content = await self.call_mcp_tool(
                        "slack_read_thread",
                        arguments={
                            "channel_id": msg["channel_id"],
                            "message_ts": msg["message_ts"]
                        }
                    )
                    msg["thread_context"] = self.parse_json_content(thread_content)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch thread for message {msg['message_ts']}: {e}")

            enriched.append(msg)

        return enriched

    async def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize Slack messages into FIS entities.

        Extract stakeholders, programs, risks, timelines, and governance items
        from Slack message content.

        Args:
            raw_data: Raw Slack messages

        Returns:
            List of normalized FIS entities
        """
        entities = []

        for msg in raw_data:
            # Extract stakeholder mentions
            stakeholders = self._extract_stakeholders(msg)
            entities.extend(stakeholders)

            # Extract program status updates
            programs = self._extract_programs(msg)
            entities.extend(programs)

            # Extract risks and blockers
            risks = self._extract_risks(msg)
            entities.extend(risks)

            # Extract timeline updates
            timelines = self._extract_timelines(msg)
            entities.extend(timelines)

        return entities

    def _extract_stakeholders(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract stakeholder mentions from Slack message."""
        stakeholders = []

        # Extract sender as stakeholder
        if msg.get("user_name") and msg.get("user_id"):
            stakeholder = {
                "entity_type": "stakeholder",
                "entity_id": msg["user_id"],
                "data": {
                    "name": msg["user_name"],
                    "role": "Unknown",  # Would need to enrich with user profile
                    "company": "Unknown",
                    "last_seen": msg.get("timestamp", datetime.now(timezone.utc)).isoformat()
                }
            }
            stakeholders.append(stakeholder)

        return stakeholders

    def _extract_programs(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract program updates from Slack message."""
        programs = []
        text = msg.get("text", "").lower()

        # Detect program mentions (Agent Factory, CDD MVP, etc.)
        program_keywords = {
            "agent factory": "Agent Factory",
            "cdd": "CDD MVP",
            "deposit pricing": "Deposit Pricing",
            "agentic platform": "Agentic Platform"
        }

        for keyword, program_name in program_keywords.items():
            if keyword in text:
                # Detect status keywords
                status = "In Progress"  # Default
                if any(word in text for word in ["blocked", "blocker", "blocking"]):
                    status = "Blocked"
                elif any(word in text for word in ["at risk", "risk", "delayed"]):
                    status = "At Risk"
                elif any(word in text for word in ["completed", "done", "finished"]):
                    status = "Completed"

                program = {
                    "entity_type": "program",
                    "entity_id": program_name.lower().replace(" ", "_"),
                    "data": {
                        "name": program_name,
                        "status": status,
                        "last_updated": msg.get("timestamp", datetime.now(timezone.utc)).isoformat(),
                        "source": f"slack://{msg.get('channel_id')}/{msg.get('message_ts')}"
                    }
                }
                programs.append(program)

        return programs

    def _extract_risks(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract risks and blockers from Slack message."""
        risks = []
        text = msg.get("text", "").lower()

        # Detect risk keywords
        risk_keywords = ["blocked", "blocker", "risk", "issue", "problem", "delay", "failure"]

        if any(keyword in text for keyword in risk_keywords):
            # Determine severity
            severity = "Medium"
            if any(word in text for word in ["critical", "urgent", "emergency"]):
                severity = "Critical"
            elif any(word in text for word in ["high", "major", "significant"]):
                severity = "High"

            risk = {
                "entity_type": "risk",
                "entity_id": self.extract_entity_id("risk", {"description": text}),
                "data": {
                    "category": "Technical",  # Default, would need AI to classify
                    "severity": severity,
                    "description": msg.get("text", "")[:200],
                    "status": "Open",
                    "first_detected": msg.get("timestamp", datetime.now(timezone.utc)).isoformat(),
                    "source": f"slack://{msg.get('channel_id')}/{msg.get('message_ts')}"
                }
            }
            risks.append(risk)

        return risks

    def _extract_timelines(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract timeline updates from Slack message."""
        timelines = []
        text = msg.get("text", "")

        # Detect date mentions (e.g., "January 31", "Q1 2026", "Dec 31 deadline")
        date_patterns = [
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}",
            r"Q[1-4]\s+\d{4}",
            r"\d{1,2}/\d{1,2}/\d{4}"
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract milestone context (look for words before the date)
                milestone_match = re.search(rf"(\w+(?:\s+\w+)?)\s+{re.escape(match)}", text, re.IGNORECASE)
                milestone = milestone_match.group(1) if milestone_match else "Unknown Milestone"

                timeline = {
                    "entity_type": "timeline",
                    "entity_id": self.extract_entity_id("timeline", {"milestone": milestone}),
                    "data": {
                        "milestone": milestone,
                        "target_date": msg.get("timestamp", datetime.now(timezone.utc)).isoformat(),  # Would need to parse actual date
                        "status": "On Track",  # Default
                        "source": f"slack://{msg.get('channel_id')}/{msg.get('message_ts')}"
                    }
                }
                timelines.append(timeline)

        return timelines
