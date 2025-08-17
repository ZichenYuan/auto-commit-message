#!/usr/bin/env python3
import os
import re
import textwrap
import subprocess
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from openai import OpenAI

# ----- Configuration -----
APP_NAME = "commit-buddy"
MAX_DIFF_CHARS = int(os.getenv("COMMIT_BUDDY_MAX_DIFF_CHARS", "200000"))
ALLOWED_ROOTS = [Path(p).resolve() for p in os.getenv("COMMIT_BUDDY_ALLOWED_ROOTS", "").split(":") if p.strip()]
DEFAULT_OPENAI_MODEL = os.getenv("COMMIT_BUDDY_OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("COMMIT_BUDDY_TEMPERATURE", "0.2"))

SECRET_PATTERNS = [
    (re.compile(r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*=\s*([A-Za-z0-9/+=]{20,})'), 'aws_secret_access_key=***'),
    (re.compile(r'(?i)api[_-]?key\s*=\s*([A-Za-z0-9_-]{16,})'), 'api_key=***'),
    (re.compile(r'(?i)authorization:\s*Bearer\s+[A-Za-z0-9._-]{16,}'), 'authorization: Bearer ***'),
    (re.compile(r'(?i)password\s*=\s*[^ \n]+'), 'password=***'),
    (re.compile(r'(?i)secret\s*=\s*[^ \n]+'), 'secret=***'),
]

mcp = FastMCP(APP_NAME)

# ----- Helpers -----
def check_allowed(path: Path) -> None:
    if not ALLOWED_ROOTS:
        return  # no restriction configured
    # Ensure the repo (or subdir) is inside at least one allowed root
    if not any(str(path).startswith(str(root)) for root in ALLOWED_ROOTS):
        raise RuntimeError(
            f"Path {path} is not in COMMIT_BUDDY_ALLOWED_ROOTS. "
            "Set COMMIT_BUDDY_ALLOWED_ROOTS to allow this repo."
        )

def run_git(args, cwd: Path) -> str:
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()

def ensure_repo(path: str) -> Path:
    p = Path(path).resolve()
    check_allowed(p)
    # confirm we're inside a git repo
    _ = run_git(["rev-parse", "--show-toplevel"], cwd=p)
    return p

def redact_secrets(text: str) -> str:
    redacted = text
    for pat, replacement in SECRET_PATTERNS:
        redacted = pat.sub(replacement, redacted)
    return redacted

def get_current_branch(cwd: Path) -> str:
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)

def has_remote(cwd: Path, remote: str) -> bool:
    remotes = run_git(["remote"], cwd=cwd).splitlines()
    return remote in remotes

def openai_generate_commit_message(diff: str, language: Optional[str], model: str, temperature: float) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Cannot generate commit message.")
    client = OpenAI(api_key=api_key)

    system_prompt = "You are a senior engineer who writes excellent Conventional Commits."
    user_prompt = textwrap.dedent(f"""
    Generate a clear, **Conventional Commits** style commit message based on the unified git diff below.

    Requirements:
    - Start with a conventional type (feat, fix, docs, style, refactor, test, chore, perf, build, ci).
    - A concise subject line (≤ 72 chars).
    - Optional body lines with bullet points summarizing key changes.
    - No code fences in the output. Plain text only.
    - If the changes are trivial (whitespace, typos), use "chore:" or "style:" accordingly.
    - {"Write it in " + language + "." if language else "Write in English."}

    Git diff:
    {diff}
    """)

    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=220,
    )
    msg = resp.choices[0].message.content.strip()
    # Defensive: strip surrounding quotes or code fences if any slipped in
    msg = msg.strip().strip("`").strip()
    return msg

# ----- Tools -----
@mcp.tool()
def get_git_diff(
    path: str = ".",
    staged_only: bool = True,
    context_lines: int = 3,
    filter_path: Optional[str] = None,
    max_chars: Optional[int] = None
) -> str:
    """Return a (redacted) unified git diff. Use staged_only=true to only show staged changes."""
    repo = ensure_repo(path)
    args = ["diff", f"-U{context_lines}"]
    if staged_only:
        args.insert(1, "--staged")
    if filter_path:
        args.append(filter_path)

    diff = run_git(args, cwd=repo)
    if not diff:
        return "[commit-buddy] No changes detected (diff is empty)."

    diff = redact_secrets(diff)
    limit = max_chars if (isinstance(max_chars, int) and max_chars > 0) else MAX_DIFF_CHARS
    if len(diff) > limit:
        diff = diff[:limit] + "\n[commit-buddy] Diff truncated for size.\n"
    return diff

@mcp.tool()
def stage_all(path: str = ".", pattern: Optional[str] = None) -> str:
    """Stage changes. If pattern is provided, runs `git add <pattern>`, else `git add -A`."""
    repo = ensure_repo(path)
    if pattern:
        run_git(["add", pattern], cwd=repo)
        return f"[commit-buddy] Staged changes matching: {pattern}"
    run_git(["add", "-A"], cwd=repo)
    return "[commit-buddy] Staged all changes."

@mcp.tool()
def generate_commit_message(
    path: str = ".",
    staged_only: bool = True,
    language: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> str:
    """Generate a Conventional Commits–style message from git diff via OpenAI."""
    repo = ensure_repo(path)
    args = ["diff", "--staged"] if staged_only else ["diff"]
    diff = run_git(args, cwd=repo)
    if not diff:
        return "[commit-buddy] No changes detected; nothing to describe."
    print(diff)
    return "testing commit message"

    # diff = redact_secrets(diff)
    # if len(diff) > MAX_DIFF_CHARS:
    #     diff = diff[:MAX_DIFF_CHARS] + "\n[commit-buddy] Diff truncated for size.\n"

    # mdl = model or DEFAULT_OPENAI_MODEL
    # temp = OPENAI_TEMPERATURE if temperature is None else float(temperature)
    # message = openai_generate_commit_message(diff=diff, language=language, model=mdl, temperature=temp)
    return message

@mcp.tool()
def commit_and_push(
    path: str = ".",
    message: str = "",
    signoff: bool = False,
    branch: Optional[str] = None,
    remote: str = "origin",
    push: bool = True,
    allow_main_push: bool = False,
    generate_if_empty: bool = True,
    staged_only_for_gen: bool = True,
    dry_run: bool = False,
    language: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> str:
    """
    Commit (and optionally push). If `message` is empty and `generate_if_empty=true`,
    generates a Conventional Commits message from the repo diff via OpenAI.

    Safety:
    - Set allow_main_push=false to block pushing to main/master.
    - Set dry_run=true to preview without executing commit/push.
    """
    repo = ensure_repo(path)

    # Ensure there is something to commit
    status = run_git(["status", "--porcelain"], cwd=repo)
    if not status:
        return "[commit-buddy] Nothing to commit."

    # Determine branch early for safety checks
    current_branch = branch or get_current_branch(repo)

    # Branch guard
    if push and not allow_main_push and current_branch in ("main", "master"):
        return f"[commit-buddy] Push blocked: refusing to push directly to {current_branch}. Set allow_main_push=true to override."

    # Autogenerate message if needed
    final_message = (message or "").strip()
    if not final_message and generate_if_empty:
        # Use the same generator logic as the tool
        args = ["diff", "--staged"] if staged_only_for_gen else ["diff"]
        diff = run_git(args, cwd=repo)
        if not diff:
            return "[commit-buddy] No changes detected for message generation."
        diff = redact_secrets(diff)
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n[commit-buddy] Diff truncated for size.\n"
        mdl = model or DEFAULT_OPENAI_MODEL
        temp = OPENAI_TEMPERATURE if temperature is None else float(temperature)
        final_message = openai_generate_commit_message(diff=diff, language=language, model=mdl, temperature=temp)

    if not final_message:
        raise RuntimeError("Commit message is required (generation disabled or failed).")

    if dry_run:
        return textwrap.dedent(f"""\
        [commit-buddy] DRY RUN
        Branch: {current_branch}
        Remote: {remote}
        Message:
        {final_message}
        (No commit/push executed.)
        """)

    # Commit
    commit_args = ["commit", "-m", final_message]
    if signoff:
        commit_args.append("--signoff")
    run_git(commit_args, cwd=repo)

    # Optionally push
    if push:
        if not has_remote(repo, remote):
            raise RuntimeError(f"Remote '{remote}' not found. Add it with 'git remote add {remote} <url>'.")
        # Ensure upstream exists
        try:
            _ = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=repo)
            run_git(["push", remote, current_branch], cwd=repo)
        except Exception:
            run_git(["push", "--set-upstream", remote, current_branch], cwd=repo)
        return f"[commit-buddy] Committed and pushed to {remote}/{current_branch}."
    else:
        return f"[commit-buddy] Committed locally on {current_branch}. Push skipped."
# ----- Runner -----
if __name__ == "__main__":
    mcp.run()
