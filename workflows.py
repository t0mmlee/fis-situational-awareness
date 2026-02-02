"""
FIS Situational Awareness System - Temporal Workflows

Defines the ingestion and change detection workflow orchestration.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity types for type hints
with workflow.unsafe.imports_passed_through():
    from agents.base import IngestionResult


@workflow.defn
class IngestionWorkflow:
    """
    Main ingestion workflow.

    Orchestrates:
    1. Data ingestion from all sources (Slack, Notion, External)
    2. Change detection and scoring
    3. Alert generation and delivery
    """

    @workflow.run
    async def run(self, since: Optional[str] = None) -> dict:
        """
        Run the ingestion workflow.

        Args:
            since: ISO timestamp to ingest from (None = last ingestion time)

        Returns:
            Workflow execution summary
        """
        workflow.logger.info("Starting FIS ingestion workflow")

        # Parse since timestamp
        since_dt = None
        if since:
            since_dt = datetime.fromisoformat(since)

        # Define retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )

        # Step 1: Ingest from all sources in parallel
        workflow.logger.info("Starting parallel ingestion from all sources")

        slack_result = await workflow.execute_activity(
            "slack_ingestion",
            args=[since],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        notion_result = await workflow.execute_activity(
            "notion_ingestion",
            args=[since],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        external_result = await workflow.execute_activity(
            "external_ingestion",
            args=[since],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        # Aggregate ingestion results
        total_ingested = (
            slack_result.get("items_ingested", 0) +
            notion_result.get("items_ingested", 0) +
            external_result.get("items_ingested", 0)
        )

        total_entities = (
            slack_result.get("items_changed", 0) +
            notion_result.get("items_changed", 0) +
            external_result.get("items_changed", 0)
        )

        workflow.logger.info(
            f"Ingestion complete: {total_ingested} items, {total_entities} entities"
        )

        # Step 2: Detect changes
        workflow.logger.info("Starting change detection")

        changes_result = await workflow.execute_activity(
            "detect_changes",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        changes_detected = changes_result.get("changes_detected", 0)
        workflow.logger.info(f"Detected {changes_detected} changes")

        # Step 3: Process alerts for CRITICAL changes
        workflow.logger.info("Processing alerts")

        alerts_result = await workflow.execute_activity(
            "process_alerts",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        alerts_sent = alerts_result.get("alerts_sent", 0)
        workflow.logger.info(f"Sent {alerts_sent} alerts")

        # Return summary
        return {
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ingestion": {
                "slack": slack_result,
                "notion": notion_result,
                "external": external_result,
                "total_ingested": total_ingested,
                "total_entities": total_entities,
            },
            "changes": {
                "detected": changes_detected,
                "details": changes_result,
            },
            "alerts": {
                "sent": alerts_sent,
                "details": alerts_result,
            },
        }


@workflow.defn
class ScheduledIngestionWorkflow:
    """
    Scheduled ingestion workflow.

    Runs on a schedule (every 3 days) and triggers the main ingestion workflow.
    """

    @workflow.run
    async def run(self) -> dict:
        """
        Run scheduled ingestion.

        Returns:
            Workflow execution summary
        """
        workflow.logger.info("Starting scheduled ingestion workflow")

        # Get last ingestion timestamp from state
        last_ingestion = await workflow.execute_activity(
            "get_last_ingestion_timestamp",
            start_to_close_timeout=timedelta(seconds=30),
        )

        since = last_ingestion.get("timestamp")

        # Execute main ingestion workflow
        result = await workflow.execute_child_workflow(
            IngestionWorkflow.run,
            args=[since],
            id=f"ingestion-{datetime.now(timezone.utc).isoformat()}",
        )

        # Update last ingestion timestamp
        await workflow.execute_activity(
            "update_last_ingestion_timestamp",
            args=[datetime.now(timezone.utc).isoformat()],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info("Scheduled ingestion workflow completed")

        return {
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "since": since,
            "result": result,
        }
