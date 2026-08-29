import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Any


_SOURCE_PATTERN = re.compile(r"^sourceDocument:\s*(.+?)\s*$", re.MULTILINE)
_DOCUMENT_BLOCK_PATTERN = re.compile(
    r"<document_metadata>\s*(.*?)\s*</document_metadata>\s*(.*?)"
    r"(?=\n\s*---\s*\n|\n?\s*<document_metadata>|\Z)",
    re.DOTALL,
)
_STOPWORDS = {
    "about", "after", "again", "ainsi", "avec", "avoir", "based", "batch",
    "been", "before", "being", "below", "between", "cette", "dans", "des",
    "each", "elle", "elles", "entre", "every", "facts", "from", "have",
    "including", "instructions", "leurs", "mais", "more", "pour", "proposal",
    "query", "relevant", "requirements", "retrieval", "section", "sections",
    "should", "sous", "such", "that", "their", "them", "there", "these",
    "this", "those", "tous", "tout", "toute", "toutes", "used", "using",
    "avec", "which", "will", "with", "your", "être", "dans", "pour", "une",
    "les", "aux", "sur", "par", "and", "the", "for", "are", "but", "not",
}
_PROXY_RELEVANCE_THRESHOLD = 0.12


def _terms(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W_]+", str(value or "").casefold(), re.UNICODE)
        if len(token) >= 3 and token not in _STOPWORDS and not token.isdigit()
    }


def _bounded_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    query_coverage = overlap / len(left)
    cosine = overlap / math.sqrt(len(left) * len(right))
    return max(0.0, min(1.0, 0.75 * query_coverage + 0.25 * cosine))


def _chunks_from_excerpts(value: Any) -> list[dict[str, str]]:
    text = str(value or "")
    chunks = []
    seen = set()
    for match in _DOCUMENT_BLOCK_PATTERN.finditer(text):
        metadata, content = match.groups()
        source_match = _SOURCE_PATTERN.search(metadata)
        if not source_match:
            continue
        chunk_id = source_match.group(1).strip()
        if not chunk_id or chunk_id in seen:
            continue
        chunks.append({"chunk_id": chunk_id, "content": content.strip()})
        seen.add(chunk_id)
    return chunks


def _normalise_chunks(value: Any) -> list[dict[str, Any]]:
    chunks = []
    seen = set()
    for item in value or []:
        record = item if isinstance(item, dict) else {"chunk_id": item}
        chunk_id = str(record.get("chunk_id") or record.get("id") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        chunks.append(
            {
                "chunk_id": chunk_id,
                "content": str(
                    record.get("content")
                    or record.get("text")
                    or record.get("excerpt")
                    or ""
                ),
                "rank": record.get("rank"),
                "vector_score": record.get("vector_score"),
                "rerank_score": record.get("rerank_score"),
                "metadata": record.get("metadata") or {},
            }
        )
        seen.add(chunk_id)
    return chunks


def _retrieval_cases(state: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = state.get("generation_evidence") or {}
    cases = []
    for index, batch in enumerate(evidence.get("section_batches") or [], start=1):
        if not isinstance(batch, dict):
            continue
        sections = [str(value) for value in batch.get("sections") or [] if str(value)]
        candidate_chunks = _normalise_chunks(batch.get("candidate_chunks"))
        used_chunks = _normalise_chunks(batch.get("used_chunks"))
        fitted_chunks = _chunks_from_excerpts(batch.get("tender_excerpts"))
        if not candidate_chunks:
            candidate_chunks = list(fitted_chunks)
        if not used_chunks:
            used_chunks = list(candidate_chunks)
        elif fitted_chunks:
            fitted_content = {
                chunk["chunk_id"]: chunk["content"] for chunk in fitted_chunks
            }
            used_chunks = [
                {
                    **chunk,
                    "content": fitted_content.get(
                        chunk["chunk_id"], chunk.get("content", "")
                    ),
                }
                for chunk in used_chunks
                if chunk["chunk_id"] in fitted_content
            ]
        if not sections or not candidate_chunks:
            continue
        query = str(batch.get("retrieval_query") or " ".join(sections))
        draft = str(batch.get("draft") or "")
        for section in sections:
            cases.append(
                {
                    "case_id": f"automatic-{index}-{section}",
                    "query": query,
                    "section": section,
                    "draft": draft,
                    "candidate_chunks": candidate_chunks,
                    "used_chunks": used_chunks,
                }
            )

    for index, trace in enumerate(state.get("retrieval_trace") or [], start=1):
        if not isinstance(trace, dict):
            continue
        section = str(trace.get("section") or trace.get("query") or "")
        candidate_chunks = _normalise_chunks(
            trace.get("candidate_chunks") or trace.get("chunks")
        )
        used_chunks = _normalise_chunks(trace.get("used_chunks")) or list(
            candidate_chunks
        )
        if section and candidate_chunks:
            cases.append(
                {
                    "case_id": f"trace-{index}",
                    "query": str(trace.get("query") or section),
                    "section": section,
                    "draft": str(trace.get("draft") or ""),
                    "candidate_chunks": candidate_chunks,
                    "used_chunks": used_chunks,
                }
            )
    return cases


def _retrieved_chunks_by_section(state: dict[str, Any]) -> dict[str, list[str]]:
    retrieved: dict[str, list[str]] = {}
    for case in _retrieval_cases(state):
        retrieved[case["section"]] = [
            chunk["chunk_id"] for chunk in case.get("candidate_chunks") or []
        ]
    return retrieved


def _evaluate_automatic_proxy(state: dict[str, Any], k: int) -> dict[str, Any]:
    results = []
    for case in _retrieval_cases(state):
        query_terms = _terms(f"{case['section']} {case['query']}")
        draft_terms = _terms(case.get("draft"))
        scored_candidates = []
        candidate_terms: set[str] = set()
        candidates = case.get("candidate_chunks") or []
        used_chunks = case.get("used_chunks") or []
        for chunk in candidates:
            chunk_terms = _terms(chunk.get("content"))
            candidate_terms.update(chunk_terms)
            relevance = _bounded_similarity(query_terms, chunk_terms)
            scored_candidates.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "relevance_score": round(relevance, 4),
                    "relevant": relevance >= _PROXY_RELEVANCE_THRESHOLD,
                    "rank": chunk.get("rank"),
                    "vector_score": chunk.get("vector_score"),
                    "rerank_score": chunk.get("rerank_score"),
                }
            )

        used_scores = []
        used_terms: set[str] = set()
        for chunk in used_chunks:
            chunk_terms = _terms(chunk.get("content"))
            used_terms.update(chunk_terms)
            relevance = _bounded_similarity(query_terms, chunk_terms)
            utilization = (
                len(chunk_terms & draft_terms) / len(chunk_terms)
                if chunk_terms and draft_terms
                else 0.0
            )
            used_scores.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "relevance_score": round(relevance, 4),
                    "utilization_score": round(utilization, 4),
                }
            )

        candidate_ids = [item["chunk_id"] for item in scored_candidates]
        used_ids = [item["chunk_id"] for item in used_scores]
        relevant_ids = [
            item["chunk_id"] for item in scored_candidates if item["relevant"]
        ]
        precision = len(relevant_ids) / len(candidate_ids) if candidate_ids else 0.0
        covered_query_terms = query_terms & candidate_terms
        recall = len(covered_query_terms) / len(query_terms) if query_terms else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        context_relevance = (
            mean(item["relevance_score"] for item in used_scores)
            if used_scores
            else 0.0
        )
        context_utilization = (
            len(draft_terms & used_terms) / len(draft_terms)
            if draft_terms
            else 0.0
        )
        reciprocal_rank = next(
            (
                1.0 / rank
                for rank, item in enumerate(scored_candidates, start=1)
                if item["relevant"]
            ),
            0.0,
        )
        results.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "section": case["section"],
                "candidate_precision_proxy": precision,
                "candidate_recall_proxy": recall,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "f1_score": f1,
                "context_relevance": context_relevance,
                "context_utilization": context_utilization,
                "reciprocal_rank": reciprocal_rank,
                "candidate_chunk_count": len(candidate_ids),
                "used_chunk_count": len(used_ids),
                "candidate_chunk_ids": candidate_ids,
                "used_chunk_ids": used_ids,
                "relevant_chunk_ids": relevant_ids,
                "retrieved_chunk_ids": candidate_ids,
                "matched_chunk_ids": relevant_ids,
                "candidate_scores": scored_candidates,
                "used_chunk_scores": used_scores,
                "chunk_scores": scored_candidates,
            }
        )

    if not results:
        return {
            "available": False,
            "evaluation_mode": "automatic_proxy",
            "reason": "No retrievable chunk content was preserved by generation.",
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_score": None,
            "context_relevance": None,
            "context_utilization": None,
            "mrr": None,
            "case_count": 0,
            "candidate_chunk_count": 0,
            "used_chunk_count": 0,
        }
    return {
        "available": True,
        "evaluation_mode": "automatic_proxy",
        "method": (
            "Deterministic evaluation of the structured retrieval trace. "
            "Precision and recall are candidate-pool proxies; context relevance "
            "and utilization are calculated only from chunks actually supplied "
            "to generation. Recall is not labelled corpus recall."
        ),
        "k": max(
            (item["candidate_chunk_count"] for item in results),
            default=k,
        ),
        "case_count": len(results),
        "candidate_precision_proxy": mean(
            item["candidate_precision_proxy"] for item in results
        ),
        "candidate_recall_proxy": mean(
            item["candidate_recall_proxy"] for item in results
        ),
        "precision_at_k": mean(item["precision_at_k"] for item in results),
        "recall_at_k": mean(item["recall_at_k"] for item in results),
        "f1_score": mean(item["f1_score"] for item in results),
        "context_relevance": mean(item["context_relevance"] for item in results),
        "context_utilization": mean(item["context_utilization"] for item in results),
        "mrr": mean(item["reciprocal_rank"] for item in results),
        "candidate_chunk_count": sum(
            item["candidate_chunk_count"] for item in results
        ),
        "used_chunk_count": sum(item["used_chunk_count"] for item in results),
        "cases": results,
    }


def load_dataset(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {"cases": payload}
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("Evaluation dataset must contain a JSON 'cases' array")
    return payload


def evaluate_rag(
    state: dict[str, Any],
    dataset: dict[str, Any] | None,
    k: int = 5,
) -> dict[str, Any]:
    if not dataset:
        return _evaluate_automatic_proxy(state, k)

    retrieved_by_section = _retrieved_chunks_by_section(state)
    results = []
    for index, case in enumerate(dataset.get("cases") or []):
        section = str(case.get("section") or case.get("query") or "")
        relevant = {str(value) for value in case.get("relevant_chunk_ids") or []}
        retrieved = list(retrieved_by_section.get(section) or [])[:k]
        matches = [chunk_id for chunk_id in retrieved if chunk_id in relevant]
        reciprocal_rank = 0.0
        for rank, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in relevant:
                reciprocal_rank = 1.0 / rank
                break
        results.append(
            {
                "case_id": str(case.get("case_id") or index + 1),
                "query": case.get("query"),
                "section": section,
                "precision_at_k": len(matches) / len(retrieved) if retrieved else 0.0,
                "recall_at_k": len(matches) / len(relevant) if relevant else None,
                "reciprocal_rank": reciprocal_rank,
                "relevant_chunk_ids": sorted(relevant),
                "retrieved_chunk_ids": retrieved,
                "matched_chunk_ids": matches,
            }
        )

    recall_values = [
        item["recall_at_k"] for item in results if item["recall_at_k"] is not None
    ]
    return {
        "available": bool(results),
        "evaluation_mode": "labelled_ground_truth",
        "k": k,
        "case_count": len(results),
        "precision_at_k": mean(item["precision_at_k"] for item in results)
        if results
        else None,
        "recall_at_k": mean(recall_values) if recall_values else None,
        "f1_score": (
            2
            * mean(item["precision_at_k"] for item in results)
            * mean(recall_values)
            / (
                mean(item["precision_at_k"] for item in results)
                + mean(recall_values)
            )
            if results
            and recall_values
            and mean(item["precision_at_k"] for item in results)
            + mean(recall_values)
            > 0
            else 0.0
        ),
        "context_relevance": None,
        "context_utilization": None,
        "mrr": mean(item["reciprocal_rank"] for item in results)
        if results
        else None,
        "cases": results,
    }
