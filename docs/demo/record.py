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


def q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def tape(name: str, cfg: dict) -> str:
    lines = [
        f'Output "{gif_dir / f"demo-{name}.gif"}"',
        'Set Shell "bash"',
        'Set FontFamily "Menlo"',
        "Set FontSize 16",
        "Set LineHeight 1.35",
        "Set Width 1280",
        "Set Height 880",
        "Set Padding 28",
        "Set Margin 24",
        f'Set MarginFill "{cfg["page"]}"',
        "Set WindowBar Colorful",
        "Set WindowBarSize 40",
        "Set BorderRadius 12",
        "Set Framerate 24",
        "Set TypingSpeed 28ms",
        "Set CursorBlink false",
        f"Set Theme {json.dumps(cfg['theme'])}",
        "",
        "Hide",
        f'Type "source {q(str(work / "demo.bashrc"))}"',
        "Enter",
        'Type "rm -rf .openfix/demo && clear"',
        "Enter",
        "Sleep 300ms",
        "Show",
        "",
        "Sleep 600ms",
        'Type "# Fix one finding. Model calls are replayed; Semgrep and the tests run live."',
        "Enter",
        "Sleep 700ms",
        r"Type `openfix fix findings/semgrep.sarif --only path-traversal-path-join-var \`",
        "Enter",
        'Type "  --model scripted:demo/path-traversal.script.yaml --sandbox local --out .openfix/demo"',
        "Sleep 400ms",
        "Enter",
        "Wait+Line@60s /❯ *$/",
        "Sleep 2.5s",
        "",
        'Type "clear"',
        "Enter",
        'Type "# The patch, plus the regression test it had to write"',
        "Enter",
        "Sleep 300ms",
        r"Type `grep -vE '^(diff|index|new file)' .openfix/demo/of-*/patch.diff | bat -pf -l diff --theme=ansi`",
        "Sleep 300ms",
        "Enter",
        "Wait+Line@10s /❯ *$/",
        "Sleep 4.5s",
        "",
        'Type "clear"',
        "Enter",
        'Type "# Every check the policy required, from the receipt"',
        "Enter",
        "Sleep 300ms",
        r"""Type `jq -r '.predicate.checks[] | "\u2714 \(.name): \(.detail)"' .openfix/demo/of-*/receipt.json`""",
        "Sleep 300ms",
        "Enter",
        "Wait+Line@10s /❯ *$/",
        "Sleep 1.2s",
        'Type "openfix receipt verify .openfix/demo/of-*/ --repo ."',
        "Sleep 300ms",
        "Enter",
        "Wait+Line@20s /❯ *$/",
        "Sleep 4s",
        "",
        "Hide",
        'Type "rm -rf .openfix/demo"',
        "Enter",
    ]
    return "\n".join(lines) + "\n"


BASHRC = f"""export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 BASH_SILENCE_DEPRECATION_WARNING=1
export PATH="{VENV}:$PATH"
cd "{APP}"
PS1='\\[\\e[90m\\]vulnerable-app \\[\\e[35m\\]❯\\[\\e[0m\\] '
PS2='  '
"""

if __name__ == "__main__":
    (work / "demo.bashrc").write_text(BASHRC)
    for name, cfg in THEMES.items():
        path = work / f"demo-{name}.tape"
        path.write_text(tape(name, cfg))
        subprocess.run(["vhs", str(path)], check=True)
        print(gif_dir / f"demo-{name}.gif")
