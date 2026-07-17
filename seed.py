"""Run with: python seed.py
Inserts two demo patient records so /patients returns data immediately."""
from app.database import Base, engine, SessionLocal
from app import models, crud, schemas

Base.metadata.create_all(bind=engine)
db = SessionLocal()

seed_records = [
    schemas.PatientCreate(
        first_name="Jane",
        last_name="Doe",
        date_of_birth="1990-04-12",
        sex="Female",
        phone_number="5125550100",
        email="jane.doe@example.com",
        address_line_1="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78701",
        preferred_language="English",
    ),
    schemas.PatientCreate(
        first_name="Miguel",
        last_name="Alvarez",
        date_of_birth="1985-11-02",
        sex="Male",
        phone_number="2125550187",
        address_line_1="456 Oak Ave",
        city="New York",
        state="NY",
        zip_code="10001",
        preferred_language="Spanish",
    ),
]

for rec in seed_records:
    existing = crud.get_patient_by_phone(db, rec.phone_number)
    if not existing:
        crud.create_patient(db, rec)
        print(f"Seeded {rec.first_name} {rec.last_name}")
    else:
        print(f"Skipped {rec.first_name} {rec.last_name} (already exists)")

db.close()
