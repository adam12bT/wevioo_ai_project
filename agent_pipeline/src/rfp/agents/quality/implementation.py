"""
Quality Agent Implementation
--------------
Runs after Security — but only if security passed (see the guard below;
the graph itself already routes a failed security check straight to END,
so this is a defensive double-check, not the primary gate).

Checks the draft's QUALITY, not its safety: source groundedness, coherence,
template compliance, length, tone, and refusal detection. The evidence review
uses the exact RAG/research context preserved by the Generation agent. Unlike
the Security agent, it returns a verdict and report only. Retry and terminal
status policy belongs exclusively to the orchestrator.

When explicitly enabled, optionally uses LLM Guard's:
  - `Toxicity`      -> tone/appropriateness scoring
  - `NoRefusal`      -> catches the generation model refusing / punting
                        instead of writing the section (a common failure
                        mode for generation agents)
plus the pre-existing template-compliance and word-count checks.

(PII / secrets / malicious-URL scanning moved to agents/security_agent.py
— see that module's docstring for why the split.)

LLM Guard is disabled by default for lightweight deployments. Groundedness,
coherence, template compliance, section order, and word-count checks remain
active independently of it.
"""

import json
import logging
import os
import re

from json_repair import loads as repair_json_loads

from rfp.prompts import QUALITY_GROUNDING_PROMPT_TEMPLATE
from rfp.default_template import resolve_response_template
from providers import get_provider

logger = logging.getLogger(__name__)


def _repair_text_for_matching(value: str) -> str:
    """Best-effort normalization for UTF-8 text decoded as Latin-1/CP1252."""
    repaired = str(value or "")
    markers = ("Ã", "Â", "â€", "ï¿½")
    for _ in range(2):
        current_score = sum(repaired.count(marker) for marker in markers)
        candidates = []
        for codec in ("cp1252", "latin-1"):
            try:
                candidate = repaired.encode(codec).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            candidates.append(
                (sum(candidate.count(marker) for marker in markers), candidate)
            )
        if not candidates:
            break
        score, candidate = min(candidates, key=lambda item: item[0])
        if score >= current_score:
            break
        repaired = candidate
    return repaired

# A non-empty draft is the only universal length rule. Section count and order
# come from the uploaded template or the canonical fallback template.
MIN_WORD_COUNT = 1
MIN_SECTION_BODY_WORDS = max(
    1, int(os.environ.get("QUALITY_MIN_SECTION_BODY_WORDS", "12"))
)
_EVIDENCE_PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:[^\]]*(?:TO BE CONFIRMED|CONFIRMER|TEAM PROFILES TO BE COMPLETED)[^\]]*)\]",
    flags=re.IGNORECASE,
)
MIN_GROUNDEDNESS_SCORE = float(os.environ.get("QUALITY_MIN_GROUNDEDNESS", "0.75"))
MIN_COHERENCE_SCORE = float(os.environ.get("QUALITY_MIN_COHERENCE", "0.75"))
QUALITY_EVIDENCE_MAX_CHARS = min(
    6000,
    max(3000, int(os.environ.get("QUALITY_EVIDENCE_MAX_CHARS", "6000"))),
)
QUALITY_DRAFT_MAX_CHARS = min(
    6000,
    max(3000, int(os.environ.get("QUALITY_DRAFT_MAX_CHARS", "6000"))),
)
QUALITY_MAX_TOKENS = min(
    700,
    max(512, int(os.environ.get("QUALITY_MAX_TOKENS", "700"))),
)
QUALITY_LLM_MODEL = os.environ.get("QUALITY_LLM_MODEL", "").strip() or None
LLM_GUARD_FAIL_CLOSED = os.environ.get(
    "LLM_GUARD_FAIL_CLOSED", "true"
).strip().lower() not in {"0", "false", "no", "off"}
LLM_GUARD_ENABLED = os.environ.get(
    "LLM_GUARD_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}

if LLM_GUARD_ENABLED:
    try:
        from llm_guard.output_scanners import NoRefusal, Toxicity

        _LLM_GUARD_AVAILABLE = True
    except ImportError:  # pragma: no cover - depends on deployment extras
        _LLM_GUARD_AVAILABLE = False
        logger.warning(
            "LLM Guard was enabled but is unavailable; toxicity/refusal "
            "model scanning will be skipped."
        )
else:
    _LLM_GUARD_AVAILABLE = False
    logger.info("LLM Guard is disabled; toxicity/refusal model scanning is skipped.")

_scanners_cache = None


def llm_guard_available() -> bool:
    return _LLM_GUARD_AVAILABLE


def _get_scanners():
    global _scanners_cache
    if _scanners_cache is None:
        _scanners_cache = {
            "toxicity": Toxicity(threshold=0.7),
            "no_refusal": NoRefusal(threshold=0.5),
        }
    return _scanners_cache


def _run_llm_guard(draft: str) -> dict:
    scanners = _get_scanners()
    findings = {}
    for name, scanner in scanners.items():
        try:
            _, is_valid, risk_score = scanner.scan(prompt="", output=draft)
        except Exception as exc:
            logger.exception("LLM Guard scanner %r failed", name)
            if LLM_GUARD_FAIL_CLOSED:
                findings[f"{name}_scanner_error"] = str(exc)[:300]
            continue
        if not is_valid:
            findings[name] = round(risk_score, 3)
    return findings


def _template_sections(state: dict) -> tuple[list[str], list[str]]:
    requirements = state.get("requirements") or {}
    template = resolve_response_template(requirements)

    raw_required = template.get("required_sections") or []
    raw_ordered = template.get("section_order") or []
    if not isinstance(raw_required, list):
        raw_required = []
    if not isinstance(raw_ordered, list):
        raw_ordered = []

    required = [
        str(section).strip()
        for section in raw_required
        if str(section).strip()
    ]
    ordered = [
        str(section).strip()
        for section in raw_ordered
        if str(section).strip()
    ]
    return required, ordered or required


def _canonical_section_title(value: str) -> str:
    """Normalize client numbering and Markdown decoration for comparison."""
    title = str(value).strip().casefold()
    title = re.sub(r"^\s{0,3}#{1,6}\s*", "", title)
    title = re.sub(r"[*_`]", "", title)
    title = re.sub(r"^\s*(?:section\s+)?\d+(?:\.\d+)*[.)\-:]?\s*", "", title)
    return re.sub(r"\s+", " ", title).strip(" :-–—")


def _section_positions(draft: str, sections: list[str]) -> list[int]:
    normalized_lines = [_canonical_section_title(line) for line in draft.splitlines()]
    positions = []
    for section in sections:
        target = _canonical_section_title(section)
        position = next(
            (
                index
                for index, line in enumerate(normalized_lines)
                if line == target or line.startswith(f"{target}:")
            ),
            -1,
        )
        positions.append(position)
    return positions


def _check_template_compliance(draft: str, required_sections: list[str]) -> list[str]:
    positions = _section_positions(draft, required_sections)
    return [section for section, position in zip(required_sections, positions) if position < 0]


def _check_section_order(draft: str, section_order: list[str]) -> list[str]:
    positions = _section_positions(draft, section_order)
    present_positions = [position for position in positions if position >= 0]
    if len(present_positions) < 2 or present_positions == sorted(present_positions):
        return []
    return section_order


def _duplicate_sections(draft: str, sections: list[str]) -> list[str]:
    """Return template sections whose Markdown heading occurs more than once."""
    heading_titles = [
        _canonical_section_title(line)
        for line in draft.splitlines()
        if re.match(r"^\s{0,3}#{1,2}\s+", line)
    ]
    return [
        section
        for section in sections
        if heading_titles.count(_canonical_section_title(section)) > 1
    ]


def _section_blocks(draft: str, sections: list[str]) -> dict[str, str]:
    """Split a proposal into template sections for localized repair decisions."""
    lines = draft.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not re.match(r"^\s{0,3}#{1,2}\s+", line):
            continue
        normalized = _canonical_section_title(line)
        matched = next(
            (
                section
                for section in sections
                if normalized == _canonical_section_title(section)
            ),
            None,
        )
        if matched and matched not in {section for _, section in starts}:
            starts.append((index, matched))

    blocks = {}
    for position, (start, section) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        blocks[section] = "\n".join(lines[start:end]).strip()
    return blocks


def _section_body(block: str) -> str:
    lines = block.strip().splitlines()
    if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _insubstantial_sections(draft: str, sections: list[str]) -> list[str]:
    """Detect present headings that contain no meaningful proposal body."""
    blocks = _section_blocks(draft, sections)
    failed = []
    for section in sections:
        block = blocks.get(section, "")
        body = _section_body(block)
        body_words = len(re.findall(r"\b[\w'-]+\b", body, flags=re.UNICODE))
        disclosed_gap = bool(_EVIDENCE_PLACEHOLDER_PATTERN.search(body))
        if block and body_words < MIN_SECTION_BODY_WORDS and not disclosed_gap:
            failed.append(section)
    return failed


def _evidence_gap_warnings(draft: str, sections: list[str]) -> list[dict]:
    """Return non-blocking warnings for intentionally disclosed missing evidence."""
    warnings = []
    for section, block in _section_blocks(draft, sections).items():
        body = _section_body(block)
        placeholders = _EVIDENCE_PLACEHOLDER_PATTERN.findall(body)
        if placeholders:
            company_gap = bool(re.search(r"(?i)\|\s*Company evidence\s*\|", body))
            tender_gap = bool(
                re.search(r"(?i)\|\s*Tender-backed commitment\s*\|", body)
            )
            missing = []
            if company_gap:
                missing.append("company evidence")
            if tender_gap:
                missing.append("tender-backed commitment evidence")
            missing_label = " and ".join(missing) or "supporting evidence"
            warnings.append(
                {
                    "section": section,
                    "placeholder_count": len(placeholders),
                    "message": (
                        f"Missing {missing_label}. Upload or verify the required source "
                        "documents, then regenerate this section."
                    ),
                }
            )
    return warnings


def _word_count(value: str) -> int:
    return len(
        re.findall(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", str(value), flags=re.UNICODE)
    )


def _incomplete_markdown_table_sections(
    draft: str, sections: list[str]
) -> list[str]:
    """Detect interrupted Markdown tables without making domain assumptions."""
    failed = []
    for section, block in _section_blocks(draft, sections).items():
        groups: list[list[str]] = []
        current: list[str] = []
        for line in _section_body(block).splitlines() + [""]:
            if line.strip().startswith("|"):
                current.append(line.strip())
            elif current:
                groups.append(current)
                current = []

        for rows in groups:
            if len(rows) < 2:
                continue
            expected_pipes = rows[0].count("|")
            malformed = any(
                not row.endswith("|") or row.count("|") != expected_pipes
                for row in rows[1:]
            )
            if malformed:
                failed.append(section)
                break
    return failed


def _overlong_sections(state: dict, draft: str, sections: list[str]) -> list[dict]:
    """Enforce the word range calculated dynamically during generation."""
    evidence = state.get("generation_evidence") or {}
    maximum_by_section: dict[str, int] = {}
    for batch in evidence.get("section_batches") or []:
        if not isinstance(batch, dict):
            continue
        target = batch.get("target_word_range") or {}
        source = str(target.get("source") or "").casefold()
        hard_maximum = target.get("hard_maximum")
        if hard_maximum is None:
            hard_maximum = source.startswith(
                ("template total-word limit", "template page limit")
            )
        if not hard_maximum:
            # A generated writing target is guidance, not a client compliance
            # rule. Only limits explicitly extracted from the template may
            # fail a proposal section.
            continue
        try:
            maximum = int(target.get("maximum"))
        except (TypeError, ValueError):
            continue
        for section in batch.get("sections") or []:
            maximum_by_section[str(section)] = maximum

    issues = []
    for section, block in _section_blocks(draft, sections).items():
        maximum = maximum_by_section.get(section)
        count = _word_count(_section_body(block))
        if maximum and count > maximum:
            issues.append(
                {"section": section, "word_count": count, "maximum": maximum}
            )
    return issues


def _evidence_text(
    state: dict, *, company_only: bool = False, tender_only: bool = False
) -> str:
    evidence = state.get("generation_evidence") or {}
    if company_only and tender_only:
        raise ValueError("company_only and tender_only cannot both be true")
    if company_only:
        fields = ("project_references", "cv_excerpts", "past_proposals")
    elif tender_only:
        fields = ("requirements", "tender_excerpts", "response_template_excerpts")
    else:
        fields = (
            "requirements",
            "tender_excerpts",
            "response_template_excerpts",
            "project_references",
            "cv_excerpts",
            "past_proposals",
        )
    values = [evidence.get(field, "") for field in fields]
    for batch in evidence.get("section_batches") or []:
        if isinstance(batch, dict):
            values.extend(batch.get(field, "") for field in fields)
    return "\n".join(str(value) for value in values if str(value).strip())


_MONEY_PATTERN = re.compile(
    r"(?i)(?:\b(?:TND|USD|EUR|GBP|DT)[ \t\u00a0\u202f]*"
    r"[0-9][0-9 \t\u00a0\u202f.,]*"
    r"|\b[0-9][0-9 \t\u00a0\u202f.,]*"
    r"[ \t\u00a0\u202f]*(?:TND|USD|EUR|GBP|dinars?)\b)"
)


def _normalized_amount(value: str) -> str:
    return re.sub(r"[\s,]", "", value).casefold().rstrip(".")


_NUMERIC_COMMITMENT_PATTERN = re.compile(
    r"(?i)\b\d+(?:[.,]\d+)?"
    r"[ \t\u00a0\u202f\u2010\u2011\u2012\u2013\u2014\u2015-]*"
    r"(?:%|pages?|years?|months?|weeks?|days?|hours?|minutes?|records?|"
    r"letters?|personnel|developers?|engineers?|users?|defects?|findings?|"
    r"seconds?|points?)(?=$|\W)"
)
_LEADING_TIME_RANGE_PATTERN = re.compile(
    r"(?i)\b(?:weeks?|months?|days?|years?)\s*\d+"
    r"(?:\s*[-‐‑‒–—―]\s*\d+)?\b"
)
_OTHER_NUMERIC_COMMITMENT_PATTERN = re.compile(
    r"(?i)(?:[$€£]\s*\d[\d\s.,]*|\b\d[\d\s.,]*\s*(?:TND|USD|EUR|GBP)\b|"
    r"\b(?:TND|USD|EUR|GBP)\b|\b24\s*/\s*7\b)"
)


def _normalized_commitment(value: str) -> str:
    value = value.casefold().translate(
        str.maketrans({"‐": " ", "‑": " ", "‒": " ", "–": " ", "—": " ", "―": " "})
    )
    value = re.sub(
        r"\b(pages?|years?|months?|weeks?|days?|hours?|minutes?|records?|"
        r"letters?|developers?|engineers?|users?|defects?|findings?|seconds?|points?)\b",
        lambda match: match.group(1).rstrip("s"),
        value,
    )
    return re.sub(r"[\s,]", "", value).rstrip(".")


def _unsupported_numeric_commitments(
    state: dict, draft: str, sections: list[str]
) -> list[dict]:
    """Reject measurable commitments that are absent from tender/template evidence."""
    tender_text = _evidence_text(state, tender_only=True)
    patterns = (
        _NUMERIC_COMMITMENT_PATTERN,
        _LEADING_TIME_RANGE_PATTERN,
        _OTHER_NUMERIC_COMMITMENT_PATTERN,
    )
    supported = {
        _normalized_commitment(match.group(0))
        for pattern in patterns
        for match in pattern.finditer(tender_text)
    }
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for section, block in _section_blocks(draft, sections).items():
        in_gap_table = False
        for line in _section_body(block).splitlines():
            stripped = line.strip()
            if re.match(
                r"(?i)^###\s+(?:Evidence gaps|Missing evidence|Lacunes de preuve|"
                r"Éléments à confirmer)\s*$",
                stripped,
            ):
                in_gap_table = True
                continue
            if in_gap_table:
                if stripped.startswith("### "):
                    in_gap_table = False
                else:
                    continue
            if not stripped or stripped.startswith("#"):
                continue
            for pattern in patterns:
                for match in pattern.finditer(stripped):
                    value = match.group(0).strip()
                    normalized = _normalized_commitment(value)
                    key = (section, normalized)
                    if normalized not in supported and key not in seen:
                        issues.append(
                            {
                                "section": section,
                                "value": value,
                                "claim": re.sub(r"\s+", " ", stripped)[:300],
                            }
                        )
                        seen.add(key)
    return issues


def _unsupported_financial_figures(
    state: dict, draft: str, sections: list[str]
) -> list[dict]:
    evidence_amounts = {
        _normalized_amount(match.group(0))
        for match in _MONEY_PATTERN.finditer(_evidence_text(state))
    }
    issues = []
    seen = set()
    for section, block in _section_blocks(draft, sections).items():
        for match in _MONEY_PATTERN.finditer(block):
            amount = match.group(0).strip()
            normalized = _normalized_amount(amount)
            key = (section, normalized)
            if normalized not in evidence_amounts and key not in seen:
                issues.append({"section": section, "amount": amount})
                seen.add(key)
    return issues


def _unsupported_annex_and_test_claims(
    state: dict, draft: str, sections: list[str]
) -> list[dict]:
    """Find high-risk bidder-evidence claims absent from company knowledge."""
    company_evidence = re.sub(
        r"\s+", " ", _evidence_text(state, company_only=True).casefold()
    )
    claim_patterns = (
        r"security testing was performed[^.]*\.",
        r"(?:penetration|pen)[ -]?test[^.]{0,120}(?:confirmed|showed|found)[^.]*\.",
        r"(?:scan|test) results?[^.]{0,100}(?:showed|confirmed|demonstrated)[^.]*\.",
        r"zero (?:critical|high)[^.]{0,100}(?:findings|vulnerabilities)[^.]*\.",
    )
    issues = []
    for section, block in _section_blocks(draft, sections).items():
        for pattern in claim_patterns:
            for match in re.finditer(pattern, block, flags=re.IGNORECASE):
                claim = re.sub(r"\s+", " ", match.group(0)).strip()
                normalized_claim = claim.casefold()
                line_start = block.rfind("\n", 0, match.start()) + 1
                line_end = block.find("\n", match.end())
                if line_end < 0:
                    line_end = len(block)
                same_line_context = re.sub(
                    r"\s+", " ", block[line_start:line_end]
                ).casefold()
                nearby_context = re.sub(
                    r"\s+",
                    " ",
                    block[max(0, match.start() - 220) : match.end() + 80],
                ).casefold()
                if any(
                    marker in normalized_claim
                    for marker in (
                        "[à confirmer",
                        "[to be confirmed",
                        "scheduled",
                        "planned",
                        "proposed",
                        "will be performed",
                        "will be conducted",
                    )
                ) or any(
                    marker in nearby_context
                    for marker in (
                        "acceptance criteria",
                        "acceptance criterion",
                        "acceptance target",
                        "planned test",
                        "target:",
                    )
                ) or any(
                    marker in same_line_context
                    for marker in (
                        "acceptance criteria",
                        "acceptance criterion",
                        "acceptance target",
                        "planned penetration test",
                        "planned test",
                        "planned audit",
                        "planned scan",
                        "target:",
                        "target of",
                        "target is",
                    )
                ):
                    # A transparent placeholder or future activity is not a
                    # claim that an artefact/test already exists or passed.
                    continue
                if claim.casefold() not in company_evidence:
                    issues.append({"section": section, "claim": claim[:300]})

        for line in block.splitlines():
            if not line.strip().startswith("|"):
                continue
            filenames = re.findall(
                r"[A-Za-z0-9_.-]+\.(?:pdf|docx?|xlsx?|pptx?|zip)\b",
                line,
                flags=re.IGNORECASE,
            )
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            marked_included = any(cell.casefold() in {"yes", "included", "oui"} for cell in cells)
            for filename in filenames:
                if marked_included and filename.casefold() not in company_evidence:
                    issues.append(
                        {
                            "section": section,
                            "claim": f"Artefact marked included without evidence: {filename}",
                        }
                    )
    return issues


def _unsupported_bidder_identity_claims(
    state: dict, draft: str, sections: list[str]
) -> list[dict]:
    """Reject bidder structures that are absent from company evidence."""
    company_evidence = re.sub(
        r"\s+", " ", _evidence_text(state, company_only=True).casefold()
    )
    if "consortium" in company_evidence:
        return []

    issues = []
    for section, block in _section_blocks(draft, sections).items():
        for match in re.finditer(
            r"\b(?:our|the) consortium\b[^.]*\.",
            block,
            flags=re.IGNORECASE,
        ):
            issues.append(
                {
                    "section": section,
                    "claim": re.sub(r"\s+", " ", match.group(0)).strip()[:300],
                }
            )
    return issues


def _conflicting_cross_section_values(draft: str, sections: list[str]) -> list[dict]:
    """Detect conflicting values for a small set of unambiguous project metrics."""
    patterns = {
        "RTO": r"\bRTO\b[^0-9\n]{0,20}([0-9]+(?:[.,][0-9]+)?)\s*(minutes?|mins?|hours?|hrs?|h)\b",
        "RPO": r"\bRPO\b[^0-9\n]{0,20}([0-9]+(?:[.,][0-9]+)?)\s*(minutes?|mins?|hours?|hrs?|h)\b",
        "warranty": r"\b(?:warranty|garantie)\b[^0-9\n]{0,30}([0-9]+)\s*(months?|mois|years?|ans)\b",
        "audit retention": (
            r"\b(?:audit|log|journal)[^\n.]{0,80}?"
            r"(?:retention|retained|conservation)[^0-9\n]{0,20}"
            r"([0-9]+)\s*(months?|mois|years?|ans)\b"
        ),
    }
    blocks = _section_blocks(draft, sections)
    conflicts = []
    for metric, pattern in patterns.items():
        occurrences: dict[str, set[str]] = {}
        for section, block in blocks.items():
            for match in re.finditer(pattern, block, flags=re.IGNORECASE):
                number = float(match.group(1).replace(",", "."))
                unit = match.group(2).casefold()
                if metric in {"RTO", "RPO"}:
                    normalized = number * 60 if unit.startswith(("h", "hour")) else number
                    value = f"{normalized:g} minutes"
                else:
                    normalized = number * 12 if unit.startswith(("y", "year", "ans")) else number
                    value = f"{normalized:g} months"
                occurrences.setdefault(value, set()).add(section)
        if len(occurrences) > 1:
            conflicts.append(
                {
                    "metric": metric,
                    "values": [
                        {"value": value, "sections": sorted(found_sections)}
                        for value, found_sections in occurrences.items()
                    ],
                }
            )
    return conflicts


def _deterministic_proposal_checks(
    state: dict, draft: str, sections: list[str]
) -> tuple[dict, list[str]]:
    incomplete_tables = _incomplete_markdown_table_sections(draft, sections)
    overlong = _overlong_sections(state, draft, sections)
    numeric_commitments = _unsupported_numeric_commitments(state, draft, sections)
    financial = _unsupported_financial_figures(state, draft, sections)
    evidence_claims = _unsupported_annex_and_test_claims(state, draft, sections)
    identity_claims = _unsupported_bidder_identity_claims(state, draft, sections)
    conflicts = _conflicting_cross_section_values(draft, sections)
    findings = {
        "incomplete_markdown_tables": incomplete_tables,
        "overlong_sections": overlong,
        "unsupported_numeric_commitments": numeric_commitments,
        "unsupported_financial_figures": financial,
        "unsupported_annex_or_test_claims": evidence_claims,
        "unsupported_bidder_identity_claims": identity_claims,
        "conflicting_cross_section_values": conflicts,
    }
    findings = {key: value for key, value in findings.items() if value}

    failed = set(incomplete_tables)
    failed.update(item["section"] for item in overlong)
    failed.update(item["section"] for item in numeric_commitments)
    failed.update(item["section"] for item in financial)
    failed.update(item["section"] for item in evidence_claims)
    failed.update(item["section"] for item in identity_claims)
    for conflict in conflicts:
        for value in conflict.get("values") or []:
            failed.update(value.get("sections") or [])
    return findings, [section for section in sections if section in failed]


def _claim_text(finding) -> str:
    if isinstance(finding, dict):
        return str(finding.get("claim") or finding.get("text") or "").strip()
    return str(finding or "").strip()


def _reconcile_future_plan_findings(review: dict) -> dict:
    """Remove judge findings that demand historical proof for future project plans."""
    retained = []
    removed = []
    future_pattern = re.compile(
        r"(?i)\b(?:will|shall|would|is proposed|are proposed|to be provided|"
        r"to be established|will be|shall be|planned|acceptance target)\b"
    )
    existing_fact_pattern = re.compile(
        r"(?i)\b(?:has|have|holds?|possess(?:es)?|maintains?|currently|existing|"
        r"verified|proven|previously|prior experience|track record|already|"
        r"have been compiled|has been compiled|are included|is included)\b"
    )
    project_plan_pattern = re.compile(
        r"(?i)\b(?:delivery model|delivery approach|implementation plan|"
        r"implementation approach|project lifecycle|phase[- ]gated lifecycle|"
        r"governance structure|work plan|delivery phases?)\b"
    )
    historical_proof_reason_pattern = re.compile(
        r"(?i)\b(?:previously|historical|past project|prior project|already used|"
        r"previously executed|previously delivered|past proposal|project reference)\b"
    )
    for finding in review.get("unsupported_claims") or []:
        claim = _claim_text(finding)
        reason = (
            str(finding.get("reason") or "")
            if isinstance(finding, dict)
            else ""
        )
        is_project_plan = bool(project_plan_pattern.search(claim)) and bool(
            historical_proof_reason_pattern.search(reason)
        )
        if (
            future_pattern.search(claim) or is_project_plan
        ) and not existing_fact_pattern.search(claim):
            removed.append(finding)
        else:
            retained.append(finding)
    if not removed:
        return review

    reconciled = dict(review)
    reconciled["unsupported_claims"] = retained
    reconciled["notes"] = list(reconciled.get("notes") or []) + [
        f"Ignored {len(removed)} unsupported-claim finding(s) that described "
        "future project plans rather than existing bidder facts."
    ]
    reconciled["future_plan_findings_ignored"] = removed
    if not retained and not reconciled.get("contradictions"):
        # Removing unsupported-claim false positives repairs groundedness only.
        # Independent coherence issues keep their own score and are not hidden.
        reconciled["groundedness_score"] = max(
            float(reconciled.get("groundedness_score") or 0.0),
            MIN_GROUNDEDNESS_SCORE,
        )
    return reconciled


def _reconcile_tender_requirement_findings(state: dict, review: dict) -> dict:
    """Do not demand company history for facts explicitly stated by the buyer."""
    tender_words = re.findall(
        r"[a-z0-9]+",
        _repair_text_for_matching(_evidence_text(state, tender_only=True)).casefold(),
    )
    tender_text = " ".join(tender_words)
    tender_terms = set(tender_words)
    company_proof_reason = re.compile(
        r"(?i)(?:company evidence|project reference|cv excerpt|bidder(?:'s)?\s+"
        r"(?:experience|history|past performance)|has performed|has delivered|"
        r"previously|past project|comparable project)"
    )
    ignored = []
    retained = []
    for finding in review.get("unsupported_claims") or []:
        claim = _claim_text(finding)
        reason = (
            str(finding.get("reason") or "")
            if isinstance(finding, dict)
            else ""
        )
        claim_words = re.findall(
            r"[a-z0-9]+", _repair_text_for_matching(claim).casefold()
        )
        meaningful = {term for term in claim_words if len(term) >= 3 or term.isdigit()}
        normalized_claim = " ".join(claim_words)
        overlap = meaningful & tender_terms
        supported_by_tender = bool(normalized_claim and normalized_claim in tender_text)
        if meaningful and len(overlap) / len(meaningful) >= 0.8:
            supported_by_tender = True
        if supported_by_tender and company_proof_reason.search(reason):
            ignored.append(finding)
        else:
            retained.append(finding)

    if not ignored:
        return review
    reconciled = dict(review)
    reconciled["unsupported_claims"] = retained
    reconciled["notes"] = list(reconciled.get("notes") or []) + [
        f"Ignored {len(ignored)} unsupported-claim finding(s) that repeated "
        "buyer requirements and incorrectly demanded bidder-history evidence."
    ]
    reconciled["tender_requirement_findings_ignored"] = ignored
    if not retained and not reconciled.get("contradictions"):
        reconciled["groundedness_score"] = max(
            float(reconciled.get("groundedness_score") or 0.0),
            MIN_GROUNDEDNESS_SCORE,
        )
    return reconciled


def _reconcile_disclosed_evidence_gaps(review: dict) -> dict:
    """Treat explicit missing-data disclosures as warnings, not hallucinations."""
    disclosed_claim_pattern = re.compile(
        r"(?i)(?:\[[^\]]*(?:to be confirmed|confirmer|team profiles to be completed)|"
        r"(?:evidence|cv|certificat(?:e|ion)|reference|pricing|attachment|appendix|annex)"
        r"[^.]{0,100}(?:will be provided|must be provided|is missing|is unavailable|"
        r"was not found|not found|pending))"
    )
    ignored_unsupported = []
    retained_unsupported = []
    for finding in review.get("unsupported_claims") or []:
        claim = _claim_text(finding)
        if disclosed_claim_pattern.search(claim):
            ignored_unsupported.append(finding)
        else:
            retained_unsupported.append(finding)

    gap_issue_pattern = re.compile(
        r"(?i)(?:placeholder|to be confirmed|supporting evidence not found|"
        r"evidence (?:is |are )?(?:missing|unavailable|pending)|"
        r"missing supporting documents|future documentation|no actual supporting)"
    )
    ignored_coherence = []
    retained_coherence = []
    for issue in review.get("coherence_issues") or []:
        if gap_issue_pattern.search(str(issue)):
            ignored_coherence.append(issue)
        else:
            retained_coherence.append(issue)

    if not ignored_unsupported and not ignored_coherence:
        return review

    reconciled = dict(review)
    reconciled["unsupported_claims"] = retained_unsupported
    reconciled["coherence_issues"] = retained_coherence
    reconciled["disclosed_evidence_gap_findings_ignored"] = {
        "unsupported_claims": ignored_unsupported,
        "coherence_issues": ignored_coherence,
    }
    reconciled["notes"] = list(reconciled.get("notes") or []) + [
        "Disclosed TO BE CONFIRMED evidence gaps were converted to non-blocking warnings."
    ]
    if not retained_unsupported and not reconciled.get("contradictions"):
        reconciled["groundedness_score"] = max(
            float(reconciled.get("groundedness_score") or 0.0),
            MIN_GROUNDEDNESS_SCORE,
        )
    if not retained_coherence and not reconciled.get("contradictions"):
        reconciled["coherence_score"] = max(
            float(reconciled.get("coherence_score") or 0.0),
            MIN_COHERENCE_SCORE,
        )
    return reconciled



def _repair_mojibake(value: str) -> str:
    """Best-effort repair of common mojibake sequences in proposal text.

    Handles the most frequent Windows-1252 bytes misread as Latin-1 that
    appear in copy-pasted tender documents and CV excerpts:
      â€™ → '   (right single quotation mark)
      â€œ → "   (left double quotation mark)
      â€  → "   (right double quotation mark)
      â€" → –   (en dash)
      â€" → —   (em dash)
      Ã©   → é   (e with acute)
      Ã¨   → è   (e with grave)
      Ã    → à   (a with grave)
      Ã®   → î   (i with circumflex)
      Ã´   → ô   (o with circumflex)
      Ã§   → ç   (c with cedilla)
    """
    _MOJIBAKE_MAP = [
        ("â€™", "\u2019"),   # right single quotation mark
        ("â€˜", "\u2018"),   # left single quotation mark
        ("â€œ", "\u201c"),   # left double quotation mark
        ("â€\x9d", "\u201d"), # right double quotation mark
        ("â€“", "\u2013"),   # en dash
        ("â€”", "\u2014"),   # em dash
        ("â€¦", "\u2026"),   # horizontal ellipsis
        ("Ã©", "é"),
        ("Ã¨", "è"),
        ("Ãª", "ê"),
        ("Ã ", "à"),
        ("Ã¢", "â"),
        ("Ã®", "î"),
        ("Ã´", "ô"),
        ("Ã»", "û"),
        ("Ã§", "ç"),
        ("Ã¹", "ù"),
        ("Ã«", "ë"),
        ("Ã¯", "ï"),
        ("Ã¼", "ü"),
        ("Ã±", "ñ"),
    ]
    result = str(value)
    for bad, good in _MOJIBAKE_MAP:
        if bad in result:
            result = result.replace(bad, good)
    # Attempt ftfy-style round-trip for anything the table above missed.
    try:
        round_tripped = result.encode("latin-1").decode("utf-8")
        result = round_tripped
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return result



def _sections_containing_claim(
    draft: str,
    sections: list[str],
    finding,
) -> list[str]:
    def normalized_words(value: str) -> list[str]:
        repaired = _repair_text_for_matching(str(value or ""))
        return re.findall(r"[a-z0-9]+", repaired.casefold())

    finding_text = _claim_text(finding)
    claim_words = normalized_words(finding_text)
    if len(claim_words) < 3:
        return []
    claim = " ".join(claim_words)
    meaningful_claim_terms = {
        term for term in claim_words if len(term) >= 4
    }
    blocks = _section_blocks(draft, sections)
    matches = []
    quoted_phrases = [
        " ".join(normalized_words(phrase))
        for phrase in re.findall(r"[\"\u201c\u201d']([^\"\u201c\u201d']{4,})[\"\u201c\u201d']", finding_text)
    ]
    for section, block in blocks.items():
        block_words = normalized_words(block)
        normalized_block = " ".join(block_words)
        if claim in normalized_block:
            matches.append(section)
            continue
        if any(phrase and phrase in normalized_block for phrase in quoted_phrases):
            matches.append(section)
            continue
        block_terms = set(block_words)
        overlap = meaningful_claim_terms & block_terms
        if meaningful_claim_terms and (
            len(overlap) >= 5
            and len(overlap) / len(meaningful_claim_terms) >= 0.72
        ):
            matches.append(section)
    return matches


def _reconcile_evaluator_only_claims(draft: str, sections: list[str], review: dict) -> dict:
    """Discard unsupported claims that the evaluator invented while judging.

    The quality model must judge proposal text, not synthesize a stronger claim
    (for example, a made-up staffing list) and then reject that synthesis. A
    concise paraphrase is retained when it can still be localized to a section.
    Meta-descriptions are accepted only when their quoted subject and asserted
    details are both visibly present.
    """
    meta_pattern = re.compile(
        r"(?i)^\s*(?:the|this)\s+proposal\s+(?:lists?|presents?|states?|"
        r"describes?|includes?|claims?|provides?)\b"
    )
    ignored = []
    retained = []
    normalized_draft = " ".join(
        re.findall(r"[a-z0-9]+", _repair_text_for_matching(draft).casefold())
    )

    for finding in review.get("unsupported_claims") or []:
        claim = _claim_text(finding)
        matches = _sections_containing_claim(draft, sections, finding)
        claim_normalized = " ".join(
            re.findall(r"[a-z0-9]+", _repair_text_for_matching(claim).casefold())
        )
        parenthetical = re.findall(r"\(([^)]{4,})\)", claim)
        listed_items = []
        for group in parenthetical:
            listed_items.extend(
                item.strip(" .")
                for item in re.split(r",|;|\band\b|\be\.g\.\s*", group, flags=re.I)
                if len(item.strip(" .")) >= 4
            )
        present_items = sum(
            1
            for item in listed_items
            if " ".join(re.findall(r"[a-z0-9]+", item.casefold())) in normalized_draft
        )
        invented_list = bool(listed_items) and present_items < max(1, len(listed_items) // 2)
        unsupported_meta = bool(meta_pattern.search(claim)) and (
            not matches or invented_list
        )
        absent_claim = not matches and claim_normalized not in normalized_draft
        if unsupported_meta or (absent_claim and invented_list):
            ignored.append(finding)
        else:
            retained.append(finding)

    if not ignored:
        return review
    reconciled = dict(review)
    reconciled["unsupported_claims"] = retained
    reconciled["evaluator_only_findings_ignored"] = ignored
    reconciled["notes"] = list(reconciled.get("notes") or []) + [
        f"Ignored {len(ignored)} unsupported-claim finding(s) whose alleged "
        "content was not present in the generated proposal."
    ]
    if not retained and not reconciled.get("contradictions"):
        reconciled["groundedness_score"] = max(
            float(reconciled.get("groundedness_score") or 0.0),
            MIN_GROUNDEDNESS_SCORE,
        )
    return reconciled


def _identify_failed_sections(
    *,
    draft: str,
    sections: list[str],
    missing_sections: list[str],
    out_of_order_sections: list[str],
    quality_findings: dict,
    grounding_review: dict,
    word_count: int,
    duplicate_sections: list[str] | None = None,
    incomplete_sections: list[str] | None = None,
    deterministic_failed_sections: list[str] | None = None,
) -> list[str]:
    """Map quality failures to the smallest safe set of template sections."""
    failed = (
        set(missing_sections)
        | set(out_of_order_sections)
        | set(duplicate_sections or [])
        | set(incomplete_sections or [])
        | set(deterministic_failed_sections or [])
    )
    unmapped_contradiction = False

    for field in ("unsupported_claims", "contradictions"):
        for finding in grounding_review.get(field, []) or []:
            matches = _sections_containing_claim(draft, sections, finding)
            failed.update(matches)
            if field == "contradictions" and not matches:
                unmapped_contradiction = True

    if word_count < MIN_WORD_COUNT:
        failed.update(sections)

    score_failed = (
        grounding_review.get("groundedness_score", 0.0) < MIN_GROUNDEDNESS_SCORE
        or grounding_review.get("coherence_score", 0.0) < MIN_COHERENCE_SCORE
    )
    if quality_findings or unmapped_contradiction or (score_failed and not failed):
        failed.update(sections)

    return [section for section in sections if section in failed]


def _score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _extract_review_json(text: str) -> dict:
    candidate = text.strip()
    if not candidate:
        raise ValueError("Grounding evaluator returned an empty response")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0:
            candidate = candidate[start : end + 1] if end > start else candidate[start:]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Quality evaluator returned malformed JSON; attempting local repair: %s",
            exc,
        )
        parsed = repair_json_loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Grounding evaluator returned JSON that is not an object")

    parsed["groundedness_score"] = _score(parsed.get("groundedness_score"))
    parsed["coherence_score"] = _score(parsed.get("coherence_score"))
    for field in ("unsupported_claims", "contradictions", "coherence_issues", "notes"):
        if not isinstance(parsed.get(field), list):
            parsed[field] = []
    return parsed


def _empty_review(*, error: str | None = None) -> dict:
    review = {
        "groundedness_score": 0.0,
        "coherence_score": 0.0,
        "unsupported_claims": [],
        "contradictions": [],
        "coherence_issues": [],
        "notes": [],
    }
    if error:
        review["evaluation_error"] = error
    return review


def _relevant_evidence_excerpt(source, draft: str, max_chars: int) -> str:
    """Select verbatim evidence blocks that overlap most with the draft."""
    text = str(source or "").strip()
    if not text or len(text) <= max_chars:
        return text

    draft_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", draft.casefold())
        if len(term) >= 4
    }
    # Numeric rules and named standards are easy to lose when a long evidence
    # block is clipped from its beginning. Preserve short windows around exact
    # anchors first so the judge sees the proof for page limits, percentages,
    # schedules, quantities, and standards actually present in the source.
    anchors = re.findall(
        r"(?i)\b(?:\d+(?:[.,]\d+)?\s*(?:%|pages?|years?|months?|weeks?|days?|"
        r"hours?|minutes?|records?|letters?|personnel|developers?)|"
        r"ISO\s*[0-9]{4,5}(?::[0-9]{4})?)(?=$|\W)",
        draft,
    )
    anchor_windows = []
    seen_windows = set()
    for anchor in anchors:
        flexible_anchor = r"\s*".join(
            re.escape(part) for part in re.split(r"\s+", anchor.strip()) if part
        )
        match = re.search(flexible_anchor, text, flags=re.IGNORECASE)
        if not match:
            continue
        start = max(0, match.start() - 90)
        end = min(len(text), match.end() + 130)
        window = text[start:end].strip()
        if window and window not in seen_windows:
            anchor_windows.append(window)
            seen_windows.add(window)

    blocks = [
        block.strip()
        for block in re.split(r"\n{2,}|(?=<document_metadata>)", text)
        if block.strip()
    ]
    ranked = sorted(
        enumerate(blocks),
        key=lambda item: (
            -len(
                draft_terms
                & {
                    term
                    for term in re.findall(r"[a-z0-9]+", item[1].casefold())
                    if len(term) >= 4
                }
            ),
            item[0],
        ),
    )

    selected = []
    used = 0
    for window in anchor_windows:
        remaining = max_chars - used
        if remaining <= 0:
            break
        excerpt = window if len(window) <= remaining else window[:remaining]
        selected.append(excerpt)
        used += len(excerpt) + 2
    for _, block in ranked:
        remaining = max_chars - used
        if remaining <= 0:
            break
        if block in selected:
            continue
        excerpt = block if len(block) <= remaining else block[:remaining]
        selected.append(excerpt)
        used += len(excerpt) + 2
    return "\n\n".join(selected)[:max_chars]


def _compact_excerpt(value: str, max_chars: int) -> str:
    """Keep the beginning and end of a section within its shared budget."""
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    marker = "\n[section excerpt truncated]\n"
    if max_chars <= len(marker):
        return text[:max_chars]
    remaining = max_chars - len(marker)
    head_chars = max(1, int(remaining * 0.7))
    tail_chars = max(0, remaining - head_chars)
    return f"{text[:head_chars]}{marker}{text[-tail_chars:] if tail_chars else ''}"


def _review_groups(state: dict, draft: str) -> list[tuple[dict, str]]:
    """Build one balanced, proposal-wide review request.

    Deterministic section checks run locally. The LLM judge receives one
    bounded excerpt from every generated section, avoiding one paid request per
    section while retaining whole-proposal coverage.
    """
    evidence = state.get("generation_evidence") or {}
    section_batches = evidence.get("section_batches") or []
    usable = [
        batch
        for batch in section_batches
        if isinstance(batch, dict) and str(batch.get("draft", "")).strip()
    ]
    if not usable:
        return [(evidence, draft[:QUALITY_DRAFT_MAX_CHARS])]

    section_count = len(usable)
    separators = max(0, section_count - 1) * 2
    per_section_draft = max(
        1, (QUALITY_DRAFT_MAX_CHARS - separators) // section_count
    )
    compact_drafts = []
    for batch in usable:
        section_draft = str(batch.get("draft", "")).strip()
        compact_drafts.append(
            _compact_excerpt(section_draft, per_section_draft)
        )
    group_draft = "\n\n".join(compact_drafts)[:QUALITY_DRAFT_MAX_CHARS]

    def exact_or_fallback(field: str):
        candidates = [
            str(batch.get(field) or "").strip()
            for batch in usable
            if str(batch.get(field, "")).strip()
        ]
        if candidates:
            # Combine section-specific fitted evidence rather than selecting a
            # single longest batch. De-duplication keeps repeated chunks cheap,
            # and the relevance compactor below chooses the blocks that best
            # support the proposal-wide draft.
            return "\n\n".join(dict.fromkeys(candidates))
        return evidence.get(field, "")

    # Keep the serialized evidence below the provider budget while giving every
    # section its own tender and company context. These are the exact fitted
    # excerpts captured by generation, not a fresh retrieval performed later.
    per_section_evidence = max(
        80,
        (QUALITY_EVIDENCE_MAX_CHARS - 3800) // section_count,
    )
    tender_budget = max(1, int(per_section_evidence * 0.45))
    company_budget = max(1, int(per_section_evidence * 0.45))
    template_budget = max(
        0,
        per_section_evidence - tender_budget - company_budget,
    )
    group_evidence = {
        "company_knowledge": {
            "project_references": _relevant_evidence_excerpt(
                exact_or_fallback("project_references"), group_draft, 800
            ),
            "cv_excerpts": _relevant_evidence_excerpt(
                exact_or_fallback("cv_excerpts"), group_draft, 800
            ),
            "past_proposals": _relevant_evidence_excerpt(
                exact_or_fallback("past_proposals"), group_draft, 60
            ),
            "provenance": (
                "Company CVs/references may support bidder claims; past "
                "proposals are style evidence unless explicit."
            ),
        },
        "requirements": _relevant_evidence_excerpt(
            exact_or_fallback("requirements"), group_draft, 250
        ),
        "section_evidence": [
            {
                "section": batch.get("sections", []),
                "retrieval_query": batch.get("retrieval_query", ""),
                "tender_chunk_ids": [
                    chunk.get("chunk_id")
                    for chunk in (batch.get("used_chunks") or [])
                    if isinstance(chunk, dict) and chunk.get("chunk_id")
                ],
                "tender": _relevant_evidence_excerpt(
                    batch.get("tender_excerpts", ""),
                    str(batch.get("draft", "")),
                    tender_budget,
                ),
                "company": {
                    "project_references": _relevant_evidence_excerpt(
                        batch.get("project_references", ""),
                        str(batch.get("draft", "")),
                        max(1, int(company_budget * 0.45)),
                    ),
                    "cv_excerpts": _relevant_evidence_excerpt(
                        batch.get("cv_excerpts", ""),
                        str(batch.get("draft", "")),
                        max(1, int(company_budget * 0.45)),
                    ),
                    "past_proposals": _relevant_evidence_excerpt(
                        batch.get("past_proposals", ""),
                        str(batch.get("draft", "")),
                        max(1, int(company_budget * 0.10)),
                    ),
                    "used_chunk_ids": {
                        category: [
                            chunk.get("chunk_id")
                            for chunk in chunks
                            if isinstance(chunk, dict) and chunk.get("chunk_id")
                        ]
                        for category, chunks in (
                            batch.get("used_company_chunks") or {}
                        ).items()
                        if isinstance(chunks, list)
                    },
                },
                "template": _relevant_evidence_excerpt(
                    batch.get("response_template_excerpts", ""),
                    str(batch.get("draft", "")),
                    template_budget,
                ),
            }
            for batch in usable
        ],
        "market_research": {
            "summary": _relevant_evidence_excerpt(
                exact_or_fallback("research_summary"), group_draft, 80
            ),
            "provenance": "External context only; never bidder evidence.",
        },
    }
    return [(group_evidence, group_draft)]


def _merge_reviews(reviews: list[dict]) -> dict:
    merged = _empty_review()
    merged["groundedness_score"] = min(
        review["groundedness_score"] for review in reviews
    )
    merged["coherence_score"] = min(
        review["coherence_score"] for review in reviews
    )
    for field in ("unsupported_claims", "contradictions", "coherence_issues", "notes"):
        merged[field] = [
            item for review in reviews for item in review.get(field, [])
        ]
    errors = [
        review.get("evaluation_error")
        for review in reviews
        if review.get("evaluation_error")
    ]
    if errors:
        merged["evaluation_error"] = "; ".join(errors)[:500]
    merged["evaluation_batches"] = len(reviews)
    return merged


def _evaluate_grounding_and_coherence(state: dict, draft: str) -> dict:
    if not draft.strip():
        review = _empty_review(error="No draft was available for evaluation.")
        review["coherence_issues"] = ["The generated proposal is empty."]
        return review

    evidence = state.get("generation_evidence") or {}
    if not evidence:
        review = _empty_review(
            error="Cannot evaluate grounding without generation evidence."
        )
        review["coherence_issues"] = ["Generation evidence was not preserved."]
        return review

    provider = get_provider()
    reviews = []
    for batch_number, (batch_evidence, batch_draft) in enumerate(
        _review_groups(state, draft), start=1
    ):
        evidence_text = json.dumps(batch_evidence, ensure_ascii=False, default=str)
        prompt = QUALITY_GROUNDING_PROMPT_TEMPLATE.format(
            evidence=evidence_text[:QUALITY_EVIDENCE_MAX_CHARS],
            draft=batch_draft[:QUALITY_DRAFT_MAX_CHARS],
        )
        try:
            completion_options = {
                "temperature": 0.0,
                "max_tokens": QUALITY_MAX_TOKENS,
                "model": QUALITY_LLM_MODEL,
                "reasoning_effort": "low",
                "include_reasoning": False,
            }
            try:
                response = provider.complete(
                    prompt,
                    **completion_options,
                    response_format={"type": "json_object"},
                    request_label=f"quality.batch_{batch_number}",
                )
            except Exception as exc:
                # Groq can reject a model-generated response in strict JSON
                # mode before returning any text. There is then nothing for
                # our local JSON repair step to process. Retry exactly once
                # without strict mode and repair/validate the returned text.
                if "json_validate_failed" not in str(exc).casefold():
                    raise
                logger.warning(
                    "Groq strict JSON validation failed for quality batch %d; "
                    "retrying once in text mode",
                    batch_number,
                )
                response = provider.complete(
                    prompt,
                    **completion_options,
                    request_label=f"quality.batch_{batch_number}.json_fallback",
                )
            reviews.append(_extract_review_json(response))
        except Exception as exc:
            logger.exception(
                "Grounding/coherence evaluation batch %d failed", batch_number
            )
            reviews.append(_empty_review(error=str(exc)[:500]))
            break
    return _merge_reviews(reviews)


def quality_agent(state: dict, *, scanner=None) -> dict:
    if not state.get("is_verified"):
        return {}
    if not state.get("security_passed", True):
        # Defensive — the graph should never route here on a security
        # failure, but don't silently score a blocked draft if it does.
        return {}

    draft = state.get("draft_proposal", "")
    word_count = len(draft.split())
    required_sections, section_order = _template_sections(state)
    missing_sections = _check_template_compliance(draft, required_sections)
    out_of_order_sections = _check_section_order(draft, section_order)
    duplicate_sections = _duplicate_sections(draft, section_order)
    incomplete_sections = _insubstantial_sections(draft, section_order)
    evidence_warnings = _evidence_gap_warnings(draft, section_order)
    deterministic_findings, deterministic_failed_sections = (
        _deterministic_proposal_checks(state, draft, section_order)
    )
    quality_findings = (
        scanner.scan(draft)
        if scanner is not None
        else (_run_llm_guard(draft) if _LLM_GUARD_AVAILABLE else {})
    )
    grounding_review = _reconcile_evaluator_only_claims(
        draft,
        section_order,
        _reconcile_disclosed_evidence_gaps(
            _reconcile_tender_requirement_findings(
                state,
                _reconcile_future_plan_findings(
                    _evaluate_grounding_and_coherence(state, draft)
                ),
            )
        ),
    )
    groundedness_score = grounding_review["groundedness_score"]
    coherence_score = grounding_review["coherence_score"]
    evaluator_error = bool(grounding_review.get("evaluation_error"))
    grounding_failed = (
        evaluator_error
        or groundedness_score < MIN_GROUNDEDNESS_SCORE
        or coherence_score < MIN_COHERENCE_SCORE
        or bool(grounding_review.get("unsupported_claims"))
        or bool(grounding_review.get("contradictions"))
    )
    failed_sections = _identify_failed_sections(
        draft=draft,
        sections=section_order,
        missing_sections=missing_sections,
        out_of_order_sections=out_of_order_sections,
        duplicate_sections=duplicate_sections,
        incomplete_sections=incomplete_sections,
        deterministic_failed_sections=deterministic_failed_sections,
        quality_findings=quality_findings,
        grounding_review=grounding_review,
        word_count=word_count,
    )
    present_sections = [
        section for section in required_sections if section not in missing_sections
    ]
    passed_sections = [
        section for section in present_sections if section not in failed_sections
    ]

    notes = []
    if word_count < MIN_WORD_COUNT:
        notes.append(f"Draft is short ({word_count} words) — may be incomplete.")
    if missing_sections:
        notes.append(f"Missing expected sections: {missing_sections}")
    if out_of_order_sections:
        notes.append(f"Template sections are out of order: {out_of_order_sections}")
    if duplicate_sections:
        notes.append(f"Duplicate template sections: {duplicate_sections}")
    if incomplete_sections:
        notes.append(
            "Sections without substantive body content "
            f"(minimum {MIN_SECTION_BODY_WORDS} words): {incomplete_sections}"
        )
    if evidence_warnings:
        notes.append(
            f"Non-blocking evidence warnings: {evidence_warnings}"
        )
    if deterministic_findings:
        notes.append(
            "Deterministic proposal checks failed: "
            f"{deterministic_findings}"
        )
    if quality_findings:
        notes.append(f"LLM Guard flagged: {quality_findings}")
    score_threshold_failed = (
        groundedness_score < MIN_GROUNDEDNESS_SCORE
        or coherence_score < MIN_COHERENCE_SCORE
    )
    if score_threshold_failed and not evaluator_error:
        notes.append(
            "Grounding/coherence review failed: "
            f"groundedness={groundedness_score:.2f} "
            f"(minimum {MIN_GROUNDEDNESS_SCORE:.2f}), "
            f"coherence={coherence_score:.2f} "
            f"(minimum {MIN_COHERENCE_SCORE:.2f})."
        )
    elif grounding_failed and not evaluator_error:
        notes.append(
            "Grounding review found unsupported or contradictory claims despite "
            "passing the numeric score thresholds."
        )
    if evaluator_error:
        notes.append(
            "Quality evaluator unavailable; stopping without regenerating the proposal."
        )
    if grounding_review.get("unsupported_claims"):
        notes.append(
            f"Unsupported claims: {grounding_review['unsupported_claims']}"
        )
    if grounding_review.get("contradictions"):
        notes.append(f"Contradictions: {grounding_review['contradictions']}")

    passed = (
        word_count >= MIN_WORD_COUNT
        and not missing_sections
        and not out_of_order_sections
        and not duplicate_sections
        and not incomplete_sections
        and not deterministic_findings
        and not quality_findings
        and not grounding_failed
    )

    quality_report = {
        "word_count": word_count,
        "missing_sections": missing_sections,
        "out_of_order_sections": out_of_order_sections,
        "duplicate_sections": duplicate_sections,
        "incomplete_sections": incomplete_sections,
        "deterministic_findings": deterministic_findings,
        "evidence_warnings": evidence_warnings,
        "failed_sections": failed_sections,
        "required_sections": required_sections,
        "present_sections": present_sections,
        "passed_sections": passed_sections,
        "quality_findings": quality_findings,
        "grounding_review": grounding_review,
        "evaluation_available": not evaluator_error,
        "groundedness_threshold": MIN_GROUNDEDNESS_SCORE,
        "coherence_threshold": MIN_COHERENCE_SCORE,
        "notes": notes,
    }

    if evaluator_error:
        logger.error(
            "Quality evaluator failed: %s",
            grounding_review.get("evaluation_error"),
        )
    elif not passed:
        logger.warning("Quality check failed. Notes: %s", notes)
    else:
        logger.info("Quality check passed.")

    return {
        "quality_passed": passed,
        "quality_report": quality_report,
    }
