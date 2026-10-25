"""Utensil sensor: tells you when the spoon, knife and fork are put down or picked up.

Each utensil rests on its own copper-tape pad, and each pad is connected to one
electrode on the Adafruit MPR121 gator breakout (I2C address 0x5A):

    spoon -> pad 0      knife -> pad 5      fork -> pad 10

A metal utensil on its pad adds capacitance, which lowers that electrode's
filtered reading. Putting a utensil down = reading drops; picking it up = it recovers.

  python fork_sensor.py --calibrate              guided calibration of all three, saved to a file
  python fork_sensor.py --calibrate spoon        redo just one
  python fork_sensor.py                          watch all three using the saved calibration
  python fork_sensor.py --tune                   live readings, to see how far each utensil moves its pad

Start with every utensil OFF its pad: the first second is used to measure the empty pads.

Why not just use mpr121[i].value? The chip's baseline keeps re-tracking, so a utensil
that stays put gets "absorbed" and the touch flag eventually clears. Here the reference
only updates while a pad is empty, so a utensil stays detected for as long as it is there.
"""
import argparse
import json
import sys
import time
from pathlib import Path

SAMPLE_HZ = 20

# name -> MPR121 electrode number
UTENSILS = {"spoon": 0, "knife": 5, "fork": 10}

CAL_FILE = Path(__file__).with_name("fork_sensor_calibration.json")


class PadDetector:
    """Turns a stream of MPR121 filtered readings into put-down / picked-up events.

    Readings DROP when something conductive touches the pad, so
    delta = reference - reading is positive while the utensil is on.
    Hysteresis (on > off) and a confirm count stop it flickering at the edge.
    """

    def __init__(self, reference, on=8, off=4, confirm=3, drift=0.002):
        self.reference = float(reference)
        self.on = on
        self.off = off
        self.confirm = confirm
        # Fraction of the gap the empty-pad reference closes per reading. Slow on purpose
        # (about 10-25 s to follow a change): real drift is gradual, and a utensil resting
        # weakly on the pad must not be soaked into the reference within a few seconds.
        self.drift = drift
        self.present = False
        self._streak = 0

    def delta(self, reading):
        return self.reference - reading

    def update(self, reading):
        """Feed one reading. Returns True (put down), False (picked up) or None."""
        threshold = self.off if self.present else self.on
        wants_present = self.delta(reading) > threshold
        if wants_present == self.present:
            self._streak = 0
            if not self.present and abs(self.delta(reading)) <= self.off:
                # Empty pad: follow slow temperature/humidity drift. Only while the reading is
                # inside the noise band, so a utensil resting weakly on the pad (a drop between
                # off and on) is never absorbed into the reference and mistaken for "empty".
                self.reference += self.drift * (reading - self.reference)
            return None
        self._streak += 1
        if self._streak < self.confirm:
            return None
        self.present = wants_present
        self._streak = 0
        return self.present


def utensil_changed(name, present, down):
    """Hook for what should happen on a change. `down` lists what is on its pad now.
    Replace the body to drive the servo, LEDs, a log file, etc."""
    verb = "put down" if present else "picked up"
    on_pads = ", ".join(down) if down else "nothing"
    print(f"[{time.strftime('%H:%M:%S')}] {name}: {verb}    (on pads now: {on_pads})")


def load_calibration():
    try:
        return json.loads(CAL_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_calibration(cal):
    CAL_FILE.write_text(json.dumps(cal, indent=2))


def sample(mpr, pin, seconds):
    """Average the filtered reading over `seconds`; also returns the peak-to-peak noise."""
    readings = []
    end = time.time() + seconds
    while time.time() < end:
        readings.append(mpr.filtered_data(pin))
        time.sleep(1 / SAMPLE_HZ)
    return sum(readings) / len(readings), max(readings) - min(readings)


def guided_calibration(mpr, name):
    """Measure the empty pad, then the pad with the utensil. Returns (on, off) or None."""
    pin = UTENSILS[name]
    input(f"\n{name} (pad {pin}): take the {name} OFF its pad, then press Enter...")
    empty, noise = sample(mpr, pin, 1.5)
    input(f"{name} (pad {pin}): put the {name} DOWN on its copper, then press Enter...")
    present, _ = sample(mpr, pin, 1.5)
    gap = empty - present
    print(f"  empty={empty:.0f}  {name}={present:.0f}  difference={gap:.0f}  noise={noise}")
    if gap < max(4, noise * 2):
        # Thresholds this low would sit inside the noise and trigger on nothing.
        print(f"  Not usable: the {name}'s effect is no bigger than the reading's own wobble.")
        print("  Check the connection to the pad, use a bigger pad, or bridge to a GND strip.")
        return None
    on, off = gap * 0.5, gap * 0.25
    print(f"  saved thresholds: on {on:.0f}, off {off:.0f}")
    return on, off


def tune(mpr):
    """Live readout so you can see how far each utensil moves its pad."""
    print("Tune mode: watch the 'drop' numbers. Put utensils on/off their pads. Ctrl-C to stop.\n")
    refs = {name: sample(mpr, pin, 1.0)[0] for name, pin in UTENSILS.items()}
    while True:
        parts = []
        for name, pin in UTENSILS.items():
            drop = refs[name] - mpr.filtered_data(pin)
            parts.append(f"{name} {drop:4.0f} {'#' * max(0, min(10, int(drop / 3))):<10}")
        print("\r" + "  ".join(parts), end="", flush=True)
        time.sleep(1 / SAMPLE_HZ)


def watch(mpr, detectors, sleep=time.sleep, ticks=None):
    """Poll every pad forever (or `ticks` times) and report changes."""
    n = 0
    while ticks is None or n < ticks:
        for name, det in detectors.items():
            try:
                change = det.update(mpr.filtered_data(UTENSILS[name]))
            except OSError:
                continue  # a dropped I2C read; try again next tick
            if change is not None:
                utensil_changed(name, change, [k for k, d in detectors.items() if d.present])
        sleep(1 / SAMPLE_HZ)
        n += 1


def connect(address=0x5A):
    """Open the MPR121 on the Pi's I2C bus, or explain what to check and exit."""
    # Hardware imports live here so PadDetector can be tested on a laptop.
    import board
    import busio
    import adafruit_mpr121

    try:
        return adafruit_mpr121.MPR121(busio.I2C(board.SCL, board.SDA), address=address)
    except (ValueError, RuntimeError, OSError) as err:
        print(f"Could not talk to the MPR121 at {address:#04x}: {err}")
        print("Check I2C is on (sudo raspi-config) and run `i2cdetect -y 1`: you should see 5a "
              "(the Servo pHAT shows up separately as 40).")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--address", type=lambda s: int(s, 0), default=0x5A, help="I2C address (default 0x5A)")
    parser.add_argument("--on", type=float, default=8, help="default drop needed to call a utensil present (uncalibrated pads)")
    parser.add_argument("--off", type=float, default=4, help="default drop below which a utensil counts as gone (uncalibrated pads)")
    parser.add_argument("--tune", action="store_true", help="show live readings instead of events")
    parser.add_argument("--calibrate", nargs="*", choices=list(UTENSILS), metavar="NAME",
                        help="guided calibration; give names to redo only those (spoon knife fork)")
    args = parser.parse_args()

    mpr = connect(args.address)

    try:
        if args.tune:
            tune(mpr)
            return

        cal = load_calibration()
        if args.calibrate is not None:
            for name in args.calibrate or list(UTENSILS):
                result = guided_calibration(mpr, name)
                if result:
                    cal[name] = {"on": result[0], "off": result[1]}
                else:
                    cal.pop(name, None)
            save_calibration(cal)
            input("\nTake every utensil off its pad and press Enter to start...")

        print("Measuring the empty pads: keep all utensils off for a few seconds...")
        detectors = {}
        for name, pin in UTENSILS.items():
            c = cal.get(name)
            if c is None:
                print(f"  note: {name} is not calibrated, using --on {args.on:g} --off {args.off:g}")
            detectors[name] = PadDetector(sample(mpr, pin, 1.0)[0],
                                          c["on"] if c else args.on, c["off"] if c else args.off)

        print("Watching spoon, knife and fork. Ctrl-C to stop.")
        watch(mpr, detectors)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
