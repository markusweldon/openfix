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
| README logo | `docs/assets/logo-dark.svg` (lime tile, Ink glyph, on a dark card) |
| Icon, avatar, favicon | `docs/assets/mark.svg` |
| GitHub social preview (Settings → General → Social preview) | `docs/assets/social-preview.png` |

Keep at least a quarter of the tile's width clear around the mark. Don't recolour it, outline it or put it on a busy image.

## Colour

| Token | Hex | Use |
| --- | --- | --- |
| Signal Lime | `#C6F432` | The brand colour. Means *verified*. Mark tile, highlights, the Verify stage. |
| Ink | `#0A0E16` | Backgrounds, and the mark's glyph on lime. |
| Blue | `#7DB2FF` | Deterministic steps (ingest, policy, scanners). |
| Violet | `#BFA2FF` | Anything a model does. |
| Amber | `#FFBE5C` | Outputs and human decisions. |

Lime is for proof: use it for text and accents on Ink.

The README is dark only. Every image, including the logo, sits on its own dark card, so it reads the same on light and dark GitHub pages. The demo GIF's terminal uses the same palette.

## Type

- **Space Grotesk** (400, 500, 700) for headings and labels.
- **JetBrains Mono** (500, 700) for commands, file names, eyebrows and pills.

Both are under the SIL Open Font License 1.1 (`fonts/OFL-*.txt`). The SVGs embed a subset of each, so they render the same everywhere, including GitHub's image sandbox.

## Voice

Short, literal and checkable. "Models propose. Code verifies." Say what was proved, not how clever it was.
