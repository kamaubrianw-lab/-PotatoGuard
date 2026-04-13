import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone
from app.auth import hash_password as hashed_pw
from app.database import SessionLocal, User, ScanHistory, init_db

# Create tables if needed, then open a session
init_db()
session = SessionLocal()

sample_email = "test2@example.com"
user = session.query(User).filter(User.email == sample_email).first()
if not user:
    user = User(
        email=sample_email,
        hashed_password=hashed_pw("password123"),
        role="user"
    )
    session.add(user)
    session.commit()  # commit so the user gets an ID
    print(f"Created sample user: {sample_email}")
else:
    print(f"Sample user already exists: {sample_email}")

# Add a sample scan history linked to that user
new_scan = ScanHistory(
    user_id=user.id,
    email=user.email,
    disease_type="Potato___Late_blight",
    confidence_score=0.62,
    llm_advice="""
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
    image_path="images/sample_leaf.jpg",
    timestamp=datetime.now(timezone.utc)
)
session.add(new_scan)
session.commit()

print("Inserted sample user and scan history!")
session.close()
