"""
Feature-to-PR Service
=====================
POST /generate-pr   — Submit a job (returns job_id immediately)
GET  /jobs/{job_id} — Poll for status and result
GET  /health        — Health check
"""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks

from config import settings
from models import GeneratePRRequest, GeneratePRResponse, JobResult, JobStatus
from pipeline.orchestrator import run_pipeline

app = FastAPI(
    title="Feature-to-PR Service",
    description="Clone a GitHub repo, implement a feature with Claude, open a PR.",
    version="1.0.0",
)

# In-memory job store: { job_id: JobResult }
_jobs: dict[str, JobResult] = {}


# --- Helpers ---

def _get_job(job_id: str) -> JobResult:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


def _run_job(job_id: str, repo_url: str, feature_description: str, base_branch: str):
    """Background task: runs the pipeline and updates the job store."""

    def log(msg: str):
        print(f"[job:{job_id}] {msg}", flush=True)
        _jobs[job_id].logs.append(msg)

    job = _jobs[job_id]

    try:
        job.status = JobStatus.CLONING
        log(f"Starting pipeline for repo: {repo_url}")

        pr_url = run_pipeline(
            job_id=job_id,
            repo_url=repo_url,
            feature_description=feature_description,
            base_branch=base_branch,
            log=log,
        )

        job.status = JobStatus.DONE
        job.pr_url = pr_url
        log(f"Pipeline complete. PR: {pr_url}")

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        log(f"Pipeline failed: {exc}")


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "ok", "model": settings.model}


@app.post("/generate-pr", response_model=GeneratePRResponse, status_code=202)
def generate_pr(req: GeneratePRRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobResult(job_id=job_id, status=JobStatus.PENDING)

    background_tasks.add_task(
        _run_job,
        job_id=job_id,
        repo_url=req.repo_url,
        feature_description=req.feature_description,
        base_branch=req.base_branch,
    )
    return GeneratePRResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobResult)
def get_job(job_id: str):
    return _get_job(job_id)


@app.get("/jobs", response_model=list[JobResult])
def list_jobs():
    return list(_jobs.values())
