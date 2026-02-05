"""
FIS Situational Awareness System - Weekly Executive Digest Generator

Generates weekly executive summaries of FIS account status and changes.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from mcp import ClientSession
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from config import config
from models import DetectedChange, EntitySnapshot, IngestionRun


logger = logging.getLogger(__name__)


class DigestGenerator:
    """
    Generates weekly executive digest for FIS account.

    Aggregates changes, risks, opportunities, and external signals
    from the past week into a concise executive summary (≤250 words).
    """

    def __init__(self, db_session: Session, mcp_session: ClientSession):
        self.db = db_session
        self.mcp_session = mcp_session
        self.logger = logging.getLogger(__name__)

    async def generate_and_send_digest(self) -> Dict[str, Any]:
        """
        Generate and send weekly executive digest to Slack.

        Returns:
            Dict with generation stats and delivery status
        """
        self.logger.info("Starting weekly digest generation")

        # Get changes from past week
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        changes = self._get_weekly_changes(cutoff_date)

        # Get external events from past week
        external_events = self._get_external_events(cutoff_date)

        # Generate digest sections
        account_snapshot = self._generate_account_snapshot(changes)
        what_changed = self._generate_what_changed(changes)
        key_risks = self._generate_key_risks(changes)
        opportunities = self._generate_opportunities(external_events, changes)
        decisions_needed = self._generate_decisions_needed(changes)
        external_signals = self._generate_external_signals(external_events)

        # Format digest message
        digest_message = self._format_digest(
            account_snapshot=account_snapshot,
            what_changed=what_changed,
            key_risks=key_risks,
            opportunities=opportunities,
            decisions_needed=decisions_needed,
            external_signals=external_signals
        )

        # Send to Slack
        message_ts = await self._send_to_slack(digest_message)

        self.logger.info("Weekly digest sent successfully")

        return {
            "success": True,
            "changes_analyzed": len(changes),
            "external_events_analyzed": len(external_events),
            "message_ts": message_ts,
            "word_count": len(digest_message.split()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _get_weekly_changes(self, since: datetime) -> List[DetectedChange]:
        """Get all detected changes from the past week."""
        changes = self.db.execute(
            select(DetectedChange)
            .where(DetectedChange.change_timestamp >= since)
            .order_by(desc(DetectedChange.significance_score))
        ).scalars().all()

        return list(changes)

    def _get_external_events(self, since: datetime) -> List[EntitySnapshot]:
        """Get external events from the past week."""
        external_events = self.db.execute(
            select(EntitySnapshot)
            .where(
                and_(
                    EntitySnapshot.entity_type == "external_event",
                    EntitySnapshot.snapshot_timestamp >= since
                )
            )
            .order_by(desc(EntitySnapshot.snapshot_timestamp))
        ).scalars().all()

        return list(external_events)

    def _generate_account_snapshot(self, changes: List[DetectedChange]) -> Dict[str, str]:
        """
        Generate Account Snapshot section.

        Returns:
            Dict with status, momentum, and summary
        """
        # Calculate status based on changes
        critical_count = sum(1 for c in changes if c.significance_level == "CRITICAL")
        high_count = sum(1 for c in changes if c.significance_level == "HIGH")

        # Determine status
        if critical_count >= 3:
            status = "Red"
        elif critical_count >= 1 or high_count >= 5:
            status = "Yellow"
        else:
            status = "Green"

        # Determine momentum by comparing to previous week
        # For now, use simple heuristic based on change types
        negative_changes = sum(
            1 for c in changes
            if c.change_type == "removed" or
            (c.entity_type == "risk" and c.change_type == "added") or
            (c.entity_type == "program" and "blocked" in str(c.new_value).lower())
        )
        positive_changes = sum(
            1 for c in changes
            if c.change_type == "added" and c.entity_type not in ["risk"] or
            (c.entity_type == "program" and "completed" in str(c.new_value).lower())
        )

        if negative_changes > positive_changes + 2:
            momentum = "Deteriorating"
        elif positive_changes > negative_changes + 2:
            momentum = "Improving"
        else:
            momentum = "Flat"

        # Generate summary
        if len(changes) == 0:
            summary = "No material changes detected this week; account remains stable."
        elif status == "Red":
            summary = f"Multiple critical issues requiring immediate attention; {critical_count} critical changes detected."
        elif status == "Yellow":
            summary = f"Account showing some concerning signals; monitoring {critical_count + high_count} high-priority changes."
        else:
            summary = "Account progressing normally with routine updates."

        return {
            "status": status,
            "momentum": momentum,
            "summary": summary
        }

    def _generate_what_changed(self, changes: List[DetectedChange]) -> List[str]:
        """
        Generate What Changed This Week section.

        Returns:
            List of material change descriptions (material = HIGH or CRITICAL)
        """
        material_changes = [
            c for c in changes
            if c.significance_level in ["CRITICAL", "HIGH"]
        ]

        # Limit to top 5 most significant
        material_changes = material_changes[:5]

        change_descriptions = []
        for change in material_changes:
            desc = self._summarize_change(change)
            if desc:
                change_descriptions.append(desc)

        return change_descriptions

    def _summarize_change(self, change: DetectedChange) -> Optional[str]:
        """Summarize a change into one concise bullet point."""
        entity_type = change.entity_type.replace("_", " ").title()

        if change.entity_type == "stakeholder":
            name = (change.new_value or change.previous_value or {}).get("name", "Unknown")
            role = (change.new_value or change.previous_value or {}).get("role", "Unknown")

            if change.change_type == "added":
                return f"New {role} added: {name}"
            elif change.change_type == "removed":
                return f"{role} departed: {name}"
            elif change.field_changed == "role":
                return f"{name} role changed to {(change.new_value or {}).get('role', 'Unknown')}"

        elif change.entity_type == "program":
            name = (change.new_value or change.previous_value or {}).get("name", "Unknown")

            if change.field_changed == "status":
                old_status = (change.previous_value or {}).get("status", "Unknown")
                new_status = (change.new_value or {}).get("status", "Unknown")
                return f"{name} status: {old_status} → {new_status}"

        elif change.entity_type == "risk":
            severity = (change.new_value or change.previous_value or {}).get("severity", "Unknown")
            desc = (change.new_value or change.previous_value or {}).get("description", "Unknown")[:50]

            if change.change_type == "added":
                return f"New {severity} risk: {desc}"

        elif change.entity_type == "external_event":
            title = (change.new_value or {}).get("title", "Unknown")
            event_type = (change.new_value or {}).get("event_type", "Unknown")
            return f"{event_type}: {title}"

        # Fallback
        return f"{entity_type} {change.change_type}"

    def _generate_key_risks(self, changes: List[DetectedChange]) -> List[Dict[str, str]]:
        """
        Generate Key Risks & Watch Items section.

        Returns:
            List of up to 3 risks with description, why it matters, and outcome
        """
        # Get risk-related changes
        risk_changes = [
            c for c in changes
            if c.entity_type == "risk" or
            (c.entity_type == "program" and "blocked" in str(c.new_value).lower()) or
            c.significance_level == "CRITICAL"
        ]

        # Sort by significance and take top 3
        risk_changes = sorted(risk_changes, key=lambda c: c.significance_score, reverse=True)[:3]

        risks = []
        for change in risk_changes:
            risk = {
                "description": self._summarize_change(change) or "Risk detected",
                "why_matters": self._extract_why_matters(change),
                "outcome": self._predict_outcome(change)
            }
            risks.append(risk)

        return risks

    def _extract_why_matters(self, change: DetectedChange) -> str:
        """Extract why a change matters from its rationale."""
        # Use the rationale field which already contains this
        rationale = change.rationale or "Impact unclear"

        # Extract the "why it matters" part
        if "may" in rationale.lower():
            parts = rationale.split("may")
            if len(parts) > 1:
                return "May" + parts[1].strip()

        return "Requires attention due to potential program impact."

    def _predict_outcome(self, change: DetectedChange) -> str:
        """Predict likely outcome if unaddressed."""
        if change.entity_type == "risk":
            severity = (change.new_value or {}).get("severity", "Unknown")
            if severity == "Critical":
                return "Program delay or failure if unresolved within 48 hours."
            elif severity == "High":
                return "Timeline slippage likely within next sprint."
            else:
                return "Minor impact if addressed within 2 weeks."

        elif change.entity_type == "program":
            status = (change.new_value or {}).get("status", "")
            if "blocked" in status.lower():
                return "Milestone delay and potential budget overrun."
            elif "at risk" in status.lower():
                return "Requires intervention to prevent escalation."

        elif change.entity_type == "stakeholder":
            role = (change.new_value or change.previous_value or {}).get("role", "")
            if "ceo" in role.lower() or "cfo" in role.lower():
                return "Strategic direction may shift; relationship reset needed."

        return "Impact assessment ongoing."

    def _generate_opportunities(
        self,
        external_events: List[EntitySnapshot],
        changes: List[DetectedChange]
    ) -> List[Dict[str, str]]:
        """
        Generate Opportunities section.

        Returns:
            List of up to 3 opportunities with brief rationale
        """
        opportunities = []

        # Look for partnership announcements in external events
        for event in external_events[:10]:
            event_data = event.entity_data
            event_type = event_data.get("event_type", "")
            title = event_data.get("title", "")

            if "partnership" in event_type.lower():
                opportunities.append({
                    "description": f"Leverage FIS partnership: {title[:50]}",
                    "rationale": "Potential to expand collaboration scope."
                })

            elif "m&a" in event_type.lower():
                opportunities.append({
                    "description": f"M&A activity: {title[:50]}",
                    "rationale": "New leadership may accelerate AI adoption."
                })

        # Look for positive program changes
        for change in changes:
            if change.entity_type == "program" and "completed" in str(change.new_value).lower():
                program_name = (change.new_value or {}).get("name", "Unknown")
                opportunities.append({
                    "description": f"Expand {program_name} scope",
                    "rationale": "Successful delivery builds trust for next phase."
                })

        # Limit to top 3
        return opportunities[:3]

    def _generate_decisions_needed(self, changes: List[DetectedChange]) -> List[Dict[str, str]]:
        """
        Generate Decisions or Actions Needed section.

        Returns:
            List of decisions/actions requiring leadership attention
        """
        decisions = []

        # Look for CRITICAL changes requiring decisions
        critical_changes = [c for c in changes if c.significance_level == "CRITICAL"]

        for change in critical_changes[:3]:
            if change.entity_type == "stakeholder":
                role = (change.new_value or change.previous_value or {}).get("role", "Unknown")
                if any(exec_role in role for exec_role in ["CEO", "CFO", "CTO", "Executive"]):
                    decisions.append({
                        "action": f"Schedule intro with new {role}",
                        "due_date": "Within 2 weeks",
                        "owner": "Account Lead"
                    })

            elif change.entity_type == "program":
                status = (change.new_value or {}).get("status", "")
                if "blocked" in status.lower():
                    program_name = (change.new_value or {}).get("name", "Unknown")
                    decisions.append({
                        "action": f"Unblock {program_name} - escalate internally",
                        "due_date": "This week",
                        "owner": "Delivery Lead"
                    })

            elif change.entity_type == "risk":
                severity = (change.new_value or {}).get("severity", "")
                if severity == "Critical":
                    decisions.append({
                        "action": "Review critical risk mitigation plan",
                        "due_date": "Immediate",
                        "owner": "Exec Sponsor"
                    })

        return decisions

    def _generate_external_signals(self, external_events: List[EntitySnapshot]) -> str:
        """
        Generate External Signals section.

        Returns:
            Brief summary of external developments
        """
        if not external_events:
            return "No relevant external signals this week."

        # Categorize events
        ma_events = []
        exec_changes = []
        financial_reports = []
        other_events = []

        for event in external_events:
            event_data = event.entity_data
            event_type = event_data.get("event_type", "")
            title = event_data.get("title", "")

            if "m&a" in event_type.lower():
                ma_events.append(title)
            elif "executive" in event_type.lower():
                exec_changes.append(title)
            elif "financial" in event_type.lower() or "earnings" in event_type.lower():
                financial_reports.append(title)
            else:
                other_events.append(title)

        # Build summary
        summary_parts = []

        if ma_events:
            summary_parts.append(f"M&A activity detected ({len(ma_events)} events)")
        if exec_changes:
            summary_parts.append(f"{len(exec_changes)} leadership changes")
        if financial_reports:
            summary_parts.append(f"Financial results published")
        if other_events and len(summary_parts) < 2:
            summary_parts.append(f"{len(other_events)} other developments")

        if summary_parts:
            return "; ".join(summary_parts) + ". Monitoring for strategic implications."
        else:
            return "No material external signals this week."

    def _format_digest(
        self,
        account_snapshot: Dict[str, str],
        what_changed: List[str],
        key_risks: List[Dict[str, str]],
        opportunities: List[Dict[str, str]],
        decisions_needed: List[Dict[str, str]],
        external_signals: str
    ) -> str:
        """
        Format digest into Slack message (≤250 words).

        Args:
            account_snapshot: Status, momentum, summary
            what_changed: List of material changes
            key_risks: List of risks with context
            opportunities: List of opportunities
            decisions_needed: List of required actions
            external_signals: External summary

        Returns:
            Formatted Slack message
        """
        lines = []

        # Header
        lines.append("📊 **FIS WEEKLY EXECUTIVE DIGEST**")
        lines.append(f"*Week of {datetime.now(timezone.utc).strftime('%B %d, %Y')}*")
        lines.append("")

        # 1) Account Snapshot
        lines.append(f"**Account Snapshot:** {account_snapshot['status']} | {account_snapshot['momentum']}")
        lines.append(account_snapshot['summary'])
        lines.append("")

        # 2) What Changed This Week
        lines.append("**What Changed:**")
        if what_changed:
            for change in what_changed:
                lines.append(f"• {change}")
        else:
            lines.append("• No material changes this week")
        lines.append("")

        # 3) Key Risks & Watch Items
        lines.append("**Key Risks:**")
        if key_risks:
            for i, risk in enumerate(key_risks, 1):
                lines.append(f"{i}. {risk['description']}")
                lines.append(f"   ↳ {risk['why_matters']}")
        else:
            lines.append("• No material risks identified this week")
        lines.append("")

        # 4) Opportunities
        if opportunities:
            lines.append("**Opportunities:**")
            for opp in opportunities:
                lines.append(f"• {opp['description']} - {opp['rationale']}")
            lines.append("")

        # 5) Decisions or Actions Needed
        lines.append("**Actions Needed:**")
        if decisions_needed:
            for decision in decisions_needed:
                lines.append(f"• {decision['action']} ({decision['owner']}, by {decision['due_date']})")
        else:
            lines.append("• No exec action required this week")
        lines.append("")

        # 6) External Signals
        lines.append("**External Signals:**")
        lines.append(external_signals)

        message = "\n".join(lines)

        # Check word count and trim if needed
        word_count = len(message.split())
        if word_count > 250:
            self.logger.warning(f"Digest exceeds 250 words ({word_count}). Consider trimming.")

        return message

    async def _send_to_slack(self, message: str) -> str:
        """
        Send digest to Slack channel.

        Args:
            message: Formatted digest message

        Returns:
            Message timestamp from Slack
        """
        channel_id = config.alerting.channel_id

        if not channel_id:
            self.logger.warning("No Slack channel configured for digest")
            return "no-channel-configured"

        try:
            result = await self.mcp_session.call_tool(
                "slack_send_message",
                arguments={
                    "channel_id": channel_id,
                    "message": message
                }
            )

            self.logger.info(f"Digest sent to {channel_id}")
            return datetime.now(timezone.utc).isoformat()

        except Exception as e:
            self.logger.error(f"Failed to send digest to Slack: {e}")
            raise
