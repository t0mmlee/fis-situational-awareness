"""
FIS Situational Awareness System - Temporal Activities

Implements all activities called by workflows.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker
from temporalio import activity

from agents.external_agent import ExternalIngestionAgent
from agents.notion_agent import NotionIngestionAgent
from agents.slack_agent import SlackIngestionAgent
from alert_manager import AlertManager
from change_detector import ChangeDetector
from config import config
from models import Base, EntitySnapshot, DetectedChange, IngestionRun, AlertHistory

# Configure logging
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(
    str(config.database.url),
    pool_size=config.database.pool_size,
    max_overflow=config.database.max_overflow,
    echo=config.database.echo,
)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, caller will close


async def get_mcp_session() -> ClientSession:
    """
    Create and return MCP client session.

    Returns:
        Active MCP ClientSession
    """
    server_params = StdioServerParameters(
        command=config.mcp.server_path,
        args=config.mcp.server_args,
    )

    # Create stdio client
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return session


@activity.defn
async def slack_ingestion(since: Optional[str] = None) -> Dict[str, Any]:
    """
    Ingest data from Slack.

    Args:
        since: ISO timestamp to ingest from

    Returns:
        Ingestion result dictionary
    """
    activity.logger.info("Starting Slack ingestion activity")

    db = get_db()
    try:
        # Parse since timestamp
        since_dt = datetime.fromisoformat(since) if since else None

        # Create MCP session
        server_params = StdioServerParameters(
            command=config.mcp.server_path,
            args=config.mcp.server_args,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create agent and run ingestion
                agent = SlackIngestionAgent(session)
                result = await agent.ingest(since=since_dt)

                # Store ingestion run in database
                ingestion_run = IngestionRun(
                    source="slack",
                    status="success" if result.success else "failed",
                    items_ingested=result.items_ingested,
                    items_changed=result.items_changed,
                    error_log="\n".join(result.errors) if result.errors else None,
                    duration_seconds=int(result.duration_seconds),
                    run_timestamp=result.timestamp,
                )
                db.add(ingestion_run)
                db.commit()

                activity.logger.info(f"Slack ingestion completed: {result.items_ingested} items")

                return {
                    "success": result.success,
                    "items_ingested": result.items_ingested,
                    "items_changed": result.items_changed,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                }

    except Exception as e:
        activity.logger.error(f"Slack ingestion failed: {e}")
        # Store failed run
        ingestion_run = IngestionRun(
            source="slack",
            status="failed",
            items_ingested=0,
            items_changed=0,
            error_log=str(e),
            duration_seconds=0,
        )
        db.add(ingestion_run)
        db.commit()
        raise
    finally:
        db.close()


@activity.defn
async def notion_ingestion(since: Optional[str] = None) -> Dict[str, Any]:
    """
    Ingest data from Notion.

    Args:
        since: ISO timestamp to ingest from

    Returns:
        Ingestion result dictionary
    """
    activity.logger.info("Starting Notion ingestion activity")

    db = get_db()
    try:
        # Parse since timestamp
        since_dt = datetime.fromisoformat(since) if since else None

        # Create MCP session
        server_params = StdioServerParameters(
            command=config.mcp.server_path,
            args=config.mcp.server_args,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create agent and run ingestion
                agent = NotionIngestionAgent(session)
                result = await agent.ingest(since=since_dt)

                # Store ingestion run in database
                ingestion_run = IngestionRun(
                    source="notion",
                    status="success" if result.success else "failed",
                    items_ingested=result.items_ingested,
                    items_changed=result.items_changed,
                    error_log="\n".join(result.errors) if result.errors else None,
                    duration_seconds=int(result.duration_seconds),
                    run_timestamp=result.timestamp,
                )
                db.add(ingestion_run)
                db.commit()

                activity.logger.info(f"Notion ingestion completed: {result.items_ingested} items")

                return {
                    "success": result.success,
                    "items_ingested": result.items_ingested,
                    "items_changed": result.items_changed,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                }

    except Exception as e:
        activity.logger.error(f"Notion ingestion failed: {e}")
        # Store failed run
        ingestion_run = IngestionRun(
            source="notion",
            status="failed",
            items_ingested=0,
            items_changed=0,
            error_log=str(e),
            duration_seconds=0,
        )
        db.add(ingestion_run)
        db.commit()
        raise
    finally:
        db.close()


@activity.defn
async def external_ingestion(since: Optional[str] = None) -> Dict[str, Any]:
    """
    Ingest data from external sources (news, SEC).

    Args:
        since: ISO timestamp to ingest from

    Returns:
        Ingestion result dictionary
    """
    activity.logger.info("Starting external sources ingestion activity")

    db = get_db()
    try:
        # Parse since timestamp
        since_dt = datetime.fromisoformat(since) if since else None

        # Create MCP session (needed for base class)
        server_params = StdioServerParameters(
            command=config.mcp.server_path,
            args=config.mcp.server_args,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create agent and run ingestion
                agent = ExternalIngestionAgent(session)
                result = await agent.ingest(since=since_dt)

                # Store ingestion run in database
                ingestion_run = IngestionRun(
                    source="external",
                    status="success" if result.success else "failed",
                    items_ingested=result.items_ingested,
                    items_changed=result.items_changed,
                    error_log="\n".join(result.errors) if result.errors else None,
                    duration_seconds=int(result.duration_seconds),
                    run_timestamp=result.timestamp,
                )
                db.add(ingestion_run)
                db.commit()

                activity.logger.info(f"External ingestion completed: {result.items_ingested} items")

                return {
                    "success": result.success,
                    "items_ingested": result.items_ingested,
                    "items_changed": result.items_changed,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                }

    except Exception as e:
        activity.logger.error(f"External ingestion failed: {e}")
        # Store failed run
        ingestion_run = IngestionRun(
            source="external",
            status="failed",
            items_ingested=0,
            items_changed=0,
            error_log=str(e),
            duration_seconds=0,
        )
        db.add(ingestion_run)
        db.commit()
        raise
    finally:
        db.close()


@activity.defn
async def detect_changes() -> Dict[str, Any]:
    """
    Detect changes between current and previous entity snapshots.

    Returns:
        Change detection result dictionary
    """
    activity.logger.info("Starting change detection activity")

    db = get_db()
    try:
        # Get most recent ingestion run
        latest_run = db.execute(
            select(IngestionRun)
            .order_by(desc(IngestionRun.run_timestamp))
            .limit(1)
        ).scalar_one_or_none()

        if not latest_run:
            activity.logger.warning("No ingestion runs found")
            return {"changes_detected": 0, "changes": []}

        # Get current entities (from latest run)
        current_snapshots = db.execute(
            select(EntitySnapshot)
            .where(EntitySnapshot.ingestion_run_id == latest_run.id)
        ).scalars().all()

        # Get previous entities (from second-to-latest run)
        previous_run = db.execute(
            select(IngestionRun)
            .where(IngestionRun.id != latest_run.id)
            .order_by(desc(IngestionRun.run_timestamp))
            .limit(1)
        ).scalar_one_or_none()

        previous_snapshots = []
        if previous_run:
            previous_snapshots = db.execute(
                select(EntitySnapshot)
                .where(EntitySnapshot.ingestion_run_id == previous_run.id)
            ).scalars().all()

        # Convert to entity dictionaries
        current_entities = [
            {
                "entity_type": s.entity_type,
                "entity_id": s.entity_id,
                "data": s.entity_data,
            }
            for s in current_snapshots
        ]

        previous_entities = [
            {
                "entity_type": s.entity_type,
                "entity_id": s.entity_id,
                "data": s.entity_data,
            }
            for s in previous_snapshots
        ]

        # Detect changes
        detector = ChangeDetector()
        changes = detector.detect_changes(current_entities, previous_entities)

        # Store detected changes in database
        for change in changes:
            detected_change = DetectedChange(
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                change_type=change.change_type,
                previous_value=change.previous_value,
                new_value=change.new_value,
                field_changed=change.field_changed,
                significance_score=change.significance_score,
                significance_level=change.significance_level,
                rationale=change.rationale,
                ingestion_run_id=latest_run.id,
            )
            db.add(detected_change)

        db.commit()

        activity.logger.info(f"Change detection completed: {len(changes)} changes detected")

        return {
            "changes_detected": len(changes),
            "changes": [
                {
                    "entity_type": c.entity_type,
                    "entity_id": c.entity_id,
                    "change_type": c.change_type,
                    "significance_score": c.significance_score,
                    "significance_level": c.significance_level,
                }
                for c in changes
            ],
        }

    except Exception as e:
        activity.logger.error(f"Change detection failed: {e}")
        raise
    finally:
        db.close()


@activity.defn
async def process_alerts() -> Dict[str, Any]:
    """
    Process alerts for CRITICAL changes.

    Returns:
        Alert processing result dictionary
    """
    activity.logger.info("Starting alert processing activity")

    db = get_db()
    try:
        # Get unsent CRITICAL changes
        critical_changes = db.execute(
            select(DetectedChange)
            .where(
                DetectedChange.alert_sent == False,
                DetectedChange.significance_score >= config.alerting.significance_threshold
            )
            .order_by(desc(DetectedChange.significance_score))
        ).scalars().all()

        if not critical_changes:
            activity.logger.info("No CRITICAL changes to alert")
            return {"alerts_sent": 0, "alerts": []}

        # Get alert history for deduplication
        alert_history = db.execute(
            select(AlertHistory)
            .order_by(desc(AlertHistory.alert_timestamp))
            .limit(100)
        ).scalars().all()

        alert_history_dicts = [
            {
                "change_id": str(a.change_id),
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "change_type": a.change_type,
                "alert_timestamp": a.alert_timestamp,
            }
            for a in alert_history
        ]

        # Create MCP session for Slack alerting
        server_params = StdioServerParameters(
            command=config.mcp.server_path,
            args=config.mcp.server_args,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create alert manager
                alert_manager = AlertManager(session)

                # Convert DetectedChange objects to ChangeRecord-like dicts
                changes = [
                    type('ChangeRecord', (), {
                        'change_id': str(c.id),
                        'entity_type': c.entity_type,
                        'entity_id': c.entity_id,
                        'change_type': c.change_type,
                        'previous_value': c.previous_value,
                        'new_value': c.new_value,
                        'field_changed': c.field_changed,
                        'significance_score': c.significance_score,
                        'significance_level': c.significance_level,
                        'rationale': c.rationale,
                    })()
                    for c in critical_changes
                ]

                # Process alerts
                alerts_sent = await alert_manager.process_changes(changes, alert_history_dicts)

                # Update database with sent alerts
                for alert in alerts_sent:
                    # Mark change as alerted
                    change = db.get(DetectedChange, alert.change_id)
                    if change:
                        change.alert_sent = True
                        change.alert_timestamp = datetime.now(timezone.utc)

                    # Record alert history
                    alert_record = AlertHistory(
                        change_id=alert.change_id,
                        channel_id=config.alerting.channel_id,
                        message_text=alert.summary,
                        slack_message_ts=str(datetime.now(timezone.utc).timestamp()),
                        entity_type=change.entity_type if change else "unknown",
                        entity_id=change.entity_id if change else "unknown",
                        change_type=change.change_type if change else "unknown",
                    )
                    db.add(alert_record)

                db.commit()

                activity.logger.info(f"Alert processing completed: {len(alerts_sent)} alerts sent")

                return {
                    "alerts_sent": len(alerts_sent),
                    "alerts": [
                        {
                            "change_id": a.change_id,
                            "level": a.level,
                            "score": a.score,
                            "summary": a.summary,
                        }
                        for a in alerts_sent
                    ],
                }

    except Exception as e:
        activity.logger.error(f"Alert processing failed: {e}")
        raise
    finally:
        db.close()


@activity.defn
async def get_last_ingestion_timestamp() -> Dict[str, Any]:
    """
    Get the timestamp of the last successful ingestion.

    Returns:
        Dictionary with timestamp
    """
    db = get_db()
    try:
        latest_run = db.execute(
            select(IngestionRun)
            .where(IngestionRun.status == "success")
            .order_by(desc(IngestionRun.run_timestamp))
            .limit(1)
        ).scalar_one_or_none()

        if latest_run:
            return {"timestamp": latest_run.run_timestamp.isoformat()}
        else:
            return {"timestamp": None}

    finally:
        db.close()


@activity.defn
async def update_last_ingestion_timestamp(timestamp: str) -> Dict[str, Any]:
    """
    Update the last ingestion timestamp.

    Args:
        timestamp: ISO timestamp

    Returns:
        Success dictionary
    """
    # This is a no-op since we track timestamps in ingestion_runs table
    return {"success": True, "timestamp": timestamp}
