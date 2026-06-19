"""Render an audit as a self-contained HTML dashboard (no external assets).

Charts are emitted as inline SVG computed server-side, so the file works fully
offline — open it in any browser, no JS framework, no CDN, no network.
"""

from __future__ import annotations

import html
import math
from collections import Counter

from .parser import Session
from .report import _sorted, summary_stats
from .rules import Finding

SEV_COLOR = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}
ACCENT = "#d97757"  # Claude terracotta


def _donut(counts: dict[str, int], total: int) -> str:
    """Stacked-arc SVG donut for severity breakdown."""
    r, cx, cy = 70, 90, 90
    circ = 2 * math.pi * r
    if total == 0:
        return (f'<svg viewBox="0 0 180 180" width="180" height="180">'
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#2a2e3a" stroke-width="22"/>'
                f'<text x="{cx}" y="{cy+6}" text-anchor="middle" fill="#9aa0b4" font-size="16">0</text></svg>')
    segs = []
    offset = 0.0
    for sev in ("high", "medium", "low"):
        n = counts.get(sev, 0)
        if not n:
            continue
        dash = (n / total) * circ
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{SEV_COLOR[sev]}" '
            f'stroke-width="22" stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += dash
    return (
        f'<svg viewBox="0 0 180 180" width="180" height="180">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#2a2e3a" stroke-width="22"/>'
        + "".join(segs)
        + f'<text x="{cx}" y="{cy-2}" text-anchor="middle" fill="#e8eaf0" font-size="30" font-weight="700">{total}</text>'
        f'<text x="{cx}" y="{cy+18}" text-anchor="middle" fill="#9aa0b4" font-size="12">findings</text>'
        f'</svg>'
    )


def _cat_bars(by_cat: dict[str, int]) -> str:
    if not by_cat:
        return '<p class="muted">No findings.</p>'
    top = max(by_cat.values())
    rows = []
    for cat, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        pct = (n / top) * 100
        label = cat.replace("-", " ").title()
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{html.escape(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.0f}%"></span></span>'
            f'<span class="bar-val">{n}</span></div>'
        )
    return "".join(rows)


def _trend(sessions: dict[str, Session], findings: list[Finding], max_days: int = 21) -> str:
    """SVG bar chart: findings per day, with a session-count line on top."""
    by_sid_date = {}
    for s in sessions.values():
        if s.first_ts:
            by_sid_date[s.session_id] = s.first_ts.date()
    if not by_sid_date:
        return ""
    find_by_day = Counter()
    for f in findings:
        d = by_sid_date.get(f.session_id)
        if d:
            find_by_day[d] += 1
    sess_by_day = Counter(by_sid_date.values())
    days = sorted(set(find_by_day) | set(sess_by_day))[-max_days:]
    if len(days) < 2:
        return ""  # a trend needs at least two days

    w, h, pad_b, pad_t = 920, 150, 26, 12
    n = len(days)
    slot = w / n
    bw = min(34, slot * 0.6)
    top = max([find_by_day.get(d, 0) for d in days] + [1])
    usable = h - pad_b - pad_t

    bars, labels, pts = [], [], []
    for i, d in enumerate(days):
        fc = find_by_day.get(d, 0)
        bh = (fc / top) * usable
        x = i * slot + (slot - bw) / 2
        y = pad_t + (usable - bh)
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{ACCENT}"/>')
        if fc:
            bars.append(f'<text x="{x + bw/2:.1f}" y="{y-4:.1f}" text-anchor="middle" fill="#9aa0b4" font-size="10">{fc}</text>')
        if i % max(1, n // 10) == 0:
            labels.append(f'<text x="{i*slot + slot/2:.1f}" y="{h-8}" text-anchor="middle" fill="#6b7280" font-size="10">{d.strftime("%m/%d")}</text>')
        pts.append(f"{i*slot + slot/2:.1f},{pad_t + usable - (sess_by_day.get(d,0)/max(sess_by_day.values()))*usable:.1f}")
    line = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#5b9bd5" stroke-width="2" opacity="0.8"/>'
    dots = "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="2.5" fill="#5b9bd5"/>' for p in pts)
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">'
        + "".join(bars) + line + dots + "".join(labels) + "</svg>"
        + '<div class="legend"><div class="leg"><span class="swatch" style="background:'
        + ACCENT + '"></span>findings/day</div><div class="leg"><span class="swatch" style="background:#5b9bd5"></span>sessions/day</div></div>'
    )


def _stat(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="stat-sub">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="stat"><div class="stat-val">{html.escape(value)}</div>'
            f'<div class="stat-label">{html.escape(label)}</div>{sub_html}</div>')


def _finding_card(f: Finding) -> str:
    return (
        f'<div class="finding sev-{f.severity}">'
        f'<div class="finding-head"><span class="dot"></span>'
        f'<span class="finding-title">{html.escape(f.title)}</span>'
        f'<span class="chip">{html.escape(f.category)}</span>'
        f'<span class="sev-tag">{f.severity}</span></div>'
        f'<div class="finding-detail">{html.escape(f.detail)}</div>'
        f'<div class="finding-fix">↳ {html.escape(f.remediation)}</div>'
        f'</div>'
    )


def _session_rows(sessions: dict[str, Session], findings: list[Finding]) -> str:
    by_sid = Counter(f.session_id for f in findings)
    rows = []
    ordered = sorted(sessions.values(), key=lambda s: -s.message_count)
    for s in ordered[:50]:
        yolo = f"{s.yolo_share:.0%}" if sum(s.perm_modes.values()) else "—"
        dur = f"{s.duration_min:.0f}m" if s.duration_min else "—"
        rows.append(
            f"<tr><td class='mono'>{html.escape(s.session_id[:8])}</td>"
            f"<td>{html.escape(s.workspace)}</td>"
            f"<td class='num'>{s.message_count}</td>"
            f"<td class='num'>{len(s.user_prompts)}</td>"
            f"<td class='num'>{dur}</td>"
            f"<td class='num'>{s.total_tools}</td>"
            f"<td class='num'>{yolo}</td>"
            f"<td class='num'>{by_sid.get(s.session_id, 0)}</td></tr>"
        )
    if len(ordered) > 50:
        rows.append(f"<tr><td colspan='8' class='muted'>… and {len(ordered) - 50} more sessions</td></tr>")
    return "".join(rows)


def to_html(sessions: dict[str, Session], findings: list[Finding], generated: str = "") -> str:
    stats = summary_stats(sessions, findings)
    sev = stats["by_severity"]
    denom = stats["tokens_in"] + stats["cache_read"]
    cache_pct = f"{(stats['cache_read'] / denom):.0%}" if denom else "—"
    top_model = next(iter(stats["models"]), "—")

    cards = "".join([
        _stat("Sessions", str(stats["sessions"])),
        _stat("Messages", f"{stats['messages']:,}"),
        _stat("Real prompts", f"{stats['prompts']:,}"),
        _stat("Findings", str(stats["findings"]),
              f"{sev.get('high', 0)} high · {sev.get('medium', 0)} med · {sev.get('low', 0)} low"),
        _stat("Tokens out", f"{stats['tokens_out']:,}", f"cache hit {cache_pct}"),
        _stat("Top model", top_model),
    ])

    legend = "".join(
        f'<div class="leg"><span class="swatch" style="background:{SEV_COLOR[s]}"></span>'
        f'{s.title()} <b>{sev.get(s, 0)}</b></div>'
        for s in ("high", "medium", "low")
    )

    findings_html = (
        "".join(_finding_card(f) for f in _sorted(findings))
        if findings else '<p class="muted">✅ No anti-patterns detected. Clean sessions.</p>'
    )

    trend_svg = _trend(sessions, findings)
    trend_section = f'<h2>Trend</h2><section class="panel">{trend_svg}</section>' if trend_svg else ""

    gen = f" · {html.escape(generated)}" if generated else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>claude-coach — Session Audit</title>
<style>
  :root {{ --bg:#0f1117; --card:#1a1d27; --line:#2a2e3a; --txt:#e8eaf0; --muted:#9aa0b4; --accent:{ACCENT}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:40px 24px 64px; }}
  header h1 {{ margin:0; font-size:26px; }}
  header h1 .mark {{ color:var(--accent); }}
  header p {{ color:var(--muted); margin:6px 0 0; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin:28px 0; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
  .stat-val {{ font-size:26px; font-weight:700; }}
  .stat-label {{ color:var(--muted); font-size:13px; margin-top:2px; }}
  .stat-sub {{ color:var(--muted); font-size:12px; margin-top:6px; opacity:.85; }}
  .grid2 {{ display:grid; grid-template-columns:220px 1fr; gap:18px; align-items:center;
            background:var(--card); border:1px solid var(--line); border-radius:12px; padding:22px; margin-bottom:28px; }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-bottom:28px; }}
  .donut-wrap {{ text-align:center; }}
  .legend {{ display:flex; gap:16px; justify-content:center; margin-top:6px; font-size:13px; color:var(--muted); }}
  .leg b {{ color:var(--txt); }}
  .swatch {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; }}
  .bar-row {{ display:grid; grid-template-columns:150px 1fr 36px; gap:12px; align-items:center; margin:9px 0; }}
  .bar-label {{ font-size:13px; color:var(--muted); }}
  .bar-track {{ background:#222632; border-radius:6px; height:14px; overflow:hidden; }}
  .bar-fill {{ display:block; height:100%; background:linear-gradient(90deg,var(--accent),#e8a;); }}
  .bar-val {{ text-align:right; font-variant-numeric:tabular-nums; }}
  h2 {{ font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:32px 0 14px; }}
  .finding {{ background:var(--card); border:1px solid var(--line); border-left:4px solid var(--line);
              border-radius:10px; padding:14px 16px; margin-bottom:12px; }}
  .finding.sev-high {{ border-left-color:{SEV_COLOR['high']}; }}
  .finding.sev-medium {{ border-left-color:{SEV_COLOR['medium']}; }}
  .finding.sev-low {{ border-left-color:{SEV_COLOR['low']}; }}
  .finding-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .finding-title {{ font-weight:600; }}
  .dot {{ width:9px; height:9px; border-radius:50%; }}
  .sev-high .dot {{ background:{SEV_COLOR['high']}; }}
  .sev-medium .dot {{ background:{SEV_COLOR['medium']}; }}
  .sev-low .dot {{ background:{SEV_COLOR['low']}; }}
  .chip {{ font-size:11px; color:var(--muted); background:#222632; border-radius:20px; padding:2px 10px; }}
  .sev-tag {{ margin-left:auto; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .finding-detail {{ margin:8px 0 4px; font-size:14px; }}
  .finding-fix {{ color:var(--muted); font-size:13px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card);
           border:1px solid var(--line); border-radius:12px; overflow:hidden; font-size:13px; }}
  th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; text-transform:uppercase; font-size:11px; letter-spacing:.04em; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num, td.mono {{ font-variant-numeric:tabular-nums; }}
  .mono {{ font-family:ui-monospace,Menlo,monospace; color:var(--accent); }}
  .muted {{ color:var(--muted); }}
  footer {{ color:var(--muted); font-size:12px; margin-top:36px; border-top:1px solid var(--line); padding-top:16px; }}
  footer a {{ color:var(--accent); }}
</style></head>
<body><div class="wrap">
  <header>
    <h1><span class="mark">claude</span>-coach — Session Audit</h1>
    <p>Local anti-pattern audit of your Claude Code sessions{gen}</p>
  </header>

  <section class="stats">{cards}</section>

  <section class="grid2">
    <div class="donut-wrap">{_donut(sev, stats['findings'])}<div class="legend">{legend}</div></div>
    <div>{_cat_bars(stats['by_category'])}</div>
  </section>

  {trend_section}

  <h2>Findings</h2>
  {findings_html}

  <h2>Sessions</h2>
  <table>
    <tr><th>ID</th><th>Workspace</th><th>Msgs</th><th>Prompts</th><th>Dur</th><th>Tools</th><th>YOLO</th><th>Flags</th></tr>
    {_session_rows(sessions, findings)}
  </table>

  <footer>
    Generated by <a href="https://github.com/eaymon/claude-coach">claude-coach</a> ·
    100% local, no data left your machine · Findings are signals, not verdicts.
  </footer>
</div></body></html>
"""
