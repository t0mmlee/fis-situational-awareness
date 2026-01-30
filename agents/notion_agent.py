"""
FIS Situational Awareness System - Notion Ingestion Agent

Ingests FIS-related data from Notion via Tribe MCP.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseIngestionAgent, IngestionResult
from ..config import config


class NotionIngestionAgent(BaseIngestionAgent):
    """
    Ingests FIS-related Notion data via Tribe MCP.

    Fetches known pages (main hub, stakeholders DB) and searches for
    FIS-tagged pages.
    """

    def __init__(self, mcp_session):
        super().__init__("notion", mcp_session)
        self.main_hub_id = config.ingestion.notion_main_hub_id
        self.stakeholders_id = config.ingestion.notion_stakeholders_id
        self.search_tag = config.ingestion.notion_search_tag

    async def ingest(self, since: Optional[datetime] = None) -> IngestionResult:
        """Ingest Notion data."""
        start_time = datetime.now()
        errors = []

        try:
            await self.log_ingestion_start()

            # Fetch known pages
            raw_pages = []
            for page_id in [self.main_hub_id, self.stakeholders_id]:
                try:
                    page = await self._fetch_page(page_id)
                    raw_pages.append(page)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch page {page_id}: {e}")
                    errors.append(f"Page {page_id}: {str(e)}")

            # Search for additional FIS-tagged pages
            search_pages = await self._search_pages(self.search_tag)
            raw_pages.extend(search_pages)

            self.logger.info(f"Found {len(raw_pages)} Notion pages")

            # Normalize to FIS entities
            entities = await self.normalize(raw_pages)
            self.logger.info(f"Extracted {len(entities)} entities from Notion")

            duration = (datetime.now() - start_time).total_seconds()

            return IngestionResult(
                source=self.source_name,
                success=True,
                items_ingested=len(raw_pages),
                items_changed=len(entities),
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"Notion ingestion failed: {e}")
            errors.append(str(e))
            duration = (datetime.now() - start_time).total_seconds()
            return IngestionResult(
                source=self.source_name,
                success=False,
                items_ingested=0,
                items_changed=0,
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now()
            )

    async def _fetch_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch a specific Notion page by ID."""
        result_content = await self.call_mcp_tool(
            "notion-fetch",
            arguments={"id": page_id}
        )
        return self._parse_notion_page(result_content, page_id)

    async def _search_pages(self, query: str) -> List[Dict[str, Any]]:
        """Search for Notion pages by query."""
        result_content = await self.call_mcp_tool(
            "notion-search",
            arguments={
                "query": query,
                "query_type": "internal"
            }
        )
        return self._parse_notion_search_results(result_content)

    def _parse_notion_page(self, content: Any, page_id: str) -> Dict[str, Any]:
        """Parse Notion page content."""
        parsed = self.parse_json_content(content)

        if isinstance(parsed, dict) and "text" in parsed:
            return {
                "page_id": page_id,
                "content": parsed["text"],
                "last_edited": datetime.now()  # Would need to extract from metadata
            }

        return {
            "page_id": page_id,
            "content": str(parsed),
            "last_edited": datetime.now()
        }

    def _parse_notion_search_results(self, content: Any) -> List[Dict[str, Any]]:
        """Parse Notion search results."""
        parsed = self.parse_json_content(content)
        pages = []

        # Parse search results format
        if isinstance(parsed, dict) and "text" in parsed:
            text = parsed["text"]
            # Extract page URLs from text
            url_pattern = r"https://www\.notion\.so/([a-f0-9]+)"
            matches = re.findall(url_pattern, text)
            for page_id in matches:
                pages.append({
                    "page_id": page_id,
                    "content": "",  # Would need to fetch full content
                    "last_edited": datetime.now()
                })

        return pages

    async def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize Notion pages into FIS entities."""
        entities = []

        for page in raw_data:
            content = page.get("content", "")

            # Extract entities based on page content
            stakeholders = self._extract_stakeholders_from_page(page)
            entities.extend(stakeholders)

            programs = self._extract_programs_from_page(page)
            entities.extend(programs)

            risks = self._extract_risks_from_page(page)
            entities.extend(risks)

        return entities

    def _extract_stakeholders_from_page(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract stakeholders from Notion page."""
        stakeholders = []
        content = page.get("content", "")

        # Look for stakeholder patterns (Name - Role - Email)
        email_pattern = r"([A-Za-z\s]+)\s*-\s*([A-Za-z\s]+)\s*-\s*([\w\.-]+@[\w\.-]+)"
        matches = re.findall(email_pattern, content)

        for name, role, email in matches:
            stakeholder = {
                "entity_type": "stakeholder",
                "entity_id": email.lower(),
                "data": {
                    "name": name.strip(),
                    "role": role.strip(),
                    "email": email.strip(),
                    "company": "FIS" if "fisglobal.com" in email else "Unknown",
                    "last_seen": datetime.now().isoformat()
                }
            }
            stakeholders.append(stakeholder)

        return stakeholders

    def _extract_programs_from_page(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract programs from Notion page."""
        programs = []
        content = page.get("content", "")

        # Look for program status patterns
        program_keywords = ["Agent Factory", "CDD MVP", "Deposit Pricing"]
        status_keywords = {"In Progress", "Blocked", "At Risk", "Completed"}

        for program_name in program_keywords:
            if program_name in content:
                # Find status near program name
                status = "In Progress"  # Default
                for status_keyword in status_keywords:
                    if status_keyword in content[max(0, content.find(program_name)-100):content.find(program_name)+100]:
                        status = status_keyword
                        break

                program = {
                    "entity_type": "program",
                    "entity_id": program_name.lower().replace(" ", "_"),
                    "data": {
                        "name": program_name,
                        "status": status,
                        "last_updated": page.get("last_edited", datetime.now()).isoformat(),
                        "source": f"notion://{page['page_id']}"
                    }
                }
                programs.append(program)

        return programs

    def _extract_risks_from_page(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract risks from Notion page (RAID items)."""
        risks = []
        content = page.get("content", "")

        # Look for risk indicators
        risk_keywords = ["blocker", "risk", "issue", "delay"]

        for keyword in risk_keywords:
            if keyword in content.lower():
                risk = {
                    "entity_type": "risk",
                    "entity_id": self.extract_entity_id("risk", {"description": keyword}),
                    "data": {
                        "category": "Technical",
                        "severity": "Medium",
                        "description": f"Risk mentioned in Notion: {keyword}",
                        "status": "Open",
                        "first_detected": datetime.now().isoformat(),
                        "source": f"notion://{page['page_id']}"
                    }
                }
                risks.append(risk)

        return risks
