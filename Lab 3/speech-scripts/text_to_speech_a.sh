#!/usr/bin/env bash
# Neural TTS with Piper.

set -euo pipefail
VOICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"

# Download voices
python3 -m piper.download_voices en_US-norman-medium --data-dir "$VOICES_DIR"
python3 -m piper.download_voices en_GB-southern_english_female-low --data-dir "$VOICES_DIR"
python3 -m piper.download_voices en_GB-vctk-medium --data-dir "$VOICES_DIR"

# Synthesize to a file, then play it.
python3 -m piper \
  --model en_US-norman-medium \
  --data-dir "$VOICES_DIR" \
  --output-file synthesized_greeting.wav \
  -- "Hi, Jonathan Tumalle. This is your pi!"
aplay synthesized_greeting.wav

python3 -m piper \
  --model en_GB-southern_english_female-low \
  --data-dir "$VOICES_DIR" \
  --output-file synthesized_greeting.wav \
  -- "Hi, Jonathan Tumalle. This is your pi!"
aplay synthesized_greeting.wav

python3 -m piper \
  --model en_GB-vctk-medium \
  --data-dir "$VOICES_DIR" \
  --output-file synthesized_greeting.wav \
  -- "Hi, Jonathan Tumalle. This is your pi!"
aplay synthesized_greeting.wav
