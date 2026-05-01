from typing import Dict


# shap is an optional, heavy dependency (native extensions). Import lazily
# and provide a lightweight fallback so the API can run when shap isn't
# installed.
try:
    import shap  # type: ignore
    HAS_SHAP = True
except Exception:
    shap = None
    HAS_SHAP = False


def get_explainer(model):
    """Return a SHAP explainer if available, else a dummy explainer.

    The real explainer expects a predict_fn that maps texts -> [prob0, prob1].
    """
    if not HAS_SHAP:
        class DummyExplainer:
            def __call__(self, texts):
                return None

        return DummyExplainer()

    # SHAP wrapper expects a prediction function that returns
    # probability for positive class
    def predict_fn(texts):
        return [
            [1 - p, p]
            for (label, p) in [model.predict(t) for t in texts]
        ]

    explainer = shap.Explainer(predict_fn, masker=shap.maskers.Text("word"))
    return explainer


def explain_code(explainer, code_text: str, model) -> Dict:
    """Returns token-level importance and line numbers heuristically.

    If SHAP is not available or the explainer returns None, return empty
    explanation data so the API remains responsive.
    """
    if not HAS_SHAP or explainer is None:
        return {"tokens": [], "lines": []}

    try:
        shap_vals = explainer([code_text])
        # shap output has .values and .data
        tokens = shap_vals.data[0]
        values = (
            shap_vals.values[0][:, 1]
            if shap_vals.values.ndim > 1
            else shap_vals.values[0]
        )
        token_importance = list(zip(tokens, [float(v) for v in values]))
        # Heuristic to map tokens back to lines
        lines = code_text.splitlines()
        top_tokens = sorted(token_importance, key=lambda x: -abs(x[1]))[:10]
        highlighted_lines = set()
        for tok, _ in top_tokens:
            for i, ln in enumerate(lines, start=1):
                if tok.strip() and tok in ln:
                    highlighted_lines.add(i)
        return {"tokens": token_importance, "lines": sorted(list(highlighted_lines))}
    except Exception:
        return {"tokens": [], "lines": []}
