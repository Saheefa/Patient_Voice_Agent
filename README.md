# Patient Registration Voice AI Agent

A voice-based intake agent (via [Vapi](https://vapi.ai)) that conversationally
collects U.S. patient demographics over a real phone call, persists them
through a FastAPI backend, and exposes the data via a REST API.

```
Phone Call ──▶ Vapi (telephony + STT/TTS + LLM) ──▶ /vapi/webhook (tool calls)
                                                            │
                                                            ▼
                                                   FastAPI service layer
                                                            │
                                                            ▼
                                                 SQLite (dev) / Postgres (prod)
                                                            │
                                                            ▼
                                                  REST API (/patients/*)
```

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Telephony/Voice | **Vapi** | Abstracts STT/TTS/telephony so the 3-hour budget goes into prompt engineering, tool design, and the data layer — not wiring together raw Twilio + Deepgram + ElevenLabs. |
| LLM | **GPT-4o** (via Vapi) | Strong instruction-following for natural, correction-tolerant conversation; swappable for 4o-mini for latency/cost. |
| Backend | **FastAPI** | Async, built-in Pydantic validation (server-side, independent of the voice agent), automatic OpenAPI docs, fast to write cleanly in a time-boxed challenge. |
| DB | **SQLite locally / Postgres in prod** | SQLite = zero setup for local dev and testing. Vercel's serverless filesystem is ephemeral, so production uses a `DATABASE_URL` pointed at Postgres (Vercel Postgres/Neon/Supabase) — same SQLAlchemy models, no code change. |
| Hosting | **Vercel** | Per requirements; see "Vercel + SQLite" trade-off below. |

## Repository layout

```
app/
  main.py            FastAPI app, error handlers, route registration
  database.py         SQLAlchemy engine/session (SQLite or Postgres via DATABASE_URL)
  models.py            Patient table definition
  schemas.py           Pydantic request/response models + all field validation
  crud.py               DB access functions
  routers/
    patients.py         REST API: GET/POST/PUT/DELETE /patients
    vapi.py               Webhook Vapi calls mid-conversation (tool execution)
api/index.py           Vercel serverless entrypoint (imports the FastAPI app)
vapi_config/
  system_prompt.md      Full system prompt for the Vapi assistant (commented)
  tools.json             Tool/function schemas the LLM can call
  assistant_config.json  Full assistant config for one-shot import into Vapi
tests/test_api.py        Automated tests (bonus) — 9 tests, incl. a persistence test
seed.py                  Inserts 2 demo patients
```

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL unset = uses local SQLite
python seed.py                # optional: seed 2 demo patients
uvicorn app.main:app --reload
```

API is now live at `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

Run tests:
```bash
pytest tests/ -v
```

## Deploying

**Backend (Vercel):**
1. `vercel` (or connect the GitHub repo in the Vercel dashboard) — `vercel.json` routes all traffic through `api/index.py`, which mounts the FastAPI app.
2. Set env var `DATABASE_URL` in the Vercel project to a hosted Postgres connection string (Vercel Postgres, Neon, or Supabase all work — the app auto-normalizes `postgres://` → `postgresql://`). **Do not rely on SQLite in production** — see trade-offs below.
3. Note the deployed URL, e.g. `https://your-app.vercel.app`.

**Voice agent (Vapi):**
1. Create a Vapi account, add an OpenAI key (or use Vapi credits) and an ElevenLabs voice.
2. Create an assistant. Paste `vapi_config/system_prompt.md` as the system prompt.
3. Add the three tools from `vapi_config/tools.json`, replacing `YOUR_DEPLOYMENT_URL` with your Vercel URL (`.../vapi/webhook`).
4. Buy/import a phone number in Vapi and attach it to this assistant.
5. Call the number.

## Environment variables

See `.env.example`:
- `DATABASE_URL` — Postgres connection string in production; unset locally (SQLite fallback).
- `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID` — for reference/automation scripts, not required by the FastAPI app itself (Vapi calls *out* to our webhook, not the other way around, for the core flow).
- `OPENAI_API_KEY` — only if you connect your own key in Vapi instead of Vapi's managed credits.

## API

All responses use the envelope `{ "data": ..., "error": ... }`.

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/patients` | Filters: `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| GET | `/patients/{id}` | 404 if not found or soft-deleted |
| POST | `/patients` | 201 + record on success, 422 with field-level errors on validation failure |
| PUT | `/patients/{id}` | Partial update — only send fields that changed |
| DELETE | `/patients/{id}` | Soft delete (`deleted_at` set; row retained) |

Validation (names, DOB not in future, phone format, state abbreviation, ZIP
format, sex enum) lives in `app/schemas.py` and runs **server-side on every
request**, independent of whatever the voice agent already validated
conversationally — per the "don't rely solely on the voice agent" requirement.

## Voice agent design notes

- **Prompt** (`vapi_config/system_prompt.md`) is written as an intake
  coordinator persona, not an IVR script — explicit instructions against
  robotic listing, against reading raw field names, and for handling
  corrections/out-of-order answers/restart requests without losing prior
  context.
- **Duplicate detection (bonus):** the agent calls `check_existing_patient`
  right after getting the phone number, before collecting anything else,
  and offers to update instead of create if a match is found.
- **Multi-language (bonus):** the Deepgram transcriber is set to `multi`
  and the prompt explicitly instructs a full switch to Spanish on request.
- **Call transcripts (bonus):** `recordingEnabled: true` plus the
  `end-of-call-report` handler in `app/routers/vapi.py` logs the call
  summary to stdout; wiring that into a `call_transcripts` table linked to
  `patient_id` is a natural next step (see Known Limitations).
- **Error handling:** invalid data from the caller is caught two ways —
  Pydantic validation inside `handle_register_patient`/`handle_update_patient`
  returns a structured error the LLM re-prompts around, and the same
  Pydantic models guard the REST API directly.

## Live deployment

- **Phone number**: +1 (725) 745-7126
- **API base URL**: https://patient-voice-agent-one.vercel.app
- **Repository**: https://github.com/Saheefa/Patient_Voice_Agent

## Known limitations & trade-offs

- **Vercel + database persistence:** Vercel functions have an ephemeral,
  read-only filesystem — SQLite will *not* persist across invocations
  there. The code defaults to SQLite for zero-friction local dev, but
  **production requires `DATABASE_URL` pointed at a real Postgres
  instance** (Vercel Postgres/Neon/Supabase free tiers all work). This is
  the one config step that can't be skipped for the live deployment to
  satisfy "Call 1 data survives to Call 2."
- **Free-tier Postgres cold starts:** hosted free-tier Postgres (Neon)
  pauses after a few minutes idle. The first database query after a pause
  adds a noticeable delay (observed ~3s in testing) to that one
  conversation turn — the caller may experience a longer-than-usual pause
  right when a tool is called (e.g. checking for an existing patient). A
  paid/always-on tier removes this; not addressed here to stay within the
  free-tier trade-off the challenge encourages.
- **No dashboard UI** — bonus item not built; `/docs` (FastAPI's
  auto-generated Swagger UI) is the closest thing to a browsable view
  today.
- **Call transcript is logged, not persisted to a `transcripts` table** —
  logged to stdout per the observability requirement; a `call_transcripts`
  table with a `patient_id` foreign key is the natural next step.
- **Appointment scheduling bonus not implemented.**
- **No auth on the REST API** — acceptable for a take-home per the FAQ
  (no HIPAA scope), but a real deployment needs at minimum an API key on
  `/patients/*` and the `/vapi/webhook` route (e.g. verifying Vapi's
  webhook signature).
- **Phone-number matching for duplicate detection is exact-match only** —
  doesn't handle a caller registering a *different* family member from the
  same shared home phone particularly gracefully beyond asking the LLM to
  use judgment; a more robust version would confirm name + DOB too.

## Next steps

1. Point `DATABASE_URL` at Postgres and redeploy for true multi-call persistence on Vercel.
2. Add a `call_transcripts` table + link from `end-of-call-report` handler.
3. Add API-key auth + Vapi webhook signature verification.
4. Build the simple dashboard (bonus) as a static page hitting the REST API.
5. Add appointment scheduling as a fourth Vapi tool + `appointments` table.
