from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class GeneratePRRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL to clone")
    feature_description: str = Field(
        ..., min_length=10, max_length=2000,
        description="Description of the feature to implement"
    )
    base_branch: str = Field(default="main", description="Branch to open PR against")


class JobStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    CREATING_PR = "creating_pr"
    DONE = "done"
    FAILED = "failed"


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    pr_url: Optional[str] = None
    error: Optional[str] = None
    logs: list[str] = []


class GeneratePRResponse(BaseModel):
    job_id: str
    message: str = "Job submitted. Poll /jobs/{job_id} for status."
