import os

from claude_coach.parser import parse_files

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.jsonl")


def _session():
    sessions = parse_files([FIXTURE])
    assert "test-1" in sessions
    return sessions["test-1"]


def test_real_prompts_exclude_tool_results():
    s = _session()
    # 6 real prompts; the 2 tool_result rows must NOT be counted as prompts.
    assert len(s.user_prompts) == 6
    assert "fix it" in s.user_prompts
    assert all("tool_result" not in p for p in s.user_prompts)


def test_tool_use_detected():
    s = _session()
    assert s.tool_calls["Read"] == 1
    assert s.tool_calls["Edit"] == 2
    assert s.tool_calls["Bash"] == 1
    assert s.files_read == {"/proj/app.py"}


def test_permission_mode_and_yolo():
    s = _session()
    assert s.perm_modes["bypassPermissions"] == 12
    assert s.yolo_share == 1.0
    assert s.plan_mode_used is False


def test_token_usage_and_cache():
    s = _session()
    assert s.tokens_in > 0
    assert s.cache_read > 0
    assert 0.0 < s.cache_hit_ratio <= 1.0


def test_metadata():
    s = _session()
    assert s.cwd == "/proj"
    assert s.git_branch == "main"
    assert s.assistant_turns == 12
