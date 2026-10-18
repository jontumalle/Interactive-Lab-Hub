# At the Table

A local dining practice prototype: touch a wired paper utensil and see feedback on your phone. The Pi owns the entire session; the phone displays its current state. All connected phones see the same session.

## Start and stop

From the repository root:

```bash
"Lab 4/fine_dining/start.sh"
```

The script uses `Lab 4/.venv` if present, otherwise `python3`. It needs the same CircuitPython/Blinka dependencies and I²C setup as `cap_test.py`. If these are missing, install the Lab 4 requirements into the lab virtual environment as described in the lab README.

Keep your hands off the utensils during startup. Open the printed `http://<hostname>.local:8000` URL on your phone. If that does not resolve, run `hostname -I` on the Pi and use its Wi-Fi/LAN IP, for example `http://192.168.1.42:8000` (replace the example address).

The phone and Pi must be on a network that permits device-to-device traffic. Guest/campus Wi-Fi sometimes blocks this even on the same network. Use a shared network or hotspot that allows local connections. No internet access is needed by the app. This prototype serves plain HTTP on the local network without login.

Press **Ctrl+C** in the running terminal to stop. Start again for a fresh dinner or after editing configuration. Stop other sensor demo scripts before running this app. If the port is in use:

```bash
"Lab 4/fine_dining/start.sh" --port 8001
```

## Match your wiring

The supplied mapping is a placeholder: **fork = 0, knife = 1, spoon = 2**. Check it before playing:

```bash
"Lab 4/fine_dining/start.sh" --map
```

Touch each utensil separately and note the channel printed in the terminal. Mapping mode reads all 12 channels, including disabled/unmapped ones, and does not start the website. Stop it with Ctrl+C, then edit `cutlery.json`.

Each utensil has a stable `id`, a human-readable `name`, a `channel` from 0–11, and an `enabled` flag. IDs and channels must be unique. Set `enabled` to false to ignore a channel during play. If channel 0 is troublesome, disable or remap its utensil; the separate `cap_test_sensor0_inactive.py` file does not establish that it is faulty.

`debounce_ms` controls how long a complete touch combination must remain stable before acceptance (default 100 ms). Increase it if touches flicker; lower it cautiously if short touches are missed. Touch means select: the sensor cannot prove that a utensil has been lifted or placed correctly.

## Configure a dinner

Edit `scenarios.json`. `courses` is the ordered list of prompts:

```json
{
  "dish": "Tomato soup",
  "prompt": "Your soup has arrived. Touch the utensil you would use.",
  "accepted": ["spoon"],
  "hint": "Choose a utensil that can hold the broth.",
  "explanation": "Use the spoon for soup."
}
```

`accepted` lists alternative correct utensil IDs, not a simultaneous combination. All must exist and be enabled in the mapping. Add separate IDs such as `salad_fork` and `dinner_fork` if you wire multiple forks. `feedback_seconds` sets the minimum display time for correct feedback (default 4 seconds). Wrong feedback stays visible until another selection; the learner can retry indefinitely.

Check edits without starting the sensor or web server:

```bash
"Lab 4/fine_dining/start.sh" --check-config
```

Restart to load changes. Configuration errors print in the terminal before the sensor starts.

## Interaction and first hardware trial

1. Start the app, connect your phone, and verify the live sensor indicator.
2. Touch a wrong utensil: expect a clear “Try again” message and hint.
3. Hold it: it should count only once. Release all utensils, then choose again.
4. Touch two utensils together: expect “One utensil at a time,” with no attempt counted. Touches arriving separately may be interpreted as the first selection if separated by more than the debounce interval.
5. Select correctly: the photo border glows green. Listen to the waiter, release the utensils, and wait for the next course.
6. Refresh the phone: it should rejoin the current course. Finish for the first-try/retry summary.
7. Stop the app: the phone should show disconnection within a few seconds. Restart for another dinner.

Sensor failures display separately from answer feedback and print details in the terminal. Fix the wiring/environment and restart. Session progress is in memory and resets on restart. Phones can reconnect without resetting it; the Pi continues the session even when no phone is connected.

There is no automated test suite. The first hardware trial should guide changes to debounce, timing, wording, and scenario content. Servo actuation required by Part 2 remains a subsequent iteration.

## Files

- `app.py`: sensor polling, debouncing, session decisions, and local HTTP server.
- `static/index.html`: responsive display and polling; no grading or progression logic.
- `cutlery.json`, `scenarios.json`: editable configuration.
- `start.sh`: launch using the lab Python environment; forwards command-line options.

## Course photos and atmosphere

The sample dinner includes lobster bisque, burrata, filet mignon, and dark chocolate torte. Each dish page centers on the food photo and dish title, with a green glowing border for correct choices and red for incorrect choices. The waiter supplies spoken guidance; **Replay voice** remains available below the dish. Written feedback is available to screen readers. Connection and playback errors remain visible. Photos are served locally from the Pi, so internet is unnecessary during dinner. Open **Photo credit** below the replay button for attribution and license links; source links require internet.

Optional scenario fields: `course_label` (e.g. “Main course”), `subtitle`, `description`, `image`, `image_alt`, `image_credit`, and `image_source`. Put JPG, PNG, or WebP files in `static/images/` and set `image` to the filename, such as `soup.jpg`. Supply descriptive `image_alt` text whenever an image is set. `image_source`, if provided, must be an HTTPS source link. Omit `image` for a text-only course. Restart after editing scenarios. Missing configured images produce a startup configuration error.

See [photo credits and licenses](static/images/CREDITS.md) for the included free photos. The Pi sends presentation fields and menu progress; the browser only renders them. Grading and sensor behavior are unchanged.

## Waiter recordings

The current dinner is lobster bisque, burrata, filet mignon, and dark chocolate torte. The welcome screen has a **Start dinner** button. Tap it to start the shared session and begin the welcome recording on your phone. Utensil touches are ignored until dinner starts. There is no mute control in the page. **Replay voice** repeats the current cue. If the phone blocks autoplay, tap **Replay voice** once to permit playback; later cues play automatically. A page refresh may require another tap, depending on the browser. Keep the page visible and turn up the phone's media volume. Playback errors appear beneath Replay voice, including when a recording cannot load. Refreshing does not restart dinner.

In `scenarios.json`, the top-level `sounds` object maps `welcome`, `correct`, `incorrect`, and `end` to WAV filenames in `static/sounds/`. Each course's `sound` selects its introduction. Existing filenames are used exactly, including `lobsterbique.wav` and `filletmignon.wav`.

Dessert uses `"sound": "torte.wav"`, a PCM WAV playback copy converted from your original `torte.mp3`. Both files are retained; the app serves the WAV. If you replace the MP3, regenerate its playback copy before restarting:

```bash
ffmpeg -y -i "Lab 4/fine_dining/static/sounds/torte.mp3" -ac 1 -ar 48000 -c:a pcm_s16le "Lab 4/fine_dining/static/sounds/torte.wav"
```

FFmpeg is only needed for conversion, not to run the app. Missing required recordings fail configuration validation. For a future course awaiting a recording, use `sound_optional` instead of `sound`.

The Pi sends a unique cue ID and ordered clips. Welcome plays before the first course introduction; correct/incorrect clips play for each accepted answer event, and `end.wav` plays on completion. Fresh feedback replaces an unfinished introduction. The Pi waits at least the correct clip's duration plus one second before advancing, as well as requiring release. This is based on recording duration, not a phone playback acknowledgment. Slow downloads or a phone that blocked autoplay may not finish at exactly the Pi's transition time. All recordings are local; no speech service or internet is used.

Multiple simultaneous touches are silently ignored without an attempt or voice cue. Release all utensils before selecting again. This replaces the earlier “One utensil at a time” feedback. Keep selecting only the knife for the steak cutting prompt.


The Pi waits for `POST /api/start` before accepting answers. A utensil held at start must be released before selecting. The button stays disabled until the sensor connects. Refreshing or opening another phone shows **Join dinner**, which enables that phone’s audio and rejoins the current course without resetting progress. Restarting the app on the Pi returns everyone to the welcome screen.
