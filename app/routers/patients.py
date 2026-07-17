import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/patients", tags=["patients"])
logger = logging.getLogger("patient_api")


def envelope(data=None, error=None):
    return {"data": data, "error": error}


@router.get("")
def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    patients = crud.list_patients(db, last_name, date_of_birth, phone_number)
    return envelope(data=[schemas.PatientOut.model_validate(p).model_dump(mode="json") for p in patients])


@router.get("/{patient_id}")
def get_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"))


@router.post("", status_code=201)
def create_patient(payload: schemas.PatientCreate, db: Session = Depends(get_db)):
    try:
        patient = crud.create_patient(db, payload)
        logger.info("Created patient %s (%s %s)", patient.patient_id, patient.first_name, patient.last_name)
        return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"))
    except Exception as e:
        logger.exception("Failed to create patient")
        raise HTTPException(status_code=500, detail=f"Failed to create patient: {e}")


@router.put("/{patient_id}")
def update_patient(patient_id: UUID, payload: schemas.PatientUpdate, db: Session = Depends(get_db)):
    patient = crud.update_patient(db, patient_id, payload)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return envelope(data=schemas.PatientOut.model_validate(patient).model_dump(mode="json"))


@router.delete("/{patient_id}")
def delete_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = crud.soft_delete_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return envelope(data={"patient_id": str(patient_id), "deleted": True})
