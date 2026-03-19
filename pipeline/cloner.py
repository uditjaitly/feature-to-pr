import shutil
import tempfile
from pathlib import Path

import git


def clone_repo(repo_url: str, job_id: str, depth: int = 1) -> Path:
    """
    Shallow-clone a GitHub repo into an isolated temp directory.
    Returns the path to the cloned repo.
    """
    dest = Path(tempfile.gettempdir()) / f"fpr_{job_id}"
    dest.mkdir(parents=True, exist_ok=True)

    git.Repo.clone_from(
        repo_url,
        str(dest),
        depth=depth,
        single_branch=True,
    )
    return dest


def cleanup(path: Path) -> None:
    """Remove the temp directory for a job."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
