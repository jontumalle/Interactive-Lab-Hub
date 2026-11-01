# Editable model prompts

The real adapter must read all five files at job start, snapshot them for that
job, split at the standalone SYSTEM and USER lines, and send both as messages.
All model instructions belong here. Code owns transport, JSON validation, bounded
generation settings, and assignment of IDs/paths. Fail an invalid structured
response at its stage; never silently accept unvalidated prose.

Use `string.Template.substitute(input_json=json.dumps(payload))` for templates
that have `$input_json`. Substituted JSON is data, never a second template. Observe
has no placeholder; send the analysis image as the model's image attachment and
do not include the user's explanation. The pipeline loads templates at the beginning of each run; retries also reload
them, while already completed stages retain their validated checkpoint results.

| Template | Example input | Example validated output |
| --- | --- | --- |
| observe.txt | attached photo, no user context | `{"visible_content":"A sandy shore beside water.","uncertainties":["Exact location unknown."]}` |
| synthesize.txt | `{"observation":{"visible_content":"A sandy shore.","uncertainties":[]},"metadata":{"captured_at":null,"latitude":null,"longitude":null,"place_name":"Coast","embedded_description":null},"user_description":"We stopped after lunch.","vibes":["Relaxed"]}` | `{"summary":"A relaxed stop by the coast after lunch.","grounded_details":["Sandy shore","Stop after lunch"],"uncertainties":[]}` |
| outline.txt | `{"trip_title":"A weekend away","previous_outline":null,"ordered_moments":[{"summary":"A coastal stop.","user_context":"We stopped after lunch.","place":"Coast","time":null}]}` | `{"premise":"A weekend with a coastal pause.","thread":"A pause by the shore.","closing_callback":"The shore."}` |
| chapter.txt | `{"synthesis":{"summary":"A coastal stop after lunch.","grounded_details":["Sandy shore"],"uncertainties":[]},"metadata":{"captured_at":null,"latitude":null,"longitude":null,"place_name":"Coast","embedded_description":null},"user_description":"We stopped by the coast after lunch.","vibes":["Relaxed"]}` | `{"title":"By the coast","narrative":"After lunch, we stopped by the coast. The photo holds a glimpse of the sandy shore.","summary":"A coastal stop after lunch."}` |
| framing.txt | `{"trip_title":"A weekend away","chapter_summaries":["A coastal stop after lunch."]}` | `{"opening":"These photos show a coastal stop after lunch.","closing":"The coast was one stop after lunch."}` |

Output strings are plain text. The pipeline passes only ordered summaries into
framing. Voice reads exactly the displayed narrative/opening/closing text.


The adapter sends `think: false`, a JSON schema, and configured `num_ctx`,
`num_predict`, and temperature to the local `/api/chat` endpoint. It validates
required field names and bounded strings/lists before checkpointing. Invalid
JSON or structured values expose the failed stage for retry.

Narration uses the configured local Piper executable with `--model` and
`--output-file`, writing each segment to a temporary WAV and replacing the final
file only after validation. No voice downloads occur during processing. Enabled-but-missing project Piper/voice files now fail the startup/job-start
readiness checks before inference. Later per-card synthesis errors leave the
story readable with narration marked unavailable/partial and the cause saved. Finished audio is reused on retries; missing or corrupt
WAV files are regenerated. Opening and closing narration checkpoints use a null
photo ID and distinct `result.segment` values.

Adapter references: [Ollama chat and structured outputs](https://github.com/ollama/ollama/blob/main/docs/api.md),
[Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/src/piper/__main__.py).


Grounding boundaries: observation uses generic visible content and avoids OCR
and guessed place names. Synthesis and chapter receive the original effective
metadata, user description, and vibes; chapter does not have to reconstruct user
context from a model summary. User statements override synthesis guesses. Vibes
control tone only. Framing rephrases ordered chapter summaries without introducing
new places, actions, or emotions. For example, a photo showing a bus plus the user
context "We stopped to look at the street" supports a street stop; it does not
establish that anyone boarded the bus or visited a particular city. These prompts
reduce invention but do not establish factual correctness; real story grounding
still requires the manual photo/context smoke assessment in the project checklist.

Framing checks concrete names/numbers against the supplied source summaries,
falling back to saved summary material when those specifics are unsupported.
This is not a semantic truth check. Final framing is checkpointed before narration.

Audio-only retry uses saved displayed text without loading prompts or calling
Ollama. It retries unavailable/corrupt audio and reuses valid WAVs.

Connected-journal jobs first observe/synthesize the whole set, then build an
outline from bounded ordered batches (previous outline + new moments). Every
scene receives final trip_outline, scene_position/count, previous_scene summary
and next_moment, alongside authoritative current notes/metadata/vibes. This
supports transitions and a shared narrative without inventing travel or duration.
The first-person journal instructions live in chapter/framing templates.

The former full-vocabulary framing check restricted new prose to caption wording.
It has been replaced by a conservative check for unsupported names and numbers;
ordinary connective wording is allowed. This heuristic cannot establish semantic
truth, so scene facts and whole-story coherence still need manual review.

Source priority for connected scenes: current user notes are supplied last and
remain the event being narrated. Compact outline/neighbor summaries prefer these
notes over visual-caption synthesis, and synthesized visible details are limited
so they do not displace personal context. Uncertainty in user notes must remain
uncertain. The story thread is connective composition, not permission to invent
sensory detail, a new itinerary order, or activities from adjacent scenes.

The current day-overview layer adds day.txt. It receives ordered moment/owner
notes from a single camera-calendar day and writes one connected day story in
I/we. Large days fold every source through bounded batches, retaining the prior
day story between batches. Only the final daily narrative is narrated as one WAV.
No model assigns dates, day IDs, moment membership, map positions, or route order.
The initial prompt snapshot is reused throughout a full job; day-only upgrades
load their own snapshot once at job start.
