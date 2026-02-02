"""
FIS Situational Awareness System - Main Entry Point

Starts both the web server (for Railway health checks) and the Temporal worker.
"""

import asyncio
import logging
import multiprocessing
import os
import signal
import sys

from config import config
from web import app as web_app

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.monitoring.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_temporal_worker():
    """
    Run the Temporal worker for ingestion workflows.

    This is the main application logic that handles:
    - Scheduled ingestion every 3 days
    - Change detection and scoring
    - Alert generation and delivery
    """
    from temporalio.client import Client
    from temporalio.worker import Worker

    logger.info("Starting Temporal worker...")

    # Connect to Temporal
    # Use TLS and API key if connecting to Temporal Cloud
    if config.temporal.api_key:
        # Temporal Cloud connection with TLS and API key
        from temporalio.client import TLSConfig

        tls_config = TLSConfig(
            # Temporal Cloud requires TLS
            # Default system cert verification is used
        )

        client = await Client.connect(
            config.temporal.host,
            namespace=config.temporal.namespace,
            tls=tls_config,
            api_key=config.temporal.api_key
        )
    else:
        # Local Temporal server connection
        client = await Client.connect(
            config.temporal.host,
            namespace=config.temporal.namespace
        )

    # TODO: Import your workflows and activities
    # from .workflows import IngestionWorkflow
    # from .activities import slack_ingestion, notion_ingestion, external_ingestion

    # Create worker
    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        # workflows=[IngestionWorkflow],
        # activities=[slack_ingestion, notion_ingestion, external_ingestion]
    )

    logger.info(f"Temporal worker started on task queue: {config.temporal.task_queue}")

    # Run worker
    await worker.run()


def run_web_server():
    """
    Run the web server for health checks.

    Railway requires an HTTP server to be running for health checks
    and service discovery.
    """
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting web server on {host}:{port}")

    uvicorn.run(
        "fis_situational_awareness.web:app",
        host=host,
        port=port,
        log_level=config.monitoring.log_level.lower(),
        access_log=True
    )


def run_both():
    """
    Run both web server and Temporal worker in parallel.

    Uses multiprocessing to run both servers concurrently.
    """
    logger.info("Starting FIS Situational Awareness System")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Temporal host: {config.temporal.host}")
    logger.info(f"Database: {config.database.url}")

    # Create processes for web server and Temporal worker
    web_process = multiprocessing.Process(target=run_web_server, name="WebServer")
    worker_process = multiprocessing.Process(
        target=lambda: asyncio.run(run_temporal_worker()),
        name="TemporalWorker"
    )

    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        logger.info("Shutting down gracefully...")
        web_process.terminate()
        worker_process.terminate()
        web_process.join(timeout=5)
        worker_process.join(timeout=5)
        logger.info("Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start both processes
    web_process.start()
    worker_process.start()

    logger.info("All services started successfully")

    # Wait for both processes
    try:
        web_process.join()
        worker_process.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        signal_handler(None, None)


def main():
    """Main entry point."""
    # Check if running on Railway (has PORT environment variable)
    if os.getenv("RAILWAY_ENVIRONMENT"):
        logger.info("Detected Railway environment")

    # Check if running web server only (for development)
    mode = os.getenv("RUN_MODE", "both")

    if mode == "web":
        logger.info("Running web server only")
        run_web_server()
    elif mode == "worker":
        logger.info("Running Temporal worker only")
        asyncio.run(run_temporal_worker())
    else:
        logger.info("Running both web server and Temporal worker")
        run_both()


if __name__ == "__main__":
    main()
