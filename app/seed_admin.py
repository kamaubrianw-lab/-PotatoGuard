"""
app/seed_admin.py
=================
One-time script to create demo accounts in the database.

Run from the PROJECT ROOT with:
    python -m app.seed_admin

Accounts created
----------------
  Admin → email: admin@potatoguard.ai   | password: admin1234
  User  → email: demo@potatoguard.ai    | password: demo1234
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from passlib.context import CryptContext

# Load .env before importing database (DATABASE_URL may be in .env)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

from .database import SessionLocal, User, init_db   # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SEED_ACCOUNTS = [
    {
        "email"   : "admin@potatoguard.ai",
        "password": "admin1234",
        "role"    : "admin",
    },
    {
        "email"   : "demo@potatoguard.ai",
        "password": "demo1234",
        "role"    : "user",
    },
]


def seed() -> None:
    print("\n🌱  Seeding database…\n")
    init_db()
    db = SessionLocal()
    try:
        for acc in SEED_ACCOUNTS:
            if db.query(User).filter(User.email == acc["email"]).first():
                print(f"  [SKIP] '{acc['email']}' already exists.")
                continue
            user = User(
                email           =acc["email"],
                hashed_password =pwd_context.hash(acc["password"]),
                role            =acc["role"],
            )
            db.add(user)
            print(f"  [OK]   Created {acc['role']:5s}: {acc['email']}")
        db.commit()
        print("\n✅  Seeding complete.\n")
        print("  Admin  →  admin@potatoguard.ai  /  admin1234")
        print("  User   →  demo@potatoguard.ai   /  demo1234\n")
    finally:
        db.close()


if __name__ == "__main__":
    seed()