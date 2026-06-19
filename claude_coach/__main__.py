"""claude-coach CLI — audit Claude Code sessions for anti-patterns. All local."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import timedelta

from . import __version__
from .parser import DEFAULT_ROOT, discover_logs, filter_recent, parse_files
from .readiness import score_project
from .report import (
    print_readiness,
    print_rules,
    print_terminal,
    to_json,
    to_markdown,
)
from .rules import audit_session


def _parse_since(value: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([dwh])", value.strip())
    if not m:
        raise argparse.ArgumentTypeError("use forms like 7d, 2w, 24h")
    n, unit = int(m.group(1)), m.group(2)
    return {"h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-coach",
        description="Audit Claude Code session logs for anti-patterns (100%% local).",
    )
    p.add_argument("path", nargs="?", default=DEFAULT_ROOT,
                   help="log file, project dir, or Claude projects root (default: ~/.claude/projects)")
    p.add_argument("--rules", action="store_true", help="list the anti-pattern catalog and exit")
    p.add_argument("--readiness", metavar="PROJECT", help="score a project's agentic readiness and exit")
    p.add_argument("--since", type=_parse_since, metavar="DUR", help="only sessions active within e.g. 7d, 2w, 24h")
    p.add_argument("--json", metavar="FILE", help="write JSON report to FILE")
    p.add_argument("--markdown", metavar="FILE", help="write a markdown report to FILE")
    p.add_argument("--html", metavar="FILE", help="write a self-contained HTML dashboard to FILE")
    p.add_argument("--version", action="version", version=f"claude-coach {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.rules:
        print_rules()
        return 0

    if args.readiness:
        score, checks = score_project(args.readiness)
        print_readiness(args.readiness, score, checks)
        return 0

    paths = discover_logs(args.path)
    if not paths:
        print(f"No .jsonl session logs found at: {args.path}", file=sys.stderr)
        return 1

    sessions = parse_files(paths)
    # Drop bookkeeping-only groups (rows with no user/assistant messages).
    sessions = {sid: s for sid, s in sessions.items() if s.message_count > 0}
    if args.since:
        sessions = filter_recent(sessions, args.since)
    if not sessions:
        print("No sessions matched the filter.", file=sys.stderr)
        return 1

    findings = []
    for s in sessions.values():
        findings.extend(audit_session(s))

    print_terminal(sessions, findings)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(to_json(sessions, findings))
        print(f"  JSON report → {args.json}")
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(sessions, findings))
        print(f"  Markdown report → {args.markdown}")
    if args.html:
        from datetime import datetime
        from .html import to_html
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(to_html(sessions, findings, generated=stamp))
        print(f"  HTML dashboard → {args.html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
