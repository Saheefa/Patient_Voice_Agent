import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from app.routers import patients, vapi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Patient Registration API",
    description="REST API + Vapi voice-agent webhook for patient intake.",
    version="1.0.0",
)

app.include_router(patients.router)
app.include_router(vapi.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # exc.errors() includes raw exception objects (e.g. the ValueError raised
    # inside a validator) that aren't JSON-serializable — stringify them.
    errors = [
        {"field": ".".join(str(p) for p in e.get("loc", [])), "message": str(e.get("msg"))}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"data": None, "error": errors})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"data": None, "error": exc.detail})


@app.get("/")
def root():
    return {"data": {"service": "patient-registration-api", "status": "ok"}, "error": None}


@app.get("/health")
def health():
    return {"data": {"status": "healthy"}, "error": None}


@app.get("/dashboard")
def dashboard():
    """Simple staff-facing UI listing registered patients (bonus)."""
    path = Path(__file__).parent / "static" / "dashboard.html"
    return FileResponse(path, media_type="text/html")
