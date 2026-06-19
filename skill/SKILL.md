---
name: claude-coach
description: "Audit Claude Code sessions for anti-patterns. Use when the user wants to review their agentic workflow, find wasted tokens/time, check prompt quality, session hygiene, tool/skill usage, plan-mode and YOLO (bypassPermissions) habits, or score a project's agentic readiness. All analysis is local."
---

# claude-coach — Session Auditor

Audits Claude Code session logs (`~/.claude/projects/**/*.jsonl`) against ~18
anti-patterns across 5 categories. 100% local — no data leaves the machine.
Inspired by Microsoft's AI Engineer Coach (MIT) and Vector Coach, but the parser
understands Claude Code's real log structure (tool_use blocks, permissionMode,
per-turn token usage).

## Commands

```bash
# Audit every session in ~/.claude/projects
claude-coach

# Audit a single log, a project dir, or anything under a path
claude-coach ~/.claude/projects/<slug>/<id>.jsonl

# Only recent sessions
claude-coach --since 7d

# List the full anti-pattern catalog
claude-coach --rules

# Score a project's agentic readiness
claude-coach --readiness /path/to/repo

# Machine-readable / shareable output
claude-coach --json report.json --markdown report.md
```

## Categories

- **Session Hygiene** — mega-sessions, marathon duration, late-night, weekend, runaway tool loops, high interrupt rate
- **Prompt Quality** — repeated prompts, lazy prompting, frustration signals
- **Tool Mastery** — never uses plan mode, no skills, YOLO mode (bypassPermissions), no subagents on huge sessions
- **Context Management** — no file context, cache-hit starvation
- **Code Review** — premium model for simple work, vibe coding (edits with no test runs)

## Notes

- Thresholds live in `claude_coach/rules.py` (`T` dict) — tune per workflow.
- Findings are signals, not verdicts. They flag patterns, not correctness.
- Works best across many sessions for trend analysis.
