# AI Engineering Team — Demo Log

**Feature Request:** Build a pipeline service in Python that accepts a GitHub repository URL and a
feature description, clones the repo, analyzes the existing codebase structure,
and generates a ready-to-merge pull request with implementation code, tests,
and a PR description. The service should expose a REST API endpoint, handle
errors gracefully, and clean up temporary files after the PR is created.

**Generated:** 2026-03-17 12:02:24

---

## 🏗️ Architect

> Output saved to `architecture.md`

# Architecture Plan: AI-Powered PR Generation Service

## Component Breakdown

**1. API Layer** (`FastAPI`)
- Single endpoint: `POST /generate-pr`
- Request validation via Pydantic models
- Async request handling with job ID response (async pattern — this will be slow)

**2. Job Queue** (`Celery + Redis`)
- Offloads long-running pipeline tasks
- `GET /jobs/{job_id}` for status polling
- Prevents HTTP timeouts on large repos

**3. Pipeline Orchestrator** (core module)
- Coordinates sequential stages, passes context between them
- Handles stage failures with rollback/cleanup hooks

**4. Pipeline Stages** (discrete modules)
- `RepoCloner`: GitPython to clone into isolated `/tmp/{job_id}/` sandbox
- `CodeAnalyzer`: AST parsing (built-in `ast`), file tree mapping, dependency detection
- `CodeGenerator`: LLM client (OpenAI/Anthropic) — sends analyzed context + feature description
- `PRCreator`: PyGitHub to branch, commit, and open PR against origin

**5. Cleanup Service** (context manager pattern)
- Guaranteed temp directory removal via `try/finally` in orchestrator
- Runs regardless of success or failure

## Data Flow

```
Client → FastAPI → Celery Queue → Orchestrator
                                      ↓
                    RepoCloner → CodeAnalyzer → CodeGenerator → PRCreator
                                                                    ↓
                                                            GitHub API → PR URL
                                      ↓
                                  Cleanup → Job Result Store (Redis)
```

## Key Tech Choices

| Choice | Reason |
|---|---|
| FastAPI | Native async, automatic OpenAPI docs |
| Celery + Redis | Battle-tested async task queue, simple setup |
| GitPython | Full Git control without subprocess hacking |
| PyGitHub | Clean GitHub API abstraction |
| LLM with structured output | Force JSON schema response for code + tests + PR description |

## Scaling Concerns

- **Repo size**: Enforce clone depth (`--depth=1`) and size limits (reject >500MB)
- **LLM context limits**: Summarize large files; send only relevant modules
- **Concurrency**: Each job gets isolated temp directory — no shared state
- **Rate limits**: GitHub API throttling needs exponential backoff + token rotation

---

## 💻 Developer

> Output saved to `implementation.py`

# AI-Powered PR Generation Service — Full Implementation

## Project Structure

```
pr_gen_service/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings management
├── celery_app.py            # Celery + Redis worker setup
├── models.py                # Pydantic request/response models
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py      # Pipeline coordinator
│   ├── cloner.py            # Git clone stage
│   ├── analyzer.py          # Codebase analysis stage
│   ├── generator.py         # LLM code generation stage
│   └── pr_creator.py        # GitHub PR creation stage
├── utils/
│   ├── cleanup.py           # Temp file management
│   ├── github_client.py     # PyGitHub wrapper
│   └── llm_client.py        # OpenAI/Anthropic client
├── requirements.txt
└── docker-compose.yml
```

---

## `requirements.txt`

```txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
celery==5.4.0
redis==5.0.4
gitpython==3.1.43
PyGithub==2.3.0
openai==1.30.0
pydantic-settings==2.2.1
pydantic==2.7.1
tenacity==8.3.0
httpx==0.27.0
python-dotenv==1.0.1
```

---

## `config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- LLM ---
    openai_api_key: str
    openai_model: str = "gpt-4o"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.2          # Low temp = deterministic code output

    # --- GitHub ---
    github_token: str                      # PAT with repo + PR write scopes
    github_bot_username: str = "pr-gen-bot"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Pipeline Limits ---
    max_repo_size_mb: int = 500
    clone_depth: int = 1                   # Shallow clone keeps things fast
    max_file_size_kb: int = 100            # Skip huge generated/binary files
    max_files_analyzed: int = 150          # Cap LLM context size
    analysis_extensions: list[str] = [
        ".py", ".js", ".ts", ".go", ".java",
        ".rb", ".rs", ".cpp", ".c", ".cs",
    ]

    # --- Service ---
    temp_base_dir: str = "/tmp/pr_gen"
    job_result_ttl_seconds: int = 3600     # Keep job results 1 hour

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

---

## `models.py`

```python
from pydantic import BaseModel, HttpUrl, field_validator
from enum import Enum
from typing import Optional
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    CREATING_PR = "creating_pr"
    COMPLETED = "completed"
    FAILED = "failed"


class PRGenerationRequest(BaseModel):
    repo_url: HttpUrl
    feature_description: str
    base_branch: str = "main"
    pr_branch_prefix: str = "feature/ai-gen"

    @field_validator("feature_description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Feature description must be at least

---

## 🔒 Security Reviewer

> Output saved to `security_report.md`

# Security Review: AI-Powered PR Generation Service

## Threat Model Summary

This service is **exceptionally high-risk** by nature. It accepts untrusted URLs, clones untrusted code onto your infrastructure, feeds that code to an LLM, then writes back to GitHub with an authenticated token. Every stage is an attack surface. The developer's implementation has good instincts but several critical gaps that would make this **exploitable in production as written**.

---

## Risk Registry

| # | Risk | Severity | CVSS Estimate | Stage |
|---|------|----------|---------------|-------|
| 1 | SSRF via repo URL + path traversal in clone destination | **Critical** | 9.3 | Cloner |
| 2 | Prompt injection via malicious repo content → arbitrary code committed | **Critical** | 9.1 | Analyzer → Generator |
| 3 | GitHub token over-scoped + no PR scope isolation | **High** | 8.2 | PR Creator |
| 4 | Symlink attack in cloned repo escapes temp sandbox | **High** | 7.8 | Analyzer |
| 5 | LLM-generated code executed without sandbox during test generation | **High** | 7.6 | Generator |
| 6 | Job result data leaks repo contents via Redis without encryption | **Medium** | 6.1 | Queue |
| 7 | No rate limiting → resource exhaustion / GitHub token burn | **Medium** | 5.9 | API Layer |

---

## Critical Risk #1: SSRF + Path Traversal

### The Problem

The `repo_url: HttpUrl` validator accepts any URL that Pydantic considers valid. An attacker can:

```python
# These all pass Pydantic's HttpUrl validation
"http://169.254.169.254/latest/meta-data/"          # AWS metadata SSRF
"http://internal-github-enterprise.corp/evil/repo"  # Internal network pivot
"file:///etc/passwd"                                # Local file read via GitPython
"https://github.com/x/y/../../../etc/passwd"        # Path traversal attempt

# The clone destination in developer's code:
clone_path = os.path.join(settings.temp_base_dir, job_id)
# If job_id were ever user-influenced (future bug), this escapes /tmp/pr_gen/
```

### The Fix

```python
# utils/url_validator.py
import ipaddress
import re
from urllib.parse import urlparse
from typing import Final
import socket

# Allowlist approach — only GitHub/GitLab/Bitbucket public hosts
ALLOWED_HOSTS: Final[frozenset] = frozenset({
    "github.com",
    "gitlab.com",
    "bitbucket.org",
})

# Block all RFC-1918 + loopback + link-local ranges
BLOCKED_IP_NETWORKS: Final[list] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # AWS/GCP/Azure metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

# Only allow standard GitHub repo URL pattern
GITHUB_REPO_PATTERN: Final[re.Pattern] = re.compile(
    r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/?$"
)


class URLValidationError(ValueError):
    pass


def validate_repo_url(url: str) -> str:
    """
    Strict allowlist validation. Fails closed — rejects anything not
    explicitly permitted. Resolves DNS to block SSRF via DNS rebinding.
    """
    url = url.strip()

    # 1. Schema must be HTTPS only — no file://, git://, ssh://
    parsed = urlparse(url)

---

## 🧪 QA Engineer

> Output saved to `test_suite.py`

# QA Engineer: Test Plan & Implementation

## Test Strategy Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST PYRAMID                             │
│                                                             │
│                    ┌─────────┐                              │
│                    │  E2E /  │  ← 5%  (real GitHub, real   │
│                    │  Load   │         LLM, full pipeline)  │
│                   /─────────\                               │
│                  /           \                              │
│                 / Integration \  ← 25% (mocked externals,  │
│                /───────────────\         real logic)        │
│               /                 \                           │
│              /    Unit Tests     \  ← 70% (pure logic,      │
│             /─────────────────────\       fast, isolated)   │
└─────────────────────────────────────────────────────────────┘
```

## Project Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── test_url_validator.py      # Security: URL validation
│   ├── test_models.py             # Pydantic model validation
│   ├── test_analyzer.py           # Codebase analysis logic
│   ├── test_generator.py          # LLM prompt building + response parsing
│   ├── test_cleanup.py            # Temp file cleanup
│   └── test_orchestrator.py      # Pipeline state machine
├── integration/
│   ├── test_api_endpoints.py      # FastAPI route testing
│   ├── test_pipeline_stages.py    # Stage-to-stage data flow
│   ├── test_celery_tasks.py       # Task queue behavior
│   └── test_github_client.py     # GitHub API wrapper
├── security/
│   └── test_security_controls.py # All security reviewer findings
├── load/
│   └── locustfile.py             # Load test scenarios
└── fixtures/
    ├── sample_repos/              # Minimal fake repo structures
    │   ├── python_project/
    │   ├── empty_project/
    │   └── large_project/
    └── llm_responses/            # Canned LLM JSON responses
```

---

## `tests/conftest.py`

```python
import pytest
import tempfile
import os
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient


# ── Paths ──────────────────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"
LLM_RESPONSES_DIR = FIXTURES_DIR / "llm_responses"
SAMPLE_REPOS_DIR = FIXTURES_DIR / "sample_repos"


# ── Settings override for ALL tests ────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """
    Inject safe test-only settings before any module imports Settings.
    Prevents accidental calls to real GitHub/OpenAI APIs.
    """
    test_env = {
        "OPENAI_API_KEY": "sk-test-000000000000000000000000000000000000000000",
        "GITHUB_TOKEN": "ghp_test000000000000000000000000000000000",
        "GITHUB_BOT_USERNAME": "test-bot",
        "REDIS_URL": "redis://localhost:6379/15",  # DB 15 = test-only DB
        "TEMP_BASE_DIR": "/tmp/pr_gen_test",
        "MAX_REPO_SIZE_MB": "50",
        "MAX_FILES_ANALYZED": "20",
    }
    with patch.dict(os.environ, test_env):
        yield


# ── Temp directory management ───────────────────────────────────────────────
@pytest.fixture
def temp_dir():
    """Isolated temp dir per test — cleaned up

---

## ⭐ Tech Lead

> Output saved to `review.md`

# Tech Lead Final Review: AI-Powered PR Generation Service

## Executive Summary

The team has done solid work. The architecture is sound, the security review caught real critical issues, and the test plan is thorough. But there are **gaps between the three outputs** that would cause this to fail in production. My job here is to identify exactly what needs to close before this ships, what's acceptable as logged tech debt, and what I'd reject outright.

---

## Cross-Cutting Assessment

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPONENT HEALTH MATRIX                              │
├──────────────────────┬──────────┬───────────────────────────────────────┤
│ Component            │ Status   │ Note                                  │
├──────────────────────┼──────────┼───────────────────────────────────────┤
│ API Layer            │ ⚠ REVIEW │ Missing auth, rate limiting           │
│ Job Queue            │ ✅ GOOD  │ Celery/Redis pattern is correct        │
│ RepoCloner           │ ❌ BLOCK │ SSRF fix exists but not wired in      │
│ CodeAnalyzer         │ ⚠ REVIEW │ Symlink protection incomplete         │
│ CodeGenerator        │ ❌ BLOCK │ LLM-generated code not sandboxed      │
│ PRCreator            │ ⚠ REVIEW │ Token scope isolation missing         │
│ Cleanup Service      │ ✅ GOOD  │ Context manager pattern solid         │
│ Security Controls    │ ⚠ REVIEW │ Identified but partially implemented  │
│ Test Coverage        │ ⚠ REVIEW │ Security tests + load tests good,     │
│                      │          │ E2E tests missing CI gate              │
│ Observability        │ ❌ BLOCK │ No structured logging, no tracing      │
│ Deployment Config    │ ❌ BLOCK │ docker-compose only, no prod config    │
└──────────────────────┴──────────┴───────────────────────────────────────┘
```

---

## Full Production-Ready Implementation

### Critical Missing Piece #1: Structured Logging & Observability

**This was completely absent from all three prior outputs. You cannot operate this service blind.**

```python
# utils/logger.py
import logging
import sys
import json
from contextvars import ContextVar
from typing import Any
from datetime import datetime, timezone

# Per-request context propagated through async/celery boundaries
current_job_id: ContextVar[str] = ContextVar("job_id", default="no-job")
current_repo: ContextVar[str] = ContextVar("repo", default="unknown")


class StructuredFormatter(logging.Formatter):
    """
    Outputs JSON logs — required for any log aggregation system
    (Datadog, CloudWatch, ELK). Never use plain text logs in production.
    """

    RESERVED_FIELDS = frozenset({"message", "timestamp", "level", "logger"})

    def format(self, record: logging.LogRecord) -> str:
        # Base fields always present on every log line
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # Distributed tracing context — always include
            "job_id": current_job_id.get(),
            "repo": current_repo.get(),
        }

        # Attach any extra fields passed via logger.info(..., extra={})
        for key, value in record.__dict__.items():
            if (
                key not in logging.LogRecord.__dict__
                and key not in self.RESERVED_FIELDS
                and not key.startswith("_")
            ):
                log_entry[key] = value

        # Always capture exceptions with full context
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

---

