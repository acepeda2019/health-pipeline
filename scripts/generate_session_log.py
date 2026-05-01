#!/usr/bin/env python3
"""
SessionEnd hook: reads the conversation JSONL, calls Claude API to generate
a structured session log, writes docs/dev-log/session-NNN.md, and appends
a row to docs/dev-log/index.md.

Invoked automatically by Claude Code on session end.
Reads the hook payload JSON from stdin.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_transcript(transcript_path: str) -> str:
    """Extract human-readable user/assistant exchanges from JSONL."""
    messages = []
    with open(transcript_path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "user":
                content = entry.get("message", {}).get("content", "")
                if isinstance(content, str):
                    text = content.strip()
                elif isinstance(content, list):
                    # Skip tool_result blocks; keep plain text blocks
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    text = " ".join(parts).strip()
                else:
                    continue
                if text:
                    messages.append(f"USER: {text}")

            elif entry.get("type") == "assistant":
                content = entry.get("message", {}).get("content", [])
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    text = " ".join(parts).strip()
                    if text:
                        # Truncate very long assistant responses
                        messages.append(f"ASSISTANT: {text[:800]}")

    return "\n\n".join(messages)


def next_session_number(dev_log_dir: Path) -> int:
    existing = list(dev_log_dir.glob("session-???.md"))
    if not existing:
        return 1
    numbers = []
    for f in existing:
        m = re.search(r"session-(\d+)", f.stem)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def append_to_index(dev_log_dir: Path, session_num: int, date: str, focus: str):
    index_path = dev_log_dir / "index.md"
    content = index_path.read_text()
    filename = f"session-{session_num:03d}.md"
    new_row = f"| {session_num} | {date} | {focus} | [{filename}]({filename}) |"

    # Find the last table row and append after it
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

    transcript = parse_transcript(transcript_path)
    if len(transcript) < 200:
        print("[session-log] Session too short to log, skipping.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[session-log] ANTHROPIC_API_KEY not set, skipping.")
        return

    try:
        import anthropic
    except ImportError:
        print("[session-log] anthropic package not installed, skipping.")
        return

    session_num = next_session_number(dev_log_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are writing a development session log for a personal health data pipeline project (Airflow + Postgres + dbt + Lightdash). The project owner is a data engineer building this as a learning project.

Analyze this conversation transcript and produce two things:

1. A one-line "focus" summary (10 words max) for the session index table
2. A full session log markdown document

Return your response as JSON with this exact structure:
{{
  "focus": "short one-line description",
  "content": "full markdown session log here"
}}

The markdown session log must follow this template exactly:
# Session {session_num:03d} — <descriptive title>

## Goals
<what the user was trying to accomplish>

## Accomplished
<bulleted list of what actually got done>

## Key Decisions
<bulleted list of technical decisions made and why — omit if none>

## Issues & Fixes
<bulleted list: problem → fix — omit if none>

## Pending / Next Steps
<bulleted list of what's left or what to do next session>

Keep it concise, technical, and useful for resuming work in a future session.

Transcript:
<transcript>
{transcript[:40000]}
</transcript>"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        result_text = re.sub(r"^```(?:json)?\n?", "", result_text)
        result_text = re.sub(r"\n?```$", "", result_text)

        result = json.loads(result_text)
        focus = result.get("focus", "session work")
        session_content = result.get("content", "")
    except Exception as e:
        print(f"[session-log] Claude API call failed: {e}")
        return

    session_file = dev_log_dir / f"session-{session_num:03d}.md"
    session_file.write_text(session_content + "\n")
    append_to_index(dev_log_dir, session_num, date, focus)

    subprocess.run(
        ["git", "add", str(dev_log_dir)],
        cwd=cwd, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"docs: auto-generate session {session_num:03d} log [skip ci]"],
        cwd=cwd, capture_output=True,
    )

    print(f"[session-log] Written session-{session_num:03d}.md and updated index.md")


if __name__ == "__main__":
    main()
