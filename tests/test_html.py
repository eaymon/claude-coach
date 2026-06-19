import os

from claude_coach.html import to_html
from claude_coach.parser import parse_files
from claude_coach.rules import audit_session

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.jsonl")


def _render():
    sessions = parse_files([FIXTURE])
    findings = []
    for s in sessions.values():
        findings.extend(audit_session(s))
    return to_html(sessions, findings, generated="test")


def test_html_is_self_contained():
    out = _render()
    assert out.lstrip().startswith("<!doctype html>")
    assert "</html>" in out
    # no external assets / network dependencies
    assert "http://" not in out.replace("http://www.w3.org", "")  # svg ns is fine
    assert "cdn" not in out.lower()
    assert "<script" not in out.lower()


def test_html_contains_findings_and_svg():
    out = _render()
    assert "YOLO Mode" in out          # a fired rule
    assert "<svg" in out               # donut chart
    assert "test-1" in out             # session row
