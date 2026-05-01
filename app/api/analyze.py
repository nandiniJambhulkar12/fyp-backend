
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session
from app.core import static_analysis, ml_engine, xai_engine, fix_recommender, risk_engine
from app.core.security import get_current_user
from app.db.database import SessionLocal, get_db
from app.db import schemas
import uuid
import logging

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze")
async def analyze_code(
    file: UploadFile = File(None),
    code: Optional[str] = Form(None),
    language: str = Form("python"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze code snippet pasted in UI OR uploaded as a file.
    
    ⚠️ PROTECTED ROUTE: Only verified and active users can access this endpoint.

    Returns:
      - findings: list of static + ML findings
      - dataset_risk: dataset-based similarity risk analysis (CWE/risk_level/rationale)
    """
    # Additional verification check (double-check from middleware)
    user = schemas.get_user_by_id(db, current_user["user_id"])
    if not user or not user.verified or not user.active:
        logger.warning(f"Access denied for user {current_user['user_id']}: verified={user.verified if user else 'N/A'}, active={user.active if user else 'N/A'}")
        raise HTTPException(
            status_code=403,
            detail="Your account is not verified or has been deactivated. Please contact admin."
        )
    
    logger.info(f"Analysis requested by user {user.email} (ID: {current_user['user_id']})")
    
    if file is None and not code:
        raise HTTPException(status_code=400, detail="Either file upload or code text is required.")

    # Read code text
    if file:
        contents = await file.read()
        code_text = contents.decode("utf-8", errors="ignore")
        # infer language from filename (best-effort)
        if file.filename and "." in file.filename:
            language = file.filename.split(".")[-1].lower()
    else:
        code_text = code or ""

    # 1) Static analysis
    static_findings = static_analysis.run_all(code_text, language)

    # 2) ML inference (binary classification)
    model = ml_engine.get_model()
    ml_label, ml_conf = model.predict(code_text)

    # 3) Explainability (SHAP optional)
    explainer = xai_engine.get_explainer(model)
    token_importance = xai_engine.explain_code(explainer, code_text, model)

    # 4) Dataset-driven risk analysis (CWE/risk_level/rationale from dataset)
    dataset_risk = risk_engine.dataset_risk_analysis(code_text, top_k=3)

    findings = []

    # Add static findings
    for sf in static_findings:
        # Enrich static findings with dataset context
        exploit = "This vulnerability could be exploited by an attacker to compromise system security or integrity."
        if dataset_risk and dataset_risk.get("rationale"):
            exploit = dataset_risk.get("rationale")
        
        sf["exploit_scenario"] = exploit
        findings.append(sf)

    # Add ML finding only if label=1
    if int(ml_label) == 1:
        inferred_risk_level = "Medium"
        if ml_conf >= 0.85:
            inferred_risk_level = "High"
        elif ml_conf < 0.65:
            inferred_risk_level = "Low"

        ml_exploit = "The ML model detected patterns associated with vulnerable code."
        if dataset_risk and dataset_risk.get("rationale"):
            ml_exploit = dataset_risk.get("rationale")

        findings.append({
            "id": "ml-1",
            "rule_id": "ML-PREDICT",
            "severity": inferred_risk_level,
            "standard": "ML-Model",
            "explanation": "ML model flagged this snippet as vulnerable.",
            "exploit_scenario": ml_exploit,
            "highlighted_lines": token_importance.get("lines", []),
            "model_confidence": float(ml_conf),
            "fix_suggestion": fix_recommender.suggest_fix("ml", code_text),
        })

    # Determine risk level from findings
    risk_level = "Low"
    vulnerability_count = len(findings)
    if any(f.get("severity") == "High" for f in findings):
        risk_level = "High"
    elif any(f.get("severity") == "Medium" for f in findings):
        risk_level = "Medium"
    
    # Save report to DB using the passed db session
    report_id = str(uuid.uuid4())
    report = schemas.ReportCreate(
        id=report_id,
        findings=findings,
        summary={
            "ml_label": int(ml_label),
            "ml_confidence": float(ml_conf),
            "dataset_risk": dataset_risk
        }
    )
    schemas.save_report(db, report)

    # Save to analysis history
    history_id = str(uuid.uuid4())
    analysis_create = schemas.AnalysisHistoryCreate(
        code_snippet=code_text,
        language=language,
        findings=findings,
        risk_level=risk_level,
        vulnerability_count=vulnerability_count
    )
    schemas.save_analysis_history(
        db,
        user_id=current_user["user_id"],
        analysis_create=analysis_create,
        history_id=history_id
    )
    
    logger.info(f"Analysis saved successfully - History ID: {history_id}, Findings: {len(findings)}, Risk Level: {risk_level}")

    return {
        "report_id": report_id,
        "history_id": history_id,
        "findings": findings,
        "dataset_risk": dataset_risk,
        "ml_label": int(ml_label),
        "ml_confidence": float(ml_conf),
    }
