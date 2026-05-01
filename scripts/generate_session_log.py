#!/usr/bin/env python3
"""
SessionEnd hook: reads the conversation JSONL and generates a session log
from the raw transcript — no API calls, no cost.

Extracts: user messages, files created/modified, git commits made.
Writes docs/dev-log/session-NNN.md and appends a row to index.md.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_transcript(transcript_path: str):
    """
    Returns:
      user_messages: list of str (what the user typed)
      files_written: list of str (paths passed to Write tool)
      files_edited:  list of str (paths passed to Edit tool)
      commits:       list of str (git commit -m values found in Bash calls)
    """
    user_messages = []
    files_written = []
    files_edited = []
    commits = []

    with open(transcript_path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # User text messages (skip tool_result blocks)
            if entry.get("type") == "user":
                content = entry.get("message", {}).get("content", "")
                if isinstance(content, str):
                    text = content.strip()
                    if text:
                        user_messages.append(text)
                elif isinstance(content, list):
                    parts = [
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    text = " ".join(parts).strip()
                    if text:
                        user_messages.append(text)

            # Assistant tool calls
            elif entry.get("type") == "assistant":
                content = entry.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    inp = block.get("input", {})

                    if name == "Write":
                        path = inp.get("file_path", "")
                        if path:
                            files_written.append(path)

                    elif name == "Edit":
                        path = inp.get("file_path", "")
                        if path and path not in files_edited:
                            files_edited.append(path)

                    elif name == "Bash":
                        cmd = inp.get("command", "")
                        # Extract git commit messages
                        m = re.search(r'git commit -m ["\']([^"\']+)["\']', cmd)
                        if not m:
                            # HEREDOC style
                            m = re.search(r'git commit -m.*?EOF\n(.*?)\n.*?EOF', cmd, re.DOTALL)
                            if m:
                                first_line = m.group(1).strip().splitlines()[0].strip()
                                commits.append(first_line)
                        else:
                            commits.append(m.group(1).split("\n")[0].strip())

    return user_messages, files_written, files_edited, commits


def shorten_path(path: str, cwd: str) -> str:
    """Make absolute path relative to project root if possible."""
    try:
        return str(Path(path).relative_to(cwd))
    except ValueError:
        return path


def next_session_number(dev_log_dir: Path) -> int:
    numbers = []
    for f in dev_log_dir.glob("session-???.md"):
        m = re.search(r"session-(\d+)", f.stem)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def append_to_index(dev_log_dir: Path, session_num: int, date: str, focus: str):
    index_path = dev_log_dir / "index.md"
    content = index_path.read_text()
    filename = f"session-{session_num:03d}.md"
    new_row = f"| {session_num} | {date} | {focus} | [{filename}]({filename}) |"

    lines = content.splitlines()
    last_row_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\|\s*\d+\s*\|", line):
            last_row_idx = i

    if last_row_idx is not None:
        lines.insert(last_row_idx + 1, new_row)
    else:
        lines.append(new_row)

    index_path.write_text("\n".join(lines) + "\n")


def build_session_log(session_num: int, date: str, cwd: str,
                      user_messages, files_written, files_edited, commits) -> tuple[str, str]:
    """Returns (markdown_content, one_line_focus)."""

    # Focus: first substantive user message, trimmed
    focus = next((m for m in user_messages if len(m) > 10), "general session work")
    focus = re.sub(r'\s+', ' ', focus).strip()
    if len(focus) > 60:
        focus = focus[:57] + "..."

    lines = [
        f"# Session {session_num:03d} — {date}",
        "",
        "## What Was Asked",
    ]
    for i, msg in enumerate(user_messages, 1):
        # Truncate very long messages (screenshots, pastes)
        display = msg if len(msg) <= 200 else msg[:197] + "..."
        display = display.replace("\n", " ")
        lines.append(f"{i}. {display}")

    if files_written or files_edited:
        lines += ["", "## Files Touched"]
        seen = set()
        for path in files_written:
            rel = shorten_path(path, cwd)
            if rel not in seen:
                lines.append(f"- `{rel}` (created)")
                seen.add(rel)
        for path in files_edited:
            rel = shorten_path(path, cwd)
            if rel not in seen:
                lines.append(f"- `{rel}` (modified)")
                seen.add(rel)

    if commits:
        lines += ["", "## Commits Made"]
        for c in commits:
            lines.append(f"- {c}")

    lines += ["", "## Notes", "_Add context, decisions, or issues here after reviewing._"]

    return "\n".join(lines) + "\n", focus


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("[session-log] No payload received, skipping.")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("[session-log] Could not parse hook payload, skipping.")
        return

    transcript_path = payload.get("transcript_path", "")
    cwd = payload.get("cwd", os.getcwd())
    project_root = Path(cwd)
    dev_log_dir = project_root / "docs" / "dev-log"

    if not transcript_path or not Path(transcript_path).exists():
        print("[session-log] No transcript file found, skipping.")
        return

    if not dev_log_dir.exists():
        print(f"[session-log] {dev_log_dir} does not exist, skipping.")
        return

    user_messages, files_written, files_edited, commits = parse_transcript(transcript_path)

    if len(user_messages) < 2:
        print("[session-log] Session too short to log, skipping.")
        return

    session_num = next_session_number(dev_log_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    content, focus = build_session_log(
        session_num, date, cwd,
        user_messages, files_written, files_edited, commits,
    )

    session_file = dev_log_dir / f"session-{session_num:03d}.md"
    session_file.write_text(content)
    append_to_index(dev_log_dir, session_num, date, focus)

    subprocess.run(["git", "add", str(dev_log_dir)], cwd=cwd, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"docs: auto-generate session {session_num:03d} log [skip ci]"],
        cwd=cwd, capture_output=True,
    )

    print(f"[session-log] Written session-{session_num:03d}.md and updated index.md")


if __name__ == "__main__":
    main()
