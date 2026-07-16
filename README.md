<<<<<<< HEAD
# AI-Powered QA Test Case Generation System

A production-grade technical PDF parser, hierarchical version matching engine, and LLM-powered test case generator. Built specifically for medical device QA engineering requirements.

---

## 1. Project Folder Structure

The complete folder structure is structured as follows:

```text
app/
├── api/
│   ├── v1/
│   │   ├── documents.py   # Upload, list, search, tree, and diff endpoints
│   │   ├── selections.py  # Selection pinning endpoints
│   │   ├── generations.py # Test generation and staleness endpoints
│   │   └── router.py      # Main router assembly
│   └── errors.py          # Custom global handlers
├── core/
│   ├── config.py          # Pydantic BaseSettings management
│   └── logging.py         # Stdlib logging configuration
├── database/
│   ├── session.py         # SQLAlchemy engine & SQLite config
│   └── mongodb.py         # Async MongoDB Motor manager
├── models/
│   ├── base.py            # Declarative base & Timestamp Mixin
│   ├── document.py        # Document, Version, and Node schemas
│   ├── selection.py       # Selection and SelectionNode mapping
│   └── generation.py      # Generation and GenerationNode mapping
├── schemas/
│   ├── document.py        # Pydantic validators for docs/nodes
│   ├── selection.py       # Pydantic validators for selections
│   └── generation.py      # Pydantic validators for QA cases & staleness
├── services/
│   ├── parser.py          # PDF parser (PyMuPDF + pdfplumber)
│   ├── versioning.py      # Node version matching (RapidFuzz)
│   ├── diff.py            # Difference text engine (difflib)
│   ├── search.py          # Fuzzy query index (RapidFuzz)
│   ├── selection.py       # Selection pins coordinator
│   ├── staleness.py       # Version change verification
│   └── llm.py             # LLM executor (Gemini / OpenAI / Mock)
└── utils/
    └── helpers.py         # Whitespace normalizer & SHA256 hashes
tests/
├── conftest.py            # Fixtures, SQLite memory DB, Mock MongoDB setup
├── test_parser.py         # Duplicate/nested heading test scenarios
├── test_versioning.py     # Alignment & diff validation tests
├── test_generation.py     # Selections & staleness verification tests
└── test_api.py            # Full workflow integration tests
main.py                    # FastAPI entrypoint
README.md                  # Installation, running, and API docs
Approach.md                # Decision log and architectural tradeoffs
requirements.txt           # Python dependency tree
Dockerfile                 # Multi-stage production container setup
docker-compose.yml         # Dev/Prod local services orchestrator
.env.example               # Config environment settings variables
```

---

## 2. Installation and Local Setup

### Prerequisite Dependencies
Ensure you have the following installed on your system:
- **Python 3.12**
- **Docker** and **Docker Compose**
- **Git**

### Step A: Clone the Repository
```bash
git clone <repository_url> smlqo1
cd smlqo1
```

### Step B: Create a Virtual Environment and Install Dependencies
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Step C: Configure Environment Variables
Copy the `.env.example` template to `.env` and fill in your details:
```bash
cp .env.example .env
```
*Modify the `GEMINI_API_KEY` or `OPENAI_API_KEY` in the `.env` file if you wish to run on cloud models. By default, `LLM_PROVIDER="mock"` is configured to run entirely offline.*

---

## 3. Database & Services Launch

### Step A: Start MongoDB
Start a local MongoDB container using Docker Compose:
```bash
docker-compose up -d mongodb
```
*Verify MongoDB is listening on port `27017`.*

### Step B: Run Alembic Database Migrations
Initialize the SQLite database schema by executing the Alembic scripts:
```bash
# Verify initial tables are created via Alembic upgrade command
alembic upgrade initial_revision
```
*(FastAPI also auto-creates SQLite schemas on start if they do not exist as a fallback).*

### Step C: Start the FastAPI Server
Launch the development server:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
- **Local Host URL**: `http://127.0.0.1:8000`
- **Swagger Documentation UI**: `http://127.0.0.1:8000/docs`

---

## 4. Run Unit and Integration Tests

Execute the full test suite with coverage:
```bash
pytest -v
```

---

## 5. Walkthrough Workflow & API Commands

Follow these cURL commands to execute the complete QA test sequence. 

### Step 1: Upload Version 1 PDF
*Ensure you have a sample PDF document inside your working directory named `CardioTrack_v1.pdf`.*
```bash
curl -X POST "http://127.0.0.1:8000/documents/upload" \
  -F "name=CardioTrack CT-200" \
  -F "file=@CardioTrack_v1.pdf"
```
**Sample Response:**
```json
{
  "id": "v1_version_uuid",
  "document_id": "document_uuid",
  "version_number": 1,
  "file_path": "documents/document_uuid_v1.pdf"
}
```

### Step 2: Browse the Reconstructed Document Tree
Fetch the parsed tree hierarchy for Version 1:
```bash
curl -X GET "http://127.0.0.1:8000/documents/tree/?version_id=v1_version_uuid"
```
*Note down the `id` of a specific requirement node (e.g. `node_uuid_1`).*

### Step 3: Create a Pinned Selection
Group specific requirement nodes under a named pin configuration:
```bash
curl -X POST "http://127.0.0.1:8000/selection" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hypertension QA Group",
    "document_version_id": "v1_version_uuid",
    "node_ids": ["node_uuid_1"]
  }'
```
**Sample Response:**
```json
{
  "id": "selection_uuid",
  "name": "Hypertension QA Group",
  "document_version_id": "v1_version_uuid",
  "selection_hash": "selection_hash_value",
  "created_at": "2026-07-16T12:00:00"
}
```

### Step 4: Generate QA Test Cases
Invoke the test case generation engine using the saved selection:
```bash
curl -X POST "http://127.0.0.1:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "selection_id": "selection_uuid",
    "llm_provider": "mock"
  }'
```
**Sample Response:**
```json
{
  "id": "generation_uuid",
  "selection_id": "selection_uuid",
  "selection_hash": "selection_hash_value",
  "llm_provider": "mock",
  "model_name": "gemini-1.5-flash",
  "status": "SUCCESS",
  "created_at": "2026-07-16T12:05:00"
}
```

### Step 5: Retrieve Generated Test Cases
Fetch details and the Pydantic-validated test case list (joined from MongoDB):
```bash
curl -X GET "http://127.0.0.1:8000/generation/generation_uuid"
```
**Sample Response:**
```json
{
  "id": "generation_uuid",
  "status": "SUCCESS",
  "test_cases": [
    {
      "test_id": "TC-001",
      "title": "Systolic Blood Pressure Range Limit Testing",
      "requirement_ref": "System Specifications",
      "preconditions": ["CardioTrack CT-200 is on."],
      "steps": ["Step 1...", "Step 2..."],
      "expected_result": "Displays pressure correctly.",
      "priority": "HIGH",
      "risk": "MAJOR",
      "reason": "HYPERTENSIVES SAFETY"
    }
  ]
}
```

### Step 6: Upload Version 2 PDF (Revision)
Upload a revised manual. The system aligns requirement sections to preserve ID mappings:
```bash
curl -X POST "http://127.0.0.1:8000/documents/version" \
  -F "document_id=document_uuid" \
  -F "file=@CardioTrack_v2.pdf"
```

### Step 7: Inspect Section Diffs
Browse the new Version 2 tree via `/documents/tree/?version_id=v2_version_uuid` and locate the new node ID of the modified section (`node_uuid_2`).
Check the precise differences against its sibling in Version 1:
```bash
curl -X GET "http://127.0.0.1:8000/diff/node_uuid_2"
```
**Sample Response:**
```json
{
  "added_text": "Apply pressure up to 180 mmHg.",
  "removed_text": "Apply pressure up to 150 mmHg.",
  "similarity_score": 0.88,
  "changed_hash": "updated_node_hash_value",
  "diff_summary": "Added 1 line of text. Removed 1 line of text."
}
```

### Step 8: Verify Staleness Status of Past Generation
Query the system to confirm if the test cases generated in Step 4 are still valid or are now outdated:
```bash
curl -X GET "http://127.0.0.1:8000/staleness/generation_uuid"
```
**Sample Response:**
```json
{
  "status": "Outdated",
  "reason": "Generation is outdated because 1 selected node(s) were modified in version 2.",
  "modified_node_ids": ["node_uuid_1"],
  "deleted_node_ids": [],
  "new_version_available": true
}
```
*If a node was modified, it returns "Outdated". If the node is unchanged but a new manual version exists, it returns "Possibly Stale".*
=======
# Document-Management-API
>>>>>>> 27724071fb7c96520796e866780460c37640bf83
