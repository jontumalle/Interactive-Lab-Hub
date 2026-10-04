# WordHound POC

This is the Part 2, single-round WordHound prototype. Both players can read a target word on the Adafruit Mini PiTFT. The clue giver presses the left Mini PiTFT button, describes the word, and stops speaking. After two seconds of silence, WordHound saves the VAD-bounded clue, transcribes it locally on the Pi, asks Codex CLI to infer one word from the transcript, displays that guess, and says it through the USB speaker.

The target word remains on the Pi throughout the round. It is never supplied to the transcription or guess request.

## Controls and feedback

| State | Screen feedback | Button A / left (GPIO 23) | Button B / right (GPIO 24) |
| --- | --- | --- | --- |
| Card | target word and ready state | start recording | select the next target card |
| Listening | green `LISTENING` state | — | cancel the current clue |
| Result | guess and the transcript | replay the same card | select the next target card |

The changes from the Part 1 script make turn-taking visible: the display names the current state, the physical button explicitly gives the system permission to listen, and the two-second endpoint is printed on screen. The target word is visible to both players because this is the requested POC rather than the full two-player Taboo game.

## Setup

From `Lab 3`, prepare the existing lab environment and install the Mini PiTFT libraries:

```bash
source .venv/bin/activate
pip install -r wordhound/requirements.txt
./speech-scripts/setup.sh
python -m piper.download_voices en_US-ryan-medium --data-dir voices
codex login
```

The PiTFT uses SPI, GPIO 5 for chip select, GPIO 25 for data/command, GPIO 22 for its backlight, and its two onboard buttons on GPIO 23 and 24. This matches the working Lab 2 wiring. The default microphone and speaker must be the attached USB devices; check them with `arecord -l` and `aplay -l` before a demo.

## Run

```bash
wordhound/run_demo.sh
```

The launcher stops `piscreen.service` only while WordHound owns the Mini PiTFT, then restores it on exit, including after `Ctrl-C`. To run without touching that service, use `python wordhound/app.py` after manually stopping the display service.

If direct use of `python wordhound/app.py` reports that it cannot open `gpiochip`, use `wordhound/run_demo.sh`. It starts WordHound under the `gpio` group when an older SSH or VNC terminal session has not inherited that permission yet. Starting a new terminal session also refreshes the group membership.

The app writes the speech-only WAV from each completed clue to `wordhound/recordings/` so a later iteration can inspect or label interaction data. Those recordings are ignored by Git. Add or change target words in [cards.json](cards.json).

WordHound announces each result through the local Piper `en_US-ryan-medium` voice, giving the guesses a confident, game-show-style delivery. This voice is hardcoded for the POC. Piper streams raw audio to `aplay`, just as [piper_demo.sh](../speech-scripts/piper_demo.sh) does.

For a display-free development session, use terminal controls:

```bash
python wordhound/app.py --headless
```

Useful adjustments:

```bash
python wordhound/app.py --silence-seconds 1.5
python wordhound/app.py --max-clue-seconds 45
python wordhound/app.py --no-speech
```

## Speech and guessing

`app.py` runs Lab 3's local faster-whisper `tiny.en` model on the completed WAV. It then runs `codex exec` with only the returned transcript. Codex runs in an ephemeral, read-only temporary directory containing only the JSON output schema, so it cannot read `cards.json` or the target word. Codex uses its own saved CLI sign-in; use `codex login` if this Pi has not been connected to a ChatGPT account. No `OPENAI_API_KEY` is required.

[Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) documents `codex exec` for scripted use.
