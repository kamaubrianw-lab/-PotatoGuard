"""
app/main.py
===========
FastAPI application — launch from the project root with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Upgrades in this version
------------------------
  - DELETE /admin/users/{user_id}  — hard delete user + cascade scan history
  - Expert advice fallback library (Gemini → fallback on quota/error)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Relative imports
# ---------------------------------------------------------------------------
from . import inference as inf
from .auth import UserOut, get_current_user, require_admin, router as auth_router
from .database import ScanHistory, User, get_db, init_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
UPLOAD_DIR = _ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Gemini setup — supports both new and legacy package
# ---------------------------------------------------------------------------
_GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
_gemini_client = None

if _GEMINI_KEY:
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=_GEMINI_KEY)
        logger.info("Gemini configured via google-genai.")
    except ImportError:
        try:
            import google.generativeai as genai
            genai.configure(api_key=_GEMINI_KEY)
            _gemini_client = genai
            logger.info("Gemini configured via google-generativeai (legacy).")
        except ImportError:
            logger.warning("No Gemini package found. Expert fallback active.")
else:
    logger.warning("GEMINI_API_KEY not set — expert fallback active.")

_GEMINI_PROMPT = (
    "A potato leaf has been diagnosed with {disease}. "
    "As an agricultural expert, provide a 3-step treatment plan "
    "and specific fungicide recommendations."
)

# ---------------------------------------------------------------------------
# Expert advice fallback library
# Priority: Gemini API → this library on any failure
# ---------------------------------------------------------------------------
_EXPERT_ADVICE = {
    "Potato___Early_blight": """
🍂 EARLY BLIGHT TREATMENT PLAN (Alternaria solani)

STEP 1 — IMMEDIATE ACTION
Remove and destroy all infected leaves showing dark brown
concentric ring spots. Do not compost them — place in sealed
bags and dispose away from the field to stop spore spread.

STEP 2 — FUNGICIDE APPLICATION
Apply every 7–10 days until symptoms are controlled.

  Organic options:
  • Copper Oxychloride — apply in early morning
  • Neem oil (2% solution) — effective for mild infections
  • Bordeaux mixture — traditional, highly effective

  Chemical options:
  • Chlorothalonil (Bravo, Echo) — broad spectrum protectant
  • Mancozeb (Dithane M-45) — apply before rain events
  • Azoxystrobin (Amistar) — systemic, excellent control

STEP 3 — PREVENTION
  • Water at the base only — never wet the foliage
  • Apply mulch to prevent soil splash onto lower leaves
  • Maintain 45–60cm spacing between plants for airflow
  • Rotate crops — avoid potatoes in same soil for 2–3 seasons
  • Remove all plant debris after harvest
""",
    "Potato___Late_blight": """
🌧️ LATE BLIGHT EMERGENCY PLAN (Phytophthora infestans)

⚠️ URGENT — Late Blight spreads rapidly in cool, wet conditions
and can destroy an entire crop within days. Act immediately.

STEP 1 — IMMEDIATE ACTION
Remove all stems and leaves with water-soaked dark lesions
and white mould on the underside. Bag and burn — do not compost.
If more than 30% of the plant is infected, remove the entire
plant to protect neighbouring crops.

STEP 2 — FUNGICIDE APPLICATION
Apply immediately and repeat every 5–7 days in wet weather.

  Organic options:
  • Copper Hydroxide (Kocide) — most effective organic option
  • Bordeaux mixture — classic Late Blight treatment
  • Bacillus subtilis (Serenade) — biological control

  Chemical options (most effective):
  • Metalaxyl + Mancozeb (Ridomil Gold) — systemic, best choice
  • Cymoxanil + Mancozeb (Curzate) — curative and protective
  • Dimethomorph (Acrobat) — excellent systemic control
  • Propamocarb (Previcur) — soil and foliar application

STEP 3 — PREVENTION
  • Monitor daily in cool (10–20°C) and humid conditions
  • Destroy all volunteer potato plants near the field
  • Hill up soil around stems to protect tubers
  • Harvest tubers quickly if above-ground infection is severe
  • Store in cool, dry, well-ventilated space
  • Rotate crops for minimum 3 years in infected soil
""",
}

_HEALTHY_ADVICE = """
✅ YOUR POTATO PLANT IS HEALTHY

No disease detected. Your plant shows healthy green foliage
with no signs of fungal infection or blight.

MAINTENANCE TIPS:

  • Watering — water deeply at the base, never the leaves.
    Morning watering is best so foliage dries during the day.

  • Spacing — ensure 45–60cm between plants for good airflow.
    Poor airflow is the leading cause of fungal disease.

  • Monitoring — inspect leaves weekly, especially the underside.
    Early detection saves the entire crop.

  • Feeding — apply balanced NPK fertiliser at planting.
    Potassium strengthens cell walls and improves resistance.

  • Crop rotation — never plant potatoes in the same bed
    two seasons running. Rotate with legumes or brassicas.

  • Mulching — apply straw mulch to prevent soil splash
    which carries fungal spores onto lower leaves.
"""


def _get_gemini_advice(disease_class: str) -> str:
    """
    Returns agricultural advice for the detected disease.
    Attempts Gemini API first — falls back to expert library
    on any failure (quota, invalid key, network error).
    """
    if disease_class == "Potato___healthy":
        return _HEALTHY_ADVICE

    if _gemini_client is not None:
        try:
            display = inf.DISPLAY_NAMES.get(disease_class, disease_class)
            prompt  = _GEMINI_PROMPT.format(disease=display)
            if hasattr(_gemini_client, "models"):
                response = _gemini_client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt,
                )
            else:
                response = _gemini_client.generate_content(prompt)
            return response.text
        except Exception as exc:
            logger.warning("Gemini unavailable (%s) — using expert library.", exc)

    return _EXPERT_ADVICE.get(
        disease_class,
        "Please consult your local agricultural extension officer.",
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PotatoGuard AI — Disease Detection API",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    logger.info("Initialising database…")
    init_db()
    logger.info("Pre-loading TFLite model…")
    inf.load_model()
    logger.info("API ready — docs at http://127.0.0.1:8000/docs")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class PredictOut(BaseModel):
    id              : int
    email           : str
    disease_type    : str
    confidence_score: float
    llm_advice      : Optional[str]
    timestamp       : datetime
    image_path      : Optional[str]

    class Config:
        from_attributes = True


class AdminStats(BaseModel):
    total_users         : int
    total_scans         : int
    disease_distribution: dict[str, int]


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------
@app.get("/users/me", response_model=UserOut, tags=["Users"])
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# ---------------------------------------------------------------------------
# /predict
# ---------------------------------------------------------------------------
@app.post("/predict", response_model=PredictOut, tags=["Inference"])
async def predict(
    file        : UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
    db          : Session    = Depends(get_db),
) -> ScanHistory:
    """Upload a potato leaf image → TFLite diagnosis + advisory."""

    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WEBP images are accepted.",
        )

    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    save_path = UPLOAD_DIR / safe_name
    contents  = await file.read()
    save_path.write_bytes(contents)

    try:
        pil_image                    = Image.open(BytesIO(contents))
        disease_class, confidence, _ = inf.predict(pil_image)
    except Exception as exc:
        logger.error("Inference error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model inference failed: {exc}",
        )

    advice = _get_gemini_advice(disease_class)

    scan = ScanHistory(
        user_id         =current_user.id,
        email           =current_user.email,
        disease_type    =disease_class,
        confidence_score=confidence,
        llm_advice      =advice,
        image_path      =f"uploads/{safe_name}",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------
@app.get("/history", response_model=list[PredictOut], tags=["Inference"])
def get_history(
    current_user: User    = Depends(get_current_user),
    db          : Session = Depends(get_db),
    limit       : int     = 50,
) -> list[ScanHistory]:
    return (
        db.query(ScanHistory)
        .filter(ScanHistory.user_id == current_user.id)
        .order_by(ScanHistory.timestamp.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Admin — stats
# ---------------------------------------------------------------------------
@app.get("/admin/stats", response_model=AdminStats, tags=["Admin"])
def admin_stats(
    _  : User    = Depends(require_admin),
    db : Session = Depends(get_db),
) -> AdminStats:
    total_users = db.query(func.count(User.id)).scalar()
    total_scans = db.query(func.count(ScanHistory.id)).scalar()
    rows        = (
        db.query(ScanHistory.disease_type, func.count(ScanHistory.id))
        .group_by(ScanHistory.disease_type)
        .all()
    )
    return AdminStats(
        total_users          =total_users,
        total_scans          =total_scans,
        disease_distribution ={d: c for d, c in rows},
    )


# ---------------------------------------------------------------------------
# Admin — list users
# ---------------------------------------------------------------------------
@app.get("/admin/users", response_model=list[UserOut], tags=["Admin"])
def admin_list_users(
    _  : User    = Depends(require_admin),
    db : Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Admin — delete user (hard delete + cascade scan history)
# ---------------------------------------------------------------------------
@app.delete("/admin/users/{user_id}", status_code=204, tags=["Admin"])
def admin_delete_user(
    user_id: int,
    _      : User    = Depends(require_admin),
    db     : Session = Depends(get_db),
) -> None:
    """
    Permanently delete a user and ALL their associated scan records.

    Cascade strategy: Hard delete via SQLAlchemy relationship cascade
    ('all, delete-orphan') + DB-level ON DELETE CASCADE on the FK.
    Both layers ensure no orphaned ScanHistory rows remain.
    Image files on disk are also removed to prevent storage bloat.
    Admin accounts cannot delete themselves.
    """
    current_admin = db.query(User).filter(User.id == _.id).first()
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be deleted via the API.",
        )

    # Remove image files from disk before deleting DB records
    scans = db.query(ScanHistory).filter(ScanHistory.user_id == user_id).all()
    for scan in scans:
        if scan.image_path:
            (_ROOT / scan.image_path).unlink(missing_ok=True)

    db.delete(user)   # cascade handles ScanHistory rows automatically
    db.commit()
    logger.info("User %s (id=%s) deleted by admin.", user.email, user_id)


# ---------------------------------------------------------------------------
# Admin — delete individual scan
# ---------------------------------------------------------------------------
@app.delete("/admin/scans/{scan_id}", status_code=204, tags=["Admin"])
def admin_delete_scan(
    scan_id: int,
    _      : User    = Depends(require_admin),
    db     : Session = Depends(get_db),
) -> None:
    scan = db.query(ScanHistory).filter(ScanHistory.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    if scan.image_path:
        (_ROOT / scan.image_path).unlink(missing_ok=True)
    db.delete(scan)
    db.commit()