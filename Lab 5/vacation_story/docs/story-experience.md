# An itinerary told as one story

## Diagnosis

The current reader makes the photo the unit of the experience: one image, one
isolated paragraph, then a button to replace the entire screen. Repeated labels
such as “Moment 1” and a `2 / 14` counter frame the result as a slideshow. The
reader cannot see the path of the trip or how the current scene connects to what
came before. Each chapter is also generated before the next photo is considered,
so the prose naturally becomes an expanded caption. Styling alone will not solve
that generation problem.

The intended unit should be **one journey, illustrated by the picture set**.
Every scene must contribute to that journey; photos supply evidence and texture,
and known dates/places give the story its itinerary.

## Useful precedents

| Experience | Verified pattern | Adaptation here |
| --- | --- | --- |
| Polarsteps | A trip has steps combining a visited place, personal experience, photos, and text. | Keep a visible itinerary spine and meaningful stop labels alongside the narrative. A photo should belong to a journey, rather than appear as an unrelated card. [Official first-trip guide](https://support.polarsteps.com/hc/en-us/articles/24267454919314-How-do-I-create-my-first-trip) |
| Google Photos Memories | Its Memories view presents curated trips and moments as a scrapbook-like timeline; users can adjust a memory's title and photos. | Give the whole set a cover, recognizable title, and continuous keepsake layout. Treat the collection as one memory that the owner can revisit. [Official product announcement](https://blog.google/products-and-platforms/products/photos/google-photos-memories-view/) |
| Relive | Its current product framing emphasizes personalized memories, people, and moments, and supports photo/video highlights and custom titles. | Make “Listen to our journey” the main guided action, with the photo sequence supporting one narrated experience. The useful inspiration is the whole-adventure recap, not route tracking or video export. [Official feature overview](https://support.relive.com/kb/guide/en/your-new-relive-is-here-SkECJOTybj/Steps/4393615) |
| ArcGIS StoryMaps guided tours | A guided tour presents related places in a numbered sequence that readers navigate by scrolling, with media and narrative text. | Use scrolling scenes and a linked stop list. Replace the map with a simple local text itinerary; retain the sense of movement through a sequence. [Official guided-tour documentation](https://doc.arcgis.com/en/arcgis-storymaps/author-and-share/add-guided-tours.htm) |
| Adobe Express webpages | Its webpage builder combines titles, images, text, photo grids, split layouts, and a glideshow. | Vary the rhythm between a spacious opening, large photographs, prose, and a final reflection. This is a visual-story reference, not an external editor integration. [Official webpage tutorial](https://www.adobe.com/learn/express/web/create-webpage-with-adobe-express) |

These are design inferences from the cited product patterns. They do not require
integrating any of those services. Keep all photos, narration, rendering, and
runtime assets local; add no maps, external fonts, stock imagery, or geocoding.

## Proposed reader

1. **A cover for the whole journey.** Show the trip title, the first real photo as
   a cover image, a short opening that establishes what connects this set, and
   known date range/place labels. Primary action: “Listen to the journey.”
   Secondary action: “Read the story.” Avoid a blank opening card.
2. **A visible itinerary.** Below the cover, show compact linked stops in the
   actual story order: ordinal, known place/date, and scene title. On wide screens
   this becomes a narrow sticky contents column. On phones it is a collapsible
   “Your journey” list above the story. No map and no inferred travel distances.
3. **One continuous illustrated travelogue.** Render the opening, all photo
   scenes, and reflection on one page. Each scene has a title, small itinerary
   label, actual photo, and connected prose. Alternate spacious image/text
   arrangements on desktop; use a simple image-then-prose column on phones.
   Preserve full photo visibility in scenes, even if the cover is cropped.
4. **A connected ending.** The closing returns to a detail/theme established at
   the beginning and shared by the provided scenes. Finish with a compact strip
   of all trip photos and “Start again,” giving the set a sense of completion.
5. **A persistent, quiet player.** A sticky bottom bar contains play/pause,
   previous/next scene, the active scene title, and progress through the journey.
   Playback starts only with a gesture. After a segment ends, highlight and scroll
   to the next scene and continue. Manual scrolling must not unexpectedly start
   audio or seize focus. A jump/next action pauses current audio; pressing play
   resumes from that scene. Respect reduced-motion preferences.
6. **Readable partial narration.** Missing audio must leave that scene's prose
   visible. Guided listening should pause there with a clear “Continue to next
   scene” action, rather than silently omit part of the story. Keep the existing
   retry-missing-narration action, with errors in a details area instead of the
   central reading space.

A near-term implementation can retain one internal chapter per photo. Rendering
all scenes together removes the slideshow structure without changing media
associations. True multi-photo scene grouping is a later contract change; it is
not necessary to make the first revision feel like one journey.

## Generation must change too

The pipeline should inspect the full set before it writes its first scene:

1. Observe and synthesize **all** ordered photos, preserving user descriptions,
   corrected metadata, and vibes as authoritative inputs.
2. Build one small trip outline from that fact set: a shared premise, a grounded
   thread, and the role of each scene in order. The thread can be a progression
   of places, activities, or a repeated detail. It does not need a dramatic
   conflict, invented emotion, or an assumed “arrival”/“departure.”
3. Write each scene with the same trip outline, its authoritative facts, the
   previous scene's short summary, and the next scene's known topic. Use an
   opening connection, one specific event/detail, and a transition where facts
   support it. Avoid repeatedly introducing “this photo shows.” Do not manufacture
   transport, elapsed time, weather, motives, relationships, or place names.
4. Write opening and closing from that shared outline and the completed scenes;
   the ending should make a callback rather than merely describe the last photo.
5. Narrate the final displayed prose, preserving the project-local Piper checks,
   saved errors, audio-only retry, and valid-audio reuse.

The distinction between connected prose and invented facts matters. “The next
part of our journey brings the shore back into view” can connect two known
shore scenes without inventing a bus ride. “After a long bus ride, we finally
reached the shore” is only valid if the user's context actually supplies that
trip. Let factual sequence, recurring details, and the owner's notes create the
arc. If dates/locations are unknown, use neutral sequence labels rather than
pretending to know an itinerary.

## Collection and processing

Keep bulk upload. After the set is uploaded, show a small **whole-trip preview**:
photo count, ordered thumbnail strip, and available places/dates. Explain the
order in plain language: capture time when all timestamps are comparable,
otherwise upload order. A future improvement is one optional trip-level note —
“What should this story remember about the trip?” — so the owner can supply the
purpose or significance that images cannot establish. It is not added to this
revision because the current API has no trip-note field. Per-photo details remain
editable and optional; no extra mandatory questionnaire.

Processing labels should describe the promised transformation: “Understanding
your moments,” “Finding the thread of your journey,” “Writing the connected
story,” then “Recording the narration.” Show which phase is active and that the
whole uploaded set is saved. Do not display a fake completion estimate.

## Existing stories and verification

The finished output should only be the connected story. Older caption results
are finalized automatically when opened, reusing saved observations/synthesis
and retaining a private backup. The reader shows progress until that final result
is ready. A separate rewrite action was used during prototyping and has been
removed from the user flow. Audio-only retry remains separate and never rewrites
text.

Check one fixture journey with three different scenes: all photos remain
accessible on a single page; itinerary links find the right scene; playing
continues into the next scene; pause/jump works; unavailable audio leaves readable
text. For generation, assert that all scene calls receive the same outline and
correct neighboring context, rather than asserting exact prose. Manual review
must assess whether the entire narrated set has continuity and a grounded ending.

## Observed model constraint

The continuous reader and full-set outline address the structural caption problem;
they do not establish that the generated prose is a good or factual story. In a
live local sample, `qwen3.5:0.8b` loosely followed the personal-journal voice but
still mixed facts between adjacent scenes, invented sensory details, and added a
frame purchase that the source did not establish, even with a restrained editing
prompt. Providing shared context is necessary for continuity, but this tiny writer
can also misattribute details from that context.

The published story is not automatically replaced by those experimental outputs.
The current revision needs manual review of a complete generated journey before
any claim about literary quality or grounding. A stronger future writer, tighter
source attribution, and owner editing are possible improvements; the UX redesign
alone should not be described as solving those model limitations. Older results are finalized internally, retaining the prior story as a private
backup. Already connected stories are not regenerated automatically.
