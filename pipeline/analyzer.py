import ast
from pathlib import Path


# File extensions we care about
CODE_EXTENSIONS = {".py", ".js", ".ts", ".go", ".java", ".rb", ".rs", ".cpp", ".c", ".h"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".env.example"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode"}

MAX_FILE_SIZE_BYTES = 50_000  # 50KB per file to avoid blowing context


def build_file_tree(root: Path, max_depth: int = 4) -> str:
    """Return an indented string file tree."""
    lines = []

    def _walk(path: Path, depth: int):
        if depth > max_depth:
            return
        for item in sorted(path.iterdir()):
            if item.name in IGNORE_DIRS or item.name.startswith("."):
                continue
            prefix = "  " * depth
            if item.is_dir():
                lines.append(f"{prefix}{item.name}/")
                _walk(item, depth + 1)
            else:
                lines.append(f"{prefix}{item.name}")

    _walk(root, 0)
    return "\n".join(lines)


def extract_python_summary(file_path: Path) -> str:
    """Extract top-level classes and functions from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return ""

    summaries = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Only top-level functions (not nested)
                summaries.append(f"  def {node.name}()")
        elif isinstance(node, ast.ClassDef):
            summaries.append(f"  class {node.name}")
    return "\n".join(summaries)


def analyze_repo(root: Path) -> dict:
    """
    Analyze the repo and return a context dict with:
    - file_tree: string representation
    - key_files: dict of {relative_path: content or summary}
    - languages: detected languages
    """
    file_tree = build_file_tree(root)

    key_files: dict[str, str] = {}
    languages: set[str] = set()

    all_files = list(root.rglob("*"))
    for fpath in all_files:
        if not fpath.is_file():
            continue
        # Skip ignored dirs
        if any(part in IGNORE_DIRS for part in fpath.parts):
            continue
        # Skip hidden files
        if fpath.name.startswith("."):
            continue

        suffix = fpath.suffix.lower()
        rel = str(fpath.relative_to(root))

        if suffix in CODE_EXTENSIONS:
            languages.add(suffix.lstrip("."))
            size = fpath.stat().st_size
            if size <= MAX_FILE_SIZE_BYTES:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                key_files[rel] = content
            elif suffix == ".py":
                # Too big — extract structural summary instead
                summary = extract_python_summary(fpath)
                key_files[rel] = f"[FILE TOO LARGE — structural summary]\n{summary}"
            else:
                key_files[rel] = f"[FILE TOO LARGE — {size} bytes]"

        elif suffix in CONFIG_EXTENSIONS or fpath.name in ("README.md", "requirements.txt", "package.json", "go.mod"):
            size = fpath.stat().st_size
            if size <= MAX_FILE_SIZE_BYTES:
                key_files[rel] = fpath.read_text(encoding="utf-8", errors="ignore")

    return {
        "file_tree": file_tree,
        "key_files": key_files,
        "languages": sorted(languages),
    }


def build_context_prompt(analysis: dict, feature_description: str) -> str:
    """Assemble the full prompt to send to Claude."""
    parts = [
        "You are an expert software engineer. Your task is to implement a feature in an existing codebase.",
        "",
        f"## Feature to Implement\n{feature_description}",
        "",
        "## Repository File Tree",
        "```",
        analysis["file_tree"],
        "```",
        "",
        f"## Detected Languages: {', '.join(analysis['languages']) or 'unknown'}",
        "",
        "## Key Files",
    ]

    for rel_path, content in analysis["key_files"].items():
        parts.append(f"\n### `{rel_path}`\n```\n{content}\n```")

    parts += [
        "",
        "## Your Task",
        "Produce a JSON object with exactly these keys:",
        '  "files_to_create": { "<relative_path>": "<full file content>" }',
        '  "files_to_modify": { "<relative_path>": "<full updated file content>" }',
        '  "pr_title": "<concise PR title>"',
        '  "pr_body": "<markdown PR description explaining the change>"',
        "",
        "Rules:",
        "- Only include files that are new or changed.",
        "- Provide the COMPLETE file content (not diffs).",
        "- Follow the existing code style and conventions.",
        "- Include tests if the repo has a test directory.",
        "- Respond with valid JSON only — no markdown fences around the JSON itself.",
    ]

    return "\n".join(parts)
