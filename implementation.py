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



---

## `config.py`




---

## `models.py`

