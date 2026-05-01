"""Deterministic merging of AI and rule-based findings."""

from __future__ import annotations

from typing import Any, Dict, List


_SEVERITY_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _finding_key(finding: Dict[str, Any]) -> tuple[str, str, int, str]:
    issue = _normalize_text(finding.get("risk_type") or finding.get("issue") or finding.get("title"))
    cwe = _normalize_text(finding.get("cwe") or finding.get("cwe_id"))
    line = int(finding.get("line") or finding.get("lineNumber") or 0)
    category = _normalize_text(finding.get("category") or finding.get("owasp"))
    return issue.lower(), cwe.lower(), line, category.lower()


def _severity_score(severity: Any) -> int:
    return _SEVERITY_ORDER.get(_normalize_text(severity).title(), 0)


def merge_findings(*finding_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[tuple[str, str, int, str], Dict[str, Any]] = {}

    for group in finding_groups:
        for finding in group or []:
            key = _finding_key(finding)
            current = merged.get(key)
            if current is None:
                merged[key] = dict(finding)
                continue

            if _severity_score(finding.get("severity")) > _severity_score(current.get("severity")):
                current["severity"] = finding.get("severity", current.get("severity"))
            if len(_normalize_text(finding.get("description"))) > len(_normalize_text(current.get("description"))):
                current["description"] = finding.get("description", current.get("description"))
            if len(_normalize_text(finding.get("explanation"))) > len(_normalize_text(current.get("explanation"))):
                current["explanation"] = finding.get("explanation", current.get("explanation"))
            if len(_normalize_text(finding.get("fix_suggestion") or finding.get("fix"))) > len(
                _normalize_text(current.get("fix_suggestion") or current.get("fix"))
            ):
                current["fix_suggestion"] = finding.get("fix_suggestion") or finding.get("fix")
            if not current.get("codeSnippet") and finding.get("codeSnippet"):
                current["codeSnippet"] = finding.get("codeSnippet")
            if not current.get("line") and finding.get("line"):
                current["line"] = finding.get("line")
            current_conf = int(current.get("model_confidence") or 0)
            finding_conf = int(finding.get("model_confidence") or finding.get("confidence") or 0)
            if finding_conf > current_conf:
                current["model_confidence"] = finding_conf

    return sorted(
        merged.values(),
        key=lambda item: (
            -_severity_score(item.get("severity")),
            int(item.get("line") or 0),
            _normalize_text(item.get("risk_type") or item.get("issue")).lower(),
        ),
    )
