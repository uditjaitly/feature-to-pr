from pathlib import Path
from typing import Callable

from pipeline.cloner import clone_repo, cleanup
from pipeline.generator import generate_code
from pipeline.pr_creator import create_pr
from config import settings


def run_pipeline(
    job_id: str,
    repo_url: str,
    feature_description: str,
    base_branch: str,
    log: Callable[[str], None],
) -> str:
    """
    Runs the full pipeline: clone → analyze+generate → create PR.
    `log` is a callback to append status messages to the job store.
    Returns the PR URL on success; raises on failure.
    """
    repo_path: Path | None = None
    try:
        # Stage 1: Clone
        log(f"[cloning] Cloning {repo_url} ...")
        repo_path = clone_repo(repo_url, job_id, depth=settings.clone_depth)
        log(f"[cloning] Cloned to {repo_path}")

        # Stage 2+3: Analyze & Generate (combined — LLM sees the full repo)
        log("[analyzing] Analyzing codebase structure ...")
        log("[generating] Sending context to Claude, generating implementation ...")
        generated = generate_code(repo_path, feature_description)
        log(f"[generating] Claude returned: pr_title='{generated.get('pr_title')}'")
        log(f"[generating] Files to create: {list(generated.get('files_to_create', {}).keys())}")
        log(f"[generating] Files to modify: {list(generated.get('files_to_modify', {}).keys())}")

        # Stage 4: Create PR
        log("[creating_pr] Writing files and opening GitHub PR ...")
        pr_url = create_pr(
            repo_path=repo_path,
            repo_url=repo_url,
            github_token=settings.github_token,
            generated=generated,
            base_branch=base_branch,
        )
        log(f"[done] PR created: {pr_url}")
        return pr_url

    finally:
        if repo_path:
            cleanup(repo_path)
            log("[cleanup] Temp directory removed.")
