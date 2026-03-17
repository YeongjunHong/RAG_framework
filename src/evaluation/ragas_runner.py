from typing import Any, Dict

# Ragas can be used offline, but many metrics require an LLM/judge.
# This skeleton keeps evaluation local-only and does not auto-call networked judges.

def evaluate_offline(*, dataset: Any) -> Dict[str, Any]:
    try:
        import ragas  # type: ignore
    except Exception:
        return {"enabled": False, "details": "ragas not installed"}

    # Implement your offline evaluation pipeline here.
    # Recommended: run in CI using fixed snapshots + local judge model.
    return {"enabled": True, "details": "not implemented"}
