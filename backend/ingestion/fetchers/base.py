import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ingestion.schemas import FetchedDocument, SourceType

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 EduSync/1.0"
)


class BaseFetcher(ABC):
    """Abstract base class for all document fetchers."""

    source_type: SourceType

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.headers = {"User-Agent": DEFAULT_USER_AGENT}

    async def _get_raw_bytes(self, source: str) -> tuple[bytes, dict[str, Any]]:
        """Fetch raw bytes from a remote URL or local file path."""
        # Check if source is a local file
        if os.path.exists(source) and os.path.isfile(source):
            with open(source, "rb") as f:
                content = f.read()
            metadata = {
                "file_size": len(content),
                "local_file": True,
                "file_path": source,
            }
            return content, metadata

        # Fetch over HTTP
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(source)
            response.raise_for_status()
            content = response.content
            metadata = {
                "file_size": len(content),
                "local_file": False,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
            }
            return content, metadata

    @abstractmethod
    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch and parse content from a URL or file path."""
        pass
