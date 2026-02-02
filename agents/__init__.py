"""
Agent modules for monitoring different data sources.
"""

from agents.base import BaseIngestionAgent
from agents.slack_agent import SlackIngestionAgent
from agents.notion_agent import NotionIngestionAgent

__all__ = ["BaseIngestionAgent", "SlackIngestionAgent", "NotionIngestionAgent"]
