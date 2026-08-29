from typing import Any


def evaluate_performance(record: Any) -> dict[str, Any]:
    timings = record.stage_timings or {}
    durations = {
        stage: max(
            0.0,
            float(values.get("ended_at", record.updated_at))
            - float(values["started_at"]),
        )
        for stage, values in timings.items()
        if values.get("started_at") is not None
    }
    total = max(0.0, record.updated_at - record.created_at)
    state = record.upstream_state or {}
    telemetry = state.get("telemetry") or {}
    agent_telemetry = telemetry.get("agents") or {}
    exact_durations = {
        stage: max(0.0, float(values.get("duration_seconds") or 0.0))
        for stage, values in agent_telemetry.items()
    }
    exact_total = telemetry.get("total_duration_seconds")
    if exact_total is not None:
        exact_total = max(0.0, float(exact_total))
    usage = (
        telemetry.get("llm_usage")
        or state.get("usage")
        or state.get("token_usage")
        or {}
    )
    uses_exact_telemetry = bool(agent_telemetry)
    effective_total = exact_total if exact_total is not None else total
    return {
        "available": True,
        "total_duration_seconds": effective_total,
        "exact_agent_duration_seconds": exact_durations,
        "observed_stage_duration_seconds": durations,
        "pipeline_throughput_per_hour": (
            3600 / effective_total if effective_total else None
        ),
        "llm_token_usage": usage,
        "telemetry_notes": telemetry.get("notes") or [],
        "exact_telemetry_available": uses_exact_telemetry,
        "agent_attempts": {
            stage: values.get("attempts") or []
            for stage, values in agent_telemetry.items()
        },
        "measurement_method": (
            "Exact timings and provider-reported token usage came from the agent "
            "pipeline. Polling observations are retained for comparison."
            if uses_exact_telemetry
            else "Stage durations are observed from worker polling because the "
            "upstream pipeline did not expose exact telemetry."
        ),
    }
