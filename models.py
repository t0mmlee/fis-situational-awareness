"""
FIS Situational Awareness System - Database Models

SQLAlchemy models for storing ingestion data, entity snapshots,
detected changes, and alert history.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class IngestionRun(Base):
    """
    Records each ingestion cycle execution.

    Tracks when ingestion runs occurred, which sources were processed,
    and whether they succeeded or failed.
    """

    __tablename__ = "ingestion_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source = Column(String(50), nullable=False)  # slack, notion, news, sec
    status = Column(String(20), nullable=False)  # success, partial, failed
    items_ingested = Column(Integer, default=0)
    items_changed = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    entity_snapshots = relationship(
        "EntitySnapshot",
        back_populates="ingestion_run",
        cascade="all, delete-orphan"
    )
    detected_changes = relationship(
        "DetectedChange",
        back_populates="ingestion_run",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<IngestionRun(id={self.id}, source={self.source}, status={self.status})>"


class EntitySnapshot(Base):
    """
    Historical snapshots of FIS entities.

    Stores the complete state of each entity at each ingestion cycle,
    enabling time-travel queries and diff computation.
    """

    __tablename__ = "entity_snapshots"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "snapshot_timestamp", name="uix_entity_snapshot"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)  # stakeholder, program, risk, timeline, governance, external_event
    entity_id = Column(String(255), nullable=False)
    snapshot_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    entity_data = Column(JSONB, nullable=False)
    ingestion_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ingestion_run = relationship("IngestionRun", back_populates="entity_snapshots")

    def __repr__(self) -> str:
        return f"<EntitySnapshot(type={self.entity_type}, id={self.entity_id}, ts={self.snapshot_timestamp})>"


class DetectedChange(Base):
    """
    Records detected changes between entity snapshots.

    Stores diffs, significance scores, and rationale for each change.
    """

    __tablename__ = "detected_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    change_type = Column(String(50), nullable=False)  # added, removed, modified
    previous_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    field_changed = Column(String(100), nullable=True)  # which field changed (for modified type)
    significance_score = Column(Integer, nullable=False)  # 0-100
    significance_level = Column(String(20), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    rationale = Column(Text, nullable=False)  # why this change matters
    alert_sent = Column(Boolean, default=False)
    alert_timestamp = Column(DateTime(timezone=True), nullable=True)
    ingestion_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ingestion_run = relationship("IngestionRun", back_populates="detected_changes")
    alerts = relationship(
        "AlertHistory",
        back_populates="change",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DetectedChange(type={self.entity_type}, change={self.change_type}, level={self.significance_level})>"


class AlertHistory(Base):
    """
    Tracks all alerts sent to Slack.

    Used for deduplication, acknowledgment tracking, and audit trail.
    """

    __tablename__ = "alert_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    change_id = Column(UUID(as_uuid=True), ForeignKey("detected_changes.id"), nullable=False)
    channel = Column(String(100), nullable=False)  # #fis-situational-awareness
    message_text = Column(Text, nullable=False)
    message_ts = Column(String(50), nullable=True)  # Slack message timestamp
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    change = relationship("DetectedChange", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<AlertHistory(id={self.id}, channel={self.channel}, ack={self.acknowledged})>"


# Pydantic models for API/serialization

from pydantic import BaseModel, Field
from typing import Any, Dict, List


class StakeholderEntity(BaseModel):
    """Stakeholder entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Full name")
    role: str = Field(..., description="Role (CEO, CFO, CTO, etc.)")
    email: Optional[str] = Field(None, description="Email address")
    company: str = Field(..., description="Company (FIS or Tribe AI)")
    last_seen: datetime = Field(..., description="Last seen timestamp")


class ProgramEntity(BaseModel):
    """Program entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Program name")
    status: str = Field(..., description="Status (In Progress, Blocked, etc.)")
    phase: Optional[str] = Field(None, description="Phase (Phase 1, Phase 2, etc.)")
    timeline: Dict[str, Any] = Field(default_factory=dict, description="Milestones and deadlines")
    risks: List[Dict[str, Any]] = Field(default_factory=list, description="Associated risks")
    last_updated: datetime = Field(..., description="Last updated timestamp")


class RiskEntity(BaseModel):
    """Risk entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    category: str = Field(..., description="Risk category")
    severity: str = Field(..., description="Severity (Critical, High, Medium, Low)")
    description: str = Field(..., description="Risk description")
    mitigation: Optional[str] = Field(None, description="Mitigation strategy")
    status: str = Field(..., description="Status (Open, Mitigated, Closed)")
    first_detected: datetime = Field(..., description="First detected timestamp")
    last_updated: datetime = Field(..., description="Last updated timestamp")


class TimelineEntity(BaseModel):
    """Timeline entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    milestone: str = Field(..., description="Milestone name")
    target_date: datetime = Field(..., description="Target completion date")
    actual_date: Optional[datetime] = Field(None, description="Actual completion date")
    status: str = Field(..., description="Status (On Track, At Risk, Delayed, Completed)")
    dependencies: List[str] = Field(default_factory=list, description="Dependent milestones")


class GovernanceEntity(BaseModel):
    """Governance entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    decision: str = Field(..., description="Decision description")
    decision_maker: str = Field(..., description="Decision maker")
    decision_date: datetime = Field(..., description="Decision date")
    rationale: str = Field(..., description="Decision rationale")
    impact: str = Field(..., description="Impact description")


class ExternalEventEntity(BaseModel):
    """External event entity model."""
    entity_id: str = Field(..., description="Unique identifier")
    event_type: str = Field(..., description="Event type (News, SEC Filing, M&A, etc.)")
    title: str = Field(..., description="Event title")
    description: str = Field(..., description="Event description")
    source: str = Field(..., description="Source URL or name")
    url: Optional[str] = Field(None, description="Source URL")
    event_date: datetime = Field(..., description="Event date")
    significance: str = Field(..., description="Significance (Critical, High, Medium, Low)")


class ChangeRecord(BaseModel):
    """Change record model."""
    change_id: uuid.UUID = Field(..., description="Change ID")
    entity_type: str = Field(..., description="Entity type")
    entity_id: str = Field(..., description="Entity ID")
    change_type: str = Field(..., description="Change type (added, removed, modified)")
    previous_value: Optional[Dict[str, Any]] = Field(None, description="Previous value")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New value")
    field_changed: Optional[str] = Field(None, description="Field that changed")
    significance_score: int = Field(..., description="Significance score (0-100)")
    significance_level: str = Field(..., description="Significance level")
    rationale: str = Field(..., description="Why this change matters")
    change_timestamp: datetime = Field(..., description="When change was detected")


class AlertMessage(BaseModel):
    """Alert message model."""
    change_id: uuid.UUID = Field(..., description="Associated change ID")
    level: str = Field(..., description="Alert level (CRITICAL, HIGH, etc.)")
    score: int = Field(..., description="Significance score")
    summary: str = Field(..., description="What changed")
    rationale: str = Field(..., description="Why it matters")
    affected_entities: List[str] = Field(..., description="Affected FIS context areas")
    source_links: List[str] = Field(..., description="Source URLs or references")
    timestamp: datetime = Field(..., description="Alert timestamp")
