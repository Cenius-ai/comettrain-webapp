# CometTrain design contract

CometTrain's surface is a terminal, so the committed design direction is applied as
typography rather than CSS. The tokens below are the source of truth for anything
that wraps the tool (a shell theme, a screenshot harness, a future TUI skin).

## Tokens

| Token | Value | Where it is used |
| --- | --- | --- |
| Accent | `oklch(0.58 0.12 169)` / `#00906e` | primary status only: the nearest apparition in a proximity search, the matched comet in `show` — never the sole carrier of meaning |
| Surface | terminal dark | the only honest CLI surface; the tool emits no background or colour escape codes at all |
| Type | system monospace, single family | every line of output; columns are aligned with `str.format` field widths |
| Density | compact | one blank line between regions, no decorative rules beyond `---` column separators |
| Shape | monospace, no chrome | ASCII separators only; no box-drawing, no ANSI, no progress spinners |
| Layout | aligned terminal columns | `list` → table, `perihelion`/`calendar` → date/name/offset columns, help-first output |

## Rules the output follows

- **No colour-only signal.** Signed offsets (`+2`, `-21`), the words `before`/`after`,
  and the `skipped …` footer carry every distinction as text. Colour is decoration a
  wrapper may add; the tool itself prints plain bytes.
- **Deterministic, byte-identical output** for the same command, catalogue and date,
  which is also what makes `demo/transcript.txt` a valid record.
- **80 columns.** Every emitted line stays inside 80 characters; the comet-name
  column is measured from the catalogue and capped so a long name cannot push the
  following columns out of alignment.
- **One accent, one status.** The single accent is reserved for the primary result of
  a query, so a coloured row always also reads correctly in plain text.
