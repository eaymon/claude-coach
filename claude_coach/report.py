"""Render audit findings to the terminal, markdown, or JSON."""

from __future__ import annotations

import json
from collections import Counter

from .parser import Session
from .rules import RULES, SEV_ORDER, Finding
from .readiness import ReadinessCheck, readiness_verdict

SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (SEV_ORDER.get(f.severity, 3), f.category))


def summary_stats(sessions: dict[str, Session], findings: list[Finding]) -> dict:
    by_sev = Counter(f.severity for f in findings)
    by_cat = Counter(f.category for f in findings)
    models = Counter()
    tokens_in = tokens_out = cache = 0
    prompts = msgs = 0
    for s in sessions.values():
        models.update(s.models)
        tokens_in += s.tokens_in
        tokens_out += s.tokens_out
        cache += s.cache_read
        prompts += len(s.user_prompts)
        msgs += s.message_count
    return {
        "sessions": len(sessions),
        "messages": msgs,
        "prompts": prompts,
        "findings": len(findings),
        "by_severity": dict(by_sev),
        "by_category": dict(by_cat),
        "models": dict(models.most_common(5)),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read": cache,
    }


def print_terminal(sessions: dict[str, Session], findings: list[Finding]) -> None:
    stats = summary_stats(sessions, findings)
    line = "=" * 60
    print(f"\n{line}\n  claude-coach — Session Audit\n{line}\n")
    print(f"  Sessions: {stats['sessions']}   Messages: {stats['messages']}   Prompts: {stats['prompts']}")
    print(f"  Findings: {stats['findings']}  "
          f"(🔴 {stats['by_severity'].get('high', 0)}  "
          f"🟡 {stats['by_severity'].get('medium', 0)}  "
          f"🟢 {stats['by_severity'].get('low', 0)})")
    if stats["models"]:
        top = ", ".join(f"{m} ×{n}" for m, n in stats["models"].items())
        print(f"  Models: {top}")
    if stats["tokens_in"] or stats["cache_read"]:
        denom = stats["tokens_in"] + stats["cache_read"]
        ratio = stats["cache_read"] / denom if denom else 0
        print(f"  Tokens: {stats['tokens_in']:,} in / {stats['tokens_out']:,} out  "
              f"(cache hit {ratio:.0%})")
    if not findings:
        print("\n  ✅ No anti-patterns detected. Clean sessions.\n")
        return
    print("\n  ── Findings ──")
    for f in _sorted(findings):
        print(f"  {SEV_ICON.get(f.severity, '•')} [{f.severity}] {f.title}  ({f.category})")
        print(f"      {f.detail}")
        print(f"      ↳ {f.remediation}")
    print()


def to_markdown(sessions: dict[str, Session], findings: list[Finding]) -> str:
    stats = summary_stats(sessions, findings)
    out = ["# claude-coach — Session Audit\n"]
    out.append(f"- Sessions: **{stats['sessions']}** · Messages: {stats['messages']} · Prompts: {stats['prompts']}")
    out.append(f"- Findings: **{stats['findings']}** "
               f"(🔴 {stats['by_severity'].get('high', 0)} / "
               f"🟡 {stats['by_severity'].get('medium', 0)} / "
               f"🟢 {stats['by_severity'].get('low', 0)})\n")
    if not findings:
        out.append("✅ No anti-patterns detected.\n")
        return "\n".join(out)
    out.append("| Sev | Finding | Category | Detail |")
    out.append("|-----|---------|----------|--------|")
    for f in _sorted(findings):
        detail = f.detail.replace("|", "\\|")
        out.append(f"| {SEV_ICON.get(f.severity, '')} | {f.title} | {f.category} | {detail} |")
    out.append("")
    return "\n".join(out)


def to_json(sessions: dict[str, Session], findings: list[Finding]) -> str:
    payload = {
        "summary": summary_stats(sessions, findings),
        "findings": [vars(f) for f in _sorted(findings)],
    }
    return json.dumps(payload, indent=2)


def print_rules() -> None:
    print(f"\n  Anti-Pattern Catalog ({len(RULES)} rules):\n")
    for r in sorted(RULES, key=lambda r: (r.category, r.rule_id)):
        print(f"  {SEV_ICON.get(r.severity, '')} [{r.severity:6}] {r.title}  ({r.category})")
    print()


def print_readiness(path: str, score: int, checks: list[ReadinessCheck]) -> None:
    total = len(checks)
    print(f"\n  Project Readiness — {path}")
    print(f"  Score: {score}/{total} → {readiness_verdict(score, total)}\n")
    for c in checks:
        mark = "✅" if c.passed else "❌"
        print(f"   {mark} {c.name}: {c.detail}")
    print()
