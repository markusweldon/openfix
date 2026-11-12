# ruff: noqa: E501
"""Record the README terminal demo (docs/assets/demo-{dark,light}.gif) with VHS.

Run from the repository root:  python docs/demo/record.py
Needs vhs, node, semgrep and snyk on PATH, and OpenFix installed in .venv.
It fixes one Snyk Code and one Semgrep finding in examples/vulnerable-app. The model's tool
calls are replayed from demo/snyk-and-semgrep.script.yaml; Snyk Code, Semgrep and the tests run for
real (Snyk needs `snyk auth` or SNYK_TOKEN). Waits are sped up SPEED times. Colours follow the diagrams (GitHub Primer).
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

CLEAN = work / "checkout"  # a clean worktree of HEAD, so OpenFix sees no local changes
APP = CLEAN / "examples" / "vulnerable-app"
VENV = repo / ".venv" / "bin"
SPEED = 6  # VHS plays the recording back this much faster; sleeps and typing are scaled to compensate
HOLD = "Wait+Line@300s /❯ *$/"


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
export PATH="{VENV}:$PATH"
cd "{APP}"
PS1='\\[\\e[90m\\]vulnerable-app \\[\\e[35m\\]❯\\[\\e[0m\\] '
PS2='  '
card() {{ clear; printf '\\e[?25l\\n\\n\\n\\n'; for line in "$@"; do printf '    %b\\e[0m\\n\\n' "$line"; done; }}
title() {{ card "{accent}\\e[1mOpenFix" "\\e[1mFindings from any scanner in. Verified fixes out." "{muted}Snyk Code and Semgrep each found a vulnerability in this app."; }}
intro() {{ clear; printf '\\e[?25h\\n \\e[1mSnyk Code\\e[0m: command injection in /ping    \\e[1mSemgrep\\e[0m: path traversal in readUserFile\\n {muted}One command fixes both, then proves each fix.\\e[0m\\n\\n'; }}
done_card() {{ card "{green}\\e[1m✔  2 scanners in, 2 verified fixes out" "Each fix: the scanner no longer reports it, the tests pass," "and a new regression test fails before the fix and passes after." "Every fix comes with a signed receipt and a draft PR." "{muted}Model calls are replayed for this demo; Snyk, Semgrep and the tests ran live." "{accent}github.com/markusweldon/openfix"; }}
"""


def tape(name: str, cfg: dict) -> str:
    def hidden(cmd: str) -> list[str]:
        # Enter first releases a card's `read`; it is a no-op at a prompt.
        return ["Hide", "Enter", f'Type "{q(cmd)}"', "Enter", "Sleep 600ms", "Show"]

    lines = [
        f'Output "{gif_dir / f"demo-{name}.gif"}"',
        'Set Shell "bash"',
        'Set FontFamily "Menlo"',
        "Set FontSize 22",
        "Set LineHeight 1.35",
        "Set Width 1400",
        "Set Height 700",
        "Set Padding 32",
        "Set Margin 24",
        f'Set MarginFill "{cfg["page"]}"',
        "Set WindowBar Colorful",
        "Set WindowBarSize 40",
        "Set BorderRadius 12",
        "Set Framerate 20",
        f"Set PlaybackSpeed {SPEED}",
        f"Set TypingSpeed {22 * SPEED}ms",
        "Set CursorBlink false",
        f"Set Theme {json.dumps(cfg['theme'])}",
        "",
        "Hide",
        f'Type "source {q(str(work / f"demo-{name}.bashrc"))} && rm -rf .openfix"',
        "Enter",
        "Sleep 1s",
        "Show",
        *hidden("title; read -rs"),
        wait(3.5),
        *hidden("intro"),
        wait(1.5),
        r"Type `openfix fix findings/snyk-code.sarif findings/semgrep.sarif \`",
        "Enter",
        r"Type `  --only javascript/CommandInjection,path-traversal-path-join-var \`",
        "Enter",
        'Type "  --model scripted:demo/snyk-and-semgrep.script.yaml --sandbox local"',
        wait(0.4),
        "Enter",
        HOLD,
        wait(5),
        *hidden("done_card; read -rs"),
        wait(6),
        "Hide",
        "Enter",
        'Type "rm -rf .openfix"',
        "Enter",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(CLEAN), "HEAD"], check=True)
    for name, cfg in THEMES.items():
        (work / f"demo-{name}.bashrc").write_text(rc(cfg))
        path = work / f"demo-{name}.tape"
        path.write_text(tape(name, cfg))
        subprocess.run(["vhs", str(path)], check=True)
        print(gif_dir / f"demo-{name}.gif")
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(CLEAN)], check=True)
