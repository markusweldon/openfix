# ruff: noqa: E501
"""Record the README terminal demo (docs/assets/demo-{dark,light}.gif) with VHS.

Run from the repository root:  python docs/demo/record.py
Needs vhs, bat, jq, node and semgrep on PATH, and OpenFix installed in .venv.
The model's tool calls are replayed from examples/vulnerable-app/demo/; Semgrep,
the tests and the receipt check run for real. Colours follow the diagrams (GitHub Primer).
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

APP = repo / "examples" / "vulnerable-app"
VENV = repo / ".venv" / "bin"
HOLD = "Wait+Line@60s /❯ *$/"


def q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def rc(cfg: dict) -> str:
    """Shell setup: prompt, plus `scene` and `card` helpers that draw the titles."""
    t = cfg["theme"]

    def rgb(hexcolor: str, ground: int) -> str:
        r, g, b = (int(hexcolor[i : i + 2], 16) for i in (1, 3, 5))
        return f"\\e[{ground};2;{r};{g};{b}m"

    badge = rgb(cfg["page"], 38) + rgb(t["magenta"], 48)
    accent = rgb(t["magenta"], 38)
    green = rgb(t["green"], 38)
    muted = rgb(t["brightBlack"], 38)
    return f"""export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 BASH_SILENCE_DEPRECATION_WARNING=1
export PATH="{VENV}:$PATH"
cd "{APP}"
PS1='\\[\\e[90m\\]vulnerable-app \\[\\e[35m\\]❯\\[\\e[0m\\] '
PS2='  '
scene() {{ clear; printf '\\e[?25h\\n {badge}\\e[1m  %s  \\e[0m  \\e[1m%s\\e[0m\\n\\n {muted}%s\\e[0m\\n\\n' "$1" "$2" "$3"; }}
card() {{ clear; printf '\\e[?25l\\n\\n\\n\\n\\n'; for line in "$@"; do printf '    %b\\e[0m\\n\\n' "$line"; done; }}
title() {{ card "{accent}\\e[1mOpenFix" "\\e[1mFrom scanner finding to verified fix, with proof." "{muted}One finding from the example app, start to finish." "{muted}Model calls are replayed; Semgrep and the tests run live."; }}
done_card() {{ card "{green}\\e[1m✔  Verified fix" "Semgrep no longer reports it.   The tests pass." "A new regression test fails before the fix and passes after." "Signed receipt.json with every check, ready for a draft PR." "{accent}github.com/markusweldon/openfix"; }}
"""


def tape(name: str, cfg: dict) -> str:
    def hidden(cmd: str) -> list[str]:
        # Enter first releases a title card's `read`; it is a no-op at a prompt.
        return ["Hide", "Enter", f'Type "{q(cmd)}"', "Enter", "Sleep 300ms", "Show"]

    def run(cmd: str, hold: str) -> list[str]:
        return [f"Type `{cmd}`", "Sleep 400ms", "Enter", HOLD, f"Sleep {hold}"]

    lines = [
        f'Output "{gif_dir / f"demo-{name}.gif"}"',
        'Set Shell "bash"',
        'Set FontFamily "Menlo"',
        "Set FontSize 21",
        "Set LineHeight 1.3",
        "Set Width 1400",
        "Set Height 1180",
        "Set Padding 32",
        "Set Margin 24",
        f'Set MarginFill "{cfg["page"]}"',
        "Set WindowBar Colorful",
        "Set WindowBarSize 40",
        "Set BorderRadius 12",
        "Set Framerate 20",
        "Set TypingSpeed 22ms",
        "Set CursorBlink false",
        f"Set Theme {json.dumps(cfg['theme'])}",
        "",
        "Hide",
        f'Type "source {q(str(work / f"demo-{name}.bashrc"))} && rm -rf .openfix/demo"',
        "Enter",
        "Sleep 300ms",
        "Show",
        *hidden("title; read -rs"),
        "Sleep 4.5s",
        "",
        *hidden("scene 1/4 'The finding' 'Semgrep flags a path traversal: user input reaches readFileSync.'"),
        "Sleep 1.2s",
        *run("bat -n -r 8:12 --paging=never --theme=ansi src/files.js", "3.5s"),
        "",
        *hidden(
            "scene 2/4 'The fix' 'OpenFix gives it to the model in a throwaway worktree, then checks the result itself.'"
        ),
        "Sleep 1.2s",
        r"Type `openfix fix findings/semgrep.sarif --only path-traversal-path-join-var \`",
        "Enter",
        'Type "  --model scripted:demo/path-traversal.script.yaml --sandbox local --out .openfix/demo"',
        "Sleep 400ms",
        "Enter",
        HOLD,
        "Sleep 3.5s",
        "",
        *hidden("scene 3/4 'The patch' 'A minimal change, plus the regression test the policy requires.'"),
        "Sleep 1.2s",
        *run(
            "grep -vE '^(diff|index|new file)' .openfix/demo/of-*/patch.diff | bat -pf --paging=never -l diff --theme=ansi",
            "6s",
        ),
        "",
        *hidden("scene 4/4 'The proof' 'Every check the policy required, recorded in a receipt anyone can re-verify.'"),
        "Sleep 1.2s",
        *run(r"""jq -r '.predicate.checks[] | "\(.status)  \(.name)"' .openfix/demo/of-*/receipt.json""", "1.5s"),
        *run("openfix receipt verify .openfix/demo/of-*/ --repo .", "4.5s"),
        "",
        *hidden("done_card; read -rs"),
        "Sleep 6s",
        "",
        "Hide",
        'Type "rm -rf .openfix/demo"',
        "Enter",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    for name, cfg in THEMES.items():
        (work / f"demo-{name}.bashrc").write_text(rc(cfg))
        path = work / f"demo-{name}.tape"
        path.write_text(tape(name, cfg))
        subprocess.run(["vhs", str(path)], check=True)
        print(gif_dir / f"demo-{name}.gif")
