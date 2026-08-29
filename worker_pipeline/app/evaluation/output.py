from typing import Any


def evaluate_output(state: dict[str, Any]) -> dict[str, Any]:
    quality = state.get("quality_report") or {}
    grounding = quality.get("grounding_review") or {}
    security = state.get("security_report") or {}
    scanner = security.get("scanner") or {}
    missing = list(quality.get("missing_sections") or [])
    out_of_order = list(quality.get("out_of_order_sections") or [])
    required = list(quality.get("required_sections") or [])
    unsupported = list(grounding.get("unsupported_claims") or [])
    word_count = int(quality.get("word_count") or 0)
    present_count = max(0, len(required) - len(missing))
    compliance = present_count / len(required) if required else None
    hallucinations_per_1000_words = (
        len(unsupported) * 1000 / word_count if word_count else None
    )
    return {
        "available": bool(state.get("draft_proposal")),
        "template_compliance_score": compliance,
        "required_section_count": len(required),
        "missing_sections": missing,
        "out_of_order_sections": out_of_order,
        "groundedness_score": grounding.get("groundedness_score"),
        "coherence_score": grounding.get("coherence_score"),
        "unsupported_claim_count": len(unsupported),
        "unsupported_claims": unsupported,
        "hallucinations_per_1000_words": hallucinations_per_1000_words,
        "quality_passed": bool(state.get("quality_passed")),
        "security_passed": bool(state.get("security_passed")),
        "llm_guard": {
            "enabled": bool(scanner.get("llm_guard_enabled")),
            "available": bool(scanner.get("llm_guard_available")),
            "mode": scanner.get("mode", "unknown"),
            "findings": security.get("findings") or {},
        },
        "note": (
            None
            if scanner.get("llm_guard_available")
            else "LLM Guard was unavailable; its metrics were not fabricated."
        ),
    }

