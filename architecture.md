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