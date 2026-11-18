# OpenFix brand

The README logo, diagrams and social preview are generated from one script, so they stay consistent.

```bash
uv run --with fonttools --with brotli python docs/brand/build.py          # SVGs in docs/assets/
uv run --with fonttools --with brotli --with playwright \
  python docs/brand/build.py --png                                        # + social-preview.png
```

Edit `build.py` and rerun it; don't hand-edit the SVGs in `docs/assets/`.

## Mark

An open ring with a check that breaks out through the gap: **open** source, a **fix** that is **verified**.

| Use | File |
| --- | --- |
| Logo for light backgrounds | `docs/assets/logo-light.svg` (Ink tile, lime glyph) |
| Logo for dark backgrounds | `docs/assets/logo-dark.svg` (lime tile, Ink glyph) |
| Icon, avatar, favicon | `docs/assets/mark.svg` |
| GitHub social preview (Settings → General → Social preview) | `docs/assets/social-preview.png` |

Keep at least a quarter of the tile's width clear around the mark. Don't recolour it, outline it or put it on a busy image.

## Colour

| Token | Hex | Use |
| --- | --- | --- |
| Signal Lime | `#C6F432` | The brand colour. Means *verified*. Mark tile, highlights, the Verify stage. |
| Ink | `#0A0E16` | Text on light, background on dark, the mark's glyph on lime. |
| Lime text (light) | `#456B00` | Lime-family text on white, where `#C6F432` is unreadable. |
| Blue | `#7DB2FF` / `#1B5FD9` | Deterministic steps (ingest, policy, scanners). Dark / light. |
| Violet | `#BFA2FF` / `#6A3BDB` | Anything a model does. Dark / light. |
| Amber | `#FFBE5C` / `#B65A00` | Outputs and human decisions. Dark / light. |

Lime is for proof. On dark backgrounds use it as text; on light backgrounds use it as a highlighter behind Ink text (as in "Code verifies." in the pipeline diagram), never as thin text.

## Type

- **Space Grotesk** (400, 500, 700) for headings and labels.
- **JetBrains Mono** (500, 700) for commands, file names, eyebrows and pills.

Both are under the SIL Open Font License 1.1 (`fonts/OFL-*.txt`). The SVGs embed a subset of each, so they render the same everywhere, including GitHub's image sandbox.

## Voice

Short, literal and checkable. "Models propose. Code verifies." Say what was proved, not how clever it was.
