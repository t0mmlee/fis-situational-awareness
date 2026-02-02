"""
FIS Situational Awareness System - External Sources Ingestion Agent

Ingests FIS-related data from external sources:
- Public news (Bloomberg, Reuters, WSJ, Financial Times)
- SEC filings (8-K, 10-K, 10-Q, DEF 14A, Form 4)
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from agents.base import BaseIngestionAgent, IngestionResult
from config import config


class ExternalIngestionAgent(BaseIngestionAgent):
    """
    Ingests FIS-related data from external sources.

    Uses:
    - SEC EDGAR API for filings
    - Direct HTTP requests for news sources (public web scraping)
    """

    def __init__(self, mcp_session):
        super().__init__("external", mcp_session)
        self.news_sources = config.ingestion.news_sources
        self.sec_cik = config.ingestion.sec_cik
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "FIS Situational Awareness System/1.0 (Tribe AI; support@tribe.ai)"
            }
        )

    async def ingest(self, since: Optional[datetime] = None) -> IngestionResult:
        """
        Ingest external data.

        Args:
            since: Only fetch data since this timestamp

        Returns:
            IngestionResult with stats
        """
        start_time = datetime.now(timezone.utc)
        errors = []
        all_items = []

        try:
            await self.log_ingestion_start()

            # Fetch SEC filings
            try:
                sec_filings = await self._fetch_sec_filings(since)
                all_items.extend(sec_filings)
                self.logger.info(f"Found {len(sec_filings)} SEC filings")
            except Exception as e:
                self.logger.error(f"SEC filings fetch failed: {e}")
                errors.append(f"SEC: {str(e)}")

            # Fetch news (using SEC API's press releases as a proxy)
            # Note: Direct news scraping would require API keys or web scraping
            # For now, we'll use SEC's RSS feed which includes press releases
            try:
                news_items = await self._fetch_news_mentions(since)
                all_items.extend(news_items)
                self.logger.info(f"Found {len(news_items)} news mentions")
            except Exception as e:
                self.logger.error(f"News fetch failed: {e}")
                errors.append(f"News: {str(e)}")

            # Normalize to FIS entities
            entities = await self.normalize(all_items)
            self.logger.info(f"Extracted {len(entities)} entities from external sources")

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return IngestionResult(
                source=self.source_name,
                success=True,
                items_ingested=len(all_items),
                items_changed=len(entities),
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            self.logger.error(f"External ingestion failed: {e}")
            errors.append(str(e))
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return IngestionResult(
                source=self.source_name,
                success=False,
                items_ingested=0,
                items_changed=0,
                errors=errors,
                duration_seconds=duration,
                timestamp=datetime.now(timezone.utc)
            )

    async def _fetch_sec_filings(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch FIS SEC filings from EDGAR API.

        Args:
            since: Only fetch filings since this date

        Returns:
            List of SEC filing dictionaries
        """
        filings = []

        # SEC EDGAR API endpoint
        # https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001136893&type=&dateb=&owner=exclude&count=100

        try:
            # Use SEC's JSON API (submissions endpoint)
            url = f"https://data.sec.gov/submissions/CIK{self.sec_cik.zfill(10)}.json"

            response = await self.http_client.get(url)
            response.raise_for_status()
            data = response.json()

            # Parse recent filings
            recent_filings = data.get("filings", {}).get("recent", {})

            if recent_filings:
                filing_dates = recent_filings.get("filingDate", [])
                forms = recent_filings.get("form", [])
                accession_numbers = recent_filings.get("accessionNumber", [])
                primary_documents = recent_filings.get("primaryDocument", [])
                descriptions = recent_filings.get("primaryDocDescription", [])

                # Filter by date if specified
                cutoff_date = since.date() if since else (datetime.now(timezone.utc) - timedelta(days=90)).date()

                for i in range(len(forms)):
                    filing_date_str = filing_dates[i] if i < len(filing_dates) else None
                    if not filing_date_str:
                        continue

                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()

                    if filing_date >= cutoff_date:
                        form_type = forms[i] if i < len(forms) else "Unknown"
                        accession_num = accession_numbers[i] if i < len(accession_numbers) else ""
                        primary_doc = primary_documents[i] if i < len(primary_documents) else ""
                        description = descriptions[i] if i < len(descriptions) else ""

                        # Build filing URL
                        accession_clean = accession_num.replace("-", "")
                        filing_url = f"https://www.sec.gov/Archives/edgar/data/{self.sec_cik}/{accession_clean}/{primary_doc}"

                        filings.append({
                            "type": "sec_filing",
                            "form_type": form_type,
                            "filing_date": filing_date_str,
                            "accession_number": accession_num,
                            "description": description,
                            "url": filing_url,
                            "timestamp": datetime.combine(filing_date, datetime.min.time(), tzinfo=timezone.utc)
                        })

            self.logger.info(f"Fetched {len(filings)} SEC filings since {cutoff_date}")

        except httpx.HTTPStatusError as e:
            self.logger.error(f"SEC API HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            self.logger.error(f"SEC API error: {e}")
            raise

        return filings

    async def _fetch_news_mentions(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch FIS-related news mentions.

        Note: This is a basic implementation using SEC press releases.
        For production, integrate with news APIs (Bloomberg Terminal API,
        Reuters API, etc.) or use web scraping services.

        Args:
            since: Only fetch news since this date

        Returns:
            List of news item dictionaries
        """
        news_items = []

        try:
            # Fetch FIS press releases from their investor relations site
            # This is publicly accessible and doesn't require authentication

            # Option 1: Use SEC's 8-K filings as proxy for major announcements
            # Already covered in _fetch_sec_filings

            # Option 2: Fetch from FIS investor relations RSS/API
            # For now, we'll create a placeholder that searches for press releases
            # in the SEC filings (8-K forms are used for material events)

            # This would be where you'd integrate:
            # - Bloomberg Terminal API (requires subscription)
            # - Reuters News API (requires subscription)
            # - News API (newsapi.org) - limited free tier
            # - Google News RSS (basic, no API key needed)

            # Basic implementation: Check Google News RSS for FIS mentions
            google_news_url = "https://news.google.com/rss/search?q=Fidelity+National+Information+Services+OR+FIS+financial&hl=en-US&gl=US&ceid=US:en"

            try:
                response = await self.http_client.get(google_news_url)
                response.raise_for_status()

                # Parse RSS XML (basic parsing)
                xml_content = response.text

                # Extract items using regex (simple approach)
                # In production, use feedparser or xmltodict
                item_pattern = r'<item>(.*?)</item>'
                items = re.findall(item_pattern, xml_content, re.DOTALL)

                cutoff_date = since if since else (datetime.now(timezone.utc) - timedelta(days=7))

                for item in items[:20]:  # Limit to 20 most recent
                    # Extract title
                    title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
                    title = title_match.group(1) if title_match else "Unknown"

                    # Extract link
                    link_match = re.search(r'<link>(.*?)</link>', item)
                    link = link_match.group(1) if link_match else ""

                    # Extract pubDate
                    date_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
                    pub_date_str = date_match.group(1) if date_match else None

                    if pub_date_str:
                        try:
                            # Parse RFC 2822 date format
                            pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        except:
                            pub_date = datetime.now(timezone.utc)
                    else:
                        pub_date = datetime.now(timezone.utc)

                    if pub_date >= cutoff_date:
                        # Extract source
                        source_match = re.search(r'<source>(.*?)</source>', item)
                        source = source_match.group(1) if source_match else "Unknown"

                        news_items.append({
                            "type": "news",
                            "title": title,
                            "url": link,
                            "source": source,
                            "published_date": pub_date.isoformat(),
                            "timestamp": pub_date
                        })

                self.logger.info(f"Fetched {len(news_items)} news items from Google News RSS")

            except Exception as e:
                self.logger.warning(f"Google News RSS fetch failed: {e}")
                # Don't raise, continue with empty news list

        except Exception as e:
            self.logger.error(f"News fetch error: {e}")
            raise

        return news_items

    async def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize external data into FIS entities.

        Extract external events (news, filings) that may impact FIS programs.

        Args:
            raw_data: Raw external data

        Returns:
            List of normalized FIS entities
        """
        entities = []

        for item in raw_data:
            item_type = item.get("type")

            if item_type == "sec_filing":
                # SEC filings become external_event entities
                entity = self._normalize_sec_filing(item)
                if entity:
                    entities.append(entity)

            elif item_type == "news":
                # News items become external_event entities
                entity = self._normalize_news_item(item)
                if entity:
                    entities.append(entity)

        return entities

    def _normalize_sec_filing(self, filing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize SEC filing into external_event entity."""
        form_type = filing.get("form_type", "")

        # Determine event type based on form
        event_type = "SEC Filing"
        if form_type == "8-K":
            event_type = "Material Event Filing"
        elif form_type in ["10-K", "10-Q"]:
            event_type = "Financial Report"
        elif form_type == "DEF 14A":
            event_type = "Proxy Statement"
        elif form_type == "4":
            event_type = "Insider Trading Report"

        # Determine significance
        significance = "Medium"
        if form_type == "8-K":
            significance = "High"  # Material events are significant
        elif form_type in ["10-K", "10-Q"]:
            significance = "Medium"

        return {
            "entity_type": "external_event",
            "entity_id": filing.get("accession_number", ""),
            "data": {
                "title": f"FIS {form_type} Filing",
                "event_type": event_type,
                "description": filing.get("description", f"FIS filed {form_type} with SEC"),
                "source": "SEC EDGAR",
                "url": filing.get("url", ""),
                "published_date": filing.get("filing_date", ""),
                "significance": significance,
                "timestamp": filing.get("timestamp", datetime.now(timezone.utc)).isoformat()
            }
        }

    def _normalize_news_item(self, news: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize news item into external_event entity."""
        title = news.get("title", "")

        # Determine event type from title keywords
        event_type = "News Article"
        title_lower = title.lower()

        if any(word in title_lower for word in ["merger", "acquisition", "acquires", "m&a"]):
            event_type = "M&A Activity"
        elif any(word in title_lower for word in ["ceo", "cfo", "executive", "appoint", "resign"]):
            event_type = "Executive Change"
        elif any(word in title_lower for word in ["earnings", "revenue", "profit", "loss"]):
            event_type = "Financial Results"
        elif any(word in title_lower for word in ["partnership", "partner", "collaboration"]):
            event_type = "Partnership Announcement"

        # Determine significance
        significance = "Low"
        if event_type in ["M&A Activity", "Executive Change"]:
            significance = "High"
        elif event_type in ["Financial Results", "Partnership Announcement"]:
            significance = "Medium"

        return {
            "entity_type": "external_event",
            "entity_id": news.get("url", title),
            "data": {
                "title": title,
                "event_type": event_type,
                "description": title,
                "source": news.get("source", "News"),
                "url": news.get("url", ""),
                "published_date": news.get("published_date", ""),
                "significance": significance,
                "timestamp": news.get("timestamp", datetime.now(timezone.utc)).isoformat()
            }
        }

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        await self.http_client.aclose()
