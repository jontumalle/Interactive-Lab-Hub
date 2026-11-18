# Printable Paper Prototype

These templates use the current two diagnostic clues and single setting decoder. They support a physical test of decoding, port allocation, and the receiver handoff. Simulate waveform matching or use a separate working receiver prototype.

## Print files

- [Player templates](../output/pdf/last-transmission-player-templates.pdf) — seven pages without an answer key.
- [Facilitator guide](../output/pdf/last-transmission-facilitator-guide.pdf) — two pages with assembly, answers, hints, reset, and observation prompts. Keep this separate from player materials.

Print single sided on US Letter at **Actual Size or 100%**, with automatic orientation. Page 6 is landscape. Disable Fit to page and duplex. Check the printed 100 mm ruler before assembly.

| Player page | Contents |
| --- | --- |
| 1 | Fixed numbered decoder base |
| 2 | Cut out rotating symbol disk |
| 3 | Two separate diagnostic clue cards |
| 4 | Encrypted dispatch fragments A and B |
| 5 | Attribute legend and blank decoded requirement notes |
| 6 | Landscape patch panel with eight connection positions |
| 7 | Transmitter port specification card |

## Assemble

Use scissors, scrap cardboard or cardstock, one paper fastener, four approximately 30 cm strings, low tack tape or clips, and a pencil. Cut the rotor and attach it through the center of the base. Its 124 mm diameter leaves the fixed numbers visible on the 170 mm base. The dimensions are for the paper prototype, not final fabrication.

Keep the fixed base intact. Cut the diagnostic cards apart and retain them as receiver rewards: the first signal reveals the Triangle record and the second reveals the Moon record. Set out the legend, blank notes, empty patch panel, and port table. Hold both encrypted dispatch cards until players correctly confirm the wheel setting. Then hand over both for decoding. Give players no completed checklist or solution diagram.

## Regenerate

Run `python3 "Final Project/paper-prototype/build_printables.py"` from the repository root using a Python environment with `reportlab` and `pypdf`. The script embeds DejaVu Sans fonts and defaults to the author's bundled font directory. Set `PAPER_FONT_DIR` to a directory containing `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` on another machine.

The generator verifies the unique diagnostic and patch solutions, the page counts, and the portrait/landscape page sizes. Both final PDFs were rendered and visually reviewed. Jonathan subsequently reported a successful paper experiment and positive feedback that the experience made sense; see [test notes and design response](test-notes.md). Hardware testing remains the next focus.
