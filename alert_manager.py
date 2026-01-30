"""
FIS Situational Awareness System - Alert Manager

Formats and sends Slack notifications for high-significance changes.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging

from mcp import ClientSession
from .models import ChangeRecord, AlertMessage
from .config import config


logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alert formatting, deduplication, and delivery via Slack.

    Ensures only CRITICAL changes are alerted, deduplicates alerts,
    and formats messages for optimal readability.
    """

    def __init__(self, mcp_session: ClientSession):
        self.mcp_session = mcp_session
        self.channel_id = config.alerting.channel_id
        self.significance_threshold = config.alerting.significance_threshold
        self.dedup_window_hours = config.alerting.dedup_window_hours
        self.logger = logging.getLogger(__name__)

    async def process_changes(
        self,
        changes: List[ChangeRecord],
        alert_history: List[dict]
    ) -> List[AlertMessage]:
        """
        Process changes and send alerts for significant ones.

        Args:
            changes: List of detected changes
            alert_history: Previous alerts for deduplication

        Returns:
            List of alerts that were sent
        """
        alerts_sent = []

        for change in changes:
            # Filter by significance threshold (CRITICAL only)
            if change.significance_score < self.significance_threshold:
                self.logger.debug(
                    f"Change {change.change_id} below threshold "
                    f"({change.significance_score} < {self.significance_threshold})"
                )
                continue

            # Check deduplication
            if self._is_duplicate(change, alert_history):
                self.logger.info(f"Change {change.change_id} is duplicate, skipping alert")
                continue

            # Format and send alert
            try:
                alert = self._format_alert(change)
                await self._send_alert(alert)
                alerts_sent.append(alert)
                self.logger.info(f"Alert sent for change {change.change_id}")
            except Exception as e:
                self.logger.error(f"Failed to send alert for change {change.change_id}: {e}")

        return alerts_sent

    def _is_duplicate(
        self,
        change: ChangeRecord,
        alert_history: List[dict]
    ) -> bool:
        """
        Check if alert would be a duplicate.

        Args:
            change: Change to check
            alert_history: Previous alerts

        Returns:
            True if duplicate, False otherwise
        """
        # Check for exact duplicate (same change_id)
        for alert in alert_history:
            if alert.get("change_id") == change.change_id:
                return True

        # Check for similar alerts in dedup window
        cutoff_time = datetime.now() - timedelta(hours=self.dedup_window_hours)

        for alert in alert_history:
            alert_time = alert.get("alert_timestamp")
            if alert_time and alert_time > cutoff_time:
                # Same entity and change type
                if (alert.get("entity_type") == change.entity_type and
                    alert.get("entity_id") == change.entity_id and
                    alert.get("change_type") == change.change_type):
                    return True

        return False

    def _format_alert(self, change: ChangeRecord) -> AlertMessage:
        """
        Format change into an alert message.

        Args:
            change: Change to format

        Returns:
            AlertMessage ready to send
        """
        # Build change summary
        summary = self._build_change_summary(change)

        # Build affected entities list
        affected_entities = self._build_affected_entities(change)

        # Build source links
        source_links = self._extract_source_links(change)

        alert = AlertMessage(
            change_id=change.change_id,
            level=change.significance_level,
            score=change.significance_score,
            summary=summary,
            rationale=change.rationale,
            affected_entities=affected_entities,
            source_links=source_links,
            timestamp=datetime.now()
        )

        return alert

    def _build_change_summary(self, change: ChangeRecord) -> str:
        """Build human-readable change summary."""
        entity_type = change.entity_type.replace("_", " ").title()

        if change.change_type == "added":
            if change.entity_type == "stakeholder":
                name = (change.new_value or {}).get("name", "Unknown")
                role = (change.new_value or {}).get("role", "Unknown")
                return f"New {role} added: {name}"
            elif change.entity_type == "external_event":
                title = (change.new_value or {}).get("title", "Unknown")
                return f"External event detected: {title}"
            else:
                return f"New {entity_type} added"

        elif change.change_type == "removed":
            if change.entity_type == "stakeholder":
                name = (change.previous_value or {}).get("name", "Unknown")
                role = (change.previous_value or {}).get("role", "Unknown")
                return f"{role} removed: {name}"
            else:
                return f"{entity_type} removed"

        elif change.change_type == "modified":
            field = change.field_changed or "unknown field"
            prev_val = (change.previous_value or {}).get(field, "Unknown")
            new_val = (change.new_value or {}).get(field, "Unknown")
            return f"{entity_type} {field} changed from '{prev_val}' to '{new_val}'"

        return f"{entity_type} {change.change_type}"

    def _build_affected_entities(self, change: ChangeRecord) -> List[str]:
        """Build list of affected FIS context areas."""
        affected = []

        if change.entity_type == "stakeholder":
            affected.append("Executive Leadership")
            affected.append("Strategic Decision-Making")

        if change.entity_type == "program":
            program_name = (change.new_value or change.previous_value or {}).get("name", "Unknown")
            affected.append(f"Program: {program_name}")
            affected.append("Phase 1 Milestones")

        if change.entity_type == "risk":
            affected.append("Program Delivery")
            affected.append("Timeline & Schedule")

        if change.entity_type == "external_event":
            affected.append("Corporate Strategy")
            affected.append("Market Position")
            affected.append("Competitive Dynamics")

        if change.entity_type == "timeline":
            affected.append("Project Schedule")
            affected.append("Milestone Delivery")

        return affected

    def _extract_source_links(self, change: ChangeRecord) -> List[str]:
        """Extract source URLs from change data."""
        sources = []

        # Check both previous and new values for source fields
        for value_dict in [change.previous_value, change.new_value]:
            if value_dict:
                source = value_dict.get("source")
                url = value_dict.get("url")

                if source and source not in sources:
                    sources.append(source)
                if url and url not in sources:
                    sources.append(url)

        return sources

    async def _send_alert(self, alert: AlertMessage) -> str:
        """
        Send alert to Slack via Tribe MCP.

        Args:
            alert: Alert message to send

        Returns:
            Message timestamp from Slack
        """
        # Format message in Markdown
        message = self._format_slack_message(alert)

        # Send via MCP slack_send_message
        result = await self.mcp_session.call_tool(
            "slack_send_message",
            arguments={
                "channel_id": self.channel_id,
                "message": message
            }
        )

        # Extract message_ts from result
        # (would need to parse MCP tool response)
        message_ts = "unknown"

        self.logger.info(f"Alert sent to {self.channel_id}")
        return message_ts

    def _format_slack_message(self, alert: AlertMessage) -> str:
        """
        Format alert as Slack markdown message.

        Args:
            alert: Alert to format

        Returns:
            Formatted Slack message
        """
        lines = []

        # Header
        lines.append("🚨 **FIS Situational Awareness Alert** 🚨")
        lines.append("")

        # What changed
        lines.append("**What Changed:**")
        lines.append(alert.summary)
        lines.append("")

        # Significance
        lines.append(f"**Significance:** {alert.level} (Score: {alert.score}/100)")
        lines.append("")

        # Why it matters
        lines.append("**Why It Matters:**")
        lines.append(alert.rationale)
        lines.append("")

        # Context impact
        if alert.affected_entities:
            lines.append("**Context Impact:**")
            for entity in alert.affected_entities:
                lines.append(f"• {entity}")
            lines.append("")

        # Sources
        if alert.source_links:
            lines.append("**Source:**")
            for source in alert.source_links:
                if source.startswith("http"):
                    lines.append(f"• {source}")
                else:
                    lines.append(f"• {source}")
            lines.append("")

        # Timestamp
        lines.append(f"**Detected:** {alert.timestamp.strftime('%Y-%m-%d %I:%M %p %Z')}")
        lines.append("───────────────────────────────")
        lines.append("React with ✅ to acknowledge this alert.")

        return "\n".join(lines)
