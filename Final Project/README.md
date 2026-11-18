# The Last Transmission

Portable escape room in a briefcase by Jonathan Tumalle.

The current design combines joystick waveform matching, a directly sensed decoder wheel, and a physical cable patch panel. The receiver reveals two diagnostic records. Players use them to deduce the wheel setting, which unlocks the encrypted dispatch cards. They decode the cards and connect the transmitter ports.

## Design documents

- [Working waveform receiver](waveform/README.md) — Pi joystick implementation and arrow key browser simulator using the same player display.
- [Printable paper prototype](paper-prototype/README.md) — player templates and a separate facilitator guide for testing the diagnostic clues, decoder, and patch panel.
- [Paper prototype feedback](paper-prototype/test-notes.md) — positive initial feedback and the resulting focus on essential clue presentation.
- [Current interaction storyboard](receiver-decoder-storyboard.md) — diagnostic record recovery, wheel deduction, dispatch unlocking, and the final patch puzzle.
- [Illustrated design specification](design-document.md) — current revision, with setup, interactions, wiring, parts, reset, and validation plans.
- [Concept and paper test worksheet](01-concept-and-paper-test.md) — earlier planning worksheet, retained as process history.
- [Diagram assets](design-assets/) — editable SVGs referenced by the Markdown document.

## Status

Design revision 5, with paper test feedback recorded November 18 2026. Jonathan reports that the paper experiment worked and made sense to players. The main feedback is to develop the presentation of essential clues for the final design. Hardware implementation and testing are the next focus. Diagrams are explanatory, not final fabrication templates. Encoder detents and coupling, waveform readability, and patch cable sensing are the first bench checks.

## Editing and diagram generation

Edit `design-document.md` directly; it is the authoritative design document. To regenerate the seven SVG diagrams, run `python3 "Final Project/generate_design_diagrams.py"` from the repository root. The script uses only the Python standard library and checks the example patch solution, decoder angles, and Markdown diagram references. It does not overwrite the document, control hardware, or run the game.

The current design documents subsequent AI assisted development. Independently created initial sketches should be archived separately as required by the course rubric.
