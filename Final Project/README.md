# The Last Transmission

Portable escape room in a briefcase by Jonathan Tumalle.

The current design combines joystick waveform matching, a directly sensed decoder wheel, and a physical cable patch panel. Recovering a sender identity and time lets players interpret an operator notebook, configure the decoder, and recover a missing requirement for the final patching puzzle.

## Design documents

- [Current interaction storyboard](receiver-decoder-storyboard.md) — reception of ciphertext, deduction from two diagnostic records, and the final patch puzzle.
- [Illustrated design specification](design-document.md) — current revision, with setup, interactions, wiring, parts, reset, and validation plans.
- [Concept and paper test worksheet](01-concept-and-paper-test.md) — earlier planning worksheet, retained as process history.
- [Diagram assets](design-assets/) — editable SVGs referenced by the Markdown document.

## Status

Design revision 4, November 16 2026. Hardware construction and user tests remain pending. Diagrams are explanatory, not final fabrication templates. Encoder detents and coupling, waveform readability, and protected patch cable sensing are the first bench checks.

## Editing and diagram generation

Edit `design-document.md` directly; it is the authoritative design document. To regenerate the seven SVG diagrams, run `python3 "Final Project/generate_design_diagrams.py"` from the repository root. The script uses only the Python standard library and checks the example patch solution, decoder angles, and Markdown diagram references. It does not overwrite the document, control hardware, or run the game.

The current design documents subsequent AI assisted development. Independently created initial sketches should be archived separately as required by the course rubric.
