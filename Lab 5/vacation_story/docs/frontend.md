# Frontend experience and checks

The frontend uses the local Flask API and buildless HTML/CSS/JavaScript. Open trips
have a `#trip=<id>` URL, so reloading restores collecting, processing, failed, or
ready state. Polling stops when leaving a trip or reaching a ready/failed state.
No inference starts during collection.

## Collection

The picker accepts multiple photos. Batches upload serially with file-by-file
progress, separate failure messages, and failed-file-only retry. Editing and
finishing are disabled during uploads. Leaving stops the remaining batch; saved
photos stay in the trip. A failed file does not block later selected files.

After upload, review the first new photo, then save and review the next or finish
with available details. Known metadata is shown with optional corrections;
unknown time/place questions are optional. Coordinates allow an optional place
name without maps or geocoding. Six checkbox vibes can be combined or skipped.

## A continuous personal travel journal

The ready page contains the whole journey on one scrollable page: a real-photo
cover and opening, a linked itinerary, all illustrated photo scenes, and a closing
reflection with a photo contact strip. The itinerary stays beside the story on
wide displays and becomes a collapsible contents list on phones. Labels use only
available dates/places; they do not infer missing travel facts. Generated text is
always inserted as plain text.

`static/journal.js` maps the finished connected Story API response into an
ordered journey. The reader has no caption-version choice or rewriting button.
Opening a ready older trip with `requires_processing` automatically posts to
`/process`, then shows ordinary progress until its final connected story is
ready. The server blocks intermediate captions from the story endpoint.

The outline stage is presented as “Finding the thread through your trip.”

A sticky player shows the current scene, journey position, listen/pause, and
previous/next controls. A gesture starts narration. Completed audio advances and
scrolls to the next scene without moving keyboard focus. Manual jumps pause
playback; manual scrolling never starts audio. Reduced-motion settings disable
smooth scrolling. A saved per-trip browser listening position permits resuming,
but storage failures do not block reading or playback. A changed edition resets
old listening positions after internal preparation.

Missing narration leaves the scene visible and pauses the guided experience;
readers can continue with Next. Per-scene errors are expandable. The existing
**Retry missing narration** action remains separate from rewriting and uses only
the saved displayed text.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_journal.py tests/test_bulk_uploads.py
.venv/bin/python -m pytest -q tests/test_frontend.py
```

The Node-backed checks need no browser: the journal check verifies the complete
ordered scene set, photo/audio associations, optional metadata and errors, and
unchanged source records. The batch check covers serial order, partial failure,
retry of failures only, and cancellation after leaving a trip.

The installed-Chromium fixture covers collection, bulk review, progress reopening,
a continuous ready journal, itinerary jumps, gesture playback, pause, manual
navigation, narration failure, and automatic finalization of older trips. It uses temporary
localhost fixtures and mocked audio, with deterministic geometry observation;
manual device checks must assess actual scrolling/layout/audio behavior.

The previous environment could not start a Chromium renderer: escalated runs
timed out without a DOM result, and restricted-socket runs skip. No fresh browser
pass is claimed for this revision. JavaScript syntax and pure view-model checks
are run locally. A real phone check must confirm layout, itinerary scrolling,
listen/pause/resume, and full-story continuity.

See [research and design rationale](story-experience.md) for the official product
precedents and the reasoning behind the journal layout.

## Day/map revision

The current reader supersedes the continuous chapter-scrolling layout above with
a whole-journey street-map overview, one day story/WAV per day, and photo-click
moment detail. User-facing chapter labels are now moments. The actual app.js
renderer is exercised by tests/test_day_map_frontend.py using a DOM/Leaflet seam,
so map and audio bindings are checked without any external tile requests.
The Chromium fixture uses no-GPS records; manual iPhone QA remains necessary.
See [day journey](day-journey.md) for the current complete behavior.
