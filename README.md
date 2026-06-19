# claude-coach

**A local anti-pattern auditor for [Claude Code](https://claude.com/claude-code) sessions.** Observe, measure, and improve your agentic workflow — all on your machine, nothing leaves it.

Inspired by [Microsoft's AI Engineer Coach](https://github.com/microsoft/AI-Engineering-Coach) (MIT) and [Vector Coach](https://github.com/Osmosy/vector-coach), but the parser is rewritten to understand **Claude Code's real log format** — actual `tool_use` blocks, `permissionMode` (plan vs `bypassPermissions`/YOLO), and per-turn token usage — instead of regex-grepping a generic log.

## Why another one?

Generic auditors mis-read Claude Code logs: they can't see `tool_use` blocks (so they report "0 tool calls"), and they count tool *results* as if they were your prompts. `claude-coach` reads the JSONL structure properly:

| Signal | Generic log parser | claude-coach |
|--------|-------------------|--------------|
| Tool / skill usage | ❌ invisible (`tool_use` ≠ `"tool_call"` string) | ✅ counted by name |
| Real prompts vs tool results | ❌ conflated | ✅ separated (text blocks only) |
| Plan mode / YOLO | ❌ unguessable | ✅ from `permissionMode` |
| Token cost / cache reuse | ❌ — | ✅ from `usage` |

## Install

```bash
pip install -e .          # from a clone
# or, once published:  pip install claude-coach
```

Python 3.9+. Zero dependencies.

## Usage

```bash
claude-coach                       # audit every session in ~/.claude/projects
claude-coach path/to/session.jsonl # audit one log, a project dir, or any path
claude-coach --since 7d            # only recent sessions (7d / 2w / 24h)
claude-coach --rules               # list the anti-pattern catalog
claude-coach --readiness ./my-repo # score a project's agentic readiness
claude-coach --json r.json --markdown r.md   # shareable reports
```

### Example

```
============================================================
  claude-coach — Session Audit
============================================================

  Sessions: 2   Messages: 1515   Prompts: 44
  Findings: 8  (🔴 3  🟡 2  🟢 3)
  Models: claude-opus-4-8 ×1086
  Tokens: 67,137 in / 2,032,557 out  (cache hit 100%)

  ── Findings ──
  🔴 [high] Mega Sessions  (session-hygiene)
      1515 messages (threshold 1000) — consider /clear or splitting work
      ↳ Use /clear between tasks; keep sessions focused.
  🔴 [high] YOLO Mode  (tool-mastery)
      70% of turns in bypassPermissions/acceptEdits — review discipline at risk
      ↳ Reserve bypassPermissions for trusted, reversible work.
  ...
```

## The 17 rules

| Category | Rules |
|----------|-------|
| **Session Hygiene** | mega-sessions · marathon duration · late-night · weekend · runaway tool loop · high interrupt rate |
| **Prompt Quality** | repeated prompts · lazy prompting · frustration signals |
| **Tool Mastery** | never uses plan mode · no skills · YOLO mode · no subagents on huge sessions |
| **Context Management** | no file context · cache-hit starvation |
| **Code Review** | premium model for simple work · vibe coding (edits without test runs) |

Thresholds live in [`claude_coach/rules.py`](claude_coach/rules.py) (the `T` dict) — tune them to your own workflow.

## As a Claude Code skill

Copy [`skill/SKILL.md`](skill/SKILL.md) into your skills directory (e.g. `~/.claude/skills/claude-coach/SKILL.md`) and ask Claude to *"audit my recent Claude Code sessions."*

## Privacy

All analysis runs locally on your own log files. No network calls, no telemetry. Findings are signals to reflect on — they flag patterns, not correctness, and are not a substitute for human review.

## License

MIT. Anti-pattern catalog adapted from Microsoft AI Engineer Coach (MIT).
