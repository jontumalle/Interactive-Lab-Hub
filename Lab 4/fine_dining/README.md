# At the Table

A local dining practice prototype: real utensils rest on copper-tape pads, and picking one up is your answer, with feedback on your phone. The Pi owns the entire session; the phone displays its current state. All connected phones see the same session.

## Start and stop

From the repository root:

```bash
"Lab 4/fine_dining/start.sh"
```

The script uses `Lab 4/.venv` if present, otherwise `python3`. It needs the same CircuitPython/Blinka dependencies and I²C setup as `cap_test.py`. If these are missing, install the Lab 4 requirements into the lab virtual environment as described in the lab README.

Open the printed `http://<hostname>.local:8000` URL on your phone. If that does not resolve, run `hostname -I` on the Pi and use its Wi-Fi/LAN IP, for example `http://192.168.1.42:8000` (replace the example address).

The phone and Pi must be on a network that permits device-to-device traffic. Guest/campus Wi-Fi sometimes blocks this even on the same network. Use a shared network or hotspot that allows local connections. No internet access is needed by the app. This prototype serves plain HTTP on the local network without login.

Press **Ctrl+C** in the running terminal to stop. Start again for a fresh dinner or after editing configuration. Stop other sensor demo scripts before running this app. If the port is in use:

```bash
"Lab 4/fine_dining/start.sh" --port 8001
```

## Table setup (calibration)

Every time the app starts, the phone opens on a short **table setup** instead of "Start dinner". The Pi learns your sensor readings, so no numbers need editing:

1. Take every utensil off its pad, keep your hands away from the pads and wires, and tap **The table is clear — measure**. The Pi spends about 1.5 seconds measuring the empty pads. If a pad wobbles too much (hands or wires moving), it asks you to measure again.
2. Place the **spoon**, then the **knife**, then the **fork** on their pads when prompted, one at a time, and leave each there. A utensil counts once the pad has held steady for about a second; its row turns green. If one is not detected after 30 seconds the phone suggests pressing it firmly onto the tape and checking the connection.
3. When all three are green, **Start dinner** appears with a note to leave every utensil resting on its pad until it is time to choose. All utensils are now on their pads, which is the starting position for the dinner.

During the dinner, if a utensil is still off its pad when the table should be reset, the phone shows a banner such as "Please put the spoon back on its pad and press down." The terminal prints a line for every lift and put-back, for example `Knife: back on its pad (drop 14; on > 12, off < 6)`. If a utensil is sitting on its pad but the Pi still counts it as lifted, the drop in that line shows by how much it missed. The delay is 2 seconds after the correct-answer feedback ends, 5 seconds after a wrong answer, and 3 seconds when a utensil was already up when the dinner started. Change `REMIND_AFTER_CORRECT`, `REMIND_AFTER_WRONG` and `REMIND_AFTER_OTHER` at the top of `app.py`. The reminder is on screen only; a spoken one would need a new waiter recording.

**Redo table setup** (below Start dinner) repeats this before the dinner begins. The learned on/off thresholds are saved to `Lab 4/fork_sensor_calibration.json`, the same file `fork_sensor.py` and `utensil_quiz.py` use, so they stay in step. The empty-pad reading is measured fresh each run because it drifts between sessions.

A utensil whose pad cannot beat its own sensor noise by 2× is never detected, the same bar as `python fork_sensor.py --calibrate`. Fix the connection, use a bigger pad, or bridge to a GND strip.

## Match your wiring

The mapping in `cutlery.json` is **spoon = 0, knife = 5, fork = 10** (the order is also the order setup asks for them). To find the channel for a pad, run:

```bash
"Lab 4/fine_dining/start.sh" --map
```

Mapping mode uses the chip's own touch flag, so touch each pad with a finger (a resting utensil may not trigger it) and note the channel printed in the terminal. Mapping mode reads all 12 channels, including disabled/unmapped ones, and does not start the website. Stop it with Ctrl+C, then edit `cutlery.json`.

Each utensil has a stable `id`, a human-readable `name`, a `channel` from 0–11, and an `enabled` flag. IDs and channels must be unique. Set `enabled` to false to ignore a channel during play. If channel 0 is troublesome, disable or remap its utensil; the separate `cap_test_sensor0_inactive.py` file does not establish that it is faulty.

`debounce_ms` controls how long the set of lifted utensils must remain stable before acceptance (default 100 ms). Increase it if lifts flicker; lower it cautiously if short lifts are missed. Picking up means select: a utensil off its pad is "selected" until you put it back. The sensor cannot tell which utensil is physically on a pad, only that something conductive is on that pad, so a utensil placed on the wrong pad counts as the pad's utensil.

## Configure a dinner

Edit `scenarios.json`. `courses` is the ordered list of prompts:

```json
{
  "dish": "Tomato soup",
  "prompt": "Your soup has arrived. Pick up the utensil you would use.",
  "accepted": ["spoon"],
  "hint": "Choose a utensil that can hold the broth.",
  "explanation": "Use the spoon for soup."
}
```

`accepted` lists the alternative correct answers. An entry that is a utensil ID (`"spoon"`) means that utensil alone; an entry that is a list (`["fork", "knife"]`) means those utensils picked up together. The steak course uses `"accepted": [["fork", "knife"]]`, and you can mix both kinds, for example `["spoon", ["fork", "knife"]]`. All IDs must exist and be enabled in the mapping. Add separate IDs such as `salad_fork` and `dinner_fork` if you wire multiple forks.

**How answers are judged.** The answer is whatever is in the diner's hand (off its pad). It is judged straight away when it can no longer become a correct answer (the spoon for a steak) or is already complete and cannot grow (the spoon for soup). While it could still grow into a correct answer (the fork alone for a steak) the Pi waits for the rest, up to `ANSWER_SETTLE` seconds (default 2, at the top of `app.py`) after the last change, then judges what is in hand. So the second utensil must be picked up within about 2 seconds of the first. The phone shows "In hand: …" while this happens. `feedback_seconds` sets the minimum display time for correct feedback (default 4 seconds). Wrong feedback stays visible until another selection; the learner can retry indefinitely.

Check edits without starting the sensor or web server:

```bash
"Lab 4/fine_dining/start.sh" --check-config
```

Restart to load changes. Configuration errors print in the terminal before the sensor starts.

## Interaction and first hardware trial

1. Start the app, connect your phone, verify the live sensor indicator, and complete the table setup above.
2. Pick up a wrong utensil: expect a clear “Try again” message and hint.
3. Hold it up: it should count only once. Put it back, then choose again.
4. On the steak, pick up the fork, then the knife within two seconds: expect "In hand: Fork", then a correct answer. Try the fork alone and wait: after about two seconds it counts as a wrong answer. Pick up two utensils on a one-utensil course (for example fork and spoon for the soup): that is a wrong answer.
5. Select correctly: the photo border glows green. Listen to the waiter, put the utensil back, and wait for the next course.
6. Refresh the phone: it should rejoin the current course. Finish for the first-try/retry summary.
7. Stop the app: the phone should show disconnection within a few seconds. Restart for another dinner.

Sensor failures display separately from answer feedback and print details in the terminal. Fix the wiring/environment and restart. Session progress is in memory and resets on restart. Phones can reconnect without resetting it; the Pi continues the session even when no phone is connected.

There is no automated test suite. The first hardware trial should guide changes to debounce, timing, wording, and scenario content. Servo actuation required by Part 2 remains a subsequent iteration.

## Files

- `app.py`: sensor polling, debouncing, session decisions, and local HTTP server.
- `calibration.py`: the table-setup logic (measure empty pads, learn each utensil). Uses `../fork_sensor.py` for pick-up/put-down detection.
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

Every utensil must be back on its pad before the next answer counts. The steak course now needs the fork and the knife together; the `filletmignon.wav` introduction was recorded for the earlier knife-only version, so check that it does not tell the diner to use only the knife.


The Pi waits for `POST /api/start` before accepting answers. A utensil held at start must be released before selecting. The button stays disabled until the sensor connects. Refreshing or opening another phone shows **Join dinner**, which enables that phone’s audio and rejoins the current course without resetting progress. Restarting the app on the Pi returns everyone to the welcome screen.
