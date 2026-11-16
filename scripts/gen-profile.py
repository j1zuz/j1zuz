#!/usr/bin/env python3
"""Regenerate assets/profile.svg — a bento grid of cards with live GitHub data.

    python3 scripts/gen-profile.py [login]

Requires the `gh` CLI authenticated as that account. One static SVG, no React,
no MDX: a README cannot run components, so the whole bento is baked into a file.
mdxcn look: dashed frame, [ TITLE ] on the top edge, monospace, one cyan accent.

    +----------------------------------------------+
    |                   COMMITS                    |
    +-------------------------+--------------------+
    |         WHOAMI          |       STACK        |
    +-------------------------+--------------------+
    |                  LANGUAGES                   |
    +----------------------------------------------+

The butterfly (assets/butterfly.png) is not part of the grid: the README shows
it as its own <img> above this bento.
"""

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

LOGIN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GH_LOGIN", "j1zuz")
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "profile.svg"

BG = "#0b1016"
FRAME = "#2c3644"
MUTED = "#7d8899"
TEXT = "#c9d4e2"
DIM = "#1e2735"
ACCENT = "#22d3ee"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

W = 880          # canvas width
GAP = 18
ROW_H = [226, 232, 210]
OPACITY = [0.34, 0.55, 0.78, 1.0]


# ---------------------------------------------------------------- primitives

def card(x, y, w, h, title=None, inner=""):
    out = [
        f'<g transform="translate({x},{y})">',
        f'<rect width="{w}" height="{h}" rx="10" fill="{BG}"/>',
        inner,
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="9" class="frame"/>',
    ]
    if title:
        label = f"[ {title} ]"
        box = len(label) * 8.4 + 16
        out += [
            f'<rect x="{w / 2 - box / 2:.1f}" y="11" width="{box:.1f}" height="16" fill="{BG}"/>',
            f'<text x="{w / 2:.1f}" y="23" class="title" text-anchor="middle">{label}</text>',
        ]
    return out


def txt(x, y, value, cls="val", anchor="start"):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}"{a}>{value}</text>'


def rect(x, y, w, h, fill, op=None, rx=2):
    o = f' fill-opacity="{op}"' if op is not None else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{o}/>'


# ---------------------------------------------------------------------- data

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch():
    raw = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={LOGIN}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(raw)["data"]["user"]


# ------------------------------------------------------------------- commits

CELL_W, CELL_H, BAR_W, BAR_MAX = 15, 16, 7, 12


def level(count):
    if count <= 0:
        return None
    if count < 3:
        return 0
    if count < 6:
        return 1
    if count < 12:
        return 2
    return 3


def commits(x, y, w, h, cal):
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
            for wk in cal["weeks"] for d in wk["contributionDays"]]
    days = [(d, c) for d, c in days if c is not None]

    weeks, col = [], {}
    for date, count in days:
        row = date.weekday()
        if not weeks or (row == 0 and col):
            weeks.append(col)
            col = {}
        col[row] = (date, count)
    if col:
        weeks.append(col)

    pad, gutter = 24, 30
    x0, y0 = pad + gutter, 60
    total = cal["totalContributions"]

    out = card(x, y, w, h, "COMMITS")
    seen = set()
    for i, week in enumerate(weeks):
        dates = [v[0] for v in week.values()]
        if not dates:
            continue
        first = min(dates)
        if (first.year, first.month) not in seen:
            seen.add((first.year, first.month))
            out.append(txt(x0 + i * CELL_W, y0 - 8, first.strftime("%b"), "cap"))

    for row, name in ((0, "M"), (2, "W"), (4, "F")):
        out.append(txt(pad - 4, y0 + row * CELL_H + CELL_H - 2, name, "cap", "end"))

    for i, week in enumerate(weeks):
        for row, (_, count) in week.items():
            bx = x0 + i * CELL_W + (CELL_W - BAR_W) / 2
            by = y0 + row * CELL_H + CELL_H - 1
            lv = level(count)
            if lv is None:
                out.append(rect(bx, by - 2, BAR_W, 2, DIM, rx=1))
            else:
                bh = 3 + round(BAR_MAX * min(1.0, count / 12))
                out.append(rect(bx, by - bh, BAR_W, bh, ACCENT, OPACITY[lv], rx=1))

    fy = y0 + 7 * CELL_H + 20
    out.append(txt(pad, fy, f"{total:,} contributions"))

    lx = w - pad
    out.append(txt(lx, fy, "More", "cap", "end"))
    for n, op in enumerate(reversed([0.12] + OPACITY)):
        out.append(rect(lx - 44 - n * (BAR_W + 3), fy - 9, BAR_W, 9, ACCENT, op, rx=1))
    out.append(txt(lx - 44 - 5 * (BAR_W + 3), fy, "Less", "cap", "end"))

    out.append(f"<title>{days[0][0]} to {days[-1][0]}</title>")
    out.append("</g>")
    return out


# -------------------------------------------------------------------- whoami

def whoami_card(x, y, w, h):
    out = card(x, y, w, h, "WHOAMI")
    pad = 24
    rows = [("prompt", "whoami"), ("big", LOGIN), ("gap", None),
            ("prompt", "links --social"),
            ("pair", ("telegram", f"@{LOGIN}")), ("pair", ("x", f"@{LOGIN}"))]
    content = sum(16 if kind == "gap" else 25 for kind, _ in rows)
    y0 = 62 + max(0, (h - 82 - content) / 2)
    for kind, value in rows:
        if kind == "gap":
            y0 += 16
            continue
        if kind == "prompt":
            out.append(txt(pad, y0, "$", "accent"))
            out.append(txt(pad + 20, y0, value))
        elif kind == "big":
            out.append(txt(pad, y0 + 4, value, "lede"))
        else:
            key, val = value
            out.append(txt(pad + 20, y0, key, "key"))
            out.append(txt(pad + 96, y0, val))
        y0 += 25
    out.append("</g>")
    return out


# --------------------------------------------------------------------- stack

STACK = [
    ("Sistema", "Linux"),
    ("Shell", "Bash"),
    ("Versiones", "Git"),
    ("UI", "React · Storybook"),
    ("Datos", "Python"),
    ("Web", "JavaScript · TypeScript"),
]


def stack_card(x, y, w, h):
    out = card(x, y, w, h, "STACK")
    pad, label_w, y0 = 24, 104, 64
    for label, value in STACK:
        out.append(txt(pad, y0, label, "key"))
        out.append(txt(pad + label_w, y0, value))
        y0 += 23
    out.append("</g>")
    return out


# ----------------------------------------------------------------- languages

def languages_card(x, y, w, h, repos):
    totals = {}
    for node in repos["nodes"]:
        for edge in node["languages"]["edges"]:
            totals[edge["node"]["name"]] = totals.get(edge["node"]["name"], 0) + edge["size"]
    size = sum(totals.values()) or 1
    share = [(name, bytes_ / size * 100)
             for name, bytes_ in sorted(totals.items(), key=lambda kv: -kv[1])[:5]]
    rest = 100 - sum(p for _, p in share)
    if rest >= 0.3:
        share.append(("other", rest))

    out = card(x, y, w, h, "LANGUAGES")
    pad, label_w, pct_w, row_h = 24, 96, 58, 26
    x_bar = pad + label_w
    bar_w = w - pad * 2 - label_w - pct_w
    mx = max(p for _, p in share)
    y0 = 64
    for name, pct in share:
        out.append(txt(pad, y0, name))
        out.append(rect(x_bar, y0 - 10, bar_w, 10, DIM))
        out.append(rect(x_bar, y0 - 10, max(3, round(bar_w * pct / mx)), 10, ACCENT, 0.85))
        out.append(txt(w - pad, y0, f"{pct:.1f}%", "val", "end"))
        y0 += row_h

    out.append(txt(pad, h - 20, f"by language bytes · {repos['totalCount']} repos", "cap"))
    out.append("</g>")
    return out


# --------------------------------------------------------------------- build

def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    repos = user["repositories"]

    col1 = 420
    rows = [0, ROW_H[0] + GAP, ROW_H[0] + ROW_H[1] + GAP * 2]
    height = sum(ROW_H) + GAP * 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="j1zuz: {cal["totalContributions"]} contributions, stack, languages">',
        f'<style>text{{font-family:{FONT}}}'
        f'.frame{{fill:none;stroke:{FRAME};stroke-dasharray:4 4}}'
        f'.lbl{{fill:{MUTED};font-size:11px}}'
        f'.cap{{fill:{MUTED};font-size:10px}}'
        f'.val{{fill:{TEXT};font-size:11px}}'
        f'.key{{fill:{MUTED};font-size:11px}}'
        f'.lede{{fill:{TEXT};font-size:13px}}'
        f'.accent{{fill:{ACCENT};font-size:11px}}'
        f'.title{{fill:{MUTED};font-size:10px;letter-spacing:2px}}'
        "</style>",
        f'<rect width="{W}" height="{height}" fill="none"/>',
    ]
    parts += commits(0, rows[0], W, ROW_H[0], cal)
    parts += whoami_card(0, rows[1], col1, ROW_H[1])
    parts += stack_card(col1 + GAP, rows[1], W - col1 - GAP, ROW_H[1])
    parts += languages_card(0, rows[2], W, ROW_H[2], repos)
    parts.append("</svg>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts) + "\n")
    print(f"wrote {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    build(fetch())
