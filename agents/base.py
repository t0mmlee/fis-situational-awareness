"""
FIS Situational Awareness System - Base Ingestion Agent

Abstract base class for all ingestion agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json

from mcp import ClientSession
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class IngestionResult(BaseModel):
    """Result of an ingestion operation."""
    source: str
    success: bool
    items_ingested: int
    items_changed: int
    errors: List[str]
    duration_seconds: float
    timestamp: datetime


class BaseIngestionAgent(ABC):
    """
    Abstract base class for ingestion agents.

    All ingestion agents must implement the ingest() method to fetch
    data from their respective sources via Tribe MCP.
    """

    def __init__(self, source_name: str, mcp_session: ClientSession):
        """
        Initialize the ingestion agent.

        Args:
            source_name: Name of the data source (e.g., "slack", "notion")
            mcp_session: Active MCP client session
        """
        self.source_name = source_name
        self.mcp_session = mcp_session
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

    @abstractmethod
    async def ingest(self, since: Optional[datetime] = None) -> IngestionResult:
        """
        Fetch data from the source.

        Args:
            since: Only fetch data modified/created since this timestamp (incremental ingestion)

        Returns:
            IngestionResult with ingestion stats and any errors
        """
        pass

    @abstractmethod
    async def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize raw data into FIS entity schema.

        Args:
            raw_data: Raw data from the source

        Returns:
            List of normalized entity dictionaries
        """
        pass

    async def call_mcp_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        max_retries: int = 3
    ) -> Any:
        """
        Call an MCP tool with retry logic.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments
            max_retries: Maximum number of retry attempts

        Returns:
            Tool result content

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Calling MCP tool: {tool_name} (attempt {attempt + 1}/{max_retries})")
                result = await self.mcp_session.call_tool(tool_name, arguments=arguments)
                self.logger.info(f"MCP tool {tool_name} succeeded")
                return result.content
            except Exception as e:
                self.logger.warning(f"MCP tool {tool_name} failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"MCP tool {tool_name} failed after {max_retries} attempts")
                    raise
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

    def parse_json_content(self, content: Any) -> Dict[str, Any]:
        """
        Parse MCP tool result content into JSON.

        Args:
            content: Raw content from MCP tool result

        Returns:
            Parsed JSON dictionary
        """
        if isinstance(content, dict):
            return content
        elif isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, return as-is in a dict
                return {"raw_content": content}
        elif isinstance(content, list) and len(content) > 0:
            # MCP tools may return list of content blocks
            if hasattr(content[0], "text"):
                return {"text": content[0].text}
            return {"content": content}
        else:
            return {"content": str(content)}

    def extract_entity_id(self, entity_type: str, entity_data: Dict[str, Any]) -> str:
        """
        Generate a unique entity ID.

        Args:
            entity_type: Type of entity (stakeholder, program, etc.)
            entity_data: Entity data

        Returns:
            Unique entity ID
        """
        # Use natural keys when available
        if entity_type == "stakeholder":
            return entity_data.get("email", entity_data.get("name", "unknown")).lower()
        elif entity_type == "program":
            return entity_data.get("name", "unknown").lower().replace(" ", "_")
        elif entity_type == "risk":
            return entity_data.get("description", "unknown")[:100].lower()
        elif entity_type == "timeline":
            return entity_data.get("milestone", "unknown").lower().replace(" ", "_")
        elif entity_type == "external_event":
            return entity_data.get("url", entity_data.get("title", "unknown"))
        else:
            return f"{entity_type}_{hash(str(entity_data))}"

    async def log_ingestion_start(self):
        """Log the start of an ingestion cycle."""
        self.logger.info(f"Starting ingestion from {self.source_name}")

    async def log_ingestion_end(self, result: IngestionResult):
        """Log the end of an ingestion cycle."""
        self.logger.info(
            f"Completed ingestion from {self.source_name}: "
            f"{result.items_ingested} items ingested, "
            f"{result.items_changed} items changed, "
            f"{len(result.errors)} errors, "
            f"{result.duration_seconds:.2f}s"
        )


import asyncio
