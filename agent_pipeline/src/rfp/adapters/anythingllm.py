"""Single AnythingLLM boundary for ingestion, RAG, and company knowledge."""

import logging
import re
import uuid

from .anythingllm_client import AnythingLLMClient
from .extractor import ExtractorClient, summarize_extractor_response
from .retrieval import get_relevant_chunks, search_relevant_chunks

logger = logging.getLogger(__name__)

COMPANY_WORKSPACES = (
    "company-past-proposals",
    "company-cvs",
    "company-project-references",
)

KNOWLEDGE_CATEGORIES = {
    "past_proposals": COMPANY_WORKSPACES[0],
    "cvs": COMPANY_WORKSPACES[1],
    "project_references": COMPANY_WORKSPACES[2],
}


class AnythingLLMAdapter:
    def __init__(
        self,
        client: AnythingLLMClient | None = None,
        extractor: ExtractorClient | None = None,
    ):
        self.client = client or AnythingLLMClient()
        self.extractor = extractor or ExtractorClient()

    def query(self, workspace_slug: str, query: str, *, top_n: int = 5) -> str:
        return get_relevant_chunks(self.client, workspace_slug, query, top_n=top_n)

    def query_with_trace(
        self,
        workspace_slug: str,
        query: str,
        *,
        candidate_top_n: int = 8,
        used_top_n: int = 4,
        score_threshold: float = 0.15,
    ) -> dict:
        """Retrieve once and preserve ranked candidates plus prompt context."""
        retrieval_error = None
        rate_limited = False
        try:
            results = search_relevant_chunks(
                self.client,
                workspace_slug,
                query,
                top_n=max(candidate_top_n, used_top_n),
                score_threshold=score_threshold,
            )
        except Exception as exc:
            retrieval_error = f"{type(exc).__name__}: {exc}"
            rate_limited = (
                getattr(getattr(exc, "response", None), "status_code", None) == 429
            )
            logger.warning(
                "Traced retrieval failed for workspace %r query %r: %s",
                workspace_slug,
                query,
                exc,
            )
            results = []
        candidates = []
        for rank, result in enumerate(results, start=1):
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            text = str(result.get("text") or "").strip()
            source_match = re.search(
                r"(?m)^sourceDocument:\s*(.+?)\s*$", text
            )
            chunk_id = str(
                result.get("chunk_id")
                or metadata.get("sourceDocument")
                or (source_match.group(1).strip() if source_match else "")
                or metadata.get("chunk_id")
                or result.get("id")
                or metadata.get("id")
                or f"rank-{rank}"
            )
            candidates.append(
                {
                    "chunk_id": chunk_id,
                    "content": text,
                    "vector_score": result.get("score"),
                    "rerank_score": result.get("rerank_score", result.get("score")),
                    "rank": rank,
                    "metadata": metadata,
                }
            )

        selected = candidates[: max(1, used_top_n)]
        context_blocks = []
        for chunk in selected:
            content = chunk["content"]
            if re.search(r"(?m)^sourceDocument:\s*", content):
                context_blocks.append(content)
            else:
                context_blocks.append(
                    "<document_metadata>\n"
                    f"sourceDocument: {chunk['chunk_id']}\n"
                    "</document_metadata>\n\n"
                    f"{content}"
                )
        return {
            "query": query,
            "candidates": candidates,
            "selected": selected,
            "retrieval_error": retrieval_error,
            "rate_limited": rate_limited,
            "context": "\n\n---\n\n".join(context_blocks)
            if context_blocks
            else "(no relevant content found in the document for this query)",
        }

    def search(self, workspace_slug: str, query: str, *, top_n: int = 5) -> list[dict]:
        return self.client.vector_search(workspace_slug, query, top_n=top_n)

    def ensure_ready(self) -> dict[str, dict[str, bool]]:
        result = {}
        for workspace_slug in COMPANY_WORKSPACES:
            outcome = self.client.get_or_create_workspace(workspace_slug)
            result[workspace_slug] = {"created": bool(outcome["created"])}
        return result

    def knowledge_status(self) -> dict[str, dict]:
        """Return UI-ready status for every persistent knowledge workspace."""
        self.ensure_ready()
        result = {}
        for category, slug in KNOWLEDGE_CATEGORIES.items():
            workspace = self.client.get_workspace(slug)
            documents = []
            if workspace:
                for document in workspace.get("documents", []) or []:
                    documents.append(
                        {
                            "title": document.get("title")
                            or document.get("filename")
                            or "unknown",
                            "id": document.get("id"),
                        }
                    )
            result[category] = {
                "slug": slug,
                "exists": workspace is not None,
                "document_count": len(documents),
                "documents": documents,
            }
        return result

    def upload_knowledge(self, category: str, file_path: str) -> dict:
        """Upload a company document through the same AnythingLLM boundary."""
        if category not in KNOWLEDGE_CATEGORIES:
            raise ValueError(f"Unknown knowledge category: {category}")
        slug = KNOWLEDGE_CATEGORIES[category]
        self.client.get_or_create_workspace(slug)
        return self.client.upload_document(file_path, slug)

    def ingest(self, file_path: str, *, workspace_prefix: str = "rfp") -> dict:
        workspace_name = (
            f"rfp-{uuid.uuid4().hex[:8]}"
            if workspace_prefix == "rfp"
            else workspace_prefix
        )
        response = self.client.create_workspace(workspace_name)
        workspace_slug = response["workspace"]["slug"]
        extracted = self.extractor.process_and_index(file_path, workspace_slug)
        return {
            "workspace_slug": workspace_slug,
            "processing": summarize_extractor_response(extracted),
        }
