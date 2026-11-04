# Integration verification

Checks run on the Pi during implementation:

- Web/storage component: representative JPEG upload, source capture metadata and
  embedded context, orientation correction, 1600-pixel cap, source metadata
  preservation after corrections, media privacy, persistence/reload and deletion.
- Worker boundary: no inference during collection, serial job start, blocked
  edits/deletion while processing, persisted failure, explicit retry retaining
  completed work, and interrupted-job recovery after restart.
- Pipeline: fake adapters verify observation independence, user context and vibe
  propagation, stage order, persisted checkpoint reuse, photo associations,
  timestamp/submission ordering, exact narrated text, and readable partial audio.
- Ollama transport: request encoding verifies thinking disabled, JSON schema,
  configured context/output bounds and image attachment.
- Python/JavaScript/shell syntax and installed dependency consistency checked.

The restricted test run reports **23 passed, 1 skipped**. The skipped frontend
fixture check needs localhost sockets and a working installed Chromium renderer.
Headless Chromium checks were attempted separately with local permissions; see
`frontend.md` for the reproducible fixture flow. A skip is not a browser pass.

A real local smoke run used the existing `qwen3.5:0.8b`, the repository's sample
bus/street image, and the existing English Ryan Piper voice from Lab 3 (temporary
config override, no downloads). Observation, synthesis, chapter, framing and all
three narration segments completed; the saved WAVs passed format/frame checks.
Temporary trip data was removed after the test. This checks actual adapter and
model/voice compatibility, rather than phone collection or audible playback.

Manual review of the first generated text found unsupported city/action details.
The implementation was tightened afterward: observations exclude uncertain OCR
and place guesses, chapter generation receives raw authoritative user context,
and framing rephrases supplied summaries without adding names/actions/emotions.
A tiny local model can still invent details; factual quality needs human review.

Still required on a real phone: upload several vacation photos including HEIC,
close/reopen during processing, listen to narration and assess factual grounding
and story coherence using the README demo checklist.

A follow-up real text-only model check with explicit user context removed the
unsupported city from the chapter, but framing still added a moving bus, a day
beginning, and a sunset. A conservative framing vocabulary check now falls back
to saved chapter summaries if new content words appear. The component test uses
an invented city/boarding result to exercise this fallback. It cannot establish
semantic truth or correct unsupported details already in source chapters.

The separately attempted headless Chromium fixture runs timed out at browser
startup even after inference finished. No DOM result was returned. Test-owned
process groups were cleaned up; the test retains explicit failures on timeout.
Frontend browser flow therefore remains unverified on this host.

Bulk-upload update: the Node-backed transport check passes for serial multi-file
upload, partial failure with successful photos retained, failed-only retry, and
stopping after leaving a trip. The browser fixture now selects two files and
reviews them separately, but still requires a functioning Chromium host.

Project-local narration repair: Piper is now a core dependency in this project's
virtual environment. The configured English voice and matching JSON were freshly
downloaded into this project's voices folder. Full setup was rerun successfully,
and `bash run.sh check` verifies real speech offline with these local assets.
There is no fallback to another lab, another environment, or PATH-resolved Piper.

The existing 12-photo trip's 14 missing narration files were generated from its
saved displayed text. Every WAV passed the frame/header check, all API audio URLs
are present, and ranged WAV delivery passed. Before/after comparison confirmed
unchanged photos, displayed story text, and non-narration model checkpoints. A
JSON backup is kept inside the ignored trip directory. No model inference was
performed during repair. Audible playback still requires the user/device check.

New component checks confirm missing voice setup stops startup and job submission
before inference, external-project Piper paths are rejected, failed narration
retains its error, and audio-only retry reuses valid WAVs without calling a model.
Per-card errors and the retry button are implemented in the frontend; browser
verification retains the previously documented Chromium limitation.

Connected-journal revision: model-adapter tests now verify that all observation/
synthesis calls finish before outlining/writing, bounded outline batches fold the
whole collection, every scene receives the shared outline and correct neighboring
context, and retry reuses completed work. A rewrite integration check verifies
analysis reuse, JSON backup, unchanged photos/old audio, edition-separated new
WAVs, duplicate-job rejection, and corrected stage totals. A Node check verifies
the entire ordered journey and original media associations in the view model.
Rendered Flask template and local journal asset delivery pass.

The reader renders all scenes on one page with itinerary links and a persistent
player; browser layout/playback remains unverified on this host. Whole-set live
text samples exposed unsupported sensory detail, so the final chapter prompt was
shortened and source notes made the primary scene/outline facts. Neighbor and
framing summaries prefer the owner's notes over model embellishment to reduce
propagation of guesses. Original published story and repaired audio are retained;
new text requires the explicit Rewrite as a connected story action.

Final-output revision: caption/version choices and the rewrite button have been
removed. New submissions publish connected journals directly. Older trips are
automatically finalized through /process when opened; intermediate prose is not
returned by the story API. An integration check covers private backup, analysis
reuse, unavailable intermediate story responses, and publication of only the
final journal. A worker check refuses to publish an accidental caption result.
Previously connected stories and their audio are retained unchanged.

iPhone JPEG compatibility: reproduced the reported generic upload rejection
with a valid .jpeg containing multiple JPEG frames (Pillow detects MPO). The
importer now accepts MPO and explicitly uses the primary image before metadata
extraction, orientation correction and JPEG preparation. The regression check
verifies capture time/offset and context, rotated primary-photo dimensions/color,
a single saved photo, no retained original/auxiliary scene, and the two prepared
JPEG copies. A real iPhone retry remains the device confirmation. Unsupported
formats now include the detected format in their error instead of only listing
accepted extensions. The HTTP 400 POST log matches an application rejection;
the separately reported TLS-looking request bytes are HTTPS sent to the plain
HTTP development server. Use an explicit http:// LAN URL.

Reference: [Pillow JPEG/MPO detection](https://pillow.readthedocs.io/en/stable/_modules/PIL/JpegImagePlugin.html).

Day/map revision: new checks cover timezone-preserving day grouping, unknown-date
and unknown-GPS treatment, three-day lazy migration that preserves moment prose
and WAVs, full source coverage for more than twelve photos in a day, one day WAV
per day, and moment/day API audio associations. A Node harness executes real
app.js with a DOM/Leaflet seam to verify map initialization, visible attribution,
whole-route fit, route arrows, pin thumbnails/collision leader lines, day-by-day
audio, synchronous moment playback from a pin, and back-to-day navigation. It
makes no tile requests. Local Leaflet asset checks also pass. Browser fixtures
resolve the local Leaflet assets and deliberately use no-GPS data, so no live
OSM tiles are fetched during browser automation. Chromium remains unavailable
on this host; real iPhone map layout, street tiles, and listening need a device
check. No existing published trip was changed during implementation.

Zoom-aware photo clustering: replaced collision-card fanning with projected
thumbnail groups. The actual app/Leaflet seam now verifies low-zoom collapse,
higher-zoom separation, zoom-out regrouping, cluster-click fit without narration,
forced zoom progress for unchanged fitted bounds, max-zoom co-located photo
access, mixed-day/selected-member highlights, and preserved individual moment
audio/true routes. No new runtime dependencies, remote scripts, or source-data
changes are involved. Browser/device layout remains the known verification limit.
