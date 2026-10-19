"""Utensil quiz: asks what utensil to use for a dish; you answer by picking utensils up.

Run it on the Pi (over SSH is fine; the quiz shows in that terminal):

    python utensil_quiz.py

Needs the calibration from `python fork_sensor.py --calibrate` first.

Each round: the spoon, knife and fork rest on their pads. A question appears, you pick up the
utensil(s) you'd use, and hold still. Once the set of lifted utensils has stayed the same for
--settle seconds, that is your answer. The answer must be exactly the right set.
"""
import argparse
import random
import sys
import time

from fork_sensor import PadDetector, UTENSILS, connect, load_calibration, sample, SAMPLE_HZ
from quiz_questions import PROMPT, QUESTIONS

SETTLE_SECONDS = 2.0

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def read_on_pads(mpr, detectors):
    """Update every pad and return the set of utensils currently resting on their pads."""
    for name, det in detectors.items():
        try:
            det.update(mpr.filtered_data(UTENSILS[name]))
        except OSError:
            pass  # a dropped I2C read; the next poll will catch up
    return {name for name, det in detectors.items() if det.present}


def wait_for_all_on_pads(poll, sleep=time.sleep):
    """Block until every utensil is back on its pad, saying which are still missing."""
    last = None
    while True:
        missing = sorted(set(UTENSILS) - poll())
        if not missing:
            return
        if missing != last:
            print(f"{DIM}  waiting for: {', '.join(missing)}{RESET}")
            last = missing
        sleep(1 / SAMPLE_HZ)


def wait_for_answer(poll, settle, sleep=time.sleep, now=time.monotonic):
    """Return the set of lifted utensils once it is non-empty and unchanged for `settle` seconds."""
    lifted, since = frozenset(), now()
    while True:
        current = frozenset(UTENSILS) - poll()
        if current != lifted:
            lifted, since = current, now()
        elif lifted and now() - since >= settle:
            return set(lifted)
        sleep(1 / SAMPLE_HZ)


def show_result(picked, question):
    picked_text = " + ".join(sorted(picked))
    print(f"You picked: {picked_text}")
    if picked == question["answer"]:
        print(f"{GREEN}Correct!{RESET} {question['why']}")
    else:
        right = " + ".join(sorted(question["answer"]))
        print(f"{RED}Not quite.{RESET} The answer is {right}. {question['why']}")


def run_quiz(poll, questions, settle=SETTLE_SECONDS, sleep=time.sleep, now=time.monotonic):
    """Ask each question in turn. Returns (score, number answered)."""
    score = answered = 0
    try:
        for i, q in enumerate(questions, 1):
            print(f"\nPut the utensils on their pads to start question {i}/{len(questions)}...")
            wait_for_all_on_pads(poll, sleep)
            print(f"\nQ{i}: {PROMPT.format(dish=q['dish'])}")
            print(f"{DIM}  Pick up the utensil(s) you'd use, then hold still.{RESET}")
            picked = wait_for_answer(poll, settle, sleep, now)
            answered += 1
            score += picked == q["answer"]
            show_result(picked, q)
    except KeyboardInterrupt:
        print()
    return score, answered


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=0, help="number of questions (default: all, shuffled)")
    parser.add_argument("--settle", type=float, default=SETTLE_SECONDS,
                        help="seconds the lifted set must stay unchanged to lock in an answer")
    parser.add_argument("--address", type=lambda s: int(s, 0), default=0x5A, help="MPR121 I2C address")
    args = parser.parse_args()

    cal = load_calibration()
    uncalibrated = [name for name in UTENSILS if name not in cal]
    if uncalibrated:
        print(f"Not calibrated yet: {', '.join(uncalibrated)}.")
        print("Run `python fork_sensor.py --calibrate` first (add names to redo only some).")
        sys.exit(1)

    mpr = connect(args.address)
    try:
        input("Take the spoon, knife and fork OFF their pads, then press Enter...")
        print("Measuring the empty pads...")
        detectors = {name: PadDetector(sample(mpr, pin, 1.0)[0], cal[name]["on"], cal[name]["off"])
                     for name, pin in UTENSILS.items()}
        questions = random.sample(QUESTIONS, min(args.count or len(QUESTIONS), len(QUESTIONS)))
        score, answered = run_quiz(lambda: read_on_pads(mpr, detectors), questions, args.settle)
    except KeyboardInterrupt:
        print()
        return
    print(f"\nScore: {score}/{answered}")


if __name__ == "__main__":
    main()
