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
