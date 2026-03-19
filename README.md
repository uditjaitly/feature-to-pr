# Feature-to-PR

An AI-powered service that turns a feature description into a ready-to-review GitHub Pull Request — automatically.

Give it a GitHub repo URL and describe what you want built. It clones the repo, analyzes the codebase, uses Claude to generate the implementation, and opens a real PR with the code changes.

---

## How It Works

```
POST /generate-pr
      │
      ▼
 Clone Repo          (GitPython shallow clone)
      │
      ▼
 Analyze Codebase    (file tree + AST parsing)
      │
      ▼
 Generate Code       (Claude reads full context, returns file changes)
      │
      ▼
 Open GitHub PR      (push branch + PyGitHub PR creation)
      │
      ▼
GET /jobs/{id}  →  { status: "done", pr_url: "https://github.com/..." }
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/uditjaitly/feature-to-pr.git
cd feature-to-pr
pip install -r requirements.txt
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Fill in the two required values:

```env
ANTHROPIC_API_KEY=sk-ant-...       # from console.anthropic.com
GITHUB_TOKEN=github_pat_...        # GitHub fine-grained PAT (see below)
```

#### Creating a GitHub Token

Go to **GitHub → Settings → Developer Settings → Personal access tokens → Fine-grained tokens → Generate new token**

Grant the following permissions on the target repo:
- **Contents**: Read and Write
- **Pull requests**: Read and Write

### 3. Start the service

```bash
uvicorn main:app --port 8001 --reload
```

API docs available at `http://localhost:8001/docs`.

---

## Usage

### Submit a job

```bash
curl -X POST http://localhost:8001/generate-pr \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/your-username/your-repo",
    "feature_description": "Describe the feature you want implemented in plain English.",
    "base_branch": "main"
  }'
```

Response:
```json
{
  "job_id": "4eaad4b4-e61b-43dc-9e81-99f41a38d576",
  "message": "Job submitted. Poll /jobs/{job_id} for status."
}
```

### Poll for status

```bash
curl http://localhost:8001/jobs/4eaad4b4-e61b-43dc-9e81-99f41a38d576
```

Response when done:
```json
{
  "job_id": "4eaad4b4-e61b-43dc-9e81-99f41a38d576",
  "status": "done",
  "pr_url": "https://github.com/your-username/your-repo/pull/1",
  "logs": [
    "[cloning] Cloning https://github.com/your-username/your-repo ...",
    "[analyzing] Analyzing codebase structure ...",
    "[generating] Sending context to Claude, generating implementation ...",
    "[generating] Claude returned: pr_title='Your feature title'",
    "[creating_pr] Writing files and opening GitHub PR ...",
    "[done] PR created: https://github.com/your-username/your-repo/pull/1"
  ]
}
```

Job statuses: `pending` → `cloning` → `analyzing` → `generating` → `creating_pr` → `done` (or `failed`)

---

## Real Example: Adding Search to a Notes API

This service was used to add keyword search to [notes-api](https://github.com/uditjaitly/notes-api), a simple FastAPI CRUD service with no search functionality.

**Request:**
```bash
curl -X POST http://localhost:8001/generate-pr \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/uditjaitly/notes-api",
    "feature_description": "Add search functionality to GET /notes so users can filter notes by keyword. The query param should be ?q=keyword and it should search both the title and body fields case-insensitively.",
    "base_branch": "master"
  }'
```

**Result:** [github.com/uditjaitly/notes-api/pull/1](https://github.com/uditjaitly/notes-api/pull/1)

Claude analyzed the existing `main.py` and `models.py`, then modified `main.py` to add the `?q=` query parameter and updated the README — all without any manual coding.

---

## Running with Docker

```bash
docker-compose up --build
```

The service runs on port `8001`. Make sure your `.env` file is populated before starting.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/generate-pr` | Submit a new job |
| `GET` | `/jobs/{job_id}` | Get job status and result |
| `GET` | `/jobs` | List all jobs |
| `GET` | `/health` | Health check |

---

## Tech Stack

- **FastAPI** — REST API with async background tasks
- **Anthropic Claude** (`claude-sonnet-4-6`) — Code generation
- **GitPython** — Repo cloning
- **PyGitHub** — PR creation via GitHub API
- **In-memory job store** — Simple dict, no Redis needed
