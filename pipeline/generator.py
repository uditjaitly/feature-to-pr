import json
import re

import anthropic

from config import settings
from pipeline.analyzer import analyze_repo, build_context_prompt
from pathlib import Path


client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _extract_json(text: str) -> dict:
    """
    Extract the first JSON object from Claude's response.
    Claude sometimes wraps JSON in markdown fences despite instructions.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

    # Find first { ... } block
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in Claude response")

    # Use json decoder to find the end of the first complete object.
    # strict=False allows literal control chars (newlines) inside strings.
    decoder = json.JSONDecoder(strict=False)
    obj, _ = decoder.raw_decode(cleaned, start)
    return obj


def generate_code(repo_path: Path, feature_description: str) -> dict:
    """
    Send analyzed repo context + feature description to Claude.
    Returns parsed dict with files_to_create, files_to_modify, pr_title, pr_body.
    """
    analysis = analyze_repo(repo_path)
    prompt = build_context_prompt(analysis, feature_description)

    full_response = ""
    with client.messages.stream(
        model=settings.model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_response += text
            print(text, end="", flush=True)  # live progress in server logs

    print()  # newline after streaming
    return _extract_json(full_response)
