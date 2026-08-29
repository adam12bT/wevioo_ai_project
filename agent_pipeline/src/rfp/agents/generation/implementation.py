"""Generation agent implementation behind the packaged contract."""

import json
import logging
import math
import os
import re

from .prompts import GENERATION_PROMPT_TEMPLATE
from providers import get_provider
from rfp.default_template import resolve_response_template
from pipeline_progress import (
    finish_generation,
    mark_batch_completed,
    mark_batch_started,
    start_generation,
)

PROPOSALS_WORKSPACE = "company-past-proposals"
CVS_WORKSPACE = "company-cvs"
REFERENCES_WORKSPACE = "company-project-references"

logger = logging.getLogger(__name__)

_MOJIBAKE_REPLACEMENTS = {
    "â€‘": "‑",
    "â€“": "–",
    "â€”": "—",
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
    "â€¦": "…",
    "â‰¤": "≤",
    "â‰¥": "≥",
    "â‚¬": "€",
    "Ã€": "À",
    "Ã‰": "É",
    "Ã©": "é",
    "Ã¨": "è",
    "Ãª": "ê",
    "Ã ": "à",
    "Ã§": "ç",
    "Â ": "\u00a0",
}
_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â‰", "�")


def _repair_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Windows-1252 sequences without touching valid text."""
    repaired = str(value or "")
    for broken, replacement in _MOJIBAKE_REPLACEMENTS.items():
        repaired = repaired.replace(broken, replacement)
    for _ in range(2):
        current_score = sum(repaired.count(marker) for marker in _MOJIBAKE_MARKERS)
        if current_score == 0:
            break
        candidates = []
        for codec in ("cp1252", "latin-1"):
            try:
                candidate = repaired.encode(codec).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            score = sum(candidate.count(marker) for marker in _MOJIBAKE_MARKERS)
            candidates.append((score, candidate))
        if not candidates:
            break
        score, candidate = min(candidates, key=lambda item: item[0])
        if score >= current_score:
            break
        repaired = candidate
    return repaired


def _remove_generation_instruction_leaks(value: str) -> str:
    """Remove internal word-budget hints that a model echoed into its answer."""
    cleaned = []
    for line in str(value or "").splitlines():
        stripped = line.strip()
        if re.fullmatch(
            r"(?i)\(?\s*\d{2,5}\s*[-\u2010-\u2015]\s*\d{2,5}\s+words?\s*\)?[.:]?",
            stripped,
        ):
            continue
        if re.match(
            r"(?i)^(?:target length|per-section word budget)\s*:\s*\d+",
            stripped,
        ):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _strip_retrieval_metadata(value: str) -> str:
    """Remove extractor envelopes while retaining the document's actual text."""
    text = str(value or "")
    text = re.sub(
        r"(?is)<document_metadata>.*?</document_metadata>\s*",
        "",
        text,
    )
    return text.strip()


def _proposal_sections(response_template_rules: dict) -> list[str]:
    rules = resolve_response_template({"response_template": response_template_rules})
    raw_sections = rules.get("section_order") or rules.get("required_sections") or []
    sections = [str(section).strip() for section in raw_sections if str(section).strip()]
    return sections


def _section_batches(
    response_template_rules: dict, batch_size: int = 1
) -> list[list[str]]:
    size = max(1, batch_size)
    sections = _proposal_sections(response_template_rules)
    return [sections[index : index + size] for index in range(0, len(sections), size)]


def _batches_for_sections(sections: list[str], batch_size: int) -> list[list[str]]:
    size = max(1, batch_size)
    return [sections[index : index + size] for index in range(0, len(sections), size)]


def _rule_items(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _template_section_word_target(
    response_template_rules: dict,
    section_count: int,
) -> tuple[int, int, str]:
    """Derive one per-section budget from the uploaded template's global limit."""
    rules = (
        response_template_rules
        if isinstance(response_template_rules, dict)
        else {}
    )
    formatting = _rule_items(rules.get("formatting_requirements"))
    instructions = _rule_items(
        rules.get("instructions") or rules.get("template_instructions")
    )
    template_text = " ".join([*formatting, *instructions])
    normalized = re.sub(r"[\s\u00a0]+", " ", template_text.casefold())

    normalized_formatting = re.sub(
        r"[\s\u00a0]+",
        " ",
        " ".join(formatting).casefold(),
    )

    total_word_limit = None
    formatting_word_match = re.search(
        r"(?:maximum|max|not exceed|ne doit pas depasser)"
        r"\D{0,12}(\d[\d ,.]*?)\s*(?:words|mots)\b",
        normalized_formatting,
    )
    if formatting_word_match:
        digits = re.sub(r"\D", "", formatting_word_match.group(1))
        total_word_limit = int(digits) if digits else None

    total_word_patterns = (
        r"(?:proposal|response|submission|document|offre|reponse)"
        r"[^.]{0,40}?(?:maximum|max|not exceed|ne doit pas depasser)"
        r"\D{0,12}(\d[\d ,.]*?)\s*(?:words|mots)\b",
        r"(?:maximum|max|not exceed|ne doit pas depasser)"
        r"\D{0,12}(\d[\d ,.]*?)\s*(?:words|mots)\b"
        r"[^.]{0,30}?(?:total|proposal|response|submission|document|offre|reponse)",
    )
    for pattern in total_word_patterns:
        if total_word_limit:
            break
        match = re.search(pattern, normalized)
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            if digits:
                total_word_limit = int(digits)
                break

    maximum_pages = None
    page_match = re.search(
        r"(?:maximum|max|not exceed|ne doit pas depasser)"
        r"\D{0,12}(\d{1,3})\s*pages?\b",
        normalized,
    )
    if page_match:
        maximum_pages = int(page_match.group(1))

    count = max(1, section_count)
    if total_word_limit:
        target_total = max(count * 180, int(total_word_limit * 0.85))
        source = f"template total-word limit ({total_word_limit})"
    elif maximum_pages:
        target_total = max(count * 180, int(maximum_pages * 350 * 0.70))
        source = f"template page limit ({maximum_pages} pages)"
    else:
        target_total = count * 450
        source = "section count (no template word/page limit found)"

    words_per_section = target_total / count
    minimum_words = max(180, min(650, round(words_per_section * 0.80)))
    maximum_words = max(
        minimum_words,
        min(750, round(words_per_section * 1.05)),
    )
    return minimum_words, maximum_words, source


def _proposal_structure(
    response_template_rules: dict, sections: list[str] | None = None
) -> str:
    """Turn extracted template rules into an explicit Markdown outline.

    Uploaded outlines take priority. The canonical built-in outline is used
    only when no usable uploaded structure exists.
    """
    rules = response_template_rules if isinstance(response_template_rules, dict) else {}
    raw_sections = rules.get("section_order") or rules.get("required_sections") or []
    using_client_template = rules.get("template_source") == "uploaded"
    all_sections = _proposal_sections(rules)
    selected_sections = sections or all_sections
    minimum_words, maximum_words, budget_source = _template_section_word_target(
        rules,
        len(all_sections),
    )

    lines = [
        "CLIENT TEMPLATE - USE THESE EXACT HEADINGS AND THIS EXACT ORDER:"
        if using_client_template
        else "BUILT-IN RESPONSE STRUCTURE - USE THESE EXACT HEADINGS AND THIS ORDER:",
        (
            f"Per-section word budget: {minimum_words}-{maximum_words} words; "
            f"derived from {budget_source}."
        ),
    ]
    for section in selected_sections:
        lines.extend(
            [
                f"## {section}",
                f"Target length: {minimum_words}-{maximum_words} words.",
            ]
        )

    instructions = rules.get("instructions") or rules.get("template_instructions") or []
    formatting = rules.get("formatting_requirements") or []
    if isinstance(instructions, str):
        instructions = [instructions]
    if isinstance(formatting, str):
        formatting = [formatting]
    if instructions:
        lines.extend(["", "Template instructions:"])
        lines.extend(f"- {item}" for item in instructions if str(item).strip())
    if formatting:
        lines.extend(["", "Formatting requirements:"])
        lines.extend(f"- {item}" for item in formatting if str(item).strip())

    return "\n".join(lines)


import unicodedata

def _canonical_heading(value: str) -> str:
    heading = str(value).strip().casefold()
    heading = re.sub(r"^\s{0,3}#{1,6}\s*", "", heading)
    heading = re.sub(r"[*_`]", "", heading)
    heading = re.sub(r"^\s*(?:section\s+)?\d+(?:\.\d+)*[.)\-:]?\s*", "", heading)
    heading = re.sub(r"\s+", " ", heading).strip(" :-–—")
    normalized = unicodedata.normalize("NFKD", heading)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _heading_aliases(section: str) -> set[str]:
    """Return full and bilingual-half aliases for one template heading."""
    aliases = {_canonical_heading(section)}
    aliases.update(
        _canonical_heading(part)
        for part in str(section).split("/")
        if _canonical_heading(part)
    )
    return aliases


def _section_number(value: str) -> str | None:
    """Return a leading template section number, such as ``5`` or ``5.2``."""
    heading = re.sub(r"^\s{0,3}#{1,6}\s*", "", str(value).strip())
    match = re.match(r"^(?:section\s+)?(\d+(?:\.\d+)*)[.)\-:]?\s+", heading, re.I)
    return match.group(1) if match else None


def _normalize_batch_headings(draft: str, sections: list[str]) -> tuple[str, list[str]]:
    """Restore exact client titles when the model shortens bilingual headings.

    Models commonly emit only the French or English half of a bilingual title.
    The content is still the requested section, so replace that Markdown heading
    with the exact client title. Truly absent sections are returned unchanged and
    remain visible to the quality gate instead of being hidden by a placeholder.
    """
    lines = draft.splitlines()
    unmatched = []
    used_lines: set[int] = set()
    for section in sections:
        aliases = _heading_aliases(section)
        expected_number = _section_number(section)
        matched_line = next(
            (
                index
                for index, line in enumerate(lines)
                if index not in used_lines
                and re.match(r"^\s{0,3}#{1,6}\s+", line)
                and (
                    _canonical_heading(line) in aliases
                    or (
                        expected_number is not None
                        and _section_number(line) == expected_number
                    )
                )
            ),
            None,
        )
        if matched_line is None:
            unmatched.append(section)
            continue
        lines[matched_line] = f"## {section}"
        used_lines.add(matched_line)

    # Generation intentionally uses one dynamic template section per call. If the
    # model returns exactly one peer heading but paraphrases its title, it can only
    # belong to the assigned section. Rename it safely. Multiple peer headings are
    # still rejected because they may be an unwanted outline continuation.
    if len(sections) == 1 and unmatched:
        peer_headings = [
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s{0,3}#{1,2}\s+", line)
        ]
        if len(peer_headings) == 1:
            lines[peer_headings[0]] = f"## {sections[0]}"
            unmatched = []
    return "\n".join(lines), unmatched


def _split_batch_sections(draft: str, sections: list[str]) -> dict[str, str]:
    """Split assigned sections and stop at every unexpected peer heading.

    A model occasionally continues with headings copied from the full template.
    Those headings must not become the body of the section requested by this call.
    """
    lines = draft.splitlines()
    heading_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s{0,3}#{1,2}\s+", line)
    ]
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not re.match(r"^\s{0,3}#{1,6}\s+", line):
            continue
        canonical = _canonical_heading(line)
        number = _section_number(line)
        matched = next(
            (
                section
                for section in sections
                if canonical in _heading_aliases(section)
                or (number is not None and number == _section_number(section))
            ),
            None,
        )
        if matched and matched not in {title for _, title in starts}:
            starts.append((index, matched))

    content: dict[str, str] = {}
    for start, section in starts:
        end = next((index for index in heading_indexes if index > start), len(lines))
        content[section] = "\n".join(lines[start:end]).strip()
    return content


def _recover_single_section_response(
    draft: str,
    sections: list[str],
    generated_sections: dict[str, str],
) -> dict[str, str]:
    """Preserve substantive one-section output when its Markdown heading is absent.

    Some models follow the content instruction but return prose without the requested
    heading. Since generation uses one dynamic template section per request, that prose
    can be assigned safely without relying on a named or hard-coded section.
    """
    if len(sections) != 1 or generated_sections:
        return generated_sections

    section = sections[0]
    lines = draft.strip().splitlines()
    if not lines:
        return generated_sections

    # Remove an unformatted copy of the expected title, but never absorb a different
    # top-level outline into this section.
    if _canonical_heading(lines[0]) in _heading_aliases(section):
        lines = lines[1:]
    if any(re.match(r"^\s{0,3}#{1,2}\s+", line) for line in lines):
        return generated_sections

    body = "\n".join(lines).strip()
    if len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", body, flags=re.UNICODE)) < 12:
        return generated_sections

    return {section: f"## {section}\n\n{body}"}


def _batch_output_token_limit(
    response_template_rules: dict,
    section_count: int,
) -> int:
    """Calculate enough output room for the template-derived word target.

    The environment value remains a safety ceiling. The default is intentionally
    larger than the old 1,600-token cap because reasoning-capable models may count
    internal reasoning against their completion allowance.
    """
    _, maximum_words, _ = _template_section_word_target(
        response_template_rules,
        section_count,
    )
    estimated_tokens = math.ceil(maximum_words * 1.7) + 384
    configured_ceiling = max(
        1024,
        int(os.environ.get("GENERATION_BATCH_MAX_TOKENS", "2400")),
    )
    return min(configured_ceiling, max(1800, estimated_tokens))


def _section_body(block: str) -> str:
    """Return section body content without its first Markdown heading."""
    lines = block.strip().splitlines()
    if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _section_word_count(block: str) -> int:
    return len(
        re.findall(
            r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b",
            _section_body(block),
            flags=re.UNICODE,
        )
    )


def _has_substantive_section_body(block: str) -> bool:
    body = _section_body(block)
    return len(
        re.findall(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", body, flags=re.UNICODE)
    ) >= 12


def _completion_was_truncated(metadata: dict) -> bool:
    reason = str(metadata.get("finish_reason") or "").strip().casefold()
    return reason in {"length", "max_tokens", "max_token", "token_limit"}


def _salvage_truncated_section(block: str, maximum_words: int) -> str:
    """Trim an overlong provider response at its last complete safe boundary."""
    lines = block.strip().splitlines()
    heading = ""
    if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
        heading = lines.pop(0).strip()
    body = "\n".join(lines).strip()
    word_matches = list(
        re.finditer(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", body, flags=re.UNICODE)
    )
    if len(word_matches) < 12:
        return ""

    word_cap = max(12, int(maximum_words))
    if len(word_matches) > word_cap:
        candidate = body[: word_matches[word_cap - 1].end()].rstrip()
    else:
        candidate = body

    # A provider can stop in the middle of a word, sentence, list item, or table.
    # Retain the last complete sentence or complete Markdown/table line.
    if candidate == body and re.search(r"[.!?;:|\]\)]\s*$", candidate):
        trimmed = candidate
    else:
        boundaries = [
            match.end()
            for match in re.finditer(
                r"(?:[.!?][\"'’”\]\)]*|\|)\s*(?=\n|\s|$)",
                candidate,
            )
        ]
        minimum_boundary = word_matches[min(11, len(word_matches) - 1)].end()
        valid_boundaries = [end for end in boundaries if end >= minimum_boundary]
        if not valid_boundaries:
            return ""
        trimmed = candidate[: valid_boundaries[-1]].rstrip()

    result = f"{heading}\n\n{trimmed}".strip() if heading else trimmed
    return result if _has_substantive_section_body(result) else ""


def _merge_section_drafts(
    previous_draft: str,
    all_sections: list[str],
    replacements: dict[str, str],
) -> str:
    """Merge repaired sections into a prior draft in exact template order."""
    previous = _split_batch_sections(previous_draft, all_sections)
    merged = []
    for section in all_sections:
        content = replacements.get(section) or previous.get(section)
        if content and content.strip():
            merged.append(content.strip())
    return "\n\n".join(merged)


def _rebuild_section_evidence(
    all_sections: list[str],
    final_draft: str,
    evidence_batches: list[dict],
) -> list[dict]:
    """Create ordered, current evidence records after targeted replacements."""
    final_blocks = _split_batch_sections(final_draft, all_sections)
    rebuilt = []
    for section in all_sections:
        source = next(
            (
                batch
                for batch in reversed(evidence_batches)
                if section in (batch.get("sections") or [])
            ),
            {},
        )
        record = {
            key: value
            for key, value in source.items()
            if key not in {"sections", "draft"}
        }
        record["sections"] = [section]
        record["draft"] = final_blocks.get(section, "")
        rebuilt.append(record)
    return rebuilt


def _clip(value, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[context truncated to {limit} characters]"


def _truncate_to_length(value: str, target_length: int) -> str:
    marker = "\n[truncated to fit Groq request budget]"
    if len(value) <= target_length:
        return value
    if target_length <= len(marker):
        return value[:target_length]
    return f"{value[: target_length - len(marker)]}{marker}"


def _truncate_company_context(value: str, target_length: int) -> str:
    """Compact every retrieved company document instead of keeping only rank 1."""
    text = str(value or "")
    if len(text) <= target_length:
        return text
    blocks = [
        block.strip()
        for block in re.split(r"(?m)(?=^- From \[)", text)
        if block.strip()
    ]
    if len(blocks) <= 1:
        return _truncate_to_length(text, target_length)

    separator = "\n"
    marker = "\n[company evidence excerpt truncated]"
    available = max(0, target_length - len(marker) - len(separator) * (len(blocks) - 1))
    per_block = max(1, available // len(blocks))
    compacted = separator.join(block[:per_block].rstrip() for block in blocks)
    compacted = f"{compacted}{marker}"
    return compacted[:target_length]


def _fit_generation_prompt(format_values: dict, max_chars: int) -> tuple[str, dict]:
    """Render a prompt whose *total* size stays below the Groq free-tier budget.

    Per-field clipping is insufficient because the generation prompt combines
    several independent RAG fields. Keep the fixed instructions and proposal
    headings intact, then progressively trim optional evidence fields.
    """
    fitted = {key: str(value) for key, value in format_values.items()}
    prompt = GENERATION_PROMPT_TEMPLATE.format(**fitted)
    if len(prompt) <= max_chars:
        return prompt, fitted

    # Lower-priority/reference material is reduced first. Tender facts,
    # extracted requirements, template rules and headings retain larger floors.
    shrink_order = [
        ("past_proposals", 500),
        ("revision_feedback", 200),
        ("research_summary", 500),
        ("project_references", 500),
        ("cv_excerpts", 500),
        ("response_template_excerpts", 700),
        ("tender_excerpts", 1200),
        ("requirements", 1200),
        ("response_template_rules", 700),
    ]
    for field, minimum in shrink_order:
        overflow = len(prompt) - max_chars
        if overflow <= 0:
            break
        current = fitted[field]
        reducible = max(0, len(current) - minimum)
        if not reducible:
            continue
        # Leave room for the truncation marker added by the helper.
        target = len(current) - min(reducible, overflow + 50)
        truncator = (
            _truncate_company_context
            if field in {"project_references", "cv_excerpts", "past_proposals"}
            else _truncate_to_length
        )
        fitted[field] = truncator(current, max(minimum, target))
        prompt = GENERATION_PROMPT_TEMPLATE.format(**fitted)

    # The preferred evidence floors above improve quality, but they are not
    # hard requirements. On a dense template their combined size can still
    # exceed the hosted request budget. Degrade duplicated/optional context
    # further instead of aborting the entire pipeline. The exact assigned
    # proposal heading and all fixed grounding instructions remain untouched.
    emergency_order = [
        ("research_summary", 0),
        ("response_template_excerpts", 0),
        ("response_template_rules", 0),
        ("revision_feedback", 0),
        ("project_references", 200),
        ("cv_excerpts", 200),
        ("past_proposals", 250),
        ("tender_excerpts", 500),
        ("requirements", 500),
    ]
    for field, minimum in emergency_order:
        overflow = len(prompt) - max_chars
        if overflow <= 0:
            break
        current = fitted.get(field, "")
        reducible = max(0, len(current) - minimum)
        if not reducible:
            continue
        target = len(current) - min(reducible, overflow + 50)
        truncator = (
            _truncate_company_context
            if field in {"project_references", "cv_excerpts", "past_proposals"}
            else _truncate_to_length
        )
        fitted[field] = truncator(current, max(minimum, target))
        prompt = GENERATION_PROMPT_TEMPLATE.format(**fitted)

    # Last-resort fit: if even the emergency evidence floors do not fit, clear
    # optional context fields one by one. This is preferable to losing every
    # generated section; quality evaluation will still reject unsupported text.
    if len(prompt) > max_chars:
        for field, _ in emergency_order:
            if len(prompt) <= max_chars:
                break
            if fitted.get(field):
                fitted[field] = ""
                prompt = GENERATION_PROMPT_TEMPLATE.format(**fitted)

    if len(prompt) > max_chars:
        raise ValueError(
            "The fixed generation instructions exceed the configured total "
            f"prompt budget of {max_chars} characters."
        )
    return prompt, fitted


def _search_knowledge_port(knowledge, workspace_slug: str, query: str, top_n: int = 3) -> str:
    try:
        results = knowledge.search(workspace_slug, query, top_n=top_n)
    except Exception as exc:
        logger.warning("Injected knowledge search failed for %r: %s", workspace_slug, exc)
        results = []
    if not results:
        return "(none found in the company knowledge base for this query)"
    return "\n".join(
        f"- From [{item.get('metadata', {}).get('title', 'unknown source')}]: "
        f"{item.get('text', '').strip()}"
        for item in results
    )


def _search_knowledge_with_trace(
    knowledge,
    workspace_slug: str,
    query: str,
    *,
    top_n: int = 4,
) -> dict:
    """Return company context plus the exact vector chunks behind it."""
    retrieval_error = None
    rate_limited = False
    results = None
    try:
        # Company corpora are deliberately small and heterogeneous. A strict
        # similarity cutoff tends to return only the closest architect CV or
        # project, hiding other required roles and references. Use the traced
        # retrieval boundary when available so generation and quality share
        # the same broader, fully attributable evidence set.
        traced_search = getattr(knowledge, "query_with_trace", None)
        if callable(traced_search):
            traced = traced_search(
                workspace_slug,
                query,
                candidate_top_n=top_n,
                used_top_n=top_n,
                score_threshold=float(
                    os.environ.get("COMPANY_RAG_SCORE_THRESHOLD", "0.05")
                ),
            )
            if isinstance(traced, dict):
                retrieval_error = traced.get("retrieval_error")
                rate_limited = bool(traced.get("rate_limited"))
                results = [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "content": chunk.get("content"),
                        "score": chunk.get(
                            "rerank_score", chunk.get("vector_score")
                        ),
                        "metadata": chunk.get("metadata") or {},
                    }
                    for chunk in (traced.get("selected") or [])
                    if isinstance(chunk, dict)
                ]
        if results is None and retrieval_error is None:
            results = knowledge.search(workspace_slug, query, top_n=top_n)
    except Exception as exc:
        retrieval_error = f"{type(exc).__name__}: {exc}"
        rate_limited = (
            getattr(getattr(exc, "response", None), "status_code", None) == 429
        )
        logger.warning("Injected knowledge search failed for %r: %s", workspace_slug, exc)
        results = []

    results = results or []

    chunks = []
    for rank, item in enumerate(results or [], start=1):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        content = str(item.get("text") or item.get("content") or "").strip()
        if not content:
            continue
        title = str(
            metadata.get("title")
            or metadata.get("sourceDocument")
            or metadata.get("filename")
            or "unknown source"
        )
        chunk_id = str(
            item.get("chunk_id")
            or metadata.get("chunk_id")
            or metadata.get("id")
            or item.get("id")
            or f"{workspace_slug}-rank-{rank}"
        )
        chunk = {
            "chunk_id": chunk_id,
            "workspace_slug": workspace_slug,
            "title": title,
            "content": content,
            "score": item.get("score"),
            "rank": rank,
            "metadata": metadata,
        }
        chunks.append(chunk)

    # Keep the highest-ranked chunks, but present them document-first so one
    # long CV/reference cannot crowd every other uploaded document out of the
    # prompt. Exact chunk provenance remains available in ``selected_chunks``.
    document_groups: dict[str, list[dict]] = {}
    document_titles: dict[str, str] = {}
    document_order: list[str] = []
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        identity = str(
            metadata.get("sourceDocument")
            or metadata.get("filename")
            or metadata.get("document_name")
            or chunk.get("title")
            or chunk.get("chunk_id")
            or "unknown source"
        ).strip()
        # Extractor chunk filenames commonly end in -docx-3.txt or -pdf-p-2.txt.
        # Removing only that suffix groups chunks from the same uploaded file
        # without relying on any fixed CV/project names.
        document_key = re.sub(
            r"(?i)-(?:pdf|docx?|pptx?|xlsx?)(?:-p)?(?:-\d+)*\.txt$",
            "",
            identity,
        ).casefold()
        if document_key not in document_groups:
            document_groups[document_key] = []
            document_order.append(document_key)
            document_titles[document_key] = identity
        document_groups[document_key].append(chunk)

    context_blocks = []
    for document_key in document_order:
        grouped = document_groups[document_key]
        title = document_titles.get(document_key) or str(
            grouped[0].get("title") or document_key or "unknown source"
        )
        excerpts = []
        seen_content: set[str] = set()
        for chunk in grouped[:3]:
            content = _strip_retrieval_metadata(chunk.get("content") or "")
            fingerprint = re.sub(r"\s+", " ", content).casefold()
            if content and fingerprint not in seen_content:
                seen_content.add(fingerprint)
                excerpts.append(content)
        if excerpts:
            context_blocks.append(
                f"- From [{title}] (source document; {len(grouped)} retrieved chunk(s)):\n"
                + "\n\n".join(excerpts)
            )

    context = "\n".join(context_blocks)
    if not context:
        context = "(none found in the company knowledge base for this query)"
    return {
        "workspace_slug": workspace_slug,
        "query": query,
        "selected_chunks": chunks,
        "retrieval_error": retrieval_error,
        "rate_limited": rate_limited,
        "context": context,
    }


def _company_retrieval_queries(requirements: dict) -> dict[str, str]:
    """Build broad, tender-derived searches without fixed roles or domains."""
    scope = str(requirements.get("scope_summary") or "technical proposal").strip()
    evidence_fields = {
        key: requirements.get(key)
        for key in (
            "deliverables",
            "technical_constraints",
            "contractual_constraints",
            "mandatory_requirements",
            "domain_specific_constraints",
            "required_evidence",
            "evaluation_criteria",
        )
        if requirements.get(key)
    }
    tender_needs = _clip(json.dumps(evidence_fields, ensure_ascii=False), 2600)
    common = f"Tender scope: {scope}. Tender requirements and evidence: {tender_needs}."
    return {
        "references": (
            f"{common} Retrieve every relevant completed project reference, including "
            "different clients, domains, deliverables, integrations, migrations, security, "
            "and measurable outcomes. Return diverse projects, not only the closest one."
        ),
        "cvs": (
            f"{common} Retrieve all consultant CVs that can cover any required role, skill, "
            "certification, governance duty, delivery duty, migration duty, security duty, "
            "or technical duty. Return diverse people and roles, not only the closest CV."
        ),
        "proposals": (
            f"{common} Retrieve the most structurally relevant past proposal for reusable "
            "section organization, traceability tables, evidence presentation, and style."
        ),
    }


def _search_knowledge_queries_with_trace(
    knowledge,
    workspace_slug: str,
    queries: list[str],
    *,
    top_n_per_query: int = 4,
    max_chunks: int = 6,
) -> dict:
    """Fuse a small set of focused company searches and retain exact provenance."""
    selected_chunks: list[dict] = []
    seen: set[str] = set()
    for query in queries:
        trace = _search_knowledge_with_trace(
            knowledge,
            workspace_slug,
            query,
            top_n=top_n_per_query,
        )
        for chunk in trace.get("selected_chunks") or []:
            content = re.sub(r"\s+", " ", str(chunk.get("content") or "")).strip()
            dedupe_key = content.casefold()
            if not content or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            selected_chunks.append(dict(chunk))
            if len(selected_chunks) >= max_chunks:
                break
        if len(selected_chunks) >= max_chunks:
            break

    context_blocks = [
        f"- From [{chunk.get('title') or 'unknown source'}] "
        f"(chunk {chunk.get('chunk_id') or 'unknown'}): {chunk.get('content') or ''}"
        for chunk in selected_chunks
    ]
    return {
        "workspace_slug": workspace_slug,
        "query": " || ".join(queries),
        "selected_chunks": selected_chunks,
        "context": (
            "\n".join(context_blocks)
            if context_blocks
            else "(none found in the company knowledge base for these queries)"
        ),
    }


def _section_requests_company_evidence(sections: list[str]) -> bool:
    """Route evidence-heavy template sections without depending on fixed headings."""
    text = " ".join(str(section) for section in sections).casefold()
    return bool(
        re.search(
            r"\b(?:qualification|qualifications|experience|expertise|credentials?|"
            r"supporting evidence|project references?|references? pertinentes?|"
            r"curriculum vitae|\bcvs?\b|team|personnel|staff|certifications?|"
            r"équipe|equipe|profils?|preuves?|références?|references?)\b",
            text,
        )
    )


def _company_chunks_reaching_prompt(trace: dict, fitted_context: str) -> list[dict]:
    """Keep only chunks whose content or stable identity reached the fitted prompt."""
    fitted = str(fitted_context or "")
    if not fitted or fitted.startswith("(none found"):
        return []
    used = []
    for chunk in trace.get("selected_chunks") or []:
        content = str(chunk.get("content") or "")
        identity = str(chunk.get("chunk_id") or "")
        title = str(chunk.get("title") or "")
        probes = [value for value in (content[:120], identity, title) if value]
        if any(probe in fitted for probe in probes):
            used.append(chunk)
    return used


_COMPANY_EVIDENCE_PLACEHOLDER = (
    "[TO BE CONFIRMED - supporting company evidence not found]"
)
_TENDER_EVIDENCE_PLACEHOLDER = (
    "[TO BE CONFIRMED - supporting tender evidence not found]"
)
_CLAIM_STOPWORDS = {
    "about", "after", "also", "and", "are", "bidder", "client", "company",
    "for", "from", "has", "have", "into", "our", "proposal", "that", "the",
    "their", "this", "through", "will", "with",
}


def _normalized_claim_text(value: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", str(value or "").casefold()).strip()


def _clean_generated_evidence_structures(value: str) -> str:
    """Remove empty evidence tables and unfinished requirement identifiers.

    Models sometimes emit a project-table header without any evidence rows and
    then refer to the nonexistent rows as proof. They also occasionally copy an
    unfinished identifier such as ``FR-??``. Neither should reach the proposal.
    The detection is structural and does not depend on a fixed template title.
    """
    text = re.sub(
        r"(?i)\b(?:FR|REQ|RFP)[\s\-\u2010-\u2015]*\?{1,4}(?=\W|$)",
        "the applicable tender requirement",
        str(value or ""),
    )
    lines = text.splitlines()
    result: list[str] = []
    index = 0
    evidence_columns = re.compile(
        r"(?i)\b(?:project|reference|client|sector|scope|outcomes?|consultant|"
        r"personnel|candidate|role|qualification|certification)\b"
    )
    proof_sentence = re.compile(
        r"(?i)^\s*(?:these|the|such)\s+(?:projects?|references?|examples?|"
        r"profiles?|personnel|consultants?|entries)\b[^.!?]*(?:demonstrat|prove|"
        r"confirm|evidence|show|establish)[^.!?]*[.!?]?\s*$"
    )

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        separators = line.count("|") + line.count("\t")
        column_hits = len(evidence_columns.findall(stripped))
        if separators >= 2 and column_hits >= 3:
            cursor = index + 1
            # Markdown separator rows are table syntax, not evidence rows.
            while cursor < len(lines) and (
                not lines[cursor].strip()
                or re.fullmatch(r"[\s|:\-]+", lines[cursor])
            ):
                cursor += 1
            next_line = lines[cursor].strip() if cursor < len(lines) else ""
            next_is_row = (
                lines[cursor].count("|") + lines[cursor].count("\t") >= 2
                if cursor < len(lines)
                else False
            )
            if not next_is_row:
                # Omit the empty header and any prose that treats missing rows
                # as proof. Keep surrounding headings and genuine narrative.
                index = cursor
                if index < len(lines) and proof_sentence.search(lines[index]):
                    index += 1
                continue
        result.append(line)
        index += 1

    cleaned = "\n".join(result)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _claim_supported_by_company(claim: str, company_evidence: str) -> bool:
    evidence = str(company_evidence or "").strip()
    evidence = re.sub(
        r"(?im)^\s*\(none found[^\n]*\)\s*$", "", evidence
    ).strip()
    if not evidence:
        return False
    claim_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", claim.casefold())
        if len(term) >= 4 and term not in _CLAIM_STOPWORDS
    }
    evidence_terms = set(re.findall(r"[a-z0-9]+", evidence.casefold()))
    overlap = claim_terms & evidence_terms
    return len(overlap) >= 2 and len(overlap) / max(1, len(claim_terms)) >= 0.25


_COMMITMENT_VALUE_PATTERNS = {
    "page_limit": r"(?i)(?:maximum|max|not exceed|limit)[^\n.]{0,40}?(\d+(?:[.,]\d+)?\s*pages?)",
    "project_duration": r"(?i)(?:project|implementation|delivery)[^\n.]{0,45}?(?:duration|schedule|timeline)[^\n.]{0,30}?(\d+(?:[.,]\d+)?\s*(?:weeks?|months?|years?))",
    "warranty": r"(?i)\b(?:warranty|guarantee|garantie)\b[^\n.]{0,35}?(\d+(?:[.,]\d+)?\s*(?:months?|years?))",
    "rto": r"(?i)\bRTO\b[^\n.]{0,25}?(\d+(?:[.,]\d+)?\s*(?:minutes?|hours?))",
    "rpo": r"(?i)\bRPO\b[^\n.]{0,25}?(\d+(?:[.,]\d+)?\s*(?:minutes?|hours?))",
    "availability": r"(?i)\bavailability\b[^\n.]{0,35}?(\d+(?:[.,]\d+)?\s*%)",
    "migration_accuracy": r"(?i)\b(?:migration|record match)[^\n.]{0,45}?(\d+(?:[.,]\d+)?\s*%)",
    "incident_response": r"(?i)\b(?:incident|support)[^\n.]{0,45}?\bresponse[^\n.]{0,25}?(\d+(?:[.,]\d+)?\s*(?:minutes?|hours?|days?))",
    "incident_resolution": r"(?i)\b(?:incident|support)[^\n.]{0,45}?\bresolution[^\n.]{0,25}?(\d+(?:[.,]\d+)?\s*(?:minutes?|hours?|days?))",
}


def _commitment_identity(value: str) -> tuple[str, str] | None:
    """Return a stable metric/value pair for cross-section reconciliation."""
    for metric, pattern in _COMMITMENT_VALUE_PATTERNS.items():
        match = re.search(pattern, value)
        if match:
            return metric, _normalized_claim_text(match.group(1))
    if re.search(r"(?i)\b(?:penetration|security)\s+test|critical findings", value):
        targets = re.findall(
            r"(?i)\b\d+(?:[.,]\d+)?\s*(?:%|findings?|vulnerabilities?|days?)\b",
            value,
        )
        if targets:
            return "security_acceptance_target", "|".join(
                _normalized_claim_text(target) for target in targets
            )
    return None


def _sanitize_generated_claims(
    section_text: str,
    *,
    tender_evidence: str,
    company_evidence: str,
    commitment_registry: dict[str, str] | None = None,
    evidence_gap_registry: set[str] | None = None,
) -> tuple[str, list[dict]]:
    """Remove unsupported claims and aggregate their gaps once per section."""
    section_text = _clean_generated_evidence_structures(
        _remove_generation_instruction_leaks(_repair_mojibake(section_text))
    )
    tender_normalized = _normalized_claim_text(tender_evidence)
    company_normalized = _normalized_claim_text(company_evidence)
    company_evidence_available = bool(
        re.sub(
            r"(?im)^\s*\((?:none found|no relevant content found)[^\n]*\)\s*$",
            "",
            str(company_evidence or ""),
        ).strip()
    )
    redactions: list[dict] = []
    specific_gap_rows: list[tuple[str, str, str]] = []
    placeholder_pattern = re.compile(
        r"\[(?:[^\]]*(?:TO BE CONFIRMED|À CONFIRMER|CONFIRMER|"
        r"supporting (?:company|tender) evidence not found)[^\]]*)\]",
        flags=re.IGNORECASE,
    )
    bidder_fact_pattern = re.compile(
        r"(?i)(?:"
        r"\b(?:we|our (?:organisation|organization|company|firm|team)|the bidder|the firm)\b"
        r"[^.!?\n]{0,220}\b(?:has|have|holds?|possess(?:es)?|maintains?|operates?|"
        r"certified|proven|track record|experience|expertise|capabilit(?:y|ies)|"
        r"successfully|delivered|implemented|regional office|local office)\b"
        r"|\bkey personnel\b[^.!?\n]{0,160}\b(?:hold|have|possess(?:es)?|certified|experience)\b"
        r"|\b(?:documented|proven|existing)\b[^.!?\n]{0,100}\b(?:capabilit(?:y|ies)|"
        r"framework|processes|experience)\b"
        r"|\b(?:our|the proposed)\s+(?:qualified|certified|experienced)\s+"
        r"(?:team|personnel|staff)\b"
        r"|\b(?:this|the) proposal\b[^.!?\n]{0,100}\b(?:includes?|provides?|presents?)\b"
        r"[^.!?\n]{0,100}\b(?:qualified|certified|experienced)\s+"
        r"(?:team|personnel|staff)\b"
        r")"
    )
    unsupported_experience_pattern = re.compile(
        r"(?i)\b(?:demonstrable|demonstrated|proven|established|extensive|"
        r"substantial|relevant|successful|documented|verified)\b"
        r"[^.!?\n]{0,90}\b(?:experience|expertise|capabilit(?:y|ies)|"
        r"competenc(?:e|ies)|qualifications?|track record)\b"
        r"|\b(?:experience|expertise|capabilit(?:y|ies)|competenc(?:e|ies)|"
        r"qualifications?|track record)\b[^.!?\n]{0,90}\b(?:design(?:ing)?|"
        r"develop(?:ment|ing|ed)?|deploy(?:ment|ing|ed)?|deliver(?:y|ing|ed)?|"
        r"implement(?:ation|ing|ed)?|public[ -]?sector|government|comparable|similar)\b"
        r"|\bindividuals?\b[^.!?\n]{0,140}\b(?:engaged|worked|delivered|performed)\b"
        r"[^.!?\n]{0,100}\b(?:comparable|similar|programme|program|project)\b"
        r"|\b(?:projects?|references?)\b[^.!?\n]{0,120}\b(?:evidence|demonstrate|prove)\b"
        r"[^.!?\n]{0,100}\b(?:our|the bidder(?:'s)?)\s+(?:competence|capability|experience)\b"
    )
    evidence_promise_pattern = re.compile(
        r"(?i)\b(?:we|the bidder|the firm)\s+will\s+"
        r"(?:provide|supply|submit|include|present|obtain|compile|replace)\b"
        r"[^.!?\n]{0,180}\b(?:cv|curriculum vitae|reference|case stud|certificate|"
        r"certification|evidence|letter|artefact|artifact)"
    )
    artefact_existence_pattern = re.compile(
        r"(?i)\b(?:cv|curriculum vitae|reference letters?|case studies|certificate|"
        r"certification|appendix|annex|demonstration environment|test report|"
        r"supporting evidence)\b[^.!?\n]{0,180}\b(?:has been|have been|is|are|"
        r"will be|compiled|included|attached|provided|presented|available|completed|"
        r"schedule(?:d)?\s+in)\b"
    )
    annex_evidence_row_pattern = re.compile(
        r"(?i)\bannex\b[^\n|]{0,30}\|[^\n]*(?:curriculum vitae|\bcvs?\b|"
        r"reference letters?|certificate|certification|case stud)"
    )
    unsupported_pricing_pattern = re.compile(
        r"(?i)\b(?:commercial offer|financial proposal|pricing|price)\b"
        r"[^.!?\n]{0,160}\b(?:lump[ -]?sum|fixed[ -]?fee|total fee|priced at)\b"
    )
    opaque_cv_reference_pattern = re.compile(
        r"(?i)(?:\(\s*see\s+)?\bCV\s*[#:]?\s*[a-f0-9]{4,}\b\s*\)?"
    )
    distinctive_value_pattern = re.compile(
        r"(?i)\b\d+(?:[.,]\d+)?[ \t\u00a0\u202f\u2010\u2011\u2012\u2013\u2014\u2015-]*(?:%|pages?|years?|months?|"
        r"weeks?|days?|hours?|minutes?|records?|letters?|personnel|developers?|"
        r"engineers?|users?|defects?|findings?|seconds?|points?)(?=$|\W)"
    )
    leading_time_range_pattern = re.compile(
        r"(?i)\b(?:weeks?|months?|days?|years?)\s*\d+(?:\s*[-‐‑‒–—―]\s*\d+)?\b"
    )
    money_or_currency_pattern = re.compile(
        r"(?i)(?:[$€£]\s*\d[\d\s.,]*|\b\d[\d\s.,]*\s*(?:TND|USD|EUR|GBP)\b|"
        r"\b(?:TND|USD|EUR|GBP)\b|\b24\s*/\s*7\b)"
    )
    named_control_pattern = re.compile(
        r"(?i)\b(?:ISO\s*[0-9]{4,5}(?::[0-9]{4})?|NIST(?:\s*SP)?\s*[0-9-]+|"
        r"SOC\s*2|GDPR|TLS\s*\d(?:\.\d+)?|AES\s*[- ]?\d+)\b"
    )
    cadence_pattern = re.compile(
        r"(?i)\b(?:daily|weekly|fortnightly|biweekly|monthly|quarterly|annually)\b"
    )

    def normalized_numeric_commitment(value: str) -> str:
        normalized = str(value or "").casefold().translate(
            str.maketrans(
                {"‐": " ", "‑": " ", "‒": " ", "–": " ", "—": " ", "―": " "}
            )
        )
        normalized = re.sub(
            r"\b(pages?|years?|months?|weeks?|days?|hours?|minutes?|records?|"
            r"letters?|developers?|engineers?|users?|defects?|findings?|seconds?|points?)\b",
            lambda match: match.group(1).rstrip("s"),
            normalized,
        )
        return re.sub(r"[\s,]", "", normalized).rstrip(".")

    numeric_patterns = (
        distinctive_value_pattern,
        leading_time_range_pattern,
        money_or_currency_pattern,
    )
    supported_numeric_values = {
        normalized_numeric_commitment(match.group(0))
        for pattern in numeric_patterns
        for match in pattern.finditer(tender_evidence)
    }

    def record_placeholder(value: str) -> None:
        normalized = value.casefold()
        evidence_type = (
            "missing_tender_evidence"
            if "tender" in normalized
            else "missing_company_evidence"
        )
        redactions.append({"type": evidence_type, "claim": value[:300]})

    def replacement(in_table: bool) -> str:
        return ""

    existing_gap_pattern = re.compile(
        r"(?ims)^###\s+(?:Evidence gaps|Missing evidence|Lacunes de preuve|"
        r"Éléments à confirmer)\s*$.*?(?=^###\s+|\Z)"
    )
    for gap_block in existing_gap_pattern.findall(section_text):
        # Keep precise gaps (for example, one required role without a matching
        # CV) and discard vague repeated rows such as "Company evidence".
        for line in gap_block.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 3 or all(
                re.fullmatch(r"[-: ]+", cell) for cell in cells
            ):
                continue
            gap, status, action = cells[:3]
            normalized_gap = _normalized_claim_text(gap)
            if normalized_gap in {
                "evidence gap",
                "missing evidence",
                "company evidence",
                "tender backed commitment",
            }:
                continue
            if "confirm" not in _normalized_claim_text(status):
                continue
            if (
                evidence_gap_registry is not None
                and normalized_gap in evidence_gap_registry
            ):
                continue
            if evidence_gap_registry is not None:
                evidence_gap_registry.add(normalized_gap)
            specific_gap_rows.append((gap, "[TO BE CONFIRMED]", action))
        found = placeholder_pattern.findall(gap_block)
        if found:
            for placeholder in found:
                record_placeholder(placeholder)
        else:
            redactions.append(
                {"type": "missing_company_evidence", "claim": "Existing evidence-gap subsection"}
            )
    section_text = existing_gap_pattern.sub("", section_text)

    def sanitize_unit(unit: str, *, in_table: bool = False) -> str:
        stripped = unit.strip()
        if not stripped or stripped.startswith("#"):
            return unit

        placeholders = placeholder_pattern.findall(stripped)
        if placeholders:
            for placeholder in placeholders:
                record_placeholder(placeholder)
            return replacement(in_table)

        # Retrieval identifiers prove provenance internally but are not people
        # and must never appear as personnel evidence in the proposal.
        stripped = opaque_cv_reference_pattern.sub("", stripped).strip()
        unit = stripped

        company_claim = bool(
            bidder_fact_pattern.search(stripped)
            or unsupported_experience_pattern.search(stripped)
            or evidence_promise_pattern.search(stripped)
            or artefact_existence_pattern.search(stripped)
            or unsupported_pricing_pattern.search(stripped)
        )
        if company_claim and not _claim_supported_by_company(stripped, company_evidence):
            redactions.append(
                {"type": "unsupported_company_claim", "claim": stripped[:300]}
            )
            return replacement(in_table)

        numeric_values = [match.group(0) for match in distinctive_value_pattern.finditer(stripped)]
        numeric_values.extend(
            match.group(0) for match in leading_time_range_pattern.finditer(stripped)
        )
        numeric_values.extend(
            match.group(0) for match in money_or_currency_pattern.finditer(stripped)
        )
        unsupported_values = [
            value
            for value in numeric_values
            if normalized_numeric_commitment(value) not in supported_numeric_values
        ]
        if unsupported_values and not (
            company_claim and _claim_supported_by_company(stripped, company_evidence)
        ):
            redactions.append(
                {
                    "type": "unsupported_numeric_commitment",
                    "claim": stripped[:300],
                    "values": unsupported_values,
                }
            )
            return replacement(in_table)

        commitment = _commitment_identity(stripped)
        if commitment and commitment_registry is not None:
            metric, signature = commitment
            previous = commitment_registry.get(metric)
            if previous is not None and previous != signature:
                redactions.append(
                    {
                        "type": "inconsistent_cross_section_commitment",
                        "claim": stripped[:300],
                        "metric": metric,
                        "expected": previous,
                        "found": signature,
                    }
                )
                return replacement(in_table)
            commitment_registry.setdefault(metric, signature)

        unsupported_controls = [
            match.group(0)
            for match in named_control_pattern.finditer(stripped)
            if _normalized_claim_text(match.group(0)) not in tender_normalized
            and _normalized_claim_text(match.group(0)) not in company_normalized
        ]
        if unsupported_controls:
            redactions.append(
                {
                    "type": "unsupported_security_or_compliance_control",
                    "claim": stripped[:300],
                    "values": unsupported_controls,
                }
            )
            return replacement(in_table)

        unsupported_cadence = [
            match.group(0)
            for match in cadence_pattern.finditer(stripped)
            if _normalized_claim_text(match.group(0)) not in tender_normalized
        ]
        if unsupported_cadence:
            redactions.append(
                {
                    "type": "unsupported_schedule_commitment",
                    "claim": stripped[:300],
                    "values": unsupported_cadence,
                }
            )
            return replacement(in_table)

        return unit

    sanitized_lines = []
    for line in section_text.splitlines():
        if line.strip().startswith("|") and line.count("|") >= 2:
            if annex_evidence_row_pattern.search(line) and not _claim_supported_by_company(
                line, company_evidence
            ):
                redactions.append(
                    {"type": "unavailable_annex_or_attachment", "claim": line[:300]}
                )
                continue
            cells = line.split("|")
            redaction_count = len(redactions)
            sanitized_cells = [sanitize_unit(cell, in_table=True) for cell in cells]
            if len(redactions) == redaction_count:
                sanitized_lines.append("|".join(sanitized_cells))
            continue
        parts = re.split(r"(?<=[.!?])([ \t]+)", line)
        sanitized_lines.append(
            "".join(
                sanitize_unit(part) if index % 2 == 0 else part
                for index, part in enumerate(parts)
            )
        )

    sanitized = "\n".join(sanitized_lines)
    sanitized = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s*$", "", sanitized)
    sanitized = re.sub(r"[ \t]+\n", "\n", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()

    if redactions:
        gap_types = {item.get("type") for item in redactions}
        gap_rows = list(specific_gap_rows)
        if gap_types & {
            "missing_company_evidence",
            "unsupported_company_claim",
            "unavailable_annex_or_attachment",
        } and not company_evidence_available:
            gap_rows.append(
                (
                    "Company evidence",
                    "[TO BE CONFIRMED]",
                    "Upload verified CVs, project references, certificates, pricing, or attachments required by this section.",
                )
            )
        tender_evidence_available = bool(str(tender_evidence or "").strip())
        if gap_types & {
            "missing_tender_evidence",
            "unsupported_numeric_commitment",
            "unsupported_schedule_commitment",
            "unsupported_security_or_compliance_control",
            "inconsistent_cross_section_commitment",
        } and (not tender_evidence_available or not company_evidence_available):
            gap_rows.append(
                (
                    "Tender-backed commitment",
                    "[TO BE CONFIRMED]",
                    "Verify the exact value, schedule, target, standard, or instruction in the tender before committing to it.",
                )
            )
        if gap_rows:
            gap_table = [
                "### Evidence gaps",
                "| Evidence gap | Status | Required user action |",
                "| --- | --- | --- |",
            ]
            gap_table.extend(
                f"| {gap} | {status} | {action} |"
                for gap, status, action in gap_rows
            )
            sanitized = f"{sanitized}\n\n" + "\n".join(gap_table)

    elif specific_gap_rows:
        gap_table = [
            "### Evidence gaps",
            "| Evidence gap | Status | Required user action |",
            "| --- | --- | --- |",
        ]
        gap_table.extend(
            f"| {gap} | {status} | {action} |"
            for gap, status, action in specific_gap_rows
        )
        sanitized = f"{sanitized}\n\n" + "\n".join(gap_table)

    return sanitized.strip(), redactions


def generation_agent(state: dict, *, rag=None, knowledge=None) -> dict:
    if not state.get("is_verified"):
        return {}

    if rag is None or knowledge is None:
        raise RuntimeError("RagQuery and KnowledgeSearch dependencies are required")
    try:
        knowledge.ensure_ready()
    except Exception as exc:
        logger.warning("Injected company knowledge adapter is not ready: %s", exc)
    workspace_slug = state["workspace_slug"]
    template_workspace_slug = state.get("response_template_workspace_slug")
    requirements = state.get("requirements", {})
    search_query = requirements.get("scope_summary") or "technical proposal requirements"
    company_queries = _company_retrieval_queries(requirements)
    company_top_n = max(8, int(os.environ.get("COMPANY_RAG_TOP_N", "12")))
    previous_generation_evidence = state.get("previous_generation_evidence") or {}

    # Reuse the exact company evidence from the first attempt. A repair should
    # not spend more vector-search calls or silently change its evidence base.
    if previous_generation_evidence:
        project_references = previous_generation_evidence.get(
            "project_references", ""
        )
        cv_excerpts = previous_generation_evidence.get("cv_excerpts", "")
        past_proposals = previous_generation_evidence.get("past_proposals", "")
        base_reference_trace = {
            "workspace_slug": REFERENCES_WORKSPACE,
            "query": search_query,
            "selected_chunks": [],
            "context": project_references,
            "reused": True,
        }
        base_cv_trace = {
            "workspace_slug": CVS_WORKSPACE,
            "query": search_query,
            "selected_chunks": [],
            "context": cv_excerpts,
            "reused": True,
        }
        base_proposal_trace = {
            "workspace_slug": PROPOSALS_WORKSPACE,
            "query": search_query,
            "selected_chunks": [],
            "context": past_proposals,
            "reused": True,
        }
    else:
        base_reference_trace = _search_knowledge_with_trace(
            knowledge,
            REFERENCES_WORKSPACE,
            company_queries["references"],
            top_n=company_top_n,
        )
        if base_reference_trace.get("rate_limited"):
            base_cv_trace = {
                "workspace_slug": CVS_WORKSPACE,
                "query": search_query,
                "selected_chunks": [],
                "context": "(company CV retrieval deferred because the knowledge service is rate-limited)",
                "not_attempted": True,
            }
            base_proposal_trace = {
                "workspace_slug": PROPOSALS_WORKSPACE,
                "query": search_query,
                "selected_chunks": [],
                "context": "(past-proposal retrieval deferred because the knowledge service is rate-limited)",
                "not_attempted": True,
            }
        else:
            base_cv_trace = _search_knowledge_with_trace(
                knowledge,
                CVS_WORKSPACE,
                company_queries["cvs"],
                top_n=company_top_n,
            )
            if base_cv_trace.get("rate_limited"):
                base_proposal_trace = {
                    "workspace_slug": PROPOSALS_WORKSPACE,
                    "query": search_query,
                    "selected_chunks": [],
                    "context": "(past-proposal retrieval deferred because the knowledge service is rate-limited)",
                    "not_attempted": True,
                }
            else:
                base_proposal_trace = _search_knowledge_with_trace(
                    knowledge,
                    PROPOSALS_WORKSPACE,
                    company_queries["proposals"],
                    top_n=company_top_n,
                )
        project_references = str(base_reference_trace.get("context") or "")
        cv_excerpts = str(base_cv_trace.get("context") or "")
        past_proposals = str(base_proposal_trace.get("context") or "")

    response_template_rules = resolve_response_template(requirements)
    requirements["response_template"] = response_template_rules
    revision_feedback = state.get("quality_report") or "(first generation attempt)"
    attempt_number = state.get("generation_attempts", 0) + 1
    previous_draft = state.get("previous_draft", "")
    # One section per call prevents a detailed early section from consuming the
    # output allowance reserved for later headings.
    batch_size = 1
    context_limit = max(
        2000, int(os.environ.get("GENERATION_CONTEXT_MAX_CHARS", "6000"))
    )
    prompt_max_chars = min(
        11000,
        max(8000, int(os.environ.get("GENERATION_PROMPT_MAX_CHARS", "11000"))),
    )
    all_sections = _proposal_sections(response_template_rules)
    section_minimum_words, section_maximum_words, section_budget_source = _template_section_word_target(
        response_template_rules,
        len(all_sections),
    )
    batch_max_tokens = _batch_output_token_limit(
        response_template_rules,
        len(all_sections),
    )
    repair_sections = []
    if attempt_number > 1 and previous_draft.strip():
        requested_repairs = revision_feedback.get("failed_sections", []) if isinstance(
            revision_feedback, dict
        ) else []
        repair_sections = [
            section for section in all_sections if section in requested_repairs
        ]
    selected_sections = repair_sections or all_sections
    repair_mode = bool(repair_sections)
    batches = _batches_for_sections(selected_sections, batch_size=batch_size)
    run_id = state.get("run_id")
    start_generation(run_id, batches)

    retained_batches = []
    if repair_mode:
        retained_batches = [
            dict(batch)
            for batch in previous_generation_evidence.get("section_batches", [])
            if isinstance(batch, dict)
        ]
    generation_evidence = {
        "section_batches": retained_batches,
        "requirements": requirements,
        "research_summary": state.get("research_summary", "(no research available)"),
        "project_references": project_references,
        "cv_excerpts": cv_excerpts,
        "past_proposals": past_proposals,
        "repair_mode": repair_mode,
        "repaired_sections": repair_sections,
        "template_source": response_template_rules.get("template_source", "default"),
        "template_version": response_template_rules.get("version"),
    }
    commitment_registry: dict[str, str] = {}
    evidence_gap_registry: set[str] = set()

    logger.info(
        "Generation attempt %d for workspace %r using %d dynamic batch(es)%s",
        attempt_number,
        workspace_slug,
        len(batches),
        f" to repair {repair_sections}" if repair_mode else "",
    )

    replacement_sections: dict[str, str] = {}
    previous_blocks = _split_batch_sections(previous_draft, all_sections)
    prior_evidence_by_sections = {
        tuple(str(section) for section in batch.get("sections") or []): batch
        for batch in previous_generation_evidence.get("section_batches", [])
        if isinstance(batch, dict)
    }
    for batch_number, sections in enumerate(batches, start=1):
        mark_batch_started(run_id, batch_number)
        section_names = "; ".join(sections)
        scope_hint = str(requirements.get("scope_summary") or "").strip()[:400]
        batch_query = (
            f"Section(s): {section_names}. Tender scope: {scope_hint}. "
            "Retrieve the tender facts, mandatory requirements, constraints, "
            "acceptance evidence, dependencies and contractual obligations that "
            "are specifically relevant to these sections."
        )
        retrieval_trace = None
        if hasattr(rag, "query_with_trace"):
            traced_result = rag.query_with_trace(
                workspace_slug,
                batch_query,
                candidate_top_n=8,
                used_top_n=4,
                score_threshold=0.15,
            )
            if isinstance(traced_result, dict):
                retrieval_trace = traced_result
        if retrieval_trace is not None:
            if retrieval_trace.get("retrieval_error"):
                raise RuntimeError(
                    "Mandatory tender retrieval failed before generation for "
                    f"section(s) {section_names}: "
                    f"{retrieval_trace['retrieval_error']}"
                )
            tender_excerpts = str(retrieval_trace.get("context") or "")
        else:
            tender_excerpts = rag.query(workspace_slug, batch_query, top_n=4)
            retrieval_trace = {
                "query": batch_query,
                "candidates": [],
                "selected": [],
                "context": tender_excerpts,
            }
        if template_workspace_slug:
            response_template_excerpts = rag.query(
                template_workspace_slug,
                f"content instructions, tables and formatting for sections: {section_names}",
                top_n=4,
            )
        else:
            response_template_excerpts = json.dumps(
                response_template_rules, ensure_ascii=False
            )

        prior_batch_evidence = prior_evidence_by_sections.get(tuple(sections), {})
        prior_company_retrieval = prior_batch_evidence.get("company_retrieval") or {}
        company_query_base = (
            f"Proposal section(s): {section_names}. Tender scope: {scope_hint}. "
            "Return explicit company evidence relevant to this section. Do not infer "
            "capabilities that the document does not state."
        )
        if repair_mode and prior_company_retrieval:
            reference_trace = prior_company_retrieval.get("project_references") or {}
            cv_trace = prior_company_retrieval.get("cv_excerpts") or {}
            proposal_trace = prior_company_retrieval.get("past_proposals") or {}
        elif repair_mode and prior_batch_evidence:
            # Compatibility with evidence captured before per-section company
            # traces were introduced. Reuse the exact fitted strings.
            reference_trace = {
                "workspace_slug": REFERENCES_WORKSPACE,
                "query": company_query_base,
                "selected_chunks": [],
                "context": prior_batch_evidence.get("project_references") or project_references,
            }
            cv_trace = {
                "workspace_slug": CVS_WORKSPACE,
                "query": company_query_base,
                "selected_chunks": [],
                "context": prior_batch_evidence.get("cv_excerpts") or cv_excerpts,
            }
            proposal_trace = {
                "workspace_slug": PROPOSALS_WORKSPACE,
                "query": company_query_base,
                "selected_chunks": [],
                "context": prior_batch_evidence.get("past_proposals") or past_proposals,
            }
        else:
            # Retrieve company evidence once per generation attempt. Reusing
            # the exact trace prevents 3-5 extra vector calls per section and
            # still records which chunks actually survive prompt fitting.
            reference_trace = base_reference_trace
            cv_trace = base_cv_trace
            proposal_trace = base_proposal_trace

        section_project_references = str(reference_trace.get("context") or "")
        section_cv_excerpts = str(cv_trace.get("context") or "")
        section_past_proposals = str(proposal_trace.get("context") or "")
        batch_revision_feedback = revision_feedback
        if repair_mode:
            batch_revision_feedback = {
                "quality_report": revision_feedback,
                "previous_section_content": {
                    section: previous_blocks.get(section, "") for section in sections
                },
                "instruction": (
                    "Rewrite only these failed sections. Correct every cited issue "
                    "without changing facts supported elsewhere in the proposal."
                ),
            }
        prompt, fitted_context = _fit_generation_prompt(
            {
                "batch_number": batch_number,
                "batch_count": len(batches),
                "tender_excerpts": _clip(tender_excerpts, context_limit),
                "response_template_excerpts": _clip(
                    response_template_excerpts, context_limit
                ),
                "response_template_rules": _clip(
                    response_template_rules, context_limit
                ),
                "proposal_structure": _proposal_structure(
                    response_template_rules, sections
                ),
                "revision_feedback": _clip(batch_revision_feedback, context_limit),
                "requirements": _clip(requirements, context_limit),
                "research_summary": _clip(
                    state.get("research_summary", "(no research available)"),
                    context_limit,
                ),
                "project_references": _truncate_company_context(
                    section_project_references, context_limit
                ),
                "cv_excerpts": _truncate_company_context(
                    section_cv_excerpts, context_limit
                ),
                "past_proposals": _truncate_company_context(
                    section_past_proposals, context_limit
                ),
            },
            prompt_max_chars,
        )
        # Preserve the exact fitted evidence sent to the model for this section.
        # Quality must judge the generated claims against this context, not
        # against a different retrieval or a later top-level truncation.
        batch_evidence = {
            "sections": sections,
            "retrieval_query": batch_query,
            "candidate_chunks": retrieval_trace.get("candidates") or [],
            "tender_excerpts": fitted_context["tender_excerpts"],
            "response_template_excerpts": fitted_context[
                "response_template_excerpts"
            ],
            "requirements": fitted_context["requirements"],
            "research_summary": fitted_context["research_summary"],
            "project_references": fitted_context["project_references"],
            "cv_excerpts": fitted_context["cv_excerpts"],
            "past_proposals": fitted_context["past_proposals"],
            "company_retrieval": {
                "project_references": reference_trace,
                "cv_excerpts": cv_trace,
                "past_proposals": proposal_trace,
            },
            "prompt_chars": len(prompt),
            "template_source": response_template_rules.get(
                "template_source", "default"
            ),
            "target_word_range": {
                "minimum": section_minimum_words,
                "maximum": section_maximum_words,
                "source": section_budget_source,
                "hard_maximum": section_budget_source.startswith(
                    ("template total-word limit", "template page limit")
                ),
            },
        }
        fitted_chunk_ids = set(
            re.findall(
                r"(?m)^sourceDocument:\s*(.+?)\s*$",
                fitted_context["tender_excerpts"],
            )
        )
        batch_evidence["used_chunks"] = [
            chunk
            for chunk in (retrieval_trace.get("selected") or [])
            if str(chunk.get("chunk_id") or "") in fitted_chunk_ids
        ]
        batch_evidence["used_company_chunks"] = {
            "project_references": _company_chunks_reaching_prompt(
                reference_trace, fitted_context["project_references"]
            ),
            "cv_excerpts": _company_chunks_reaching_prompt(
                cv_trace, fitted_context["cv_excerpts"]
            ),
            "past_proposals": _company_chunks_reaching_prompt(
                proposal_trace, fitted_context["past_proposals"]
            ),
        }
        batch_evidence["candidate_chunk_count"] = len(
            batch_evidence["candidate_chunks"]
        )
        batch_evidence["used_chunk_count"] = len(batch_evidence["used_chunks"])
        generation_evidence["section_batches"].append(batch_evidence)
        logger.info(
            "Generation batch %d/%d retrieval preserved %d candidate chunk(s); "
            "%d chunk(s) reached the fitted prompt",
            batch_number,
            len(batches),
            batch_evidence["candidate_chunk_count"],
            batch_evidence["used_chunk_count"],
        )
        logger.info(
            "Generation batch %d/%d prompt fitted to %d/%d characters",
            batch_number,
            len(batches),
            len(prompt),
            prompt_max_chars,
        )

        try:
            completion_metadata: dict = {}
            batch_draft = get_provider().complete(
                prompt,
                max_tokens=batch_max_tokens,
                request_label=f"generation.batch_{batch_number}_of_{len(batches)}",
                reasoning_effort="low",
                include_reasoning=False,
                completion_metadata=completion_metadata,
            ).strip()
            if not batch_draft:
                raise ValueError("the model returned an empty section batch")
            reached_token_limit = _completion_was_truncated(completion_metadata)
            batch_draft = _repair_mojibake(batch_draft)
            batch_draft, unmatched_headings = _normalize_batch_headings(
                batch_draft, sections
            )
            if unmatched_headings:
                logger.warning(
                    "Generation batch %d/%d omitted template headings: %s",
                    batch_number,
                    len(batches),
                    unmatched_headings,
                )
            generated_sections = _split_batch_sections(batch_draft, sections)
            generated_sections = {
                section: block
                for section, block in generated_sections.items()
                if _has_substantive_section_body(block)
            }
            generated_sections = _recover_single_section_response(
                batch_draft,
                sections,
                generated_sections,
            )
            fitted_tender_evidence = "\n".join(
                (
                    str(fitted_context.get("tender_excerpts") or ""),
                    str(fitted_context.get("requirements") or ""),
                    str(fitted_context.get("response_template_excerpts") or ""),
                    str(fitted_context.get("response_template_rules") or ""),
                )
            )
            fitted_company_evidence = "\n".join(
                (
                    str(fitted_context.get("project_references") or ""),
                    str(fitted_context.get("cv_excerpts") or ""),
                )
            )
            generation_guard_redactions = []
            guarded_sections = {}
            for section, block in generated_sections.items():
                guarded, redactions = _sanitize_generated_claims(
                    block,
                    tender_evidence=fitted_tender_evidence,
                    company_evidence=fitted_company_evidence,
                    commitment_registry=commitment_registry,
                    evidence_gap_registry=evidence_gap_registry,
                )
                guarded_sections[section] = guarded
                generation_guard_redactions.extend(
                    {"section": section, **redaction} for redaction in redactions
                )
            generated_sections = guarded_sections
            if generation_guard_redactions:
                batch_evidence["generation_guard_redactions"] = generation_guard_redactions
                logger.warning(
                    "Generation batch %d/%d neutralized %d unsupported high-risk claim(s)",
                    batch_number,
                    len(batches),
                    len(generation_guard_redactions),
                )
            if reached_token_limit:
                salvaged_sections = {
                    section: _salvage_truncated_section(block, section_maximum_words)
                    for section, block in generated_sections.items()
                }
                generated_sections = {
                    section: block
                    for section, block in salvaged_sections.items()
                    if block
                }
                batch_evidence["provider_finish_reason"] = completion_metadata.get(
                    "finish_reason"
                )
                batch_evidence["truncated_output_salvaged"] = bool(
                    generated_sections
                )
                if generated_sections:
                    logger.warning(
                        "Generation batch %d/%d reached its %d-token output limit; "
                        "preserved complete content at a safe boundary",
                        batch_number,
                        len(batches),
                        batch_max_tokens,
                    )
            hard_section_maximum = section_budget_source.startswith(
                ("template total-word limit", "template page limit")
            )
            if hard_section_maximum:
                bounded_sections = {}
                for section, block in generated_sections.items():
                    if _section_word_count(block) <= section_maximum_words:
                        bounded_sections[section] = block
                        continue
                    bounded = _salvage_truncated_section(
                        block, section_maximum_words
                    )
                    if bounded:
                        bounded_sections[section] = bounded
                        logger.warning(
                            "Trimmed section %r to the client-derived maximum "
                            "of %d words",
                            section,
                            section_maximum_words,
                        )
                generated_sections = bounded_sections
            if not generated_sections:
                raise ValueError(
                    "the model did not return complete substantive content for the "
                    "assigned template section"
                )
            # Keep only the sections assigned to this request. This prevents an
            # outline continuation from leaking into the preceding card/draft.
            batch_draft = "\n\n".join(
                generated_sections[section]
                for section in sections
                if generated_sections.get(section, "").strip()
            )
            batch_evidence["draft"] = batch_draft
            replacement_sections.update(generated_sections)
            mark_batch_completed(
                run_id,
                batch_number,
                {
                    section: _section_body(generated_sections.get(section, ""))
                    for section in sections
                },
            )
            logger.info(
                "Generation attempt %d completed batch %d/%d (%s)",
                attempt_number, batch_number, len(batches), section_names,
            )
        except Exception as e:
            error_msg = (
                f"Generation batch {batch_number}/{len(batches)} failed "
                f"for sections {sections}: {e}"
            )
            logger.error(
                "Generation attempt %d failed in batch %d/%d for workspace %r: %s",
                attempt_number, batch_number, len(batches), workspace_slug, e,
                exc_info=True,
            )
            finish_generation(run_id, failed=True)
            return {
                "draft_proposal": "",
                "generation_evidence": generation_evidence,
                "generation_attempts": attempt_number,
                "errors": [error_msg],
            }

    # Assemble through the template order rather than relying on call order.
    draft = _merge_section_drafts(
        previous_draft if repair_mode else "",
        all_sections,
        replacement_sections,
    )
    draft = _remove_generation_instruction_leaks(_repair_mojibake(draft))
    generation_evidence["section_batches"] = _rebuild_section_evidence(
        all_sections,
        draft,
        generation_evidence["section_batches"],
    )
    finish_generation(run_id)

    return {
        "draft_proposal": draft,
        "generation_evidence": generation_evidence,
        "generation_attempts": attempt_number,
    }
