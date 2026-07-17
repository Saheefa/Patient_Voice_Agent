"""
Vercel Python entrypoint. Vercel's @vercel/python runtime auto-detects a
FastAPI/ASGI `app` object exported from a file under /api and serves it as
a serverless function. All routes are proxied through this file.
"""
from app.main import app  # noqa: F401
