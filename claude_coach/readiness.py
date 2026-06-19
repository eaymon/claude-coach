"""Project readiness score: is a repo set up for effective agentic work?"""

from __future__ import annotations

import os
from dataclasses import dataclass

INSTRUCTION_BLOAT_KB = 40


@dataclass
class ReadinessCheck:
    name: str
    passed: bool
    detail: str


def score_project(path: str) -> tuple[int, list[ReadinessCheck]]:
    path = os.path.expanduser(path)
    checks: list[ReadinessCheck] = []

    # 1. Agent instructions present.
    claude_md = next((os.path.join(path, n) for n in ("CLAUDE.md", "AGENTS.md")
                      if os.path.isfile(os.path.join(path, n))), None)
    checks.append(ReadinessCheck("Agent instructions (CLAUDE.md/AGENTS.md)", bool(claude_md),
                                 os.path.basename(claude_md) if claude_md else "missing"))

    # 2. Instructions not bloated.
    if claude_md:
        kb = os.path.getsize(claude_md) / 1024
        checks.append(ReadinessCheck("Instructions are lean", kb <= INSTRUCTION_BLOAT_KB,
                                     f"{kb:.0f} KB (cap {INSTRUCTION_BLOAT_KB} KB)"))
    else:
        checks.append(ReadinessCheck("Instructions are lean", False, "no instructions file"))

    # 3. Skills directory populated.
    skills_dir = os.path.join(path, ".claude", "skills")
    n_skills = len([d for d in os.listdir(skills_dir)]) if os.path.isdir(skills_dir) else 0
    checks.append(ReadinessCheck("Project skills present", n_skills > 0, f"{n_skills} skill(s)"))

    # 4. Settings / permissions configured.
    has_settings = any(os.path.isfile(os.path.join(path, ".claude", n))
                       for n in ("settings.json", "settings.local.json"))
    checks.append(ReadinessCheck(".claude/settings present", has_settings,
                                 "configured" if has_settings else "missing"))

    # 5. Spec/docs structure.
    has_specs = os.path.isdir(os.path.join(path, "docs")) or os.path.isdir(os.path.join(path, "specs"))
    checks.append(ReadinessCheck("Spec/docs structure", has_specs,
                                 "present" if has_specs else "no docs/ or specs/"))

    # 6. Reproducible env.
    has_env = any(os.path.exists(os.path.join(path, n))
                  for n in (".devcontainer", "Dockerfile", "flake.nix", ".tool-versions"))
    checks.append(ReadinessCheck("Reproducible environment", has_env,
                                 "present" if has_env else "none detected"))

    score = sum(1 for c in checks if c.passed)
    return score, checks


def readiness_verdict(score: int, total: int) -> str:
    pct = score / total if total else 0
    if pct >= 0.83:
        return "agent-optimized"
    if pct >= 0.5:
        return "basic readiness"
    return "not ready"
