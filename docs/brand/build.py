# ruff: noqa: E501
"""Build the OpenFix brand images in docs/assets/.

Run from the repository root:

    uv run --with fonttools --with brotli python docs/brand/build.py

Writes logo-{light,dark}.svg, mark.svg, architecture-{light,dark}.svg and implementation-{light,dark}.svg.
Pass --png to also render social-preview.png (needs Playwright; set CHROMIUM_PATH to use a specific Chromium).

Every SVG embeds a subset of Space Grotesk and JetBrains Mono (SIL OFL 1.1, see docs/brand/fonts/),
so the images look the same on every platform, including inside GitHub's <img> sandbox.
Brand rules live in docs/brand/README.md.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
ICONS = json.loads((HERE / "icons.json").read_text())

# --------------------------------------------------------------------------------------------
# Brand tokens
# --------------------------------------------------------------------------------------------

LIME = "#C6F432"  # Signal Lime: the brand colour. "Verified".
INK = "#0A0E16"  # Ink: the brand dark.

THEMES = {
    "dark": dict(
        name="dark",
        bg="#0A0E16",
        frame="#1C2433",
        dot="#182030",
        panel="#0F141F",
        raised="#141B28",
        line="#232D3F",
        text="#F2F5FA",
        muted="#A3ADBF",
        faint="#6C7689",
        glow=LIME,
        glow_opacity=0.10,
        tile=LIME,
        tile_ink=INK,
        icon="#DCE2EC",
        blue="#7DB2FF",
        blue_tint="#132541",
        violet="#BFA2FF",
        violet_tint="#241C40",
        lime=LIME,
        lime_text=LIME,
        lime_tint="#1D2A0B",
        amber="#FFBE5C",
        amber_tint="#33230B",
        neutral_tint="#1A2130",
    ),
    "light": dict(
        name="light",
        bg="#FFFFFF",
        frame="#E3E8F0",
        dot="#E9EDF3",
        panel="#F7F9FC",
        raised="#FFFFFF",
        line="#E1E6EE",
        text="#0A0E16",
        muted="#525C70",
        faint="#848DA0",
        glow="#B7EB1C",
        glow_opacity=0.16,
        tile=INK,
        tile_ink=LIME,
        icon="#1E2533",
        blue="#1B5FD9",
        blue_tint="#E9F1FF",
        violet="#6A3BDB",
        violet_tint="#F2ECFF",
        lime="#6FA300",
        lime_text="#456B00",
        lime_tint="#EEF9D2",
        amber="#B65A00",
        amber_tint="#FFF1DE",
        neutral_tint="#EEF1F6",
    ),
}

FONTS = {
    ("sans", 400): "space-grotesk-latin-400-normal.woff2",
    ("sans", 500): "space-grotesk-latin-500-normal.woff2",
    ("sans", 700): "space-grotesk-latin-700-normal.woff2",
    ("mono", 500): "jetbrains-mono-latin-500-normal.woff2",
    ("mono", 700): "jetbrains-mono-latin-700-normal.woff2",
}
FAMILY = {
    "sans": "OFSans, 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    "mono": "OFMono, 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
}
_ttf = {k: TTFont(HERE / "fonts" / v) for k, v in FONTS.items()}
_cmaps = {k: f.getBestCmap() for k, f in _ttf.items()}


def measure(s: str, size: float, font: str = "sans", weight: int = 500, ls: float = 0.0) -> float:
    f, cmap = _ttf[(font, weight)], _cmaps[(font, weight)]
    upm, hmtx = f["head"].unitsPerEm, f["hmtx"]
    w = sum(hmtx[cmap.get(ord(c), "space")][0] for c in s)
    return w * size / upm + ls * size * len(s)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def f(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------------------------
# A tiny SVG canvas that remembers which glyphs it used, for font subsetting
# --------------------------------------------------------------------------------------------


class Canvas:
    def __init__(self, w: int, h: int, label: str):
        self.w, self.h, self.label = w, h, label
        self.defs: list[str] = []
        self.out: list[str] = []
        self.glyphs: dict[tuple[str, int], set[str]] = {}

    def add(self, s: str) -> None:
        self.out.append(s)

    def text(self, x, y, s, size, fill, font="sans", weight=500, anchor="start", ls=0.0, opacity=None):
        self.glyphs.setdefault((font, weight), set()).update(s)
        extra = f' letter-spacing="{f(ls * size)}"' if ls else ""
        extra += f' opacity="{opacity}"' if opacity is not None else ""
        self.add(
            f'<text x="{f(x)}" y="{f(y)}" font-family="{FAMILY[font]}" font-size="{f(size)}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>'
        )

    def spans(self, x, y, parts, size, font="sans", weight=500, anchor="start", ls=0.0):
        """parts: list of (text, fill) or (text, fill, weight). One <text> with coloured <tspan>s."""
        inner = []
        for p in parts:
            t, fill = p[0], p[1]
            w = p[2] if len(p) > 2 else weight
            self.glyphs.setdefault((font, w), set()).update(t)
            inner.append(f'<tspan fill="{fill}" font-weight="{w}">{esc(t)}</tspan>')
        extra = f' letter-spacing="{f(ls * size)}"' if ls else ""
        self.add(
            f'<text x="{f(x)}" y="{f(y)}" font-family="{FAMILY[font]}" font-size="{f(size)}" text-anchor="{anchor}"{extra}>{"".join(inner)}</text>'
        )

    def rect(self, x, y, w, h, rx=0, fill="none", stroke=None, sw=1, extra=""):
        s = f' stroke="{stroke}" stroke-width="{f(sw)}"' if stroke else ""
        self.add(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{f(rx)}" fill="{fill}"{s}{extra}/>')

    def line(self, x1, y1, x2, y2, stroke, sw=1.5, extra=""):
        self.add(
            f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{stroke}" stroke-width="{f(sw)}"{extra}/>'
        )

    def path(self, d, fill="none", stroke=None, sw=1.5, extra=""):
        s = (
            f' stroke="{stroke}" stroke-width="{f(sw)}" stroke-linecap="round" stroke-linejoin="round"'
            if stroke
            else ""
        )
        self.add(f'<path d="{d}" fill="{fill}"{s}{extra}/>')

    def icon(self, name, x, y, size, fill):
        ic = ICONS[name]
        vb = [float(v) for v in ic["viewBox"].split()]
        h = size * vb[3] / vb[2]
        paths = "".join(f'<path d="{d}"/>' for d in ic["paths"])
        self.add(
            f'<svg x="{f(x)}" y="{f(y + (size - h) / 2)}" width="{f(size)}" height="{f(h)}" viewBox="{ic["viewBox"]}"><g fill="{fill}">{paths}</g></svg>'
        )

    def arrow(self, x1, y1, x2, y2, stroke, sw=1.75, head=6.0, dash=None):
        ang = math.atan2(y2 - y1, x2 - x1)
        d = f"M{f(x1)} {f(y1)} L{f(x2)} {f(y2)}"
        a1, a2 = ang + math.radians(150), ang - math.radians(150)
        hd = f"M{f(x2 + head * math.cos(a1))} {f(y2 + head * math.sin(a1))} L{f(x2)} {f(y2)} L{f(x2 + head * math.cos(a2))} {f(y2 + head * math.sin(a2))}"
        ex = f' stroke-dasharray="{dash}"' if dash else ""
        self.path(d, stroke=stroke, sw=sw, extra=ex)
        self.path(hd, stroke=stroke, sw=sw)

    def svg(self) -> str:
        style = font_css(self.glyphs)
        defs = f"<defs><style>{style}</style>{''.join(self.defs)}</defs>"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" role="img" aria-label="{esc(self.label)}">'
            f"{defs}{''.join(self.out)}</svg>\n"
        )


def font_css(glyphs: dict[tuple[str, int], set[str]]) -> str:
    rules = []
    for (font, weight), chars in sorted(glyphs.items()):
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = []
        opts.notdef_outline = True
        tt = TTFont(HERE / "fonts" / FONTS[(font, weight)])
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)) + " ")
        sub.subset(tt)
        buf = io.BytesIO()
        tt.flavor = "woff2"
        tt.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        fam = "OFSans" if font == "sans" else "OFMono"
        rules.append(
            f"@font-face{{font-family:{fam};font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(rules)


# --------------------------------------------------------------------------------------------
# The mark: an open ring with a check that breaks out of it. "Open" + "verified fix".
# --------------------------------------------------------------------------------------------

MARK_RING = "M45.77 30.4 A15 15 0 1 1 31 18"
MARK_CHECK = "M23.5 33.5 L30 40 L48.5 17"


def mark(c: Canvas, x: float, y: float, size: float, tile: str, ink: str, rx_ratio: float = 0.27) -> None:
    s = size / 64
    c.add(
        f'<g transform="translate({f(x)} {f(y)}) scale({f(s)})">'
        f'<rect width="64" height="64" rx="{f(64 * rx_ratio)}" fill="{tile}"/>'
        f'<path d="{MARK_RING}" fill="none" stroke="{ink}" stroke-width="6.5" stroke-linecap="round"/>'
        f'<path d="{MARK_CHECK}" fill="none" stroke="{ink}" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>'
        "</g>"
    )


def background(c: Canvas, T: dict, glow_at=(1.0, 0.0)) -> None:
    c.defs.append(
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="{T["dot"]}"/></pattern>'
        f'<radialGradient id="glow" cx="{glow_at[0]}" cy="{glow_at[1]}" r="0.75"><stop offset="0" stop-color="{T["glow"]}" stop-opacity="{T["glow_opacity"]}"/><stop offset="1" stop-color="{T["glow"]}" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="frame"><rect x="1" y="1" width="{c.w - 2}" height="{c.h - 2}" rx="20"/></clipPath>'
    )
    c.rect(1, 1, c.w - 2, c.h - 2, 20, T["bg"])
    c.add('<g clip-path="url(#frame)">')
    c.rect(0, 0, c.w, c.h, fill="url(#dots)")
    c.rect(0, 0, c.w, c.h, fill="url(#glow)")
    c.add("</g>")
    c.rect(1, 1, c.w - 2, c.h - 2, 20, "none", T["frame"])


def headline(c: Canvas, T: dict, x, y, size, plain: str, hl: str = "", ls=-0.02, weight=700) -> None:
    """Plain text followed by the brand-highlighted part: lime text on dark, a lime marker stroke on light."""
    if hl and T["name"] == "light":
        x0 = x + measure(plain, size, "sans", weight, ls) - size * 0.08
        w = measure(hl, size, "sans", weight, ls) + size * 0.16
        c.rect(x0, y - size * 0.62, w, size * 0.78, size * 0.12, LIME)
        c.spans(x, y, [(plain, T["text"]), (hl, INK)], size, weight=weight, ls=ls)
    else:
        c.spans(x, y, [(plain, T["text"]), (hl, T["lime"])], size, weight=weight, ls=ls)


def header(c: Canvas, T: dict, eyebrow: str, title: tuple[str, str], chip_parts) -> None:
    mark(c, 32, 30, 46, T["tile"], T["tile_ink"])
    c.spans(94, 44, [("OPENFIX", T["text"], 700), ("  /  " + eyebrow, T["faint"], 500)], 12, font="mono", ls=0.14)
    headline(c, T, 93, 75, 28, *title)
    # terminal-style chip on the right
    w = sum(measure(p[0], 15, "mono", 500) for p in chip_parts) + 36
    x = c.w - 32 - w
    c.rect(x, 36, w, 38, 10, T["panel"], T["line"])
    c.spans(x + 18, 60, chip_parts, 15, font="mono")


def pill(c, x, y, s, fg, bg, size=11.5, center=False, h=24, stroke=None):
    w = measure(s, size, "mono", 700, 0.12) + 22
    x0 = x - w / 2 if center else x
    c.rect(x0, y, w, h, h / 2, bg, stroke)
    c.text(
        x0 + w / 2 - 0.06 * size,
        y + h / 2 + size * 0.36,
        s,
        size,
        fg,
        font="mono",
        weight=700,
        anchor="middle",
        ls=0.12,
    )
    return w


def chip(c, x, y, w, s, T, fg=None, bg=None, stroke=None, font="sans", weight=500, size=14, h=30):
    c.rect(x, y, w, h, 8, bg or T["raised"], stroke if stroke is not None else T["line"])
    c.text(x + w / 2, y + h / 2 + size * 0.35, s, size, fg or T["text"], font=font, weight=weight, anchor="middle")


def small_arrow(c, x, y, color, length=12):
    c.arrow(x, y, x + length, y, color, sw=1.5, head=4.5)


def check(c, cx, cy, r, T):
    c.add(
        f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{T["lime_tint"]}" stroke="{T["lime"]}" stroke-width="1.25"/>'
    )
    c.path(
        f"M{f(cx - r * 0.42)} {f(cy + r * 0.02)} L{f(cx - r * 0.1)} {f(cy + r * 0.36)} L{f(cx + r * 0.45)} {f(cy - r * 0.34)}",
        stroke=T["lime_text"] if T["name"] == "light" else T["lime"],
        sw=1.9,
    )


# --------------------------------------------------------------------------------------------
# Logo lockup
# --------------------------------------------------------------------------------------------


def logo(T: dict) -> str:
    c = Canvas(560, 132, "OpenFix")
    mark(c, 6, 14, 104, T["tile"], T["tile_ink"])
    headline(c, T, 134, 82, 68, "Open", "Fix", ls=-0.035)
    c.text(137, 116, "verified security fixes from any model", 17, T["muted"], font="mono", weight=500, ls=-0.01)
    return c.svg()


def mark_svg() -> str:
    c = Canvas(64, 64, "OpenFix")
    mark(c, 0, 0, 64, INK, LIME)
    return c.svg()


# --------------------------------------------------------------------------------------------
# Pipeline diagram
# --------------------------------------------------------------------------------------------


def architecture(T: dict) -> str:
    c = Canvas(1280, 636, "OpenFix pipeline: ingest, policy, agent, verify, ship.")
    background(c, T)
    header(
        c,
        T,
        "PIPELINE",
        ("Models propose. ", "Code verifies."),
        [("$ ", T["lime_text"], 700), ("openfix fix ", T["text"]), ("report.sarif", T["muted"])],
    )

    X0, W, GAP, Y, H = 32, 220, 29, 160, 360
    cols = [X0 + i * (W + GAP) for i in range(5)]
    accents = ["blue", "blue", "violet", "lime", "amber"]

    # phase rails
    phases = [
        (0, 1, "DETERMINISTIC", "blue"),
        (2, 2, "MODEL PROPOSES", "violet"),
        (3, 3, "CODE VERIFIES", "lime"),
        (4, 4, "YOU DECIDE", "amber"),
    ]
    for a, b, label, acc in phases:
        x1, x2 = cols[a] + 4, cols[b] + W - 4
        mid = (x1 + x2) / 2
        tw = measure(label, 11.5, "mono", 700, 0.12) + 22
        fg = T["lime_text"] if acc == "lime" else T[acc]
        c.line(x1, 124, mid - tw / 2 - 8, 124, T[acc], 1.5, ' stroke-linecap="round" opacity="0.55"')
        c.line(mid + tw / 2 + 8, 124, x2, 124, T[acc], 1.5, ' stroke-linecap="round" opacity="0.55"')
        c.add(
            f'<circle cx="{f(x1)}" cy="124" r="2.5" fill="{T[acc]}"/><circle cx="{f(x2)}" cy="124" r="2.5" fill="{T[acc]}"/>'
        )
        pill(c, mid, 112, label, fg, T[acc + "_tint"], center=True)

    titles = ["Ingest", "Policy", "Agent", "Verify", "Ship"]
    footers = ["untrusted input", "openfix.yaml", "disposable worktree", "sandboxed, offline", "openfix receipt verify"]
    for i, x in enumerate(cols):
        acc = T[accents[i]]
        hero = i == 3
        if hero:
            c.defs.append(
                '<filter id="halo" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
            )
            c.rect(
                x + 6,
                Y + 10,
                W - 12,
                H - 10,
                16,
                T["lime"],
                extra=f' opacity="{0.22 if T["name"] == "dark" else 0.28}" filter="url(#halo)"',
            )
        c.rect(
            x, Y, W, H, 14, T["raised"] if hero else T["panel"], T["lime"] if hero else T["line"], 1.5 if hero else 1
        )
        c.path(f"M{x + 18} {Y + 0.75} h{W - 36}", stroke=acc, sw=3)
        c.text(
            x + 20, Y + 44, f"0{i + 1}", 13, T["lime_text"] if accents[i] == "lime" else acc, font="mono", weight=700
        )
        c.text(x + 48, Y + 45, titles[i], 23, T["text"], weight=700, ls=-0.02)
        c.line(x + 20, Y + 66, x + W - 20, Y + 66, T["line"], 1)
        c.line(x + 20, Y + H - 42, x + W - 20, Y + H - 42, T["line"], 1)
        c.text(x + W / 2, Y + H - 17, footers[i], 12.5, T["faint"], font="mono", weight=500, anchor="middle")
        if i < 4:
            c.arrow(x + W + 7, Y + 39, x + W + GAP - 7, Y + 39, T["faint"], sw=1.75, head=5)

    # 1 Ingest
    x = cols[0]
    names = ["SARIF", "CodeQL", "Semgrep", "Snyk", "Trivy", "OSV", "Gitleaks", "Dependabot"]
    for k, n in enumerate(names):
        cx = x + 20 + (k % 2) * 96
        cy = Y + 88 + (k // 2) * 40
        chip(c, cx, cy, 88, n, T, size=13.5)
    small_arrow(c, x + 22, Y + 266, T["blue"])
    c.text(x + 42, Y + 271, "one finding model", 14.5, T["muted"])

    # 2 Policy
    x = cols[1]
    rows = [("autofix", "draft PR", "lime"), ("propose", "patch only", "amber"), ("skip", "no model", "neutral")]
    for k, (a, out, tone) in enumerate(rows):
        cy = Y + 88 + k * 46
        fg = {"lime": T["lime_text"], "amber": T["amber"], "neutral": T["muted"]}[tone]
        bg = T[tone + "_tint"]
        c.rect(x + 20, cy, 92, 32, 8, bg)
        c.text(x + 66, cy + 21, a, 14, fg, font="mono", weight=700, anchor="middle")
        small_arrow(c, x + 121, cy + 16, T["faint"], 11)
        c.text(x + 140, cy + 21, out, 14, T["muted"])
    c.text(x + 20, Y + 254, "guards · budgets", 15, T["text"], weight=700)
    c.text(x + 20, Y + 278, "local-only paths", 15, T["text"], weight=700)

    # 3 Agent
    x = cols[2]
    models = ["Claude", "OpenAI", "Gemini", "Grok", "Ollama", "+ more"]
    for k, n in enumerate(models):
        cx = x + 20 + (k % 2) * 96
        cy = Y + 88 + (k // 2) * 40
        chip(c, cx, cy, 88, n, T, fg=T["violet"], bg=T["violet_tint"], stroke="none", size=14)
    c.text(x + 20, Y + 230, "read · edit · test", 14, T["text"], font="mono", weight=500)
    c.text(x + 20, Y + 254, "rescan · submit", 14, T["text"], font="mono", weight=500)
    c.text(x + 20, Y + 282, "no shell, net or git", 14.5, T["muted"])

    # 4 Verify
    x = cols[3]
    checks = [
        ("Rescan", "finding gone"),
        ("Tests", "no regressions"),
        ("Regression test", "red before, green after"),
        ("Review", "second model, optional"),
    ]
    for k, (a, b) in enumerate(checks):
        cy = Y + 98 + k * 52
        check(c, x + 31, cy - 5, 9.5, T)
        c.text(x + 50, cy, a, 15.5, T["text"], weight=700)
        c.text(x + 50, cy + 20, b, 13.5, T["muted"])

    # 5 Ship
    x = cols[4]
    ships = [
        ("receipt.json", "signed, re-checkable"),
        ("patch.diff", "hash-bound"),
        ("openfix.sarif", "SARIF fixes[]"),
        ("draft PR", "never auto-merged"),
    ]
    for k, (a, b) in enumerate(ships):
        cy = Y + 84 + k * 52
        c.rect(x + 20, cy, 3, 40, 1.5, T["amber"])
        c.text(x + 34, cy + 16, a, 15, T["text"], font="mono", weight=700)
        c.text(x + 34, cy + 35, b, 13.5, T["muted"])

    # callouts
    def callout(cx, parts, tone):
        size = 14.5
        w = sum(measure(p[0], size, "sans", p[2] if len(p) > 2 else 500) for p in parts) + 56
        y = Y + H + 46
        c.line(cx, Y + H + 2, cx, y, T["faint"], 1.5, ' stroke-dasharray="3 5" stroke-linecap="round"')
        c.rect(cx - w / 2, y, w, 40, 20, T["raised"], T["line"])
        c.add(f'<circle cx="{f(cx - w / 2 + 22)}" cy="{f(y + 20)}" r="4" fill="{T[tone]}"/>')
        c.spans(cx - w / 2 + 36, y + 25, parts, size)

    callout(
        cols[1] + W / 2,
        [("Not reproduced by a fresh scan? ", T["text"], 700), ("Dropped, no model call.", T["muted"])],
        "blue",
    )
    callout(
        cols[3] + W / 2,
        [("A required check fails? ", T["text"], 700), ("Patch and evidence, no PR.", T["muted"])],
        "amber",
    )
    return c.svg()


# --------------------------------------------------------------------------------------------
# Implementation diagram
# --------------------------------------------------------------------------------------------


def panel(c, T, x, y, w, h, label, acc, note=None):
    c.rect(x, y, w, h, 16, T["panel"], T["line"])
    c.path(f"M{x + 18} {y + 0.75} h{w - 36}", stroke=T[acc], sw=3)
    fg = T["lime_text"] if acc == "lime" else T[acc]
    pill(c, x + 18, y + 20, label, fg, T[acc + "_tint"])
    if note:
        c.text(x + w - 20, y + 37, note, 12.5, T["faint"], font="mono", weight=500, anchor="end")


def code_box(c, T, x, y, w, h, title, sub=None, acc="blue", sub_mono=False):
    c.rect(x, y, w, h, 10, T["raised"], T["line"])
    c.rect(x, y + 10, 3, h - 20, 1.5, T["lime"] if acc == "lime" else T[acc])
    c.text(x + 16, y + 25, title, 15, T["text"], font="mono", weight=700)
    if sub:
        c.text(x + 16, y + 46, sub, 13, T["muted"], font="mono" if sub_mono else "sans", weight=500)


def tag(c, T, x, y, s, fg, bg, size=12.5, font="mono", weight=500):
    w = measure(s, size, font, weight) + 20
    c.rect(x, y, w, 24, 6, bg)
    c.text(x + w / 2, y + 16.5, s, size, fg, font=font, weight=weight, anchor="middle")
    return w


def implementation(T: dict) -> str:
    c = Canvas(1280, 980, "OpenFix implementation: scanners in, OpenFix core with any model provider, results out.")
    background(c, T, glow_at=(1.0, 0.0))
    header(
        c,
        T,
        "ARCHITECTURE",
        ("How it's built", ""),
        [("src/openfix/", T["text"]), (" · ", T["faint"]), ("Python 3.10+", T["muted"])],
    )

    # --- providers ---------------------------------------------------------------------------
    PX, PY, PW, PH = 330, 112, 620, 176
    panel(c, T, PX, PY, PW, PH, "MODEL PROVIDERS", "violet", "providers/ · provider:model")
    provs = [("claude", "Claude"), ("gemini", "Gemini"), ("openai", "OpenAI"), (None, "Grok"), ("ollama", "Ollama")]
    tw, tg = 104, 12
    for k, (ic, name) in enumerate(provs):
        tx = PX + 22 + k * (tw + tg)
        c.rect(tx, PY + 60, tw, 70, 10, T["raised"], T["line"])
        if ic:
            c.icon(ic, tx + tw / 2 - 13, PY + 72, 26, T["icon"])
        else:
            c.text(tx + tw / 2, PY + 93, "xAI", 19, T["icon"], weight=700, anchor="middle", ls=-0.02)
        c.text(tx + tw / 2, PY + 118, name, 14.5, T["text"], weight=700, anchor="middle")
    by = PY + 142

    def bracket(x1, x2, label):
        c.path(f"M{f(x1)} {by - 5} V{by} H{f(x2)} V{by - 5}", stroke=T["violet"], sw=1.25, extra=' opacity="0.6"')
        c.text((x1 + x2) / 2, by + 19, label, 12.5, T["violet"], font="mono", weight=700, anchor="middle")

    t = lambda k: PX + 22 + k * (tw + tg)  # noqa: E731
    bracket(t(0) + 4, t(0) + tw - 4, "anthropic.py")
    bracket(t(1) + 4, t(1) + tw - 4, "gemini.py")
    bracket(t(2) + 4, t(4) + tw - 4, "openai_compat.py")

    # --- scanners in ---------------------------------------------------------------------------
    SX, SY, SW, SH = 28, 340, 270, 440
    panel(c, T, SX, SY, SW, SH, "SCANNERS IN", "blue")
    scanners = [
        ("snyk", "Snyk", "Code · Open Source"),
        ("semgrep", "Semgrep", "SARIF · JSON"),
        ("github", "GitHub", "CodeQL · Dependabot"),
        ("trivy", "Trivy", "vulns · IaC · secrets"),
        ("file", "Any SARIF 2.1.0", "OSV · Gitleaks · Bandit"),
    ]
    for k, (ic, name, sub) in enumerate(scanners):
        y = SY + 64 + k * 56
        c.rect(SX + 18, y, 36, 36, 9, T["raised"], T["line"])
        if ic == "file":
            c.path(f"M{SX + 29} {y + 9} h9 l6 6 v13 h-15 z M{SX + 38} {y + 9} v6 h6", stroke=T["icon"], sw=1.4)
            c.path(f"M{SX + 32} {y + 21} h8 M{SX + 32} {y + 25} h6", stroke=T["icon"], sw=1.2)
        else:
            c.icon(ic, SX + 26, y + 8, 20, T["icon"])
        c.text(SX + 66, y + 15, name, 15.5, T["text"], weight=700)
        c.text(SX + 66, y + 33, sub, 13, T["muted"])
    c.line(SX + 18, SY + 350, SX + SW - 18, SY + 350, T["line"])
    y = SY + 368
    c.rect(SX + 18, y, 36, 36, 9, T["lime_tint"])
    c.text(SX + 36, y + 23, "{ }", 14, T["lime_text"], font="mono", weight=700, anchor="middle")
    c.text(SX + 66, y + 15, "openfix.yaml", 15, T["text"], font="mono", weight=700)
    c.text(SX + 66, y + 33, "your policy", 13, T["muted"])

    # --- core ------------------------------------------------------------------------------------
    CX, CY, CW, CH = 330, 340, 620, 440
    panel(c, T, CX, CY, CW, CH, "OPENFIX CORE", "lime", "deterministic Python")
    LX, LW = CX + 22, 168
    code_box(c, T, LX, CY + 64, LW, 62, "ingest.py", "detect · normalize")
    code_box(c, T, LX, CY + 164, LW, 62, "policy.py", "first match wins")
    code_box(c, T, LX, CY + 264, LW, 62, "engine.py", "runs each finding")
    c.arrow(LX + LW / 2, CY + 130, LX + LW / 2, CY + 158, T["faint"], head=5)
    c.arrow(LX + LW / 2, CY + 230, LX + LW / 2, CY + 258, T["faint"], head=5)

    RX = CX + 214
    RW = CX + CW - 22 - RX
    # agent loop
    c.rect(RX, CY + 64, RW, 98, 10, T["raised"], T["line"])
    c.rect(RX, CY + 74, 3, 78, 1.5, T["violet"])
    c.spans(
        RX + 16,
        CY + 89,
        [("agent/loop.py", T["text"]), ("  ·  ", T["faint"]), ("tools.py", T["text"])],
        15,
        font="mono",
        weight=700,
    )
    tx = RX + 16
    for k, tool in enumerate(["read_file", "search", "edit_file", "run_tests", "rescan", "submit"]):
        if k == 3:
            tx = RX + 16
        w = tag(c, T, tx, CY + 102 + (k // 3) * 0 + (28 if k >= 3 else 0) - 2, tool, T["violet"], T["violet_tint"])
        tx += w + 8
    # gitutil
    GX, GY, GW = RX, CY + 192, 180
    code_box(c, T, GX, GY, GW, 78, "gitutil.py", acc="blue")
    c.icon("git", GX + 16, GY + 37, 16, T["icon"])
    c.text(GX + 40, GY + 50, "disposable", 13, T["muted"])
    c.text(GX + 16, GY + 68, "worktree per finding", 13, T["muted"])
    # sandbox + scanners
    BX, BW = GX + GW + 16, RX + RW - (GX + GW + 16)
    c.rect(BX, GY, BW, 78, 10, T["raised"], T["line"])
    c.rect(BX, GY + 10, 3, 58, 1.5, T["blue"])
    c.text(BX + 16, GY + 25, "sandbox.py", 15, T["text"], font="mono", weight=700)
    c.icon("docker", BX + 16, GY + 34, 18, T["icon"])
    c.text(BX + 42, GY + 47, "--network none", 13, T["muted"], font="mono", weight=500)
    c.text(BX + 16, GY + 69, "scanners.py", 15, T["text"], font="mono", weight=700)
    for k, ic in enumerate(["semgrep", "snyk", "trivy"]):
        c.icon(ic, BX + 132 + k * 22, GY + 59, 15, T["icon"])
    # verify
    VY = CY + 304
    c.rect(RX, VY, RW, 112, 10, T["raised"], T["lime"], 1.25)
    c.rect(RX, VY + 10, 3, 92, 1.5, T["lime"])
    c.spans(RX + 16, VY + 26, [("verify.py", T["text"], 700)], 15, font="mono")
    c.text(RX + 112, VY + 26, "independent of the agent", 13.5, T["muted"])
    tx = RX + 16
    for v in ["rescan", "tests", "regression_test", "review"]:
        w = tag(c, T, tx, VY + 42, v, T["lime_text"], T["lime_tint"], weight=700)
        tx += w + 8
    c.text(RX + 16, VY + 94, "baseline on the original code, then the patch", 13.5, T["muted"])

    # core arrows
    ey = CY + 295
    c.path(f"M{LX + LW + 2} {ey} H{LX + LW + 12} V{GY + 46} H{GX - 4}", stroke=T["faint"], sw=1.75)  # engine -> gitutil
    c.path(f"M{GX - 9} {GY + 41} L{GX - 4} {GY + 46} L{GX - 9} {GY + 51}", stroke=T["faint"], sw=1.75)
    c.arrow(GX + 90, GY - 2, GX + 90, CY + 168, T["faint"], head=5)  # gitutil -> agent
    px = GX + GW + 8
    c.arrow(px, CY + 166, px, VY - 4, T["faint"], head=5)  # agent -> verify (patch.diff)
    c.text(px - 8, VY - 11, "patch.diff", 12, T["faint"], font="mono", weight=500, anchor="end")
    c.arrow(BX + 80, VY - 2, BX + 80, GY + 82, T["faint"], head=5, dash="3 4")  # verify -> sandbox

    # providers <-> agent
    ax = RX + 150
    c.arrow(ax - 7, PY + PH + 2, ax - 7, CY + 60, T["violet"], head=5)
    c.arrow(ax + 7, CY + 60, ax + 7, PY + PH + 2, T["violet"], head=5)
    pill(c, ax + 24, PY + PH + 14, "TOOL CALLS ONLY", T["violet"], T["violet_tint"], size=10.5)

    # scanners -> core
    c.arrow(SX + SW + 4, CY + 95, LX - 4, CY + 95, T["blue"], head=5)

    # --- results out -----------------------------------------------------------------------------
    OX, OY, OW, OH = 982, 340, 270, 440
    panel(c, T, OX, OY, OW, OH, "RESULTS OUT", "amber")
    outs = [
        ("receipt.json", "receipt.py", "in-toto · optional cosign"),
        ("patch.diff", "receipt.py", "sha256 = receipt subject"),
        ("openfix.sarif", "sarif_out.py", "SARIF with fixes[]"),
        ("summary.md", "report.py", "+ summary.json"),
    ]
    for k, (a, mod, sub) in enumerate(outs):
        y = OY + 66 + k * 58
        c.rect(OX + 18, y, 3, 42, 1.5, T["amber"])
        c.text(OX + 32, y + 17, a, 15, T["text"], font="mono", weight=700)
        c.text(OX + OW - 18, y + 17, mod, 11.5, T["faint"], font="mono", weight=500, anchor="end")
        c.text(OX + 32, y + 37, sub, 13, T["muted"])
    y = OY + 312
    c.rect(OX + 18, y, OW - 36, 110, 12, T["raised"], T["line"])
    c.icon("github", OX + 34, y + 16, 26, T["icon"])
    c.text(OX + 72, y + 28, "Draft pull request", 15.5, T["text"], weight=700)
    c.text(OX + 72, y + 46, "github.py", 12.5, T["faint"], font="mono", weight=500)
    c.text(OX + 34, y + 76, "verified autofix only", 13, T["muted"])
    c.text(OX + 34, y + 95, "evidence table · never merges", 13, T["muted"])
    c.arrow(CX + CW + 4, y + 55, OX + 14, y + 55, T["amber"], head=5)

    # --- runs on ---------------------------------------------------------------------------------
    UX, UY, UW, UH = 28, 812, 1224, 140
    panel(c, T, UX, UY, UW, UH, "RUNS ON", "neutral_tint_label")
    runs = [
        ("actions", "CLI or GitHub Action", "composite action.yml"),
        ("git", "git worktree", "your checkout is never touched"),
        ("docker", "Docker sandbox", "no network · cap-drop ALL"),
        ("python", "Python 3.10+", "pydantic · httpx · official SDKs"),
    ]
    rw = (UW - 36 - 3 * 14) / 4
    for k, (ic, a, b) in enumerate(runs):
        x = UX + 18 + k * (rw + 14)
        c.rect(x, UY + 58, rw, 62, 10, T["raised"], T["line"])
        c.icon(ic, x + 16, UY + 75, 28, T["icon"])
        c.text(x + 58, UY + 84, a, 15.5, T["text"], weight=700)
        c.text(x + 58, UY + 104, b, 13, T["muted"])
    return c.svg()


# "RUNS ON" uses a neutral pill; give panel() what it needs without a new accent colour.
for _T in THEMES.values():
    _T["neutral_tint_label"] = _T["muted"]
    _T["neutral_tint_label_tint"] = _T["neutral_tint"]


# --------------------------------------------------------------------------------------------
# Social preview (1280x640) for the repository's Settings > Social preview
# --------------------------------------------------------------------------------------------


def social(T: dict) -> str:
    c = Canvas(1280, 640, "OpenFix")
    background(c, T, glow_at=(0.95, 0.05))
    mark(c, 96, 150, 132, T["tile"], T["tile_ink"])
    headline(c, T, 262, 248, 112, "Open", "Fix", ls=-0.035)
    headline(c, T, 100, 380, 54, "Models propose. ", "Code verifies.", ls=-0.025)
    c.text(102, 440, "Turn scanner findings into verified fixes,", 26, T["muted"], weight=500)
    c.text(102, 476, "with any model, under your policy.", 26, T["muted"], weight=500)
    # a verified-fix card on the right
    x, y, w, h = 906, 150, 282, 340
    c.defs.append(
        '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="22"/></filter>'
    )
    c.rect(x + 20, y + 30, w - 40, h - 30, 18, T["lime"], extra=' opacity="0.16" filter="url(#soft)"')
    c.rect(x, y, w, h, 18, T["raised"], T["line"])
    c.path(f"M{x + 20} {y + 0.75} h{w - 40}", stroke=T["lime"], sw=3)
    c.text(x + 24, y + 42, "FINDING", 11, T["faint"], font="mono", weight=700, ls=0.14)
    c.text(x + 24, y + 68, "command injection", 19, T["text"], weight=700)
    c.text(x + 24, y + 90, "src/exec.js:9", 13, T["muted"], font="mono", weight=500)
    c.line(x + 24, y + 110, x + w - 24, y + 110, T["line"])
    for k, (a, b) in enumerate(
        [("rescan", "finding gone"), ("tests", "passed"), ("regression test", "red → green"), ("review", "approved")]
    ):
        cy = y + 142 + k * 36
        check(c, x + 34, cy - 5, 9.5, T)
        c.text(x + 54, cy, a, 15, T["text"], weight=700)
        c.text(x + w - 24, cy, b.replace(" → ", " to "), 13, T["muted"], anchor="end")
    c.line(x + 24, y + 278, x + w - 24, y + 278, T["line"])
    pill(c, x + 24, y + 296, "VERIFIED", INK, T["lime"], size=12, h=26)
    c.text(x + w - 24, y + 314, "receipt signed", 13, T["muted"], font="mono", weight=500, anchor="end")
    c.spans(
        102,
        560,
        [
            ("$ ", T["lime_text"], 700),
            ("openfix fix ", T["text"]),
            ("report.sarif", T["muted"]),
            ("   ·   github.com/markusweldon/openfix", T["faint"]),
        ],
        20,
        font="mono",
    )
    return c.svg()


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    out = {"mark.svg": mark_svg()}
    for name, T in THEMES.items():
        out[f"logo-{name}.svg"] = logo(T)
        out[f"architecture-{name}.svg"] = architecture(T)
        out[f"implementation-{name}.svg"] = implementation(T)
    for fn, svg in out.items():
        (ASSETS / fn).write_text(svg)
        print(f"wrote docs/assets/{fn} ({len(svg) / 1024:.0f} KB)")
    if "--png" in sys.argv:  # GitHub's social preview must be a PNG or JPG
        render_png(social(THEMES["dark"]), ASSETS / "social-preview.png", 1280, 640)
        print("wrote docs/assets/social-preview.png")


def render_png(svg: str, dest: Path, w: int, h: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.set_content(f"<html><body style='margin:0;background:{INK}'>{svg}</body></html>")
        page.wait_for_timeout(300)
        page.screenshot(path=str(dest), clip={"x": 0, "y": 0, "width": w, "height": h})
        b.close()


if __name__ == "__main__":
    main()
