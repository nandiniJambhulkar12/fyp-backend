
import os
import pandas as pd
from typing import Dict, Any, List, Optional

# Lightweight similarity based "risk analysis" from provided dataset.
# This avoids heavy ML dependencies and still leverages dataset metadata (CWE, risk_level, rationale).
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except Exception:
    HAS_SKLEARN = False

DATASET_CSV = os.environ.get(
    "DATASET_CSV",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "datasets",
        "provided_dataset.csv"
    )
)

# Cache
_df: Optional[pd.DataFrame] = None
_vectorizer: Optional["TfidfVectorizer"] = None
_matrix = None


def _load_dataset():
    global _df, _vectorizer, _matrix
    if _df is not None:
        return

    if not os.path.exists(DATASET_CSV):
        _df = pd.DataFrame()
        return

    _df = pd.read_csv(DATASET_CSV)

    # Basic cleanup
    if "code" not in _df.columns:
        return

    _df["code"] = _df["code"].fillna("").astype(str)
    if "label" in _df.columns:
        _df["label"] = pd.to_numeric(_df["label"], errors="coerce").fillna(0).astype(int)

    if HAS_SKLEARN:
        _vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1
        )
        _matrix = _vectorizer.fit_transform(_df["code"].tolist())


def dataset_risk_analysis(code_text: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Returns dataset-driven risk analysis by retrieving top similar vulnerable snippets.

    Output fields:
      - matches: list of top_k dataset rows + similarity score
      - inferred_cwe
      - inferred_risk_level
      - rationale
    """
    _load_dataset()

    if _df is None or _df.empty or not HAS_SKLEARN:
        return {
            "available": False,
            "reason": "Dataset similarity engine unavailable (missing dataset or scikit-learn).",
            "matches": [],
            "inferred_cwe": None,
            "inferred_risk_level": None,
            "rationale": None
        }

    if not code_text or not code_text.strip():
        return {
            "available": True,
            "matches": [],
            "inferred_cwe": None,
            "inferred_risk_level": None,
            "rationale": None
        }

    vec = _vectorizer.transform([code_text])
    sims = cosine_similarity(vec, _matrix)[0]

    # Prefer label=1 matches if possible
    tmp = _df.copy()
    tmp["sim"] = sims

    if "label" in tmp.columns:
        vuln_tmp = tmp[tmp["label"] == 1].sort_values("sim", ascending=False)
        top = vuln_tmp.head(top_k)
        if top.empty:
            top = tmp.sort_values("sim", ascending=False).head(top_k)
    else:
        top = tmp.sort_values("sim", ascending=False).head(top_k)

    matches: List[Dict[str, Any]] = []
    for _, row in top.iterrows():
        matches.append({
            "similarity": float(row.get("sim", 0.0)),
            "cwe": row.get("cwe"),
            "risk_level": row.get("risk_level"),
            "rule_id": row.get("rule_id"),
            "standard": row.get("standard"),
            "rationale": row.get("rationale"),
            "function_name": row.get("function_name"),
            "project": row.get("project"),
        })

    # Infer most frequent CWE/risk among top matches
    inferred_cwe = None
    inferred_risk = None
    rationale = None
    if matches:
        # pick best match
        best = matches[0]
        inferred_cwe = best.get("cwe")
        inferred_risk = best.get("risk_level")
        rationale = best.get("rationale")

    return {
        "available": True,
        "matches": matches,
        "inferred_cwe": inferred_cwe,
        "inferred_risk_level": inferred_risk,
        "rationale": rationale
    }
