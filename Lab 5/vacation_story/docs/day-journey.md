# Whole journey, day stories, and moments

The output has two levels. Its default view is the entire journey on a street
map, with numbered photograph thumbnails above their recorded locations and
arrows showing photo-to-photo direction. A selected day has one connected
personal-journal story and one WAV. Clicking a pin or day thumbnail opens that
photo's **moment** and synchronously starts its separate narration. Returning to
the day overview pauses the moment; the owner deliberately resumes the day.
“Listen to the whole journey” plays day WAVs in order, rather than playing each
individual moment. Daily narration highlights its day, without pretending to
know exact per-photo timings inside one WAV.

## Map behavior and privacy

The user explicitly selected an online street map for local detail. Leaflet
JavaScript, CSS, marker images, and license are bundled inside this project.
Browser requests for the normal visible OpenStreetMap tiles provide street
context. There is no remote geocoding, route-planning request, external photo
upload, model service, or audio processing. Street tiles require a connection;
when they fail, the pins/route remain on the map and day/moment lists stay usable.
If there are no GPS coordinates, no guessed location or default-world route is
shown: an honest message and all the moment thumbnails remain available.

Pins use camera/user latitude and longitude. The line is an ordered connection
between known photo positions, **not the actual walking/driving route**. Missing
GPS moments are counted and listed; links skipping them are dashed. Direction
arrows use the displayed map projection. The full route fits once on opening;
day selection changes highlighting, and only explicit focus controls change the
viewport. Narration never auto-pans to fetch tiles. Nearby thumbnail cards are grouped by their projected on-screen footprints.
The overview shows a compact thumbnail stack and photo count instead of
shifting individual cards away from their pins. Zooming in separates them when
there is enough room for the cards, pointers, and gaps; zooming out groups them
again. Cluster markers may contain several days and highlight whenever a member
belongs to the active day or selected moment. The route still uses actual GPS.

Selecting a group zooms to its members without starting narration. If fitting
its bounds would not zoom in, the map advances one level toward its center.
At maximum zoom, or for photos with exactly the same GPS coordinates, a local
photo chooser exposes every member. Selecting a child plays only that moment.
All photos also remain accessible in their day's complete thumbnail strip.

OpenStreetMap attribution remains visible at the map's top right. Tile-failure
messages are outside the canvas. Tiles use the standard browser cache/referrer;
there is no bulk prefetch, offline tile download, or headless map crawling.

## Contracts and processing

The internal story keeps `chapters` as a compatibility storage field, but its
records are user-facing **moments**. `journey_version: 2` adds `days`:

```json
{
  "id": "day-2018-08-24",
  "date": "2018-08-24",
  "title": "Our day together",
  "narrative": "The connected story of this day…",
  "moment_ids": ["photo-one", "photo-two"],
  "audio_path": "<local path>",
  "audio_error": null
}
```

IDs, dates, membership, order, and paths are assigned by application code. Capture
days use the date written in the timestamp, without converting the photo to the
Pi's timezone. Undated photos form a separate `undated` group; they are never
assigned to an adjacent known date. Known groups follow the published moment
order, with the unknown group last.

A new `day.txt` template writes a whole-day overview in the existing I/we voice.
All day sources are considered in bounded batches of twelve; each subsequent
batch extends the same day story. Only the final story is published and narrated
as one WAV. Day checkpoints have null photo_id plus application-owned day_id and
batch fields. Day narration has segment `day:<id>`, distinct from the historical
`chapter` segment cache key used for individual moment audio. Models never return
IDs or photo associations.

The browser response supplies `moments` with photo_url, audio_url, latitude, and
longitude, plus `days` with audio_url and moment_ids. `chapters` remains an API
alias for compatibility, not a selectable caption output. Opening/closing text
and old WAVs remain stored; they are not the v2 high-level player and do not
count against v2 day/moment audio availability.

Existing completed connected journals are upgraded lazily when opened. A private
JSON backup and new edition are created, then `job_kind: days` generates only the
missing day layer, retaining approved moment text and valid moment WAVs. A failed
or interrupted upgrade is retryable from its saved day checkpoints. It does not
repeat image observation or moment prose. Audio-only retry covers both day and
moment files and never calls the story-writing model.

## Verification

Component checks cover known/unknown days, timezone-preserving grouping, GPS and
missing-GPS associations, three-day migration preserving moment prose/WAVs, full
source coverage for a large day, and separate day narration files. A Node harness
executes the actual app renderer against a small DOM/Leaflet seam: initial fit,
OSM attribution, route/pins/arrows, zoom-aware thumbnail groups, daily playback,
synchronous pin-to-moment playback, and return navigation. It makes no real tile
requests. The browser fixture uses no-GPS records so it cannot fetch map tiles.
The Pi's Chromium renderer remains unavailable; real iPhone layout, street-map
loading, and audible playback remain a manual device check.

## Official references

- Relive's route, photo, and map context informed the overview. This is a local
  implementation, not a Relive integration: [Relive feature overview](https://support.relive.com/kb/guide/en/your-new-relive-is-here-SkECJOTybj/Steps/4393615).
- Map tile usage follows [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).
- The bundled map client is [Leaflet](https://leafletjs.com/download.html); its
  license and verified asset manifest live in `static/vendor/leaflet/`.

## Clustering reference and verification

FindPenguins uses cover-photo representations on its trip map and offers a deeper
map for a Footprint's individual media. That provides an overview/detail design
reference, rather than evidence of a particular clustering algorithm: [official
photo-map guidance](https://support.findpenguins.com/hc/en-us/articles/30406231076124-Where-can-I-see-my-photos-and-videos-on-a-map).

This project's clustering is its own local screen-space implementation in
`static/photo-clusters.js`. It adds no library, remote script, service, data
migration, or story/narration regeneration. The actual-app Node harness checks
overview collapse, high-zoom separation, collapse again on zoom-out, cluster tap
without audio, stalled-fit zoom progress, max-zoom/identical-location chooser,
mixed-day/selected-moment highlighting, unchanged true route coordinates, and
synchronous child/individual moment playback. It fetches no map tiles. Actual
iPhone layout and touch behavior remain part of the manual device check.
