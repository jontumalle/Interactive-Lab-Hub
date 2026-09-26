#!/usr/bin/env python3
"""Transcribe numbers.

Ask the user for a phone number, zipcode, and number of pets.
"""

import argparse
import subprocess
import wave

from faster_whisper import WhisperModel
from piper.voice import PiperVoice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="tiny.en",
                        help="whisper model size (default: tiny.en)")
    parser.add_argument("--voice-model-path", default="../voices/en_US-norman-medium.onnx",
                        help="path to piper voice model to use")
    parser.add_argument("--audio", default="number_test.wav",
                        help="file for speech to text")
    parser.add_argument("--tts-audio", default="number_instructions.wav",
                            help="file for speech to text")
    parser.add_argument("--compute-type", default="int8",
                        choices=["int8", "int8_float32", "float32"],
                        help="quantization; int8 is ~2-3x faster on the Pi (default: int8)")
    parser.add_argument("--beam-size", type=int, default=1,
                        help="1 is greedy and fastest; 5 is more accurate and slower")
    args = parser.parse_args()

    # Give instructions
    voice = PiperVoice.load(args.voice_model_path)
    with wave.open(args.tts_audio, "wb") as tts_file:
        voice.synthesize_wav("Please provide your phone number, zipcode, and number of pets", tts_file)
    subprocess.run(["aplay", args.tts_audio])

    # arecord -d 5 -f cd -c 1 -r 16000 test.wav
    print("Speak now")
    subprocess.run(
        [
            "arecord",
            "-d", "10",
            "-f", "cd",
            "-c", "1",
            "-r", "16000",
            args.audio
        ],
        stderr=subprocess.DEVNULL
    )

    print("Processing recording...")
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute_type)

    segments, info = model.transcribe(args.audio, beam_size=args.beam_size)
    text = " ".join(seg.text.strip() for seg in segments)  # generator: consume it

    print(f"\n{text}\n")


if __name__ == "__main__":
    main()
