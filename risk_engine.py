from typing import Optional


RISK_BOUNDS = {
    "Critical": (0.90, 1.00),
    "High": (0.75, 0.89),
    "Medium": (0.60, 0.74),
    "Low": (0.40, 0.59),
}


def normalize_risk_level(risk_level: Optional[str], vulnerability_detected: bool) -> str:
    if not vulnerability_detected:
        return "Low"

    normalized = (risk_level or "").strip().title()
    if normalized in RISK_BOUNDS:
        return normalized
    return "Medium"


def map_confidence_score(
    risk_level: str,
    vulnerability_detected: bool,
    suggested_score: Optional[float],
) -> float:
    if not vulnerability_detected:
        return 0.0

    lower_bound, upper_bound = RISK_BOUNDS[risk_level]
    if suggested_score is None:
        return round((lower_bound + upper_bound) / 2, 2)

    try:
        numeric_score = float(suggested_score)
    except (TypeError, ValueError):
        return round((lower_bound + upper_bound) / 2, 2)

    if numeric_score > 1:
        numeric_score = numeric_score / 100.0

    numeric_score = max(lower_bound, min(upper_bound, numeric_score))
    return round(numeric_score, 2)


def ui_severity(risk_level: str) -> str:
    if risk_level == "Critical":
        return "High"
    return risk_level if risk_level in {"High", "Medium", "Low"} else "Medium"