from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app import models, schemas


def create_patient(db: Session, patient: schemas.PatientCreate) -> models.Patient:
    db_patient = models.Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def get_patient(db: Session, patient_id: UUID) -> Optional[models.Patient]:
    return (
        db.query(models.Patient)
        .filter(models.Patient.patient_id == str(patient_id), models.Patient.deleted_at.is_(None))
        .first()
    )


def get_patient_by_phone(db: Session, phone_number: str) -> Optional[models.Patient]:
    return (
        db.query(models.Patient)
        .filter(models.Patient.phone_number == phone_number, models.Patient.deleted_at.is_(None))
        .first()
    )


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    phone_number: Optional[str] = None,
):
    q = db.query(models.Patient).filter(models.Patient.deleted_at.is_(None))
    if last_name:
        q = q.filter(models.Patient.last_name.ilike(last_name))
    if date_of_birth:
        q = q.filter(models.Patient.date_of_birth == date_of_birth)
    if phone_number:
        q = q.filter(models.Patient.phone_number == phone_number)
    return q.order_by(models.Patient.created_at.desc()).all()


def update_patient(db: Session, patient_id: UUID, patch: schemas.PatientUpdate) -> Optional[models.Patient]:
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None
    updates = patch.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(db_patient, field, value)
    db_patient.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def soft_delete_patient(db: Session, patient_id: UUID) -> Optional[models.Patient]:
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        return None
    db_patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_patient)
    return db_patient
