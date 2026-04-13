# test_query.py
from database import SessionLocal, User, ScanHistory

# Create a new session
session = SessionLocal()

# Query all users
users = session.query(User).all()
print("Users:")
for u in users:
    print(u.id, u.email, u.role, u.created_at)

# Query all scan history
scans = session.query(ScanHistory).all()
print("\nScan History:")
for s in scans:
    print(s.id, s.email, s.disease_type, s.confidence_score, s.timestamp, s.image_path)

# Close the session
session.close()
