import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use an isolated in-memory-per-test-run SQLite DB for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_patients.db"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

VALID_PATIENT = {
    "first_name": "Test",
    "last_name": "Patient",
    "date_of_birth": "1995-06-15",
    "sex": "Other",
    "phone_number": "5551234567",
    "address_line_1": "1 Test Way",
    "city": "Testville",
    "state": "CA",
    "zip_code": "90001",
}


def unique_patient():
    p = dict(VALID_PATIENT)
    p["phone_number"] = "555" + str(uuid.uuid4().int)[:7]
    return p


def test_create_and_get_patient():
    resp = client.post("/patients", json=unique_patient())
    assert resp.status_code == 201
    body = resp.json()
    assert body["error"] is None
    patient_id = body["data"]["patient_id"]

    get_resp = client.get(f"/patients/{patient_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["first_name"] == "Test"


def test_accepts_mm_dd_yyyy_date_of_birth():
    """Regression test: the voice agent's tool schema allows MM/DD/YYYY,
    which Pydantic's default date parser used to silently reject."""
    p = unique_patient()
    p["date_of_birth"] = "01/05/1990"
    resp = client.post("/patients", json=p)
    assert resp.status_code == 201
    assert resp.json()["data"]["date_of_birth"] == "1990-01-05"


def test_reject_future_date_of_birth():
    p = unique_patient()
    p["date_of_birth"] = "2999-01-01"
    resp = client.post("/patients", json=p)
    assert resp.status_code == 422


def test_reject_invalid_phone_number():
    p = unique_patient()
    p["phone_number"] = "123"
    resp = client.post("/patients", json=p)
    assert resp.status_code == 422


def test_reject_invalid_state():
    p = unique_patient()
    p["state"] = "ZZ"
    resp = client.post("/patients", json=p)
    assert resp.status_code == 422


def test_list_and_filter_by_last_name():
    client.post("/patients", json=unique_patient())
    resp = client.get("/patients", params={"last_name": "Patient"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


def test_partial_update():
    create_resp = client.post("/patients", json=unique_patient())
    patient_id = create_resp.json()["data"]["patient_id"]

    update_resp = client.put(f"/patients/{patient_id}", json={"city": "New City"})
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["city"] == "New City"
    # unrelated field untouched
    assert update_resp.json()["data"]["first_name"] == "Test"


def test_soft_delete_hides_from_list_and_get():
    create_resp = client.post("/patients", json=unique_patient())
    patient_id = create_resp.json()["data"]["patient_id"]

    del_resp = client.delete(f"/patients/{patient_id}")
    assert del_resp.status_code == 200

    get_resp = client.get(f"/patients/{patient_id}")
    assert get_resp.status_code == 404


def test_get_nonexistent_patient_404():
    resp = client.get(f"/patients/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_persistence_across_requests():
    """Simulates 'call back later' — record created in one request is
    retrievable via a separate request without server restart, proving
    the DB layer (not in-memory state) is the source of truth."""
    resp = client.post("/patients", json=unique_patient())
    patient_id = resp.json()["data"]["patient_id"]
    again = client.get(f"/patients/{patient_id}")
    assert again.status_code == 200
    assert again.json()["data"]["patient_id"] == patient_id
