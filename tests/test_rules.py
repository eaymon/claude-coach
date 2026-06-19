import os

from claude_coach.parser import parse_files
from claude_coach.rules import audit_session

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.jsonl")


def _findings():
    s = parse_files([FIXTURE])["test-1"]
    return {f.rule_id for f in audit_session(s)}


def test_expected_rules_fire():
    fired = _findings()
    assert "repeated-prompts" in fired      # "fix it" ×3
    assert "lazy-prompting" in fired         # 4/6 prompts < 6 words
    assert "frustration-signals" in fired    # "still broken why doesn't it work"
    assert "yolo-mode" in fired              # 100% bypassPermissions


def test_clean_rules_do_not_fire():
    fired = _findings()
    # The fixture is a short, daytime, file-aware session — these must stay quiet.
    for quiet in ("mega-sessions", "marathon-session", "late-night",
                  "weekend-overwork", "no-file-context", "never-plan-mode",
                  "runaway-loop", "vibe-coding"):
        assert quiet not in fired, quiet
