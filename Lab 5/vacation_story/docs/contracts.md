# Shared contracts and API boundary

`vacation_story/contracts.py` defines the JSON-compatible internal records and
`Pipeline.run` protocol. `tests/fixtures/` contains synthetic examples; there are no
private photos. Fixture paths/URLs are illustrative and do not resolve to media.
The API below is implemented by Flask. Fixture URLs are examples; real uploads
produce trip-specific URLs.

## Internal records

- Photo input: stable ID, prepared and analysis image paths, zero-based submission
  order, effective metadata, user description, and the six permitted vibe labels.
- Metadata: nullable ISO 8601 capture time, latitude, longitude, place name, and
  embedded description. Preserve missing timezones; never use file modification
  time. Image ingestion retains extracted values separately from explicit user
  corrections, then supplies merged effective metadata to the pipeline. A correction
  to null clears a value. Embedded descriptions prefill editable context.
- Story: title, opening `{text, audio_path}`, ordered chapters, closing with the
  same shape, and narration availability. A chapter contains photo ID, title,
  narrative, nullable location/time, and nullable audio path. No model emits IDs,
  paths, HTML, or ordering. Application code assigns those fields.
- Status: `state`, `current_stage`, `completed`, `total`, `error`. States are
  collecting, queued, processing, ready, failed. Error is null or contains stage,
  nullable photo ID, an actionable message, and `retryable`.
- Checkpoint: stage, nullable photo ID, validated stage result. Persist after each
  completed stage before moving on. Stage names are observe, synthesize, outline, chapter,
  framing, narration. Pipeline receives a snapshot and persistence callback;
  Flask owns the worker and store. `StageFailure` identifies model failures.

The real pipeline will order by capture time only if *all* photos have comparable
timestamps (all timezone-aware or all naive). Normalize aware values to UTC for
comparison. Otherwise preserve submission order, including when any timestamp is
missing. Resolve equal timestamps by submission order. The fake adapter always
uses submission order and only emits chapter checkpoints; it is a development
stub, not an implementation of real pipeline sequencing/retry semantics.

Count two analysis stages and one writing stage per photo, an outline stage per
bounded batch, one framing stage, and narration per opening/scene/closing:
`total = 4 * photo_count + 3 + ceil(photo_count / outline_batch_size)`. The batch
size is configured in generation settings and capped at 12. `job_steps.py` owns
the shared progress formula. Legacy audio-only repair preserves its prior count. Skipped or unavailable
narration counts as handled; a ready story can have unavailable narration.

## HTTP interface

All JSON errors use `{ "error": { "code": "...", "message": "..." } }`.
Unknown trip IDs return 404. JSON uses null for absent values.

| Method | Route under `/api` | Payload / response | State |
| --- | --- | --- | --- |
| GET | `/health` | scaffold/service state | **working** |
| POST | `/trips` | `{title}` → trip summary, 201 | **working** |
| GET | `/trips` | `{trips: [summary]}` | **working** |
| GET | `/trips/:id` | summary + photos + story_available | **working** |
| DELETE | `/trips/:id` | deletes trip and media, 204 | **working** |
| GET | `/trips/:id/status` | processing status | **working** |
| POST | `/trips/:id/photos` | multipart `photo` → photo response, 201 | **working** |
| PATCH | `/trips/:id/photos/:photo_id` | `{metadata, user_description, vibes}` → photo response | **working** |
| POST | `/trips/:id/process` | empty JSON → queued status, 202 | **working** |
| POST | `/trips/:id/retry` | empty JSON → queued status, 202 | **working** |
| GET | `/trips/:id/story` | story response; 409 if unfinished | **working** |
| GET | `/trips/:id/media/:asset` | trip-owned prepared JPEG or WAV | **working** |

Summary fields: id, title, created_at, updated_at, status, photo_count. Trip detail
adds serialized photos and story_available; internal local paths are never returned.

Photo response fields: id, submission_order, metadata (effective),
extracted_metadata (same Metadata shape), user_description, vibes, photo_url.
PATCH accepts only corrected fields; omitted fields stay unchanged. Photo edits
are allowed only while collecting; processing freezes the input snapshot.
Ask for missing capture/location information, editable context, and skippable
multi-select vibes. Coordinates alone permit an optional place-name field.

`story-response.json` demonstrates the browser contract: Flask replaces every
audio_path with audio_url and attaches photo_url using photo_id. No filesystem
path leaves Flask. Generated strings must be rendered with textContent.

## Worker lifecycle

Use exactly one background worker and a serialized job queue in one app process.
Lock read/modify/write operations around the store. Processing starts only after
the finish action. Persist checkpoints/status so polling may resume after closing
the browser. On startup convert queued/processing trips to failed with an
actionable retryable interruption error; explicit retry reuses checkpoints.
Disallow duplicate jobs and edits/deletion while a job is queued or running.
The worker starts lazily when a job is submitted. App startup recovers interrupted
records before serving requests. The store RLock serializes process-local
transactions; run one app process. Atomic JSON replacement protects checkpoints.

Narration checkpoints use result.segment (`opening`, `chapter`, `closing`) in
addition to stage/photo_id as their identity; this distinguishes opening and
closing, which both have null photo_id. Result also holds audio_path and available.

## Bulk selection

The browser selects multiple files and posts each separately to `/trips/:id/photos`
in selection order. Each request retains the existing `photo` multipart field and
photo response; no combined multipart payload or aggregate request limit is
introduced. Failed files are reported independently and retry independently.
Submission order reflects successful server ingestion, so a failed file retried
later is appended. Capture-time ordering still applies at generation when all
timestamps are comparable.

## Narration readiness and repair

Piper is a core project dependency. Its executable and English voice paths must
resolve inside this project. Startup tests real synthesis offline, and job-start
checks refuse enabled-but-missing narration setup with a 503 before inference.

`POST /api/trips/:id/narration/retry` queues an audio-only job for ready or failed
trips with a saved story. It returns 202 and the ordinary processing status. Valid
WAV checkpoints are reused; missing/corrupt/previously unavailable narration is
retried. The job_kind internal field distinguishes these jobs from full pipeline
jobs, including across interrupted-job recovery.

Story passages/chapters may include nullable `audio_error`; the frontend displays
it for unavailable cards. Narration checkpoint results include nullable `error`
so failures retain their cause. Narration failure still leaves the story ready
and readable, with availability `partial` or `unavailable` and a retry action.

## Connected-journal generation and rewriting

New stories set optional `story_style: connected_journal`; the existing title,
opening, chapters, closing, and per-segment audio API remains compatible. First
observe/synthesize all photos. Fold their compact, ordered facts into an outline
(premise, thread, closing_callback), carrying prior outline context across batches.
Outline checkpoints use stage=outline and the app-assigned last photo ID in that
batch. Models never generate photo IDs or ordering.

All scene calls receive the same final trip_outline, current authoritative raw
notes/metadata/vibes, scene_position/count, prior scene summary, and next moment
context. Opening and closing use this outline plus bounded representative scene
summaries. Prompts now have an additional plainly named `outline.txt` template.

`POST /api/trips/:id/rewrite` requires an idle saved story, returns 202, and keeps
only observation/synthesis checkpoints. A trip.before-story-rewrite.<edition>.json
backup is saved before mutation. New prose and audio are produced with app-owned
edition_id and job_kind=story; audio lives under editions/<edition>/narration.
The old story stays saved until a new result succeeds, and the old WAVs are not
overwritten. The worker uses that edition directory for later retries as well.
This is separate from /narration/retry, which preserves text and valid audio.

The browser story response also supplies optional edition_id. Listening resume is
scoped to that edition so a rewritten story does not inherit stale audio offsets.
Scene summaries used for neighboring/framing context prefer the owner's original
notes when supplied, preventing an embellished model summary becoming authority
for later scenes. The full raw current note remains the final writer input.

## Final output boundary

Only a ready connected_journal is a published story. GET story returns 409 for
intermediate/older caption results and running/failed jobs. Trip detail reports
story_available only for that published result, and requires_processing when an
older saved story needs finishing. On opening such a ready trip, the frontend
automatically POSTs /process and shows progress. That route accepts ready older
trips as well as collecting trips, preserving a private backup and reusing
analysis through the internal prepare_journal step. Previously completed
connected journals are never automatically regenerated. Worker completion also
refuses a non-connected pipeline result instead of publishing it.

/rewrite remains a compatibility/internal endpoint; there is no reader action
for selecting a caption version or explicitly rewriting one. New submissions
perform the connected pipeline directly and publish only its final result.

## Day overview and moment detail (journey version 2)

The browser receives canonical moments plus days, with the old chapters array
retained only as a compatibility alias. Each day owns app-assigned id/date and
ordered moment_ids, its story text, and one audio URL. Moments expose real camera/
user latitude and longitude for pins; unknown positions stay null. See
[day-journey.md](day-journey.md) for grouping, cache identity, map policy and the
legacy connected-story upgrade that preserves approved moment prose/audio.
