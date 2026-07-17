"""
Webhook endpoint that Vapi calls during a live call.

Vapi is configured (see vapi_config/tools.json) with three tools/functions
the LLM can invoke mid-conversation:
  - check_existing_patient(phone_number)
  - register_patient(<all demographic fields>)
  - update_patient(patient_id, <fields to change>)

Vapi POSTs a "tool-calls" server message here; we execute the matching
local function against the database and return the result in the shape
Vapi expects: {"results": [{"toolCallId": ..., "result": "..."}]}

We also accept Vapi's "end-of-call-report" / "status-update" messages purely
for observability (logged to stdout per the Observability requirement).
"""
import json
import logging
from datetime import date

from fastapi import APIRouter, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import SessionLocal

router = APIRouter(prefix="/vapi", tags=["vapi"])
logger = logging.getLogger("vapi_webhook")


def _db() -> Session:
    return SessionLocal()


def _tool_result(tool_call_id: str, result) -> dict:
    if not isinstance(result, str):
        result = json.dumps(result)
    return {"toolCallId": tool_call_id, "result": result}


def handle_check_existing_patient(args: dict) -> dict:
    db = _db()
    try:
        phone = args.get("phone_number", "")
        patient = crud.get_patient_by_phone(db, "".join(filter(str.isdigit, phone))[-10:])
        if patient:
            return {
                "found": True,
                "patient_id": str(patient.patient_id),
                "first_name": patient.first_name,
                "last_name": patient.last_name,
            }
        return {"found": False}
    finally:
        db.close()


def handle_register_patient(args: dict) -> dict:
    db = _db()
    try:
        payload = schemas.PatientCreate(**args)
        patient = crud.create_patient(db, payload)
        logger.info(
            "VOICE AGENT REGISTERED PATIENT: %s",
            json.dumps(
                {
                    "patient_id": str(patient.patient_id),
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "phone_number": patient.phone_number,
                },
            ),
        )
        return {"success": True, "patient_id": str(patient.patient_id)}
    except ValidationError as e:
        logger.warning("Voice agent submitted invalid patient data: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception("DB write failed during voice registration")
        return {"success": False, "error": f"Could not save the record: {e}"}
    finally:
        db.close()


def handle_update_patient(args: dict) -> dict:
    db = _db()
    try:
        patient_id = args.pop("patient_id")
        patch = schemas.PatientUpdate(**args)
        patient = crud.update_patient(db, patient_id, patch)
        if not patient:
            return {"success": False, "error": "Patient not found"}
        return {"success": True, "patient_id": str(patient.patient_id)}
    except Exception as e:
        logger.exception("DB update failed during voice call")
        return {"success": False, "error": f"Could not update the record: {e}"}
    finally:
        db.close()


TOOL_HANDLERS = {
    "check_existing_patient": handle_check_existing_patient,
    "register_patient": handle_register_patient,
    "update_patient": handle_update_patient,
}


@router.post("/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type")

    if msg_type == "tool-calls":
        results = []
        for call in message.get("toolCallList", []):
            tool_call_id = call.get("id")
            fn = call.get("function", {})
            name = fn.get("name")
            raw_args = fn.get("arguments", {})
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

            handler = TOOL_HANDLERS.get(name)
            if not handler:
                results.append(_tool_result(tool_call_id, {"success": False, "error": f"Unknown tool {name}"}))
                continue
            try:
                result = handler(args)
            except Exception as e:
                logger.exception("Tool handler %s crashed", name)
                result = {"success": False, "error": str(e)}
            results.append(_tool_result(tool_call_id, result))
        return {"results": results}

    if msg_type == "end-of-call-report":
        logger.info("CALL ENDED: %s", json.dumps(message.get("analysis", message), default=str))
        return {"received": True}

    if msg_type == "status-update":
        logger.info("CALL STATUS: %s", message.get("status"))
        return {"received": True}

    # Log anything else for observability without failing the call
    logger.info("Unhandled Vapi message type: %s", msg_type)
    return {"received": True}
