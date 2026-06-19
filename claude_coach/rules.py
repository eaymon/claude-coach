"""Anti-pattern rules for Claude Code sessions.

Each rule inspects a single :class:`~claude_coach.parser.Session` and returns a
:class:`Finding` (or ``None``). Thresholds are deliberately conservative to keep
false positives low; tune them in ``RULES`` for your own workflow.

Catalog adapted from Microsoft's AI Engineer Coach (MIT) and Vector Coach, but the
detection is rewritten against Claude Code's real log structure.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

from .parser import FRUSTRATION_PAT, Session

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Finding:
    rule_id: str
    title: str
    category: str
    severity: str
    detail: str
    remediation: str
    session_id: str


@dataclass
class Rule:
    rule_id: str
    title: str
    category: str
    severity: str
    remediation: str
    check: Callable[[Session], Optional[str]]  # returns detail string if it fires

    def evaluate(self, s: Session) -> Optional[Finding]:
        detail = self.check(s)
        if detail is None:
            return None
        return Finding(
            self.rule_id, self.title, self.category, self.severity,
            detail, self.remediation, s.session_id,
        )


# --- thresholds (single place to tune) ----------------------------------
T = {
    "mega_messages": 1000,
    "marathon_min": 180,
    "runaway_tool": 60,
    "interrupt_ratio": 0.30,
    "repeat_count": 3,
    "lazy_words": 6,
    "lazy_ratio": 0.40,
    "yolo_share": 0.50,
    "huge_session": 400,
    "no_file_turns": 50,
    "cache_floor": 0.50,
    "cache_min_tokens": 50_000,
    "premium_share": 0.95,
}


def _short_prompts(s: Session) -> list[str]:
    return [p for p in s.user_prompts if len(p.split()) < T["lazy_words"]]


# --- session hygiene ----------------------------------------------------
def _mega(s):
    if s.message_count > T["mega_messages"]:
        return f"{s.message_count} messages (threshold {T['mega_messages']}) — consider /clear or splitting work"
    return None


def _marathon(s):
    if s.duration_min > T["marathon_min"]:
        return f"{s.duration_min:.0f} min single session (threshold {T['marathon_min']})"
    return None


def _late_night(s):
    if s.active_late_night:
        h = s.first_ts.hour if s.first_ts else "?"
        return f"activity in the 00:00–05:00 window (started hour {h})"
    return None


def _weekend(s):
    return "weekend session" if s.active_weekend else None


def _runaway(s):
    if s.tool_calls:
        name, n = s.tool_calls.most_common(1)[0]
        if n > T["runaway_tool"]:
            return f"{name} called {n}× in one session (threshold {T['runaway_tool']}) — possible thrashing loop"
    return None


def _interrupts(s):
    n = len(s.user_prompts)
    if n >= 5 and s.interrupts / n > T["interrupt_ratio"]:
        return f"{s.interrupts} interrupts over {n} prompts ({s.interrupts / n:.0%})"
    return None


# --- prompt quality -----------------------------------------------------
def _repeats(s):
    if len(s.user_prompts) < 3:
        return None
    counts = Counter(p.strip() for p in s.user_prompts)
    worst, n = counts.most_common(1)[0]
    if n >= T["repeat_count"]:
        return f"prompt repeated {n}×: {worst[:60]!r} — turn it into a skill/slash command"
    return None


def _lazy(s):
    n = len(s.user_prompts)
    if n >= 5:
        ratio = len(_short_prompts(s)) / n
        if ratio > T["lazy_ratio"]:
            return f"{ratio:.0%} of prompts under {T['lazy_words']} words — add goals/constraints"
    return None


def _frustration(s):
    hits = [p for p in s.user_prompts if FRUSTRATION_PAT.search(p)]
    if hits:
        return f"{len(hits)} prompt(s) with frustration signals — a step back / plan mode often beats pushing"
    return None


# --- tool mastery -------------------------------------------------------
def _never_plan(s):
    if s.message_count > 200 and not s.plan_mode_used:
        return "large session with no plan-mode use — plan mode reduces rework on complex tasks"
    return None


def _no_skills(s):
    if s.total_tools > 30 and not s.skills_used:
        return f"{s.total_tools} tool calls, 0 skills/slash-commands — repeated work is skill-worthy"
    return None


def _yolo(s):
    share = s.yolo_share
    if sum(s.perm_modes.values()) >= 10 and share > T["yolo_share"]:
        return f"{share:.0%} of turns in bypassPermissions/acceptEdits — review discipline at risk"
    return None


def _no_subagents(s):
    if s.message_count > T["huge_session"] and s.subagent_calls == 0 and s.total_tools > 50:
        return "huge session, no subagents — parallel/Task agents can offload broad searches"
    return None


# --- context management -------------------------------------------------
def _no_file_context(s):
    if s.assistant_turns > T["no_file_turns"] and not s.files_read:
        return f"{s.assistant_turns} assistant turns but 0 files Read — likely guessing at code"
    return None


def _cache_starvation(s):
    if (s.tokens_in + s.cache_read) > T["cache_min_tokens"] and s.cache_hit_ratio < T["cache_floor"]:
        return f"cache hit ratio {s.cache_hit_ratio:.0%} (floor {T['cache_floor']:.0%}) — churning context wastes tokens"
    return None


# --- code review --------------------------------------------------------
def _premium_for_simple(s):
    if not s.models:
        return None
    top_model, top_n = s.models.most_common(1)[0]
    total = sum(s.models.values())
    if "opus" in top_model.lower() and total >= 20 and (top_n / total) > T["premium_share"]:
        short = len(_short_prompts(s))
        if short >= 5:
            return f"100%-Opus session with {short} trivial prompts — cheaper models fit lookups/edits"
    return None


def _vibe_coding(s):
    if s.edit_calls >= 10 and s.test_runs == 0:
        return f"{s.edit_calls} file edits, 0 test runs — changes shipped without verification"
    return None


RULES: list[Rule] = [
    Rule("mega-sessions", "Mega Sessions", "session-hygiene", "high", "Use /clear between tasks; keep sessions focused.", _mega),
    Rule("marathon-session", "Marathon Session", "session-hygiene", "medium", "Break long sessions; context degrades over hours.", _marathon),
    Rule("late-night", "Late-Night Coding", "session-hygiene", "low", "Late-night sessions correlate with more rework.", _late_night),
    Rule("weekend-overwork", "Weekend Overwork", "session-hygiene", "low", "Watch sustainability; weekend work adds up.", _weekend),
    Rule("runaway-loop", "Runaway Tool Loop", "session-hygiene", "high", "Stop, re-read the error, change approach.", _runaway),
    Rule("high-interrupt", "High Interrupt Rate", "session-hygiene", "medium", "Front-load intent so you interrupt less.", _interrupts),
    Rule("repeated-prompts", "Repeated Prompts", "prompt-quality", "medium", "Turn repeats into a skill or slash command.", _repeats),
    Rule("lazy-prompting", "Lazy Prompting", "prompt-quality", "medium", "State the goal, constraints, and done-criteria.", _lazy),
    Rule("frustration-signals", "Frustration Signals", "prompt-quality", "low", "Switch to plan mode or step back when stuck.", _frustration),
    Rule("never-plan-mode", "Never Uses Plan Mode", "tool-mastery", "medium", "Use plan mode for multi-step / risky work.", _never_plan),
    Rule("no-skills", "No Skills Usage", "tool-mastery", "low", "Capture recurring flows as skills.", _no_skills),
    Rule("yolo-mode", "YOLO Mode", "tool-mastery", "high", "Reserve bypassPermissions for trusted, reversible work.", _yolo),
    Rule("no-subagents", "No Subagents on Huge Session", "tool-mastery", "low", "Delegate broad searches to Task/subagents.", _no_subagents),
    Rule("no-file-context", "No File Context", "context-management", "high", "Read the relevant files before editing.", _no_file_context),
    Rule("cache-starvation", "Cache Hit Starvation", "context-management", "medium", "Keep a stable context prefix to reuse cache.", _cache_starvation),
    Rule("premium-for-simple", "Premium Model for Simple Work", "code-review", "low", "Use a cheaper model for lookups/edits.", _premium_for_simple),
    Rule("vibe-coding", "Vibe Coding", "code-review", "medium", "Run tests after edits; verify before shipping.", _vibe_coding),
]


def audit_session(s: Session) -> list[Finding]:
    out = []
    for rule in RULES:
        try:
            f = rule.evaluate(s)
        except Exception:
            f = None
        if f:
            out.append(f)
    return out
