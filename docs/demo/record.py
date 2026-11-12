# ruff: noqa: E501
"""Record the README demo (docs/assets/demo-{dark,light}.gif).

Run from the repository root:  python docs/demo/record.py
Needs vhs, ffmpeg, node, semgrep, snyk, gh (signed in) and Google Chrome, and OpenFix installed in .venv.

It clones github.com/markusweldon/openfix-demo (a copy of examples/vulnerable-app), fixes one Snyk Code and
one Semgrep finding with --open-prs, then cuts to a screenshot of the Snyk fix's draft PR. Reruns reuse the
same PR branches. The model's tool calls are replayed from demo/snyk-and-semgrep.script.yaml; Snyk Code,
Semgrep, the tests and GitHub are real. Waits are sped up SPEED times. Colours follow the diagrams (GitHub Primer).
"""

import json
import subprocess
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
gif_dir = repo / "docs" / "assets"
work = Path(tempfile.mkdtemp(prefix="openfix-demo-"))

THEMES = {
    "dark": dict(
        page="#0d1117",
        theme={
            "name": "openfix-dark",
            "background": "#151b23",
            "foreground": "#f0f6fc",
            "selection": "#2e1c4f",
            "cursor": "#ab7df8",
            "black": "#484f58",
            "red": "#ff7b72",
            "green": "#3fb950",
            "yellow": "#d29922",
            "blue": "#4493f8",
            "magenta": "#ab7df8",
            "cyan": "#39c5cf",
            "white": "#b1bac4",
            "brightBlack": "#7d8590",
            "brightRed": "#ffa198",
            "brightGreen": "#56d364",
            "brightYellow": "#e3b341",
            "brightBlue": "#79c0ff",
            "brightMagenta": "#d2a8ff",
            "brightCyan": "#56d4dd",
            "brightWhite": "#f0f6fc",
        },
    ),
    "light": dict(
        page="#ffffff",
        theme={
            "name": "openfix-light",
            "background": "#f6f8fa",
            "foreground": "#1f2328",
            "selection": "#fbefff",
            "cursor": "#8250df",
            "black": "#24292f",
            "red": "#cf222e",
            "green": "#1a7f37",
            "yellow": "#9a6700",
            "blue": "#0969da",
            "magenta": "#8250df",
            "cyan": "#1b7c83",
            "white": "#6e7781",
            "brightBlack": "#59636e",
            "brightRed": "#a40e26",
            "brightGreen": "#116329",
            "brightYellow": "#7d4e00",
            "brightBlue": "#0550ae",
            "brightMagenta": "#6639ba",
            "brightCyan": "#3192aa",
            "brightWhite": "#1f2328",
        },
    ),
}

DEMO_REPO = "markusweldon/openfix-demo"
PR_BRANCH = "openfix/of-ffa7e9b99908"  # the Snyk Code fix; ids are stable fingerprints of the finding
APP = work / "openfix-demo"
VENV = repo / ".venv" / "bin"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SPEED = 6  # VHS plays the recording back this much faster; sleeps and typing are scaled to compensate
HOLD = "Wait+Line@300s /❯ *$/"
W, H, MARGIN = 1400, 800, 24


def q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def wait(seconds: float) -> str:
    """A pause that lasts ``seconds`` in the finished GIF."""
    return f"Sleep {seconds * SPEED:g}s"


def rc(cfg: dict) -> str:
    """Shell setup: the prompt, an intro header, and the title and end cards."""
    t = cfg["theme"]

    def rgb(hexcolor: str) -> str:
        r, g, b = (int(hexcolor[i : i + 2], 16) for i in (1, 3, 5))
        return f"\\e[38;2;{r};{g};{b}m"

    accent, green, muted = rgb(t["magenta"]), rgb(t["green"]), rgb(t["brightBlack"])
    return f"""export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 BASH_SILENCE_DEPRECATION_WARNING=1
export PATH="{VENV}:$PATH" GITHUB_TOKEN="$(gh auth token)"
cd "{APP}"
PS1='\\[\\e[90m\\]openfix-demo \\[\\e[35m\\]❯\\[\\e[0m\\] '
PS2='  '
card() {{ clear; printf '\\e[?25l\\n\\n\\n\\n'; for line in "$@"; do printf '    %b\\e[0m\\n\\n' "$line"; done; }}
title() {{ card "{accent}\\e[1mOpenFix" "\\e[1mFindings from any scanner in. Verified fixes out." "{muted}Snyk Code and Semgrep each found a vulnerability in this app."; }}
intro() {{ clear; printf '\\e[?25h\\n \\e[1mSnyk Code\\e[0m: command injection in /ping    \\e[1mSemgrep\\e[0m: path traversal in readUserFile\\n {muted}One command fixes both, proves each fix, and opens a draft PR for it.\\e[0m\\n\\n'; }}
done_card() {{ card "{green}\\e[1m✔  2 scanners in, 2 verified fixes out" "Each fix: the scanner no longer reports it, the tests pass," "and a new regression test fails before the fix and passes after." "Each one lands as a draft PR with the evidence and a signed receipt." "{muted}Model calls are replayed for this demo; Snyk, Semgrep, the tests and GitHub are real." "{accent}github.com/markusweldon/openfix"; }}
"""


def settings(cfg: dict, output: Path) -> list[str]:
    return [
        f'Output "{output}"',
        'Set Shell "bash"',
        'Set FontFamily "Menlo"',
        "Set FontSize 22",
        "Set LineHeight 1.35",
        f"Set Width {W}",
        f"Set Height {H}",
        "Set Padding 32",
        f"Set Margin {MARGIN}",
        f'Set MarginFill "{cfg["page"]}"',
        "Set WindowBar Colorful",
        "Set WindowBarSize 40",
        "Set BorderRadius 12",
        "Set Framerate 20",
        f"Set PlaybackSpeed {SPEED}",
        f"Set TypingSpeed {22 * SPEED}ms",
        "Set CursorBlink false",
        f"Set Theme {json.dumps(cfg['theme'])}",
        "Hide",
        f'Type "source {q(str(work / "demo.bashrc"))}"',
        "Enter",
        "Sleep 1s",
    ]


def hidden(cmd: str) -> list[str]:
    # Enter first releases a card's `read`; it is a no-op at a prompt.
    return ["Hide", "Enter", f'Type "{q(cmd)}"', "Enter", "Sleep 600ms", "Show"]


def run_tape(cfg: dict, output: Path) -> str:
    lines = [
        *settings(cfg, output),
        'Type "rm -rf .openfix && clear"',
        "Enter",
        "Sleep 600ms",
        "Show",
        *hidden("title; read -rs"),
        wait(3.5),
        *hidden("intro"),
        wait(1.5),
        r"Type `openfix fix findings/snyk-code.sarif findings/semgrep.sarif \`",
        "Enter",
        r"Type `  --only javascript/CommandInjection,path-traversal-path-join-var \`",
        "Enter",
        'Type "  --model scripted:demo/snyk-and-semgrep.script.yaml --sandbox local --open-prs"',
        wait(0.4),
        "Enter",
        HOLD,
        wait(3.5),
    ]
    return "\n".join(lines) + "\n"


def card_tape(cfg: dict, output: Path) -> str:
    return "\n".join([*settings(cfg, output), *hidden("done_card; read -rs"), wait(6)]) + "\n"


def screenshot(name: str, url: str) -> Path:
    out = work / f"pr-{name}.png"
    # GitHub follows prefers-color-scheme for signed-out visitors; force it either way (0 = dark, 1 = light).
    scheme = (
        ["--force-dark-mode", "--blink-settings=preferredColorScheme=0"]
        if name == "dark"
        else ["--blink-settings=preferredColorScheme=1"]
    )
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1400,1300",
         "--force-device-scale-factor=2", *scheme, f"--user-data-dir={work / f'chrome-{name}'}",
         f"--screenshot={out}", url],
        check=True, capture_output=True,
    )  # fmt: skip
    return out


def address_bar(name: str, cfg: dict, url: str, width: int, height: int) -> Path:
    """A browser-style strip with traffic lights and the PR's address, rendered by headless Chrome."""
    t = cfg["theme"]
    html = work / f"bar-{name}.html"
    html.write_text(
        f"""<!doctype html><meta charset=utf-8><style>
html,body{{margin:0;background:{t["background"]}}}
.b{{height:{height}px;display:flex;align-items:center;gap:8px;padding:0 16px;font:15px Menlo,monospace}}
.d{{width:12px;height:12px;border-radius:50%}}
.u{{margin-left:16px;padding:5px 14px;border-radius:7px;background:{cfg["page"]};color:{t["brightBlack"]}}}
</style><div class=b><i class=d style="background:#ff5f57"></i><i class=d style="background:#febc2e"></i>
<i class=d style="background:#28c840"></i><span class=u>{url.removeprefix("https://")}</span></div>"""
    )
    out = work / f"bar-{name}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{height}",
         f"--user-data-dir={work / f'chrome-{name}'}", f"--screenshot={out}", html.as_uri()],
        check=True, capture_output=True,
    )  # fmt: skip
    return out


def pr_clip(name: str, cfg: dict, png: Path, url: str, out: Path) -> None:
    """The PR body in a browser-style frame: hold on the summary, scroll quickly, hold on the evidence table."""
    bar_h = 44
    inner_w, inner_h = W - 2 * MARGIN, H - 2 * MARGIN
    bar = address_bar(name, cfg, url, inner_w, bar_h)
    scroll = "if(lt(t,2.4),0,min((t-2.4)*1000,ih-oh))"
    graph = (
        # PR title down to the end of the description, in the 2x screenshot.
        f"[0:v]crop=1810:1760:150:380,scale={inner_w}:-2,crop={inner_w}:{inner_h - bar_h}:0:'{scroll}'[page];"
        f"[1:v]scale={inner_w}:{bar_h}[bar];[bar][page]vstack,"
        f"pad={W}:{H}:{MARGIN}:{MARGIN}:color={cfg['page']},fps=20,format=yuv420p"
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-t", "6.5", "-i", str(png), "-loop", "1", "-t", "6.5",
         "-i", str(bar), "-filter_complex", graph, str(out)],
        check=True,
    )  # fmt: skip


def to_gif(parts: list[Path], out: Path) -> None:
    inputs = [arg for p in parts for arg in ("-i", str(p))]
    n = len(parts)
    chain = "".join(f"[{i}:v]fps=20,scale={W}:{H},setsar=1[v{i}];" for i in range(n))
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1[v];"
    palette = "[v]split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", chain + concat + palette, str(out)],
                   check=True)  # fmt: skip


if __name__ == "__main__":
    subprocess.run(["gh", "repo", "clone", DEMO_REPO, str(APP), "--", "-q"], check=True)
    for name, cfg in THEMES.items():
        (work / "demo.bashrc").write_text(rc(cfg))
        run_mp4, card_mp4, pr_mp4 = work / f"run-{name}.mp4", work / f"card-{name}.mp4", work / f"pr-{name}.mp4"
        (work / "run.tape").write_text(run_tape(cfg, run_mp4))
        subprocess.run(["vhs", str(work / "run.tape")], check=True)
        (work / "card.tape").write_text(card_tape(cfg, card_mp4))
        subprocess.run(["vhs", str(work / "card.tape")], check=True)
        url = subprocess.run(
            ["gh", "pr", "view", PR_BRANCH, "-R", DEMO_REPO, "--json", "url", "-q", ".url"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()  # fmt: skip
        pr_clip(name, cfg, screenshot(name, url), url, pr_mp4)
        to_gif([run_mp4, pr_mp4, card_mp4], gif_dir / f"demo-{name}.gif")
        print(gif_dir / f"demo-{name}.gif")
