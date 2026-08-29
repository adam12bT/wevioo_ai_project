"""Reliable client for AnythingLLM structured raw-text ingestion.

Every block carries a deterministic ``externalId``. The modified AnythingLLM
endpoint treats it as an idempotency key, so retries or repeated submissions
return the existing vectorized document instead of creating duplicates.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

import httpx

from app.config import Settings, get_settings
from app.models import ExtractedDocument, IndexResult, ParagraphBlock, TableBlock

logger = logging.getLogger(__name__)


class AnythingLLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.anythingllm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.anythingllm_api_key}"
        return headers

    @staticmethod
    def _block_text(block: ParagraphBlock | TableBlock) -> str:
        return block.markdown if isinstance(block, TableBlock) else block.text

    def _external_id(
        self, document: ExtractedDocument, block: ParagraphBlock | TableBlock
    ) -> str:
        raw = "|".join(
            [
                document.metadata.content_sha256,
                block.type.value,
                str(block.page),
                str(block.layout_order),
                self._block_text(block),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _block_payload(
        self,
        filename: str,
        block: ParagraphBlock | TableBlock,
        workspace_slug: str,
        document: ExtractedDocument | None = None,
    ) -> dict:
        content_type = block.type.value
        text_content = self._block_text(block)
        external_id = (
            self._external_id(document, block)
            if document
            else hashlib.sha256(
                f"{filename}|{block.page}|{block.layout_order}|{text_content}".encode("utf-8")
            ).hexdigest()
        )
        title = filename
        if block.page is not None:
            title += f" — p.{block.page}"
        if block.section:
            title += f" — {block.section}"

        metadata = {
            "title": title,
            "docSource": f"extractor://{filename}",
            "chunkSource": f"extractor://{filename}#block={block.layout_order}",
            "description": f"Structured block extracted from {filename}",
            "externalId": external_id,
            "sourceFilename": filename,
            "documentType": (
                document.metadata.file_type
                if document
                else filename.rsplit(".", 1)[-1].lower()
            ),
            "page": block.page,
            "section": block.section,
            "contentType": content_type,
            "extractionMethod": block.extraction_method.value,
            "layoutOrder": block.layout_order,
            "bbox": list(block.bbox) if block.bbox else None,
        }
        return {
            "textContent": text_content,
            "addToWorkspaces": workspace_slug,
            "metadata": metadata,
        }

    async def _post_with_retry(self, client: httpx.AsyncClient, url: str, payload: dict):
        last_error: Exception | None = None
        for attempt in range(self.settings.anythingllm_max_retries):
            try:
                response = await client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                # Retry throttling and temporary server failures. Validation/auth
                # errors are permanent for this payload and must fail immediately.
                if exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise
                last_error = exc
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            if attempt + 1 >= self.settings.anythingllm_max_retries:
                break
            await asyncio.sleep(
                self.settings.anythingllm_retry_backoff_seconds * (2**attempt)
            )
        assert last_error is not None
        raise last_error

    async def _rollback(
        self, client: httpx.AsyncClient, workspace_slug: str, locations: list[str]
    ) -> int:
        if not locations:
            return 0
        url = (
            f"{self.settings.anythingllm_url.rstrip('/')}/api/v1/workspace/"
            f"{workspace_slug}/update-embeddings"
        )
        try:
            response = await client.post(
                url,
                json={"adds": [], "deletes": locations},
                headers=self._headers(),
            )
            response.raise_for_status()
            return len(locations)
        except httpx.HTTPError as exc:
            logger.error("AnythingLLM rollback failed: %s", exc)
            return 0

    async def send_document(
        self, document: ExtractedDocument, workspace_slug: str
    ) -> IndexResult:
        url = f"{self.settings.anythingllm_url.rstrip('/')}/api/v1/document/raw-text"
        sent_documents: list[dict] = []
        new_locations: list[str] = []
        skipped_existing = 0

        async with httpx.AsyncClient(timeout=self.settings.anythingllm_timeout_seconds) as client:
            for block in document.blocks:
                payload = self._block_payload(
                    document.filename, block, workspace_slug, document=document
                )
                try:
                    body = await self._post_with_retry(client, url, payload)
                    if not body.get("success", False):
                        raise RuntimeError(body.get("error") or "AnythingLLM reported failure")
                    response_documents = body.get("documents", [])
                    sent_documents.extend(response_documents)
                    if body.get("idempotent", False):
                        skipped_existing += 1
                    else:
                        new_locations.extend(
                            item["location"]
                            for item in response_documents
                            if item.get("location")
                        )
                except Exception as exc:
                    logger.exception("Failed to index block %s", block.layout_order)
                    rolled_back = 0
                    if self.settings.anythingllm_rollback_on_failure:
                        rolled_back = await self._rollback(client, workspace_slug, new_locations)
                    return IndexResult(
                        success=False,
                        workspace_slug=workspace_slug,
                        blocks_sent=len(sent_documents),
                        documents=sent_documents,
                        skipped_existing=skipped_existing,
                        rolled_back=rolled_back,
                        error=str(exc),
                    )

        return IndexResult(
            success=True,
            workspace_slug=workspace_slug,
            blocks_sent=len(document.blocks),
            documents=sent_documents,
            skipped_existing=skipped_existing,
        )

    async def is_online(self) -> bool:
        url = f"{self.settings.anythingllm_url.rstrip('/')}/api/ping"
        async with httpx.AsyncClient(
            timeout=self.settings.anythingllm_timeout_seconds
        ) as client:
            for attempt in range(self.settings.anythingllm_max_retries):
                try:
                    response = await client.get(url, headers=self._headers())
                    if response.status_code == 200:
                        return True
                    # A sleeping hosted service commonly returns a temporary
                    # 5xx while it wakes. Permanent client errors should fail.
                    if response.status_code < 500 and response.status_code != 429:
                        return False
                except httpx.HTTPError:
                    pass
                if attempt + 1 < self.settings.anythingllm_max_retries:
                    await asyncio.sleep(
                        self.settings.anythingllm_retry_backoff_seconds * (2**attempt)
                    )
        return False
