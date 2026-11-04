# Local Vacation Story MVP

## Summary

Build a self-contained application in [Lab 5/vacation_story](/home/pi/Interactive-Lab-Hub/Lab%205/vacation_story). A phone on the same network submits photos and context; the Pi later creates an interactive, narrated photo itinerary.

Use Python, Flask, buildless HTML/CSS/JavaScript, JSON files, Ollama with `qwen3.5:0.8b`, and local Piper narration. No database, cloud processing, video generation, or TikTok integration.

## Experience and behavior

- Start a trip with a title, then submit photos individually.
- Extract metadata immediately after upload, before resizing. Display available capture date/time and location information with editable corrections. Do not substitute file modification time for capture time.
- Ask only for missing information. Provide an optional place-name field when metadata contains only coordinates; omit maps and reverse-geocoding services.
- Ask “What was happening here?” unless an embedded description already provides editable context.
- Ask “What was the vibe?” using six preset, skippable, multi-select choices: Relaxed, Exciting, Adventurous, Meaningful, Funny, Awe-inspiring. No custom option.
- Show confirmation after saving each photo and its answers. Offer “Add another photo” and “Finish and create my story.”
- Run no model inference until the user finishes submission. Processing continues after the browser closes; reopening the trip shows its progress.
- Present an opening card, one chapter per photo, and a closing reflection. Use actual photos, concise narrative, available itinerary details, and optional narration.
- Support previous/next controls and “Play my trip.” Playback starts only after a user gesture, advances when narration ends, and offers pause and manual navigation. Text remains usable if narration fails.
- Order photos by capture time when every photo has a comparable timestamp; otherwise preserve submission order.

## Components and interfaces

**Web application and storage**

- Flask owns uploads, metadata extraction, image preparation, trip records, status, and local media delivery.
- Use Pillow plus HEIC support for phone photos; accept JPEG, PNG, WebP, and HEIC/HEIF.
- Correct image orientation and retain a JPEG copy capped at 1600 pixels on its longest edge. Use a smaller analysis copy for inference.
- Store each trip in an ignored runtime directory containing JSON, prepared photos, and narration files. Use atomic JSON writes.
- Delete originals after metadata and usable resized copies have been saved successfully. Retain prepared photos until the user deletes the trip.
- Use one background worker and one inference request at a time. Persist completed stages so an explicit retry can reuse finished work. After a restart, mark interrupted processing as retryable.
- Provide trip creation/listing, photo upload/update, processing start/retry, status/story retrieval, media delivery, and trip deletion endpoints.
- Keep startup, dependencies, configuration, tests, and documentation inside the project folder. Use the existing system Ollama service.

**Local story and narration pipeline**

- Process each photo through observation, synthesis, and chapter generation; then generate an opening and closing from the chapter summaries.
- Observations describe visible content independently of the user’s explanation. Synthesis combines observations, metadata, description, and selected vibes; user corrections override model guesses.
- Use `qwen3.5:0.8b` throughout, thinking disabled, bounded context and output lengths, and structured responses validated by the pipeline.
- Generate narration as saved WAV files using Piper and one configurable English voice. Narration reads the displayed story text.
- A narration failure leaves a readable story with narration marked unavailable. A model failure exposes the failed stage and a retry action.
- Keep model choice, image sizes, generation settings, and voice selection in one configuration file.

**Editable prompts and shared contracts**

- Put four plainly named templates in [prompts/](/home/pi/Interactive-Lab-Hub/Lab%205/vacation_story/prompts): `observe.txt`, `synthesize.txt`, `chapter.txt`, and `framing.txt`.
- Keep all model instructions in those files, including the system instructions. Document placeholders and example inputs/outputs. Load templates at job start so edits affect the next run without code changes.
- Define shared contracts before parallel implementation:
  - Photo input: ID, prepared image path, submission order, available metadata, user description, selected vibes.
  - Story chapter: photo ID, title, narrative, optional location/time, optional audio URL.
  - Story: title, opening, ordered chapters, closing.
  - Processing status: overall state, current stage, progress count, and actionable error.
- The pipeline receives local paths and structured records; Flask alone converts local assets into browser URLs. Models never generate HTML, paths, IDs, or ordering.
- Render generated text as text. Keep private photos and runtime files out of Git.

## Parallel work across three developers

Agree on the contracts and example payloads first, then work concurrently:

| Owner | Responsibility | Parallel development boundary |
|---|---|---|
| Lead developer | Flask API, metadata/image handling, JSON storage, worker lifecycle, final integration | Supplies sample API responses and a fake pipeline |
| Developer 2 | Responsive collection flow, progress screen, story reader, audio playback | Builds against sample responses without requiring inference |
| Developer 3 | Ollama adapter, prompt templates, story pipeline, Piper narration | Builds against photo-input fixtures without requiring Flask |

Integrate after each component completes its main flow. The lead connects the pipeline to the worker, replaces frontend fixtures with API calls, and documents one-command startup and phone access. Avoid shared-file edits until integration.

## Verification and MVP defaults

Use only a small set of high-level component tests:

- **Web/storage:** submit a representative photo and answers, verify extracted metadata and retained media, persist/reload the trip, and delete it. Substitute a fake pipeline; do not test model behavior.
- **Pipeline:** process a small trip using fake Ollama and narration adapters; verify stage sequencing, user-context propagation, photo associations, and persisted completion. Do not test HTTP routes or browser behavior.
- **Frontend:** exercise collection through a ready story using fixture responses, including vibe selection, navigation, and narration controls. Do not retest metadata extraction or model output.
- Cover one interrupted/failed job and retry at the worker boundary. Skip exhaustive malformed-input and rare-format cases.
- Perform one manual real-device smoke test with several vacation photos: submit from a phone, close the browser during processing, return to the finished story, and listen to narration. Assess factual grounding and story coherence manually rather than asserting exact generated wording.

Default to one user on a trusted local network, English narration, visual save confirmation, and no login or external assets. Downloads of model/voice dependencies may require internet during setup; the completed application must work offline. Include setup instructions and a short demo checklist in the project README.
