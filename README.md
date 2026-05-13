# Nistula Summer Technology Internship 2026
## Backend Technical Assessment

Welcome to the backend technical assessment repository for the Nistula Summer Technology Internship 2026. This project implements an intelligent, AI-driven guest communication webhook designed for luxury hospitality, built with FastAPI, PostgreSQL (mocked via SQLite for local dev), and the Anthropic Claude API.

---

## 🎯 Architecture & Project Overview

This service acts as the central brain for automated guest messaging. It ingests webhook payloads from various messaging channels (WhatsApp, Airbnb, Email), validates the structure, and routes the message to Claude (`claude-sonnet-4-20250514`) to classify the intent and draft an intelligent response based on provided context.

### Core Capabilities:
- **Resilient Webhook Ingestion**: Built on **FastAPI** with strict **Pydantic** validation models to guarantee payload integrity, gracefully handling HTTP 422 errors for malformed requests.
- **AI Triage & Deterministic Routing**: Leverages Claude to assign a confidence score (`0.0 - 1.0`). Responses >= 0.85 are flagged for `auto_send`, >= 0.60 for `agent_review`, and anything below triggers an `escalate` action to prevent AI hallucination.
- **Hardware/Emergency Bypasses**: Explicitly catches strict parameters (like `query_type: complaint`) and overrides the AI score to force an immediate `escalate` action for human intervention.
- **Non-Blocking Database Transactions**: Employs async `asyncio.to_thread` wrappers around SQLAlchemy DB writes so I/O operations do not block the main FastAPI event loop.

---

## 📂 Project Structure

```text
├── app/
│   ├── main.py                  # FastAPI Application and Webhook Endpoint
│   └── database/
│       └── local_dev_db.py      # SQLAlchemy SQLite Mock for database inserts
├── schema.sql                   # Hardened PostgreSQL Schema design with Indexes & Constraints
├── thinking.md                  # System Design Response and Architecture Philosophy
├── test_main.py                 # Pytest Suite (Network and DB patched)
├── requirements.txt             # Python Dependencies
├── .env                         # Environment variables (API Keys)
└── README.md                    # Project Documentation
```

---

## 🛠️ Setup & Execution Instructions

### Prerequisites
- Python 3.9+
- `pip` (Python package manager)

### 1. Installation
Clone the repository and create an isolated virtual environment:
```bash
git clone <repo-url>
cd nistula
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Dependencies & Configuration
Install the required packages and configure your Anthropic API Key:
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and input your ANTHROPIC_API_KEY
```

### 3. Start the Server
Launch the FastAPI uvicorn worker:
```bash
uvicorn app.main:app --reload
```
The webhook will accept POST requests precisely at: `http://localhost:8000/webhook/message`

---

## 🧪 Testing Methodology

This repository includes a deterministic, high-speed test suite built with `pytest` and `unittest.mock`. 
The tests **do not** make live network calls to Anthropic, nor do they hit an actual database, guaranteeing isolated and repeatable < 2 second execution times.

**Run the tests:**
```bash
pytest test_main.py -v
```

**Test Coverage Scenarios:**
1. **Presales Inquiry (Auto-Send)**: Verifies standard parsing and routing.
2. **Emergency Complaint (Escalate)**: Validates that complaints bypass the AI drafting and force intervention.
3. **LLM Hallucination Fallback**: Tests the application's resilience recovering from malformed JSON returned by the LLM.
4. **Structural Payload Errors**: Confirms FastAPI throws a 422 Unprocessable Entity when the incoming payload violates validation constraints.

---

## 💾 PostgreSQL Schema Design

The target architecture utilizes PostgreSQL (defined perfectly in `schema.sql`). 
It was designed with the following enterprise principles:
- **Strict Data Hygiene**: Used `CHECK` constraints (e.g., `CHECK (action_taken IN ('auto_send', 'agent_review', 'escalate'))`) rather than arbitrary `VARCHAR` types to prevent application-layer typo bugs.
- **Referential Integrity**: Implemented rigorous `FOREIGN KEY` definitions.
- **O(log N) Performance**: Created explicit `B-Tree` Indexes (`CREATE INDEX`) on all foreign keys to ensure the database can scale to millions of conversations without executing full-table scans.

---

## 🧠 System Design (Thinking Question)

Please refer to `thinking.md` for a comprehensive breakdown of my system design philosophy regarding the 3:00 AM complaint incident. It dictates how the system utilizes service-level agreements (SLAs), escalation policies (PagerDuty), and proactive IoT telemetry to permanently resolve operational anomalies.

---

## 🚧 Challenges & "If I Had More Time"

As per the assessment prompt, while no critical blockers prevented the application from functioning correctly, here is an explanation of what I considered, what trade-offs I made, and how I would aggressively scale this with more time:

1. **Async Database Connections:** 
   I used an `asyncio.to_thread` wrapper around a synchronous SQLAlchemy SQLite driver to prevent event loop blocking. With more time (and a real PostgreSQL instance), I would fully migrate to `asyncpg` or `SQLModel` natively.

2. **LLM Hallucinations on the Confidence Score:**
   Initially, during my testing, Claude would sometimes output strings instead of floats for the confidence score, or add surrounding markdown text (like "\`\`\`json"). I fixed this by writing string-stripping logic and using strict Pydantic parsing (`AIResponseValidation`) with a fallback `escalate` safety net natively catching those JSONDecodeErrors. If I had more time, I would swap this entirely to **Anthropic's native Tool Use / Function Calling (JSON mode)** feature, completely forcing deterministic JSON schema outputs instead of relying on prompt engineering.

3. **Message De-duplication:**
   If a webhook channel retries a payload due to network lag, our system might process and hit the Claude API twice. With more time, I would implement a Redis caching layer using the `message_id` or a hashed fingerprint of the payload to enforce true idempotency before the LLM call.

