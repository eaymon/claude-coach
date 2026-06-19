"""Parse Claude Code session logs (``.jsonl``) into normalized ``Session`` objects.

Claude Code writes one JSON object per line under ``~/.claude/projects/<slug>/*.jsonl``.
Rows are typed (``user``, ``assistant``, ``mode``, ``permission-mode``, ``system`` ...).
The important distinctions a correct parser must make:

* A ``type: "user"`` row is **either** a real human prompt (content has ``text`` blocks)
  **or** a tool result being fed back to the model (content has ``tool_result`` blocks).
  Only the former is a "prompt". Vector Coach conflates the two.
* Tool calls live in ``type: "assistant"`` rows as ``tool_use`` content blocks, not as a
  literal ``tool_call`` string -- so a regex grep for ``tool_call`` finds nothing.
* ``permissionMode`` (and ``mode`` rows) tell us plan-mode vs ``bypassPermissions``/``acceptEdits``
  (YOLO) usage -- a genuine signal, not guessable from message text.
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")

FRUSTRATION_PAT = re.compile(
    r"\b(wtf|damn|shit|fuck+|ugh|argh|still (broken|not working|failing)|"
    r"come on|seriously|why (isn'?t|won'?t|doesn'?t)|that'?s wrong|no+ stop)\b",
    re.IGNORECASE,
)
INTERRUPT_MARKER = "[Request interrupted by user"
SKILL_TOOLS = {"Skill"}
SUBAGENT_TOOLS = {"Task", "Agent"}
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@dataclass
class Session:
    """Normalized view of one Claude Code session (grouped by ``sessionId``)."""

    session_id: str
    cwd: str | None = None
    git_branch: str | None = None
    version: str | None = None
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    message_count: int = 0
    assistant_turns: int = 0
    user_prompts: list[str] = field(default_factory=list)
    tool_calls: Counter = field(default_factory=Counter)
    skills_used: Counter = field(default_factory=Counter)
    subagent_calls: int = 0
    edit_calls: int = 0
    test_runs: int = 0
    models: Counter = field(default_factory=Counter)
    perm_modes: Counter = field(default_factory=Counter)
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    files_read: set = field(default_factory=set)
    interrupts: int = 0

    # --- derived metrics -------------------------------------------------
    @property
    def duration_min(self) -> float:
        if self.first_ts and self.last_ts:
            return max(0.0, (self.last_ts - self.first_ts).total_seconds() / 60.0)
        return 0.0

    @property
    def total_tools(self) -> int:
        return sum(self.tool_calls.values())

    @property
    def plan_mode_used(self) -> bool:
        return self.perm_modes.get("plan", 0) > 0

    @property
    def yolo_share(self) -> float:
        total = sum(self.perm_modes.values())
        if not total:
            return 0.0
        yolo = self.perm_modes.get("bypassPermissions", 0) + self.perm_modes.get("acceptEdits", 0)
        return yolo / total

    @property
    def cache_hit_ratio(self) -> float:
        denom = self.tokens_in + self.cache_read
        return (self.cache_read / denom) if denom else 0.0

    @property
    def started_hours(self) -> set[int]:
        return {self.first_ts.hour} if self.first_ts else set()

    @property
    def active_late_night(self) -> bool:
        for ts in (self.first_ts, self.last_ts):
            if ts and 0 <= ts.hour < 5:
                return True
        return False

    @property
    def active_weekend(self) -> bool:
        return bool(self.first_ts and self.first_ts.weekday() >= 5)

    @property
    def workspace(self) -> str:
        return os.path.basename(self.cwd) if self.cwd else "unknown"


def _ingest_row(row: dict, sessions: dict[str, Session]) -> None:
    sid = row.get("sessionId") or "unknown"
    sess = sessions.setdefault(sid, Session(session_id=sid))

    if row.get("cwd") and not sess.cwd:
        sess.cwd = row["cwd"]
    if row.get("gitBranch") and not sess.git_branch:
        sess.git_branch = row["gitBranch"]
    if row.get("version") and not sess.version:
        sess.version = row["version"]

    ts = _parse_ts(row.get("timestamp"))
    if ts:
        if not sess.first_ts or ts < sess.first_ts:
            sess.first_ts = ts
        if not sess.last_ts or ts > sess.last_ts:
            sess.last_ts = ts

    # Permission-mode timeline (real plan/YOLO signal).
    pm = row.get("permissionMode")
    if pm:
        sess.perm_modes[pm] += 1
    if row.get("type") in ("mode", "permission-mode"):
        val = row.get("mode") or row.get("permissionMode")
        if val:
            sess.perm_modes[val] += 1

    rtype = row.get("type")
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    content = msg.get("content")

    if rtype == "user":
        sess.message_count += 1
        if isinstance(content, str):
            text = content.strip()
            if text:
                if INTERRUPT_MARKER in text:
                    sess.interrupts += 1
                else:
                    sess.user_prompts.append(text)
        elif isinstance(content, list):
            blocks = [b for b in content if isinstance(b, dict)]
            kinds = {b.get("type") for b in blocks}
            if "tool_result" in kinds:
                return  # a tool result fed back to the model -- not a prompt
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            text = "\n".join(t for t in texts if t).strip()
            if text:
                if INTERRUPT_MARKER in text:
                    sess.interrupts += 1
                else:
                    sess.user_prompts.append(text)

    elif rtype == "assistant":
        sess.message_count += 1
        sess.assistant_turns += 1
        if msg.get("model"):
            sess.models[msg["model"]] += 1
        usage = msg.get("usage") or {}
        sess.tokens_in += usage.get("input_tokens", 0) or 0
        sess.tokens_out += usage.get("output_tokens", 0) or 0
        sess.cache_read += usage.get("cache_read_input_tokens", 0) or 0
        sess.cache_creation += usage.get("cache_creation_input_tokens", 0) or 0
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    sess.tool_calls[name] += 1
                    inp = b.get("input") or {}
                    if name in SKILL_TOOLS:
                        sess.skills_used[inp.get("skill") or inp.get("command") or "?"] += 1
                    if name in SUBAGENT_TOOLS:
                        sess.subagent_calls += 1
                    if name in EDIT_TOOLS:
                        sess.edit_calls += 1
                    if name == "Read" and inp.get("file_path"):
                        sess.files_read.add(inp["file_path"])
                    if name == "Bash":
                        cmd = (inp.get("command") or "").lower()
                        if any(k in cmd for k in ("pytest", "test", "jest", "go test", "phpunit", "vitest")):
                            sess.test_runs += 1


def parse_files(paths: list[str]) -> dict[str, Session]:
    """Parse a list of ``.jsonl`` files into ``{session_id: Session}``."""
    sessions: dict[str, Session] = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        _ingest_row(row, sessions)
        except (OSError, UnicodeDecodeError):
            continue
    return sessions


def discover_logs(root: str = DEFAULT_ROOT) -> list[str]:
    """Find all session logs under a Claude Code projects root (or a single file/dir)."""
    p = Path(os.path.expanduser(root))
    if p.is_file():
        return [str(p)]
    if p.is_dir():
        return sorted(glob.glob(str(p / "**" / "*.jsonl"), recursive=True))
    return []


def filter_recent(sessions: dict[str, Session], since: timedelta) -> dict[str, Session]:
    """Keep sessions whose last activity is within ``since`` of now."""
    cutoff = datetime.now(timezone.utc) - since
    out = {}
    for sid, s in sessions.items():
        last = s.last_ts
        if last is None:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last >= cutoff:
            out[sid] = s
    return out
