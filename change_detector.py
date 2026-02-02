"""
FIS Situational Awareness System - Change Detection Engine

Detects material changes between entity snapshots and scores their significance.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models import ChangeRecord


logger = logging.getLogger(__name__)


class ChangeDetector:
    """
    Detects material changes between entity snapshots.

    Compares current state against previous state to identify
    additions, removals, and modifications.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_changes(
        self,
        current_entities: List[Dict[str, Any]],
        previous_entities: List[Dict[str, Any]]
    ) -> List[ChangeRecord]:
        """
        Detect changes between current and previous entity states.

        Args:
            current_entities: Newly ingested entities
            previous_entities: Previous snapshot entities

        Returns:
            List of detected changes with significance scores
        """
        changes = []

        # Build lookup maps
        current_map = self._build_entity_map(current_entities)
        previous_map = self._build_entity_map(previous_entities)

        # Detect additions
        for entity_key, entity in current_map.items():
            if entity_key not in previous_map:
                change = self._create_change_record(
                    entity_type=entity["entity_type"],
                    entity_id=entity["entity_id"],
                    change_type="added",
                    previous_value=None,
                    new_value=entity["data"]
                )
                changes.append(change)

        # Detect removals
        for entity_key, entity in previous_map.items():
            if entity_key not in current_map:
                change = self._create_change_record(
                    entity_type=entity["entity_type"],
                    entity_id=entity["entity_id"],
                    change_type="removed",
                    previous_value=entity["data"],
                    new_value=None
                )
                changes.append(change)

        # Detect modifications
        for entity_key in current_map:
            if entity_key in previous_map:
                current_entity = current_map[entity_key]
                previous_entity = previous_map[entity_key]

                field_changes = self._detect_field_changes(
                    previous_entity["data"],
                    current_entity["data"]
                )

                for field_name, (prev_val, new_val) in field_changes.items():
                    change = self._create_change_record(
                        entity_type=current_entity["entity_type"],
                        entity_id=current_entity["entity_id"],
                        change_type="modified",
                        previous_value={field_name: prev_val},
                        new_value={field_name: new_val},
                        field_changed=field_name
                    )
                    changes.append(change)

        self.logger.info(f"Detected {len(changes)} changes")
        return changes

    def _build_entity_map(self, entities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build entity lookup map keyed by (entity_type, entity_id)."""
        entity_map = {}
        for entity in entities:
            key = (entity["entity_type"], entity["entity_id"])
            entity_map[key] = entity
        return entity_map

    def _detect_field_changes(
        self,
        previous: Dict[str, Any],
        current: Dict[str, Any]
    ) -> Dict[str, Tuple[Any, Any]]:
        """
        Detect field-level changes between two entity states.

        Returns:
            Dict mapping field_name to (previous_value, new_value)
        """
        changes = {}

        # Check all fields in current
        for field_name, new_value in current.items():
            prev_value = previous.get(field_name)
            if prev_value != new_value and field_name not in ["last_seen", "last_updated", "source"]:
                changes[field_name] = (prev_value, new_value)

        return changes

    def _create_change_record(
        self,
        entity_type: str,
        entity_id: str,
        change_type: str,
        previous_value: Optional[Dict[str, Any]],
        new_value: Optional[Dict[str, Any]],
        field_changed: Optional[str] = None
    ) -> ChangeRecord:
        """Create a change record with significance scoring."""

        # Calculate significance score
        score, level = self._calculate_significance(
            entity_type,
            change_type,
            previous_value,
            new_value,
            field_changed
        )

        # Generate rationale
        rationale = self._generate_rationale(
            entity_type,
            change_type,
            previous_value,
            new_value,
            field_changed,
            score,
            level
        )

        return ChangeRecord(
            change_id=uuid.uuid4(),
            entity_type=entity_type,
            entity_id=entity_id,
            change_type=change_type,
            previous_value=previous_value,
            new_value=new_value,
            field_changed=field_changed,
            significance_score=score,
            significance_level=level,
            rationale=rationale,
            change_timestamp=datetime.now(timezone.utc)
        )

    def _calculate_significance(
        self,
        entity_type: str,
        change_type: str,
        previous_value: Optional[Dict[str, Any]],
        new_value: Optional[Dict[str, Any]],
        field_changed: Optional[str]
    ) -> Tuple[int, str]:
        """
        Calculate significance score (0-100) and level (CRITICAL/HIGH/MEDIUM/LOW).

        Based on user requirement: Alert on CRITICAL only (executive/strategic changes).
        """
        score = 0

        # Base scores by entity type
        entity_scores = {
            "stakeholder": 30,
            "program": 25,
            "risk": 35,
            "timeline": 20,
            "governance": 25,
            "external_event": 40
        }
        score += entity_scores.get(entity_type, 10)

        # Modifiers based on change type
        if change_type == "added":
            score += 15
        elif change_type == "removed":
            score += 20
        elif change_type == "modified":
            score += 10

        # Entity-specific modifiers
        if entity_type == "stakeholder":
            role = (new_value or previous_value or {}).get("role", "")
            if role in ["CEO", "CFO", "CTO"]:
                score += 40  # C-Suite changes are critical
            elif role in ["Board Chairman", "Board Member"]:
                score += 35  # Board changes are critical
            elif role in ["Executive Sponsor", "AI Program Lead"]:
                score += 20  # Program leadership changes

        if entity_type == "program":
            if field_changed == "status":
                new_status = (new_value or {}).get("status", "")
                if new_status in ["Blocked", "At Risk"]:
                    score += 30  # Status degradation

        if entity_type == "risk":
            severity = (new_value or {}).get("severity", "")
            if severity == "Critical":
                score += 40
            elif severity == "High":
                score += 25

        if entity_type == "external_event":
            event_type = (new_value or {}).get("event_type", "")
            if event_type in ["M&A", "Executive Change"]:
                score += 40  # Strategic events
            elif event_type in ["SEC Filing (8-K)", "Regulatory Action"]:
                score += 35  # Regulatory events
            elif event_type in ["SEC Filing (10-K)", "SEC Filing (10-Q)"]:
                score += 15  # Routine filings

        # Cap at 100
        score = min(score, 100)

        # Categorize
        if score >= 75:
            level = "CRITICAL"
        elif score >= 60:
            level = "HIGH"
        elif score >= 40:
            level = "MEDIUM"
        else:
            level = "LOW"

        return score, level

    def _generate_rationale(
        self,
        entity_type: str,
        change_type: str,
        previous_value: Optional[Dict[str, Any]],
        new_value: Optional[Dict[str, Any]],
        field_changed: Optional[str],
        score: int,
        level: str
    ) -> str:
        """Generate human-readable rationale for why this change is significant."""

        if entity_type == "stakeholder":
            role = (new_value or previous_value or {}).get("role", "Unknown")
            name = (new_value or previous_value or {}).get("name", "Unknown")

            if change_type == "added":
                return f"{role} {name} added to FIS organization. C-Suite and board changes may signal strategic shifts."
            elif change_type == "removed":
                return f"{role} {name} removed from FIS organization. Leadership departures may indicate organizational changes."
            elif change_type == "modified" and field_changed == "role":
                prev_role = (previous_value or {}).get("role", "Unknown")
                return f"{name} role changed from {prev_role} to {role}. Leadership restructuring may impact programs."

        if entity_type == "program":
            name = (new_value or previous_value or {}).get("name", "Unknown")
            if change_type == "modified" and field_changed == "status":
                prev_status = (previous_value or {}).get("status", "Unknown")
                new_status = (new_value or {}).get("status", "Unknown")
                return f"Program {name} status changed from {prev_status} to {new_status}. This may require immediate attention from program leadership."

        if entity_type == "risk":
            severity = (new_value or previous_value or {}).get("severity", "Unknown")
            if change_type == "added":
                return f"New {severity} risk detected. This may require immediate attention from program leadership."
            elif change_type == "modified" and field_changed == "severity":
                return f"Risk severity changed to {(new_value or {}).get('severity')}. This may require immediate attention from program leadership."

        if entity_type == "external_event":
            event_type = (new_value or {}).get("event_type", "Unknown")
            title = (new_value or {}).get("title", "Unknown")
            return f"External event detected: {event_type} - {title}. This may impact FIS strategic direction or market position."

        if entity_type == "timeline":
            milestone = (new_value or previous_value or {}).get("milestone", "Unknown")
            if change_type == "modified" and field_changed == "status":
                new_status = (new_value or {}).get("status", "Unknown")
                return f"Timeline milestone '{milestone}' status changed to {new_status}. This may impact program delivery schedule."

        # Default rationale
        return f"Material change detected in {entity_type}. Review for potential program impact."
