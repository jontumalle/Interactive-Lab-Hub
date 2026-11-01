# Local Vacation Story

A local Flask application for turning phone photos into narrated vacation stories
on a Raspberry Pi. Select one photo or a whole batch, upload them together, and review their
details and optional vibes before finishing to start processing. Return to the trip
later for its progress or a whole-journey map, one narrated story per day, and
individual photo moments to explore.

Photos, JSON records, model inference, and WAV narration stay on the Pi. The
map client is bundled locally; its street-map background uses ordinary online
OpenStreetMap tiles, as selected for local map detail. There is no database,
login, reverse-geocoding request, remote photo upload, or cloud processing.
The original [MVP plan](docs/plan.md) and [contracts/API](docs/contracts.md) are kept
alongside the implementation.

## Setup

Use Python 3.11+ from this project directory. Run setup while online:

```bash
bash setup.sh
```

Setup creates this project's `.venv`, installs all dependencies including Piper,
downloads the configured English voice and matching JSON into `voices/`, and
verifies real speech synthesis. Running setup again reuses valid voice files.
Piper and voice paths must stay inside this project: there is no PATH search or
fallback to another lab, another virtual environment, or a global Piper install.
The compatibility extra `.[narration]` remains supported; Piper is now a core
dependency, so installing `.[dev]` also installs it.

Use the existing system Ollama service as specified in the MVP plan. If the model
is missing, run `ollama pull qwen3.5:0.8b` during setup. Runtime never downloads
models or voices, and narration itself needs no service or network connection.

Startup performs an offline speech check. Missing/broken Piper or voice files
stop startup with a setup instruction before a trip can be processed. To choose
text-only operation explicitly, set `narration.enabled = false` in `config.toml`.

## One-command startup and phone access

```bash
bash run.sh
```

Open `http://localhost:5050` on the Pi. From a phone on the same trusted network,
open `http://<PI_LAN_IP>:5050` (find the Pi address with `hostname -I`). The server
listens on all interfaces, with no login. Keep the server process running, for
example inside an existing `tmux` session; closing a browser does not stop a job.
Run exactly one app process: the serial worker and store lock are process-local.
The startup script disables the Flask reloader. Restart an already-running
server once after updating its code/configuration to load these checks and UI. The built-in Flask server is
intended for this trusted local MVP, rather than public hosting.

## One journey from the whole photo set

The default output shows the whole journey on a street map with photo-thumbnail
pins and directional photo-to-photo connections. A day selector presents one
connected I/we story and one narration per recorded capture day. Listen through
the day stories for the high-level journey; click a photograph to dive into that
individual **moment** and its separate narration. The map line connects recorded
photo positions, not an inferred walking/driving route. Photos without GPS remain
in the day photo lists; photos without dates form an honest undated group.

Existing approved connected stories gain the day layer when opened, preserving
their moment prose and valid audio. Progress/checkpoints, backups, local Piper
checks, readable fallback, and audio-only retry apply to day and moment narration.
See [day journey behavior and contracts](docs/day-journey.md) for details and the
online-map boundary. Model-written daily stories still require factual review. Nearby photos collapse into
thumbnail groups with counts; zoom in to separate them or select a group to
explore its area. At maximum zoom, same-location photos remain available in a
photo chooser and the day's moment list. Clustering does not regenerate stories
or change stored coordinates.

The [design research](docs/story-experience.md) records inspiration from official
Polarsteps, Google Photos Memories, Relive, StoryMaps, and Adobe Express examples.
Those services are inspiration only. The online map background is the sole
external runtime asset; photos, story processing, and narration remain local.

## Narration health and recovery

Check the project's dependencies and synthesize a short test offline:

```bash
bash run.sh check
```

Stories remain readable if an individual narration request fails. The card shows
its saved error, and **Retry missing narration** regenerates only missing/corrupt
audio, preserving the displayed text, photos, model checkpoints, and valid WAVs.
Reasons are also saved in narration checkpoints and logged on the server.

An existing story can be repaired from the project directory without language
model inference:

```bash
bash run.sh repair-narration <trip_id>
```

Use this only when the trip has no active job. The command backs up its JSON,
marks it busy while repairing, and saves progress after each card. It uses the
saved displayed text and can repair legacy trips with unavailable narration.
`/api/health` also reports narration enabled/ready and any setup problem.

## Bulk photo upload

Choose multiple photos in the file picker, then press **Upload selected photos**.
The page shows file-by-file progress. Each photo is sent in its own request, so
large batches do not hit a combined upload-size limit or load all images into Pi
memory at once. The configured upload limit still applies to each photo. iPhone-style
multi-image JPEGs are supported too: their primary photograph is prepared, while
auxiliary HDR/depth frames are excluded from the trip. If an unsupported image is
selected, its detected format is reported in the per-file error.

After upload, review the first photo and save its answers. **Review next photo**
steps through the rest; details remain optional, and you can finish using the
available metadata. Every thumbnail also has an edit button. Failed files are
listed separately; return to **Add more photos** and use **Retry failed photos**
to resend only those files. Successful uploads are already saved.

Keep the page open until uploads finish. Leaving it stops sending the remaining
files; uploaded photos remain in the trip and can be reopened for editing. Story
processing begins only when you press **Finish and create my story**.

## Configuration and retained data

`config.toml` centralizes image limits, generation settings, model, and voice.
Copy it to ignored `config.local.toml` and set `VACATION_STORY_CONFIG` to its
absolute path for local overrides. Relative asset paths resolve from this project
folder. Startup and browsing make no inference requests. Prompts in `prompts/`
are loaded at job start; see [prompt examples](prompts/README.md).

Each trip lives under ignored `runtime/<trip_id>/` with an atomically replaced
`trip.json`, prepared orientation-corrected JPEGs (up to 1600 pixels), smaller
analysis images, and optional WAVs. Capture metadata is read before preparing
images; missing dates stay missing, and file modification dates are never used.
Original upload bytes are not retained after successful preparation/persistence.
Delete a trip from the trip list to remove its JSON, images, and narration.
Queued/running trips cannot be edited or deleted until processing stops.

One worker processes one trip and one inference request at a time. Each completed
stage is checkpointed. A restart marks interrupted/queued trips as failed with an
explicit retry action. Retrying keeps completed work, while new jobs use current
prompt files. Unavailable narration is recorded without failing the story.

Timestamp ordering is used only when every photo has a comparable capture time;
otherwise the story keeps submission order. User corrections override extracted
metadata/model guesses. Framing that introduces unsupported names or numbers falls back to
saved chapter summaries. The specifics check permits connective prose instead
of requiring every word to repeat a caption. Models can still make factual
mistakes: review the story.

The reader has previous/next controls and gesture-triggered narration. Playback
advances at narration end; pause/manual navigation stop it. Cards without usable
narration remain readable and can be advanced manually.

## Development and verification

```bash
.venv/bin/python -m pytest -q
```

High-level component checks cover web ingestion/metadata/persistence/deletion,
worker failure/restart/retry, serial bulk upload/failure/retry/navigation, and
pipeline sequencing/checkpoints/context using
fake adapters. The frontend fixture flow runs in installed Chromium when local
socket/browser permissions are available; otherwise it reports a skip. No model,
voice, or browser downloads occur during tests. Synthetic fixtures contain no
private photos. The fake pipeline remains available for injected web tests.
See [verification results and remaining device checks](docs/verification.md) for
the real Ollama/Piper smoke result and the headless Chromium startup limitation.

Implementation boundaries: Flask/images/storage/worker are the lead component;
`templates/` and `static/` are the frontend; `pipeline.py`, `adapters.py`,
`prompts.py`, and `prompts/` implement local generation and narration. Flask alone
maps local files to browser URLs; generated strings are rendered as plain text.

## Real-device demo checklist

- Submit several vacation photos from a phone, including one with missing date or
  location. Confirm editable extracted details and optional/skippable vibes.
- Save each photo and its answers, finish, close the browser during processing,
  then return to the trip and see persisted progress or the completed story.
- Review day grouping, photo pins, route direction, moment associations, and
  daily story coherence. Exact model wording is intentionally not asserted by
  automated tests.
- Start narration with a gesture; pause, resume, navigate, and listen through an
  automatic transition. Verify readable text when narration is unavailable.
- Retry an interrupted/failed job and verify completed stages are reused. Delete
  the trip and confirm its prepared photos and WAVs are removed.

A real phone/HEIC collection and listening check remains a manual device step.
