import json
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import settings
from app.models.database import sqlite_session

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    SOURCE_NAME: str = "unknown"
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    TIMEOUT: float = 60.0
    RATE_LIMIT_DELAY: float = 1.0

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.TIMEOUT),
            follow_redirects=True,
            headers={"User-Agent": "GeoRisk-Dashboard/1.0 (research tool)"},
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_with_retry(self, url: str, params: dict | None = None) -> httpx.Response:
        last_exception = None
        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))

                response = await self.client.get(url, params=params)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("Rate limited on %s, waiting %ss", self.SOURCE_NAME, retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
                return response

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning("HTTP %s on attempt %d for %s", e.response.status_code, attempt + 1, self.SOURCE_NAME)
            except httpx.RequestError as e:
                last_exception = e
                logger.warning("Request error on attempt %d for %s: %s", attempt + 1, self.SOURCE_NAME, e)

        raise last_exception or Exception(f"Failed after {self.MAX_RETRIES} retries")

    def save_geojson(self, data: dict, filename: str) -> Path:
        filepath = settings.CATALOG_DIR / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file, then rename to avoid truncated files on crash.
        tmp_path = filepath.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        tmp_path.replace(filepath)
        return filepath

    def log_scrape(self, status: str, records: int, file_path: str | None = None, error: str | None = None):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite_session() as conn:
            conn.execute(
                """INSERT INTO scrape_log (source, status, records_fetched, file_path, completed_at, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (self.SOURCE_NAME, status, records, file_path, now, error),
            )
            if status == "success":
                conn.execute(
                    """UPDATE data_catalog
                       SET last_scraped = ?, record_count = ?, file_path = ?, status = 'fresh'
                       WHERE source = ?""",
                    (now, records, file_path, self.SOURCE_NAME),
                )

    @abstractmethod
    async def scrape(self) -> dict:
        ...

    async def run(self) -> dict:
        logger.info("Starting scrape: %s", self.SOURCE_NAME)
        try:
            result = await self.scrape()
            self.log_scrape("success", result.get("records", 0), result.get("file_path"))
            logger.info("Scrape complete: %s - %d records", self.SOURCE_NAME, result.get("records", 0))
            return result
        except (httpx.HTTPError, OSError, ValueError, KeyError) as e:
            logger.error("Scrape failed: %s - %s", self.SOURCE_NAME, e)
            self.log_scrape("error", 0, error=str(e))
            return {"status": "error", "source": self.SOURCE_NAME, "error": str(e)}
        finally:
            await self.close()
